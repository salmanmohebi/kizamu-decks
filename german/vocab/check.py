"""Test side-by-side packages over the original 15 October collection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageOptions, ImportAnkiPackageRequest

from german.vocab.build_base import PROFILE
from german.vocab.build import DECK_ROOT, OUT, package_name
from german.vocab.pilot_validate import digest_rows
from german.vocab.audio import MANIFEST, atomic_json
from german.vocab.content import LEVELS
from german.vocab.source import ENTRIES, BUILD, VOCAB


def copy_database(source: Path, target: Path) -> None:
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def main() -> None:
    entries = json.loads(ENTRIES.read_text())
    mapping = json.loads((BUILD / "side-by-side-mapping.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    source_note_ids = ",".join(str(entry["source_note_id"]) for entry in entries)
    production = sqlite3.connect(PROFILE / "collection.anki2")

    with tempfile.TemporaryDirectory(prefix="goethe-side-import-", dir=BUILD) as tmp:
        collection_path = Path(tmp) / "collection.anki2"
        copy_database(BUILD / "source.anki21", collection_path)
        col = Collection(str(collection_path))
        try:
            note_columns = [row[1] for row in col.db.execute("pragma table_info(notes)")]
            card_columns = [row[1] for row in col.db.execute("pragma table_info(cards)")]
            original_notes = digest_rows(col.db.execute(
                f"select {','.join(note_columns)} from notes where id in ({source_note_ids}) order by id"
            ))
            original_cards = digest_rows(col.db.execute(
                f"select {','.join(card_columns)} from cards where nid in ({source_note_ids}) order by id"
            ))
            original_note_count = col.note_count()
            original_card_count = col.card_count()
            original_review_count = col.db.scalar("select count(*) from revlog")

            options = ImportAnkiPackageOptions(with_scheduling=True)
            imported = {}
            for level in LEVELS:
                package = OUT / package_name(level)
                result = col.import_anki_package(ImportAnkiPackageRequest(
                    package_path=str(package.resolve()), options=options
                ))
                imported[level] = len(result.log.new)
                print(f"Imported {level}: {imported[level]} new notes", flush=True)

            # Existing notes/cards are byte-exact after the side-by-side import.
            assert original_notes == digest_rows(col.db.execute(
                f"select {','.join(note_columns)} from notes where id in ({source_note_ids}) order by id"
            ))
            assert original_cards == digest_rows(col.db.execute(
                f"select {','.join(card_columns)} from cards where nid in ({source_note_ids}) order by id"
            ))
            assert col.note_count() == original_note_count + len(entries)
            assert col.card_count() == original_card_count + len(entries) * 2

            schedule_columns = [
                "ord", "type", "queue", "due", "ivl", "factor", "reps",
                "lapses", "left", "odue", "odid", "flags", "data",
            ]
            copied_reviews = 0
            max_timestamp_shift_ms = 0
            for entry in entries:
                record = mapping[entry["id"]]
                clone_note = col.get_note(record["clone_note_id"])
                assert clone_note["EntryID"] == entry["id"]
                assert clone_note["History"] == ""
                assert "https://kizamu.app/" in clone_note["Source"]
                clone_cards = {card.ord: card for card in clone_note.cards()}
                for card in clone_cards.values():
                    answer = card.answer()
                    assert "previous study history" not in answer
                    assert "Study history" not in answer
                    assert "15 October 2026" not in answer
                for source_card_text, clone_card_id in record["cards"].items():
                    source_card_id = int(source_card_text)
                    source_row = list(production.execute(
                        f"select {','.join(schedule_columns)} from cards where id=?", (source_card_id,)
                    ).fetchone())
                    clone_row = col.db.first(
                        f"select {','.join(schedule_columns)} from cards where id=?", clone_card_id
                    )
                    if source_row != clone_row:
                        raise AssertionError(
                            f"schedule mismatch {entry['id']} source_card={source_card_id} "
                            f"clone_card={clone_card_id} source={source_row!r} clone={clone_row!r}"
                        )
                    source_reviews = list(col.db.execute(
                        "select id,ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id",
                        source_card_id,
                    ))
                    assert len(source_reviews) == col.db.scalar(
                        "select count(*) from revlog where cid=?", clone_card_id
                    )
                    for source_review in source_reviews:
                        clone_review_id = record["review_ids"][str(source_review[0])]
                        clone_review = col.db.first(
                            "select id,cid,ease,ivl,lastIvl,factor,time,type from revlog where id=?",
                            clone_review_id,
                        )
                        assert clone_review[1] == clone_card_id
                        assert source_review[1:] == clone_review[2:]
                        shift = abs(source_review[0] - clone_review[0])
                        max_timestamp_shift_ms = max(max_timestamp_shift_ms, shift)
                        # A review ID is also its millisecond timestamp and
                        # must be unique collection-wide. Clones use the
                        # nearest free timestamp; crowded imports can require
                        # a shift of just over one minute.
                        assert shift < 120_000
                    copied_reviews += len(source_reviews)
                expected_files = [manifest[f"{entry['id']}:{slot}"]["file"] for slot in ("word", "s1", "s2", "s3")]
                for card in clone_cards.values():
                    actual = [tag.filename for tag in card.answer_av_tags()]
                    assert actual == expected_files

            assert copied_reviews == sum(item["copied_review_records"] for item in mapping.values())
            assert col.db.scalar("select count(*) from revlog") == original_review_count + copied_reviews
            for level in LEVELS:
                did = col.decks.id(f"{DECK_ROOT}::{level}")
                assert col.decks.card_count(did, include_subdecks=False) == 2 * imported[level]
                assert col.decks.config_dict_for_deck_id(did)["autoplay"] is True

            media_dir = Path(col.media.dir())
            unique_media = {record["file"]: record["sha256"] for record in manifest.values()}
            missing = []
            for name, expected_digest in unique_media.items():
                path = media_dir / name
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
                    missing.append(name)
            assert not missing, missing
            report = {
                "native_overlay_import": "passed",
                "existing_notes_unchanged": True,
                "existing_cards_and_schedules_unchanged": True,
                "new_notes": len(entries),
                "new_cards": len(entries) * 2,
                "real_review_records_copied": copied_reviews,
                "maximum_review_timestamp_shift_ms": max_timestamp_shift_ms,
                "new_decks": [f"{DECK_ROOT}::{level}" for level in LEVELS],
                "learning_progress_required_on_import": True,
                "goethe_media_checksums_verified": len(unique_media),
                "missing_goethe_media": [],
            }
        finally:
            col.close()

    production.close()
    atomic_json(OUT / "side-by-side-validation.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
