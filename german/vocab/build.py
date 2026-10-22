"""Build side-by-side APKGs with cloned identities and copied real history.

These packages are for importing into the original collection.  Existing
notes/cards/review rows remain untouched.  Each migrated note receives new
identities, while its selected source cards' schedules, FSRS data, and review
records are copied to the new cards.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from anki.collection import Collection, NoteIdsLimit
from anki.import_export_pb2 import ExportAnkiPackageOptions

from german.vocab.build_base import PROFILE, file_sha256
from german.vocab.pilot_build import FIELDS
from german.vocab.audio import DIRECTORY, MANIFEST, atomic_json
from german.vocab.content import LEVELS
from german.vocab.source import ENTRIES, BUILD, VOCAB


OUT = VOCAB / "out-kizamu"
SIDE_PROFILE = BUILD / "side-by-side-profile"
DECK_ROOT = "kizamu-german::vocab"
MODEL_NAME = "kizamu-german · vocab"


def package_name(level: str) -> str:
    return f"kizamu-german-vocab-{level}-WITH-HISTORY.apkg"


def copy_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def side_history(value: str) -> str:
    del value
    return ""


def next_review_id(original_id: int, used: set[int]) -> int:
    # Review IDs encode millisecond timestamps. Pick the nearest free ID so
    # Card Info keeps the original date/time (normally shifted by only 1 ms).
    distance = 1
    while True:
        for candidate in (original_id + distance, original_id - distance):
            if candidate > 0 and candidate not in used:
                used.add(candidate)
                return candidate
        distance += 1


def build() -> None:
    entries = json.loads(ENTRIES.read_text())
    manifest = json.loads(MANIFEST.read_text())
    if SIDE_PROFILE.exists():
        shutil.rmtree(SIDE_PROFILE)
    SIDE_PROFILE.mkdir(parents=True)
    copy_database(PROFILE / "collection.anki2", SIDE_PROFILE / "collection.anki2")

    # The exported notes reference only the generated Goethe audio. Hard links
    # avoid another 246 MB copy while keeping this isolated profile complete.
    media_dir = SIDE_PROFILE / "collection.media"
    media_dir.mkdir()
    unique_media = {record["file"] for record in manifest.values()}
    for name in unique_media:
        os.link(DIRECTORY / name, media_dir / name)

    col = Collection(str((SIDE_PROFILE / "collection.anki2").resolve()))
    mapping: dict[str, dict] = {}
    try:
        model = col.models.by_name("Goethe vocabulary · progressive 2026")
        if model is None:
            raise RuntimeError("Migrated production note type is missing")
        model["name"] = MODEL_NAME
        for template in model["tmpls"]:
            template["afmt"] = template["afmt"].replace(
                '<div class="section"><h3>Your previous study history · import snapshot</h3>{{History}}</div>',
                "",
            ).replace(
                '<div class="section"><h3>Study history</h3>{{History}}</div>',
                "",
            )
        col.models.update(model)
        decks = {level: col.decks.id(f"{DECK_ROOT}::{level}") for level in LEVELS}
        source_config = col.decks.config_dict_for_deck_id(
            col.decks.id("Goethe vocabulary::A1")
        )
        config = next(
            (item for item in col.decks.all_config() if item["name"] == "Goethe side-by-side · audio"),
            None,
        )
        if config is None:
            config = col.decks.add_config("Goethe side-by-side · audio", clone_from=source_config)
        config["autoplay"] = True
        config["replayq"] = False
        col.decks.update_config(config)
        for did in decks.values():
            deck = col.decks.get(did)
            deck["conf"] = config["id"]
            col.decks.update(deck)

        card_columns = [
            row[1] for row in col.db.execute("pragma table_info(cards)")
            if row[1] not in {"id", "nid", "did", "mod", "usn"}
        ]
        rev_columns = [row[1] for row in col.db.execute("pragma table_info(revlog)")]
        if rev_columns != ["id", "cid", "usn", "ease", "ivl", "lastIvl", "factor", "time", "type"]:
            raise RuntimeError(f"Unexpected revlog schema: {rev_columns}")
        used_review_ids = {row[0] for row in col.db.execute("select id from revlog")}

        for index, entry in enumerate(entries, 1):
            source_note = col.get_note(entry["source_note_id"])
            source_cards = {card.ord: card for card in source_note.cards()}
            clone = col.new_note(model)
            for field in FIELDS:
                clone[field] = source_note[field]
            clone["History"] = side_history(clone["History"])
            clone["Source"] += (
                ' Continue learning with <a href="https://kizamu.app/">'
                'Kizamu</a>, an AI-enabled German learning app.'
            )
            clone.tags = sorted(set(source_note.tags + ["kizamu_german", "kizamu_vocab", entry["level"].lower()]))
            col.add_note(clone, decks[entry["level"]])
            clone_cards = {card.ord: card for card in clone.cards()}
            if set(source_cards) != {0, 1} or set(clone_cards) != {0, 1}:
                raise RuntimeError(f"Expected two directions for {entry['id']}")

            card_map = {}
            review_map = {}
            review_count = 0
            for ordinal in (0, 1):
                source_card = source_cards[ordinal]
                clone_card = clone_cards[ordinal]
                values = col.db.first(
                    f"select {','.join(card_columns)} from cards where id=?",
                    source_card.id,
                )
                assignments = ",".join(f"{name}=?" for name in card_columns)
                col.db.execute(
                    f"update cards set {assignments} where id=?",
                    *values,
                    clone_card.id,
                )
                card_map[str(source_card.id)] = clone_card.id
                rows = list(col.db.execute(
                    "select id,cid,usn,ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id",
                    source_card.id,
                ))
                for row in rows:
                    new_id = next_review_id(row[0], used_review_ids)
                    review_map[str(row[0])] = new_id
                    col.db.execute(
                        "insert into revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) values(?,?,?,?,?,?,?,?,?)",
                        new_id, clone_card.id, -1, *row[3:],
                    )
                review_count += len(rows)
            mapping[entry["id"]] = {
                "level": entry["level"],
                "source_note_id": source_note.id,
                "clone_note_id": clone.id,
                "cards": card_map,
                "review_ids": review_map,
                "copied_review_records": review_count,
            }
            if index % 500 == 0:
                print(f"Cloned {index}/{len(entries)} notes", flush=True)

        col.save(trx=False)
        OUT.mkdir(exist_ok=True)
        options = ExportAnkiPackageOptions(
            with_scheduling=True, with_media=True, with_deck_configs=True
        )
        for level in LEVELS:
            note_ids = [record["clone_note_id"] for record in mapping.values() if record["level"] == level]
            package = OUT / package_name(level)
            col.export_anki_package(
                out_path=str(package.resolve()), options=options,
                limit=NoteIdsLimit(note_ids=note_ids),
            )
            print(f"Exported {package}", flush=True)
    finally:
        col.close()

    atomic_json(BUILD / "side-by-side-mapping.json", mapping)
    report = {
        "notes": len(mapping),
        "cards": len(mapping) * 2,
        "copied_review_records": sum(item["copied_review_records"] for item in mapping.values()),
        "levels": {level: sum(item["level"] == level for item in mapping.values()) for level in LEVELS},
        "identity_policy": "new note/card identities; original cards remain unchanged",
        "history_policy": "selected source schedules, FSRS data, and review records copied to new cards",
        "deck_root": DECK_ROOT,
    }
    atomic_json(OUT / "side-by-side-build.json", report)
    instructions = """# Side-by-side import into your existing Anki profile

These packages use new note/card identities. They do not update, move, suspend,
or delete your existing cards. Their real review records and schedules are
copied from the 15 October 2026 collection snapshot.

1. Make a full Anki backup and sync all devices.
2. Import A1, A2, then B1.
3. ENABLE **Import any learning progress** for every package.
4. Open Card Info on several new cards and confirm the dated review records.
5. The new decks are under `kizamu-german::vocab`.

Do not import `Goethe-duplicate-archive-WITH-HISTORY.apkg` for this workflow.
Your old cards intentionally remain unchanged.
"""
    (OUT / "IMPORT-SIDE-BY-SIDE.md").write_text(instructions)
    packages = sorted(OUT.glob("*.apkg"))
    (OUT / "SHA256SUMS").write_text(
        "".join(f"{file_sha256(path)}  {path.name}\n" for path in packages)
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    build()
