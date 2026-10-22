"""Qwen3-TTS VoiceDesign audio for the kizamu grammar decks, checked by Whisper.

Same voice, model and sampling as the kizamu vocab decks (german/vocab/audio_cuda.py).
Clips are content-addressed: a clip is regenerated only when its text or settings
change. Each clip is transcribed with Whisper large-v3-turbo; a clip whose transcript
does not match the text is generated again with another seed (up to --attempts).
The best attempt is kept and flagged in the manifest if it still does not match.

    # one process per GPU, see scripts/run-audio.sh:
    CUDA_VISIBLE_DEVICES=0 python -m german.grammar.audio generate --shard-index 0 --shard-count 4
    python -m german.grammar.audio merge --shard-count 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time

from german.grammar.common import AUDIO, BUILD, atomic_json, load_content, spoken_texts
from german.vocab.pilot_audio import STYLE

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
ASR_MODEL = "openai/whisper-large-v3-turbo"
MANIFEST = AUDIO / "manifest.json"
SHARDS = AUDIO / "shards"

ABBREVIATIONS = [
    (r"\bz\.\s?B\.", "zum Beispiel"), (r"\bd\.\s?h\.", "das heißt"), (r"\busw\.", "und so weiter"),
    (r"\bbzw\.", "beziehungsweise"), (r"\bca\.", "circa"), (r"\bDr\.", "Doktor"),
    (r"\bNr\.", "Nummer"), (r"\bu\.\s?a\.", "unter anderem"), (r"\bggf\.", "gegebenenfalls"),
    (r"\bProf\.", "Professor"), (r"\bStr\.", "Straße"), (r"€", " Euro"), (r"%", " Prozent"),
]
NUMBERS = dict(enumerate("null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf".split()))


def spoken(text: str) -> str:
    for pattern, replacement in ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text[-1:] in ".?!" else text + "."


def tokens(text: str) -> list[str]:
    words = re.findall(r"\w+", spoken(text).casefold().replace("ß", "ss"))
    return [NUMBERS.get(int(w), w) if w.isdigit() and int(w) in NUMBERS else w for w in words]


def word_errors(expected: str, heard: str) -> int:
    a, b = tokens(expected), tokens(heard)
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (x != y))
    return row[-1]


def acceptable(expected: str, heard: str) -> bool:
    count = len(tokens(expected))
    # Allow one slip (often a compound split or a number) on longer sentences.
    return word_errors(expected, heard) <= (0 if count <= 4 else 1 if count <= 14 else 2)


def settings_for(text: str) -> dict:
    long = len(text) > 140
    return {"model": MODEL, "text": text, "spoken_text": spoken(text), "style": STYLE,
            "language": "German", "temperature": 0.65, "top_p": 0.9,
            "max_new_tokens": 420 if long else 300 if len(text) > 25 else 120,
            "backend": "qwen-tts 0.1.1 CUDA"}


def digest(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:24]


def current_jobs() -> dict[str, dict]:
    jobs = {}
    for data in load_content(skip_invalid=True).values():
        try:
            texts = spoken_texts(data)
        except (KeyError, TypeError):  # a file still being written
            continue
        for text in texts:
            settings = settings_for(text)
            key = digest(settings)
            jobs[key] = {"settings": settings, "file": f"kizamu_grammar_qwen_{key}.mp3"}
    return jobs


def file_for(text: str) -> str:
    return f"kizamu_grammar_qwen_{digest(settings_for(text))}.mp3"


def generate(args) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    from transformers import pipeline

    jobs = current_jobs()
    shard_path = SHARDS / f"manifest-{args.shard_index}-of-{args.shard_count}.json"
    manifest = json.loads(shard_path.read_text()) if shard_path.exists() else {}
    pending = [
        (key, job) for key, job in sorted(jobs.items(), key=lambda kv: (len(kv[1]["settings"]["text"]), kv[0]))
        if int(key[:16], 16) % args.shard_count == args.shard_index
        and (not (key in manifest and (AUDIO / job["file"]).exists())
             or (args.retry_flagged and not manifest[key]["asr_match"]))
    ]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(f"audio: shard {args.shard_index}/{args.shard_count}, {len(pending)} clips pending", flush=True)
    if not pending:
        return
    tts = Qwen3TTSModel.from_pretrained(args.model, device_map="cuda:0", dtype=torch.bfloat16,
                                        attn_implementation="sdpa")
    asr = pipeline("automatic-speech-recognition", model=ASR_MODEL, device="cuda:0",
                   torch_dtype=torch.float16)
    AUDIO.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    # With --retry-flagged, a new take must beat the clip already on disk.
    best: dict[str, dict] = {key: manifest[key] for key, _ in pending if key in manifest} if args.retry_flagged else {}
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset:offset + args.batch_size]
        started = time.monotonic()
        for attempt in range(args.attempts):
            todo = [(k, j) for k, j in batch if not best.get(k, {}).get("asr_match")]
            if not todo:
                break
            seed = 71000 + args.shard_index * 1_000_000 + offset * 10 + attempt + (500_000 if args.retry_flagged else 0)
            torch.manual_seed(seed)
            try:
                wavs, rate = tts.generate_voice_design(
                    text=[j["settings"]["spoken_text"] for _, j in todo],
                    language=["German"] * len(todo), instruct=[STYLE] * len(todo),
                    temperature=0.65, top_p=0.9,
                    max_new_tokens=max(j["settings"]["max_new_tokens"] for _, j in todo),
                )
            except Exception as error:  # keep the shard going; the clip stays pending
                print(f"batch failed (attempt {attempt}): {error!r}", flush=True)
                continue
            clips = []
            for (key, job), audio in zip(todo, wavs):
                audio = np.asarray(audio, dtype=np.float32).reshape(-1)
                seconds = len(audio) / rate
                peak = float(np.abs(audio).max()) if len(audio) else 0.0
                limit = 8 if job["settings"]["max_new_tokens"] == 120 else 34
                if not np.isfinite(audio).all() or peak < 0.001 or not 0.15 < seconds < limit:
                    continue
                if peak > 0.98:
                    audio = audio * (0.98 / peak)
                clips.append((key, job, audio, seconds))
            if not clips:
                continue
            options = {"generate_kwargs": {"language": "german", "task": "transcribe"}}
            inputs = [{"raw": c[2].copy(), "sampling_rate": rate} for c in clips]
            try:
                heard = asr(inputs, batch_size=len(clips), **options)
            except ValueError:
                # Clips over 30 s use Whisper's long-form mode and cannot share a batch.
                # The pipeline consumes the input dicts, so build fresh ones.
                heard = [asr({"raw": c[2].copy(), "sampling_rate": rate}, **options) for c in clips]
            for (key, job, audio, seconds), result in zip(clips, heard):
                transcript = result["text"].strip()
                errors = word_errors(job["settings"]["text"], transcript)
                previous = best.get(key)
                if previous and previous["word_errors"] <= errors:
                    continue
                path = AUDIO / job["file"]
                temporary = path.with_suffix(".tmp.mp3")
                sf.write(temporary, audio, rate, format="MP3", subtype="MPEG_LAYER_III")
                temporary.replace(path)
                best[key] = {
                    "file": path.name, "settings": job["settings"], "seconds": round(seconds, 3),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "seed": seed,
                    "attempt": attempt + 1, "transcript": transcript, "word_errors": errors,
                    "asr_match": acceptable(job["settings"]["text"], transcript), "asr_model": ASR_MODEL,
                    "provenance": "official Qwen3-TTS VoiceDesign CUDA generation",
                }
        for key, _ in batch:
            if key in best:
                manifest[key] = best.pop(key)
        atomic_json(shard_path, manifest)
        flagged = sum(not r["asr_match"] for r in manifest.values())
        print(f"audio {min(offset + len(batch), len(pending))}/{len(pending)}; batch {time.monotonic() - started:.1f}s; "
              f"flagged {flagged}; elapsed {(time.monotonic() - began) / 60:.1f}m", flush=True)


def merge(args) -> None:
    jobs = current_jobs()
    merged = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for index in range(args.shard_count):
        path = SHARDS / f"manifest-{index}-of-{args.shard_count}.json"
        if path.exists():
            merged.update(json.loads(path.read_text()))
    missing, flagged = [], []
    for key, job in jobs.items():
        record = merged.get(key)
        media = AUDIO / job["file"]
        if not record or not media.exists() or hashlib.sha256(media.read_bytes()).hexdigest() != record["sha256"]:
            missing.append(job["settings"]["text"])
        elif not record["asr_match"]:
            flagged.append({"text": record["settings"]["text"], "heard": record["transcript"]})
    merged = {key: merged[key] for key in jobs if key in merged}
    atomic_json(MANIFEST, merged)
    summary = {"clips": len(jobs), "ready": len(jobs) - len(missing), "missing": len(missing),
               "asr_flagged": len(flagged), "model": MODEL, "asr_model": ASR_MODEL}
    atomic_json(BUILD / "audio-summary.json", summary)
    atomic_json(BUILD / "audio-flagged.json", flagged)
    atomic_json(BUILD / "audio-missing.json", missing)
    print(json.dumps(summary, indent=2))
    if missing and not args.allow_missing:
        raise SystemExit(f"{len(missing)} clips missing; rerun generate (it resumes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["generate", "merge", "count"])
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--retry-flagged", action="store_true",
                        help="regenerate clips whose transcript did not match; keep the better take")
    arguments = parser.parse_args()
    if arguments.stage == "count":
        print(len(current_jobs()), "unique clips")
    else:
        (merge if arguments.stage == "merge" else generate)(arguments)
