"""Qwen3-TTS VoiceDesign audio (American English) for the kizamu-english decks, checked by Whisper.

Same model, sampling and Whisper check as the kizamu-german decks (german/grammar/audio.py),
with an American English voice. Clips are content-addressed: a clip is regenerated only
when its text or settings change. A clip whose Whisper transcript does not match the text
is generated again with another seed (up to --attempts); the best take is kept and flagged.

    # one process per GPU, see scripts/run-audio.sh:
    CUDA_VISIBLE_DEVICES=0 python -m english.audio generate --shard-index 0 --shard-count 4
    python -m english.audio merge --shard-count 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import unicodedata

from english.common import AUDIO, BUILD, SRC, atomic_json, load_content, spoken_texts

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
ASR_MODEL = "openai/whisper-large-v3-turbo"
MANIFEST = AUDIO / "manifest.json"
SHARDS = AUDIO / "shards"
PREFIX = "kizamu_english_qwen_"
STYLE = ("A warm, friendly adult female native speaker of General American English, in her thirties, "
         "speaking naturally at a relaxed conversational pace with a medium pitch and normal American "
         "connected speech. Clear and confident, without exaggeration. Read only the provided text.")

ABBREVIATIONS = [
    (r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"), (r"\betc\.", "et cetera"),
    (r"\bvs\.", "versus"), (r"\bapprox\.", "approximately"), (r"%", " percent"), (r"&", " and "),
    (r"…", "..."),
]
NUMBERS = dict(enumerate(("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                          "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()))
EQUIVALENT = {"okay": "ok", "alright": "all right", "percent": "percent",
              # Whisper writes relaxed forms in full (and sometimes the reverse); compare full forms.
              "wanna": "want to", "gonna": "going to", "gotta": "got to", "hafta": "have to",
              "hasta": "has to", "kinda": "kind of", "sorta": "sort of", "lemme": "let me",
              "gimme": "give me", "dunno": "don't know", "outta": "out of", "lotta": "lot of",
              "oughta": "ought to", "coulda": "could have", "shoulda": "should have",
              "woulda": "would have", "musta": "must have", "didja": "did you", "didya": "did you",
              "wouldja": "would you", "couldja": "could you", "whaddaya": "what do you",
              "gotcha": "got you", "betcha": "bet you", "'em": "them", "em": "them",
              "'cause": "because", "cuz": "because", "ya": "you", "supposta": "supposed to",
              "useta": "used to", "doncha": "don't you", "yer": "your", "d'you": "do you",
              "d'ya": "do you", "tryna": "trying to", "c'mon": "come on", "prob'ly": "probably",
              "dollars": "dollar"}
# Reviewed clips whose transcript differs only because the words sound the same
# (ensure/insure, complement/compliment …). Text → reason.
ACCEPTED_PATH = SRC / "audio-accepted.json"
ACCEPTED = json.loads(ACCEPTED_PATH.read_text()) if ACCEPTED_PATH.exists() else {}


def spoken(text: str) -> str:
    for pattern, replacement in ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text[-1:] in ".?!" else text + "."


NUMBER_VALUES = {word: value for value, word in NUMBERS.items()}
NUMBER_VALUES.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
                      "ninety": 90})
SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}


def numbers_to_digits(words: list[str]) -> list[str]:
    """three hundred → 300, twelve hundred → 1200, two thousand → 2000 (Whisper writes digits)."""
    out, total, current, active = [], 0, 0, False
    for word in words + [""]:
        if word in NUMBER_VALUES or (word.isdigit() and not active):
            value = NUMBER_VALUES[word] if word in NUMBER_VALUES else int(word)
            # "twenty three" = 23, but "three thirty" (a time) and "three fifty" (a price) are two numbers.
            if active and not (current % 100 == 0 or (current % 100 >= 20 and current % 10 == 0 and value < 10)):
                out.append(str(total + current))
                total, current = 0, 0
            current += value
            active = True
        elif word == "hundred" and active:
            current = (current or 1) * 100
        elif word in SCALES and active:
            total += (current or 1) * SCALES[word]
            current = 0
        else:
            if active:
                out.append(str(total + current))
                total, current, active = 0, 0, False
            if word:
                out.append(word)
    return out


def tokens(text: str, join_hyphens: bool = False) -> list[str]:
    text = spoken(text).casefold().replace("’", "'")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()  # résumé = resume
    text = re.sub(r"\b([a-z]+)in'(?![a-z])", r"\1ing", text)  # sayin' = saying
    # Single quotation marks ('free') are not part of the word; keep 'em, 'cause and contractions.
    text = re.sub(r"(?<![a-z0-9])'(?!(?:em|cause|til|bout)\b)|'(?![a-z])", " ", text)
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    text = re.sub(r"(\d):00\b|\bo'clock\b", r"\1", text)  # 3:00 = 3 o'clock = 3
    text = re.sub(r"\$(\d+(?:\.\d+)?)\s*(thousand|million|billion)\b", r"\1 \2 dollars", text)
    text = re.sub(r"\$(\d+(?:\.\d+)?)", r"\1 dollars", text)
    text = re.sub(r"(?<=[a-z0-9])-(?=[a-z0-9])", "" if join_hyphens else " ", text)
    words = []
    for word in re.findall(r"'?[a-z0-9]+(?:'[a-z]+)?", text):
        words += EQUIVALENT.get(word, word).split()
    return numbers_to_digits(words)


def collapsed(text: str) -> str:
    """Letters and digits only: multimillion-dollar = multi-million dollar."""
    return "".join(tokens(text))


def word_errors(expected: str, heard: str) -> int:
    # Hyphens are written inconsistently (speed-up / speedup, well-funded / well funded):
    # compare both ways and keep the better result.
    return min(_edit_distance(tokens(expected, join), tokens(heard, join)) for join in (False, True))


def _edit_distance(a: list[str], b: list[str]) -> int:
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (x != y))
    return row[-1]


def acceptable(expected: str, heard: str) -> bool:
    if expected in ACCEPTED or collapsed(expected) == collapsed(heard):
        return True
    count = len(tokens(expected))
    # One slip allowed on longer sentences (often a contraction or a hyphenated word).
    return word_errors(expected, heard) <= (0 if count <= 4 else 1 if count <= 14 else 2)


def settings_for(text: str) -> dict:
    long = len(text) > 140
    return {"model": MODEL, "text": text, "spoken_text": spoken(text), "style": STYLE,
            "language": "English", "temperature": 0.65, "top_p": 0.9,
            "max_new_tokens": 420 if long else 300 if len(text) > 25 else 120,
            "backend": "qwen-tts 0.1.1 CUDA"}


def digest(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:24]


def file_for(text: str) -> str:
    return f"{PREFIX}{digest(settings_for(text))}.mp3"


def current_jobs(only: set[str] | None = None) -> dict[str, dict]:
    jobs = {}
    for part_id, data in load_content(skip_invalid=True).items():
        if only and part_id not in only:
            continue
        try:
            texts = spoken_texts(data)
        except (KeyError, TypeError):  # a file still being written
            continue
        for text in texts:
            settings = settings_for(text)
            key = digest(settings)
            jobs[key] = {"settings": settings, "file": f"{PREFIX}{key}.mp3"}
    return jobs


def generate(args) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    from transformers import pipeline

    jobs = current_jobs(set(args.parts) if args.parts else None)
    shard_path = SHARDS / f"manifest-{args.shard_index}-of-{args.shard_count}.json"
    manifest = json.loads(shard_path.read_text()) if shard_path.exists() else {}
    for record in manifest.values():  # the comparison rules may have changed since generation
        record["asr_match"] = acceptable(record["settings"]["text"], record["transcript"])
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
    best: dict[str, dict] = {key: manifest[key] for key, _ in pending if key in manifest} if args.retry_flagged else {}
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset:offset + args.batch_size]
        started = time.monotonic()
        for attempt in range(args.attempts):
            todo = [(k, j) for k, j in batch if not best.get(k, {}).get("asr_match")]
            if not todo:
                break
            seed = 91000 + args.shard_index * 1_000_000 + offset * 10 + attempt + (500_000 if args.retry_flagged else 0)
            torch.manual_seed(seed)
            try:
                wavs, rate = tts.generate_voice_design(
                    text=[j["settings"]["spoken_text"] for _, j in todo],
                    language=["English"] * len(todo), instruct=[STYLE] * len(todo),
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
            options = {"generate_kwargs": {"language": "english", "task": "transcribe"}}
            # A short lead-in silence keeps Whisper from missing a first plosive (boil → "oil").
            lead = np.zeros(int(0.3 * rate), dtype=np.float32)
            inputs = [{"raw": np.concatenate([lead, c[2]]), "sampling_rate": rate} for c in clips]
            try:
                heard = asr(inputs, batch_size=len(clips), **options)
            except ValueError:
                # Clips over 30 s use Whisper's long-form mode and cannot share a batch.
                heard = [asr({"raw": np.concatenate([lead, c[2]]), "sampling_rate": rate}, **options) for c in clips]
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
    jobs = current_jobs(set(args.parts) if args.parts else None)
    merged = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for index in range(args.shard_count):
        path = SHARDS / f"manifest-{index}-of-{args.shard_count}.json"
        if path.exists():
            merged.update(json.loads(path.read_text()))
    for record in merged.values():
        record["asr_match"] = acceptable(record["settings"]["text"], record["transcript"])
        record["word_errors"] = word_errors(record["settings"]["text"], record["transcript"])
    missing, flagged = [], []
    for key, job in jobs.items():
        record = merged.get(key)
        media = AUDIO / job["file"]
        if not record or not media.exists() or hashlib.sha256(media.read_bytes()).hexdigest() != record["sha256"]:
            missing.append(job["settings"]["text"])
        elif not record["asr_match"]:
            flagged.append({"text": record["settings"]["text"], "heard": record["transcript"]})
    # Keep records of clips outside the current selection (e.g. a pilot run on some parts).
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
    parser.add_argument("--parts", nargs="*", help="only these content files (part ids)")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--retry-flagged", action="store_true",
                        help="regenerate clips whose transcript did not match; keep the better take")
    arguments = parser.parse_args()
    if arguments.stage == "count":
        print(len(current_jobs(set(arguments.parts) if arguments.parts else None)), "unique clips")
    else:
        (merge if arguments.stage == "merge" else generate)(arguments)
