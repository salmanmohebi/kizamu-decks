"""Make shareable copies of the built packages: no review history, no scheduling.

Each *-WITH-HISTORY.apkg is imported into a new, empty collection without scheduling
(all cards new, no review log), the FSRS parameters in its deck presets are reset to
the defaults (they were fitted to one person's reviews), and the result is exported
again with media and deck presets. Every output is imported once more into another
empty collection and checked.

    python -m kizamu.export_public            # → $KIZAMU_DATA/public/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from anki.collection import Collection, ExportAnkiPackageOptions, ImportAnkiPackageOptions, ImportAnkiPackageRequest
from anki.collection import NoteIdsLimit

from kizamu.paths import DATA

PACKAGES = [
    DATA / "german" / "vocab" / "out-kizamu" / "kizamu-german-vocab-A1-WITH-HISTORY.apkg",
    DATA / "german" / "vocab" / "out-kizamu" / "kizamu-german-vocab-A2-WITH-HISTORY.apkg",
    DATA / "german" / "vocab" / "out-kizamu" / "kizamu-german-vocab-B1-WITH-HISTORY.apkg",
    DATA / "german" / "grammar" / "out" / "kizamu-german-grammar-WITH-HISTORY.apkg",
    DATA / "german" / "grammar" / "out" / "kizamu-german-sentences-WITH-HISTORY.apkg",
    DATA / "english" / "C1" / "out" / "kizamu-english-C1-WITH-HISTORY.apkg",
    DATA / "english" / "C2" / "out" / "kizamu-english-C2-WITH-HISTORY.apkg",
]
OUT = DATA / "public"


def load(col: Collection, package: Path, with_scheduling: bool):
    return col.import_anki_package(ImportAnkiPackageRequest(
        package_path=str(package.resolve()),
        options=ImportAnkiPackageOptions(with_scheduling=with_scheduling, with_deck_configs=True)))


def counts(col: Collection) -> dict:
    return {
        "notes": col.db.scalar("select count() from notes"),
        "cards": col.db.scalar("select count() from cards"),
        "not_new_cards": col.db.scalar("select count() from cards where type != 0 or queue not in (0, -1)"),
        "review_records": col.db.scalar("select count() from revlog"),
        "media_files": sum(1 for _ in Path(col.media.dir()).iterdir()),
    }


# Preset names from earlier builds, renamed for the shared packages.
PRESET_NAMES = {"Goethe side-by-side · audio": "kizamu-german · vocab"}
# Text that only belongs in personal packages (history notes on the cards).
PERSONAL_TEXT = ["15 October 2026", "Card Info", "studied before"]


def clean_presets(col: Collection) -> list[str]:
    """Reset FSRS parameters to the defaults and rename old presets."""
    names = []
    for config in col.decks.all_config():
        changed = config["name"] in PRESET_NAMES
        config["name"] = PRESET_NAMES.get(config["name"], config["name"])
        for key in list(config):
            if key.startswith(("fsrsParams", "fsrsWeights")) and config[key]:
                config[key] = []
                changed = True
        if changed:
            col.decks.update_config(config)
            names.append(config["name"])
    return names


def export(source: Path, target: Path, work: Path) -> dict:
    col = Collection(str(work / "export" / "collection.anki2"))
    try:
        load(col, source, with_scheduling=False)
        reset = clean_presets(col)
        before = counts(col)
        note_ids = list(col.find_notes(""))
        col.export_anki_package(out_path=str(target.resolve()), limit=NoteIdsLimit(note_ids=note_ids),
                                options=ExportAnkiPackageOptions(with_scheduling=False, with_deck_configs=True,
                                                                 with_media=True))
    finally:
        col.close()
    check = Collection(str(work / "check" / "collection.anki2"))
    try:
        load(check, target, with_scheduling=True)
        after = counts(check)
        presets = sorted({c["name"] for c in check.decks.all_config()})
        fsrs_left = [c["name"] for c in check.decks.all_config()
                     if any(k.startswith(("fsrsParams", "fsrsWeights")) and v for k, v in c.items())]
        fsrs_keys = sorted({k for c in check.decks.all_config() for k in c if "fsrs" in k.lower()})
        personal = [text for text in PERSONAL_TEXT
                    if check.db.scalar("select count() from notes where flds like ?", f"%{text}%")]
    finally:
        check.close()
    assert after["review_records"] == 0 and after["not_new_cards"] == 0, after
    assert {k: after[k] for k in ("notes", "cards")} == {k: before[k] for k in ("notes", "cards")}, (before, after)
    assert after["media_files"] == before["media_files"], (before, after)
    assert not fsrs_left, fsrs_left
    assert not personal, personal
    return {"package": target.name, **after, "presets": presets, "presets_changed": reset, "fsrs_keys": fsrs_keys,
            "megabytes": round(target.stat().st_size / 1e6, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for source in PACKAGES:
        target = OUT / source.name.replace("-WITH-HISTORY", "")
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("export", "check"):
                (Path(tmp) / name).mkdir()
            report.append(export(source, target, Path(tmp)))
        print(json.dumps(report[-1]), flush=True)
    (OUT / "export-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    sums = [f"{hashlib.sha256((OUT / r['package']).read_bytes()).hexdigest()}  {r['package']}" for r in report]
    (OUT / "SHA256SUMS").write_text("\n".join(sums) + "\n")


if __name__ == "__main__":
    main()
