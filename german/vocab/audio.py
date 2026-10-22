"""Resumable, content-addressed Qwen3 audio for the complete vocabulary set."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from german.vocab.pilot_audio import STYLE, MODELS
from german.vocab.source import ENTRIES, VOCAB, BUILD

DIRECTORY = VOCAB / "audio/qwen"
MANIFEST = DIRECTORY / "manifest.json"


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", action="append")
    parser.add_argument("--words-only", action="store_true")
    parser.add_argument("--source", type=Path, default=ENTRIES)
    args = parser.parse_args()
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    entries = json.loads(args.source.read_text())
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    # The pilot was approved by the user. Reuse its checked clips when the text
    # and voice match; IDs change when full-collection groups are consolidated.
    pilot_dir = VOCAB / "pilot/audio/qwen"
    pilot = json.loads((pilot_dir / "manifest.json").read_text())
    reused = {}
    for record in pilot.values():
        reused[record["settings"]["text"]] = record
    jobs = {}
    for entry in entries:
        slots = [("word", entry["german"])]
        if not args.words_only: slots += [(f"s{i}", e["de"]) for i, e in enumerate(entry["examples"], 1)]
        for slot, text in slots:
            key = f"{entry['id']}:{slot}"
            if args.only and key not in args.only: continue
            settings = {"model": MODELS["qwen"], "text": text,
                "spoken_text": text.rstrip(".?!") + "." if slot == "word" else text,
                "style": STYLE, "language": "German", "temperature": .65,
                "max_tokens": 90 if slot == "word" else 240, "mlx_audio_version": "0.5.9"}
            old = manifest.get(key)
            if old and old["settings"] == settings and (DIRECTORY / old["file"]).exists() and not args.only:
                continue
            record = reused.get(text)
            if record and not args.only:
                source = pilot_dir / record["file"]
                if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
                    raise ValueError(f"Invalid pilot checksum: {source}")
                import shutil
                shutil.copyfile(source, DIRECTORY / source.name)
                manifest[key] = dict(record, settings=settings, provenance="approved pilot")
                continue
            fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:24]
            job = jobs.setdefault(fingerprint, {"settings": settings, "keys": [], "file": f"goethe_qwen_{fingerprint}.mp3"})
            job["keys"].append(key)
    atomic_json(MANIFEST, manifest)
    pending = sorted(jobs.values(), key=lambda j: (j["settings"]["max_tokens"], len(j["settings"]["spoken_text"])))
    if args.limit: pending = pending[:args.limit]
    print(f"Qwen audio: {len(pending)} unique clips pending; {len(manifest)} slots cached", flush=True)
    if not pending: return
    model = load_model(MODELS["qwen"])
    began = time.monotonic()
    failures = []
    completed = 0
    for maximum in [90, 240]:
        group = [j for j in pending if j["settings"]["max_tokens"] == maximum]
        for offset in range(0, len(group), args.batch_size):
            batch = group[offset:offset+args.batch_size]
            for attempt in range(5):
                batch_seed = 42 + completed + attempt
                mx.random.seed(batch_seed)
                retry = []
                start = time.monotonic()
                for result in model.batch_generate(
                    texts=[j["settings"]["spoken_text"] for j in batch],
                    instructs=[STYLE]*len(batch), lang_code="German", temperature=.65,
                    max_tokens=maximum, verbose=False,
                ):
                    job = batch[result.sequence_idx]
                    audio = np.array(result.audio).reshape(-1)
                    duration = len(audio)/result.sample_rate
                    peak = float(np.abs(audio).max()) if len(audio) else 0
                    if not np.isfinite(audio).all() or peak < .001 or not .15 < duration < (6 if maximum == 90 else 18) or result.token_count >= maximum:
                        retry.append(job)
                        continue
                    if peak > .98: audio *= .98/peak
                    path = DIRECTORY / job["file"]
                    temporary = path.with_suffix(".tmp.mp3")
                    sf.write(temporary, audio, result.sample_rate, format="MP3", subtype="MPEG_LAYER_III")
                    temporary.replace(path)
                    record = {"file": path.name, "settings": job["settings"], "seconds": round(duration, 3),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "seed": batch_seed,
                        "token_count": result.token_count, "provenance": "Qwen3 VoiceDesign batch generation"}
                    for key in job["keys"]: manifest[key] = record
                    atomic_json(MANIFEST, manifest)
                    completed += 1
                print(f"Audio {completed}/{len(pending)}; batch {time.monotonic()-start:.1f}s; retry {len(retry)}; total {(time.monotonic()-began)/60:.1f} min; GPU peak {mx.get_peak_memory()/1e9:.1f} GB", flush=True)
                mx.clear_cache()
                batch = retry
                if not batch: break
            failures.extend(j["keys"] for j in batch)
    atomic_json(BUILD / "audio-generation-failures.json", failures)
    if failures: raise RuntimeError(f"Audio failed for {len(failures)} clips; see audio-generation-failures.json")


if __name__ == "__main__":
    main()
