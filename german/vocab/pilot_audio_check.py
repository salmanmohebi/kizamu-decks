"""Transcribe local pilot MP3s to flag omitted, repeated, or substituted words.

ASR agreement is a useful check, not proof of native pronunciation or naturalness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from kizamu.paths import DATA

PILOT = DATA / "german" / "vocab" / "pilot"
MODEL = "mlx-community/whisper-large-v3-turbo-asr-fp16"


def normalized(text):
    numbers = {str(i): word for i, word in enumerate([
        "null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben",
        "acht", "neun", "zehn", "elf", "zwölf"])}
    return [numbers.get(token, token) for token in re.findall(r"\w+", text.casefold().replace("ß", "ss"))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["qwen", "chatterbox"], required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    from mlx_audio.stt import load
    model = load(MODEL)
    directory = PILOT / "audio" / args.engine
    manifest = json.loads((directory / "manifest.json").read_text())
    output = PILOT / "out" / f"audio-check-{args.engine}.json"
    output.parent.mkdir(exist_ok=True)
    report = json.loads(output.read_text()) if output.exists() else {}
    for index, (key, record) in enumerate(manifest.items()):
        if args.limit is not None and index >= args.limit:
            break
        path = directory / record["file"]
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if key in report and report[key]["sha256"] == sha256:
            transcript = report[key]["transcript"]
        else:
            result = model.generate(str(path), language="de", temperature=0.0,
                                    condition_on_previous_text=False, return_timestamps=False)
            transcript = result.text.strip()
        expected = record["settings"]["text"]
        matches = normalized(transcript) == normalized(expected)
        report[key] = {"expected": expected, "transcript": transcript,
                       "text_matches": matches,
                       "normalization": "ignore case/punctuation; ß=ss; digits 0–12 match spelled German numbers",
                       "sha256": sha256, "asr_model": MODEL}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{'MATCH' if matches else 'REVIEW'} {key}: {transcript}", flush=True)
    mismatches = [key for key, value in report.items() if not value.get("text_matches", value.get("matches_ignoring_case_punctuation_and_ss"))]
    print(json.dumps({"checked": len(report), "needs_review": mismatches}), flush=True)


if __name__ == "__main__":
    main()
