"""Package the audio clips for sharing: one zip + one metadata.csv per deck family.

    python -m kizamu.export_audio            # → $KIZAMU_DATA/public-audio/

Only clips listed in a manifest are included. Each zip holds the MP3s (stored, not
compressed again) and its metadata.csv; the same metadata.csv is also written next to
the zip so it can be read without unpacking.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from pathlib import Path

from kizamu.paths import DATA

FAMILIES = {
    "german-vocab": [DATA / "german" / "vocab" / "audio" / "qwen", DATA / "german" / "vocab" / "pilot" / "audio" / "qwen"],
    "german-grammar": [DATA / "german" / "grammar" / "audio" / "qwen"],
    "english": [DATA / "english" / "audio" / "qwen"],
}
OUT = DATA / "public-audio"
COLUMNS = ["file_name", "text", "spoken_text", "language", "voice", "seconds", "asr_transcript", "asr_match"]


def rows(manifest: dict, folders: list[Path]) -> tuple[list[dict], dict[str, Path], int]:
    found, paths, missing = [], {}, 0
    for record in manifest.values():
        name = record["file"]
        if name in paths:
            continue
        path = next((folder / name for folder in folders if (folder / name).exists()), None)
        if path is None:
            missing += 1
            continue
        settings = record["settings"]
        paths[name] = path
        found.append({"file_name": name, "text": settings["text"], "spoken_text": settings["spoken_text"],
                      "language": settings["language"], "voice": settings["style"], "seconds": record["seconds"],
                      "asr_transcript": record.get("transcript", ""),
                      "asr_match": record.get("asr_match", "")})
    return found, paths, missing


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for family, folders in FAMILIES.items():
        manifest = json.loads((folders[0] / "manifest.json").read_text())
        found, paths, missing = rows(manifest, folders)
        found.sort(key=lambda row: row["file_name"])
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(found)
        (OUT / f"{family}-metadata.csv").write_text(buffer.getvalue())
        with zipfile.ZipFile(OUT / f"{family}.zip", "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(f"{family}/metadata.csv", buffer.getvalue())
            for row in found:
                archive.write(paths[row["file_name"]], f"{family}/{row['file_name']}")
        report[family] = {"clips": len(found), "missing": missing,
                          "hours": round(sum(float(r["seconds"]) for r in found) / 3600, 1),
                          "megabytes": round((OUT / f"{family}.zip").stat().st_size / 1e6, 1)}
        print(family, json.dumps(report[family]), flush=True)
    (OUT / "export-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "README.md").write_text((Path(__file__).parent / "hf-dataset-card.md").read_text())


if __name__ == "__main__":
    main()
