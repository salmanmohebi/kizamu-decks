"""Generate cached German pilot audio with local models, independently of edge-tts.

Run with the optional MLX environment on Apple Silicon. No paid service is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from kizamu.paths import DATA

PILOT = DATA / "german" / "vocab" / "pilot"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
MODELS = {
    "qwen": "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-6bit",
    "chatterbox": "mlx-community/chatterbox-multilingual-v3",
}
STYLE = "A warm, calm adult male native German speaker, speaking natural Standard German with precise German pronunciation, a medium-low pitch and conversational rhythm. Clear and unhurried, without exaggeration. Read only the provided text."
REFERENCE_URLS = [f"https://raw.githubusercontent.com/thorstenMueller/Thorsten-Voice/master/docs/samples/sample0{i}-gt.wav" for i in range(1, 4)]


def reference_recording():
    """Use a deliberately published CC0 German human recording, not user audio."""
    path = PILOT / "models" / "thorsten-reference.wav"
    if not path.exists():
        import io
        import numpy as np
        import requests
        import soundfile as sf
        chunks = []
        sample_rate = None
        for url in REFERENCE_URLS:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            audio, rate = sf.read(io.BytesIO(response.content))
            if sample_rate is not None and rate != sample_rate:
                raise ValueError("Reference recordings must share a sample rate")
            sample_rate = rate
            chunks.extend([audio, np.zeros(int(rate * 0.15))])
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, np.concatenate(chunks), sample_rate)
        (path.parent / "thorsten-reference.json").write_text(json.dumps({
            "speaker": "Thorsten Müller", "sources": REFERENCE_URLS,
            "license": "CC0-1.0",
            "project": "https://github.com/thorstenMueller/Thorsten-Voice",
            "purpose": "German reference conditioning for Chatterbox pilot",
        }, ensure_ascii=False, indent=2) + "\n")
    return path


def jobs(entries):
    for entry in entries:
        yield entry["id"], "word", entry["german"]
        for number, example in enumerate(entry["examples"], 1):
            yield entry["id"], f"s{number}", example["de"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=MODELS, required=True)
    parser.add_argument("--limit", type=int, help="Number of entries, for a smoke test")
    parser.add_argument("--style", default=STYLE, help="Voice description for Qwen VoiceDesign")
    parser.add_argument("--only", action="append", help="Generate only an entry:slot key; repeatable")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    entries = json.loads((PILOT / "entries.json").read_text())
    if args.limit is not None:
        entries = entries[:args.limit]

    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model

    model_name = MODELS[args.engine]
    print(f"Loading {model_name}", flush=True)
    model = load_model(model_name)
    conditioning = None
    reference_hash = None
    if args.engine == "chatterbox":
        from mlx_audio.utils import load_audio
        reference = reference_recording()
        reference_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
        waveform = load_audio(str(reference), sample_rate=model.sample_rate)
        conditioning = model.prepare_conditionals(waveform, model.sample_rate, exaggeration=0.1)
    directory = PILOT / "audio" / args.engine
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for entry_id, slot, text in jobs(entries):
        key = f"{entry_id}:{slot}"
        if args.only and key not in args.only:
            continue
        spoken_text = text.rstrip(".?!") + "." if slot == "word" else text
        settings = {"engine": args.engine, "model": model_name, "text": text,
                    "spoken_text": spoken_text,
                    "voice": "German male voice design" if args.engine == "qwen" else "Thorsten-Voice CC0 reference",
                    "reference_sha256": reference_hash,
                    "style": args.style if args.engine == "qwen" else None,
                    "language": "German", "seed": args.seed, "temperature": 0.65,
                    "max_tokens": 90 if slot == "word" else 300, "mlx_audio_version": "0.5.9"}
        if key in manifest and (directory / manifest[key]["file"]).exists() and all(
            manifest[key]["settings"].get(k) == v for k, v in settings.items() if k != "seed"
        ) and not args.only:
            print(f"Cached {key}", flush=True)
            continue
        start = time.monotonic()
        for attempt in range(5):
            settings["seed"] = args.seed + attempt
            mx.random.seed(settings["seed"])
            if args.engine == "qwen":
                outputs = model.generate_voice_design(
                    text=spoken_text, language="German", instruct=args.style,
                    temperature=settings["temperature"], max_tokens=settings["max_tokens"])
            else:
                outputs = model.generate(
                    text=spoken_text, lang_code="de", temperature=settings["temperature"],
                    conds=conditioning, exaggeration=0.1,
                    max_new_tokens=settings["max_tokens"], verbose=False)
            chunks = []
            sample_rate = None
            for result in outputs:
                chunks.append(np.array(result.audio).reshape(-1))
                sample_rate = result.sample_rate
            if not chunks or sample_rate is None:
                raise RuntimeError(f"No audio generated for {key}")
            audio = np.concatenate(chunks)
            duration = len(audio) / sample_rate
            if np.isfinite(audio).all() and 0.15 < duration < (4 if slot == "word" else 16):
                break
            print(f"Retrying {key}: suspicious duration {duration:.2f}s", flush=True)
            mx.clear_cache()
        else:
            raise RuntimeError(f"Invalid audio after five attempts for {key}: {duration:.2f}s")
        digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:20]
        name = f"goethe_pilot_{args.engine}_{digest}.mp3"
        path = directory / name
        peak = float(np.abs(audio).max())
        if peak < 0.001:
            raise RuntimeError(f"Silent audio for {key}")
        if peak > 0.98:
            audio = audio * (0.98 / peak)
        temporary = path.with_suffix(".tmp.mp3")
        sf.write(temporary, audio, sample_rate, format="MP3", subtype="MPEG_LAYER_III")
        temporary.replace(path)
        manifest[key] = {"file": name, "settings": settings, "seconds": round(duration, 3),
                         "generation_seconds": round(time.monotonic() - start, 3),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "listening_review": "pending"}
        # Different senses may share identical spoken text and a media filename.
        # Keep every alias consistent if a later synthesis replaces that file.
        for other_key, record in manifest.items():
            if other_key != key and record["file"] == name:
                record["sha256"] = manifest[key]["sha256"]
                record["seconds"] = manifest[key]["seconds"]
        manifest_tmp = manifest_path.with_suffix(".tmp.json")
        manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        manifest_tmp.replace(manifest_path)
        print(f"Generated {key}: {duration:.2f}s in {time.monotonic()-start:.1f}s", flush=True)
        mx.clear_cache()


if __name__ == "__main__":
    main()
