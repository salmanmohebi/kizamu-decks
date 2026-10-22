"""Import the kizamu-english package (KE_LEVEL, default C2) over a copy of the 15 October collection and verify.

Checks: existing notes and cards are byte-identical after import; cards with copied
history have the old card's schedule and all its review records; every new card renders
a non-empty front and back; every referenced audio file arrived; the deck preset is set.

    python -m english.check [--pilot]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageOptions, ImportAnkiPackageRequest

from english.build import CONFIG_ID, CONFIG_NAME, MODEL_ID, PACKAGE, PILOT_PACKAGE, PROFILE
from english.common import BUILD, DECK_ROOT, OUT, SNAPSHOT, atomic_json

SCHEDULE = ["type", "queue", "due", "ivl", "factor", "reps", "lapses", "left", "odue", "odid", "flags"]


def digest(rows) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    package = OUT / (PILOT_PACKAGE if args.pilot else PACKAGE)
    mapping = json.loads((BUILD / "history-mapping.json").read_text())
    built = sqlite3.connect(f"file:{PROFILE / 'collection.anki2'}?mode=ro", uri=True)
    built_ids = {cid: (flds, ord_) for cid, flds, ord_ in built.execute(
        "select c.id, n.flds, c.ord from cards c join notes n on n.id=c.nid where n.mid=?", (MODEL_ID,))}
    built.close()
    with tempfile.TemporaryDirectory(prefix="kizamu-english-import-", dir=BUILD) as tmp:
        path = Path(tmp) / "collection.anki2"
        with sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        col = Collection(str(path))
        try:
            note_cols = [r[1] for r in col.db.execute("pragma table_info(notes)")]
            card_cols = [r[1] for r in col.db.execute("pragma table_info(cards)")]
            before_notes = digest(col.db.execute(f"select {','.join(note_cols)} from notes order by id"))
            before_cards = digest(col.db.execute(f"select {','.join(card_cols)} from cards order by id"))
            counts = (col.note_count(), col.card_count(), col.db.scalar("select count() from revlog"))
            legacy = {}
            for entry in mapping:
                legacy[entry["legacy_card"]] = (
                    col.db.first(f"select {','.join(SCHEDULE)} from cards where id=?", entry["legacy_card"]),
                    list(col.db.execute("select ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id",
                                        entry["legacy_card"])))

            result = col.import_anki_package(ImportAnkiPackageRequest(
                package_path=str(package.resolve()),
                options=ImportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True)))
            if result.log.updated or result.log.duplicate or result.log.conflicting:
                raise AssertionError("import touched existing notes")
            imported = len(result.log.new)
            print(f"Imported {package.name}: {imported} new notes", flush=True)

            existing = f"id in (select id from notes where mid != {MODEL_ID})"
            assert before_notes == digest(col.db.execute(
                f"select {','.join(note_cols)} from notes where {existing} order by id")), "existing notes changed"
            assert before_cards == digest(col.db.execute(
                f"select {','.join(card_cols)} from cards where nid in (select id from notes where mid != {MODEL_ID}) "
                "order by id")), "existing cards changed"

            imported_ids = {(flds, ord_): cid for cid, flds, ord_ in col.db.execute(
                "select c.id, n.flds, c.ord from cards c join notes n on n.id=c.nid where n.mid=?", MODEL_ID)}
            copied = 0
            for entry in mapping:
                cid = imported_ids[built_ids[entry["new_card"]]]
                want_schedule, want_reviews = legacy[entry["legacy_card"]]
                got_schedule = col.db.first(f"select {','.join(SCHEDULE)} from cards where id=?", cid)
                # Imported new-card positions are shifted; studied cards keep their schedule.
                assert want_schedule == got_schedule, f"schedule differs for {entry['item']}"
                reviews = list(col.db.execute(
                    "select ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id", cid))
                assert reviews == want_reviews, f"review records differ for {entry['item']}"
                copied += len(reviews)

            empty, errors = 0, []
            for cid in imported_ids.values():
                card = col.get_card(cid)
                try:
                    if not card.question().strip() or not card.answer().strip():
                        empty += 1
                except Exception as error:  # noqa: BLE001 - report every broken card
                    errors.append(f"{cid}: {error}")
            assert not empty and not errors, (empty, errors[:5])

            media_dir = Path(col.media.dir())
            referenced = set()
            for (flds,) in col.db.execute("select flds from notes where mid=?", MODEL_ID):
                referenced.update(part.split("]")[0] for part in flds.split("[sound:")[1:])
            missing = sorted(name for name in referenced if not (media_dir / name).exists())
            assert not missing, missing[:10]

            decks = sorted(d.name for d in col.decks.all_names_and_ids() if d.name.startswith("kizamu-english"))
            config = col.decks.config_dict_for_deck_id(col.decks.id_for_name(DECK_ROOT))
            assert config["id"] == CONFIG_ID and config["name"] == CONFIG_NAME, config["name"]
            assert col.db.scalar("select count() from revlog") == counts[2] + copied
            report = {
                "package": package.name, "native_overlay_import": "passed",
                "existing_notes_and_cards_unchanged": True,
                "new_notes": imported, "new_cards": len(imported_ids),
                "notes_before_and_after": [counts[0], col.note_count()],
                "cards_with_copied_history": len(mapping), "review_records_copied": copied,
                "cards_rendered": len(imported_ids), "audio_files_verified": len(referenced),
                "decks": len(decks), "deck_config": {"name": config["name"], "new_per_day": config["new"]["perDay"],
                                                     "gather": config["newGatherPriority"]},
            }
        finally:
            col.close()
    atomic_json(OUT / ("import-validation-pilot.json" if args.pilot else "import-validation.json"), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
