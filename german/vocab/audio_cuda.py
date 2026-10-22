"""Official CUDA Qwen3 VoiceDesign synthesis with resumable GPU shards."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from german.vocab.pilot_audio import STYLE
from german.vocab.audio import DIRECTORY, MANIFEST, atomic_json
from german.vocab.source import ENTRIES, BUILD, VOCAB

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
SHARDS = DIRECTORY / "shards"


def fingerprint(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:24]


def current_jobs(entries: list[dict]) -> dict[str, dict]:
    jobs = {}
    for entry in entries:
        for slot, text in [("word", entry["german"])] + [(f"s{i}", x["de"]) for i, x in enumerate(entry["examples"], 1)]:
            settings = {
                "model": MODEL, "text": text,
                "spoken_text": text.rstrip(".?!") + "." if slot == "word" else text,
                "style": STYLE, "language": "German", "temperature": 0.65,
                "top_p": 0.9, "max_new_tokens": 120 if slot == "word" else 300,
                "backend": "qwen-tts 0.1.1 CUDA",
            }
            digest = fingerprint(settings)
            job = jobs.setdefault(digest, {"settings": settings, "keys": [],
                                           "file": f"goethe_qwen_{digest}.mp3"})
            job["keys"].append(f"{entry['id']}:{slot}")
    return jobs


def approved_pilot(entries: list[dict]) -> dict:
    pilot_dir = VOCAB / "pilot/audio/qwen"
    source_manifest = json.loads((pilot_dir / "manifest.json").read_text())
    by_text = {x["settings"]["text"]: x for x in source_manifest.values()}
    result = {}
    for digest, job in current_jobs(entries).items():
        record = by_text.get(job["settings"]["text"])
        if not record:
            continue
        source = pilot_dir / record["file"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Invalid approved pilot checksum: {source}")
        target = DIRECTORY / source.name
        if not target.exists():
            shutil.copyfile(source, target)
        approved = dict(record)
        approved["settings"] = job["settings"]
        approved["provenance"] = "approved pilot"
        for key in job["keys"]:
            result[key] = approved
    return result


def generate(args) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    entries = json.loads(ENTRIES.read_text())
    jobs = current_jobs(entries)
    approved = approved_pilot(entries)
    shard_path = SHARDS / f"manifest-{args.shard_index}-of-{args.shard_count}.json"
    shard_manifest = json.loads(shard_path.read_text()) if shard_path.exists() else {}
    pending = []
    for digest, job in sorted(jobs.items(), key=lambda item: (item[1]["settings"]["max_new_tokens"], item[0])):
        is_word = job["settings"]["max_new_tokens"] == 120
        if args.kind == "word" and not is_word:
            continue
        if args.kind == "sentence" and is_word:
            continue
        if int(digest[:16], 16) % args.shard_count != args.shard_index:
            continue
        if all(key in approved for key in job["keys"]):
            continue
        if all(key in shard_manifest for key in job["keys"]) and (DIRECTORY / job["file"]).exists():
            continue
        pending.append((digest, job))
    if args.limit is not None:
        pending = pending[:args.limit]
    print(f"audio: shard {args.shard_index}/{args.shard_count}, {len(pending)} unique clips pending", flush=True)
    if not pending:
        return
    model = Qwen3TTSModel.from_pretrained(
        args.model, device_map="cuda:0", dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    failures = []
    began = time.monotonic()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset : offset + args.batch_size]
        started = time.monotonic()
        seed = 42000 + args.shard_index * 100000 + offset
        torch.manual_seed(seed)
        try:
            wavs, sample_rate = model.generate_voice_design(
                text=[x[1]["settings"]["spoken_text"] for x in batch],
                language=["German"] * len(batch), instruct=[STYLE] * len(batch),
                temperature=0.65, top_p=0.9,
                max_new_tokens=max(x[1]["settings"]["max_new_tokens"] for x in batch),
            )
        except Exception as error:
            failures.extend({"keys": x[1]["keys"], "error": repr(error)} for x in batch)
            atomic_json(BUILD / f"audio-failures-shard-{args.shard_index}.json", failures)
            print(f"audio batch failed: {error!r}", flush=True)
            continue
        if len(wavs) != len(batch):
            failures.extend({"keys": x[1]["keys"], "error": f"batch returned {len(wavs)}/{len(batch)} waveforms"} for x in batch)
            atomic_json(BUILD / f"audio-failures-shard-{args.shard_index}.json", failures)
            continue
        for (digest, job), audio in zip(batch, wavs):
            audio = np.asarray(audio).reshape(-1)
            duration = len(audio) / sample_rate
            peak = float(np.abs(audio).max()) if len(audio) else 0.0
            limit = 7 if job["settings"]["max_new_tokens"] == 120 else 22
            if not np.isfinite(audio).all() or peak < 0.001 or not 0.15 < duration < limit:
                failures.append({"keys": job["keys"], "error": f"invalid audio duration={duration:.3f} peak={peak:.6f}"})
                continue
            if peak > 0.98:
                audio = audio * (0.98 / peak)
            path = DIRECTORY / job["file"]
            temporary = path.with_suffix(".tmp.mp3")
            sf.write(temporary, audio, sample_rate, format="MP3", subtype="MPEG_LAYER_III")
            temporary.replace(path)
            record = {
                "file": path.name, "settings": job["settings"], "seconds": round(duration, 3),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "seed": seed,
                "provenance": "official Qwen3-TTS VoiceDesign CUDA generation",
            }
            for key in job["keys"]:
                shard_manifest[key] = record
            atomic_json(shard_path, shard_manifest)
        atomic_json(BUILD / f"audio-failures-shard-{args.shard_index}.json", failures)
        print(f"audio {min(offset+len(batch),len(pending))}/{len(pending)}; "
              f"batch {time.monotonic()-started:.1f}s; failures {len(failures)}; "
              f"elapsed {(time.monotonic()-began)/60:.1f}m", flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} audio clips failed; rerun resumes missing clips")


def merge(args) -> None:
    entries = json.loads(ENTRIES.read_text())
    expected = current_jobs(entries)
    merged = approved_pilot(entries)
    for index in range(args.shard_count):
        path = SHARDS / f"manifest-{index}-of-{args.shard_count}.json"
        if path.exists():
            merged.update(json.loads(path.read_text()))
    missing = []
    for job in expected.values():
        for key in job["keys"]:
            record = merged.get(key)
            if not record or record["settings"] != job["settings"]:
                missing.append(key)
                continue
            media = DIRECTORY / record["file"]
            if not media.exists() or hashlib.sha256(media.read_bytes()).hexdigest() != record["sha256"]:
                missing.append(key)
    if missing:
        atomic_json(BUILD / "audio-missing.json", missing)
        raise RuntimeError(f"Cannot merge: {len(missing)} current audio slots missing")
    atomic_json(MANIFEST, merged)
    atomic_json(BUILD / "audio-production-summary.json", {
        "entries": len(entries), "slots": len(merged), "unique_clips": len({x["file"] for x in merged.values()}),
        "approved_pilot_slots": sum(x.get("provenance") == "approved pilot" for x in merged.values()),
        "model": MODEL, "backend": "official qwen-tts 0.1.1 CUDA",
    })
    print(f"Merged {len(merged)} slots ({len(set(x['file'] for x in merged.values()))} unique clips)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["generate", "merge"])
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--kind", choices=["all", "word", "sentence"], default="all")
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args()
    if not 0 <= arguments.shard_index < arguments.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    merge(arguments) if arguments.stage == "merge" else generate(arguments)
