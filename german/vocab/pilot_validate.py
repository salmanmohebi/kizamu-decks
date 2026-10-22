"""Check native Anki migration of the pilot on a temporary copy only.

The source is opened read-only. No source media, live Anki profile, or archived
cards are modified. Anki's own note-type conversion preserves card identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from german.vocab.pilot_build import BACK, CSS, FIELDS, FRONT_DE, FRONT_EN, PILOT, field_values, load_entries


def digest_rows(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(json.dumps(tuple(row), ensure_ascii=False).encode() + b"\n")
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Already extracted SQLite collection")
    parser.add_argument("--allow-missing-audio", action="store_true")
    parser.add_argument("--export-pilot", action="store_true", help="Export selected original cards with their real review history")
    args = parser.parse_args()
    entries = load_entries()
    nids = [e["source_note_id"] for e in entries]
    ids = ",".join(map(str, nids))
    source = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
    source.create_collation("unicase", lambda a, b: (a.casefold() > b.casefold()) - (a.casefold() < b.casefold()))
    before_revlog = digest_rows(source.execute("select * from revlog order by id"))
    before_other_notes = digest_rows(source.execute(f"select * from notes where id not in ({ids}) order by id"))
    before_other_cards = digest_rows(source.execute(f"select * from cards where nid not in ({ids}) order by id"))
    columns = [r[1] for r in source.execute("pragma table_info(cards)") if r[1] not in {"did", "mod", "usn"}]
    cols = ",".join(columns)
    before_cards = digest_rows(source.execute(f"select {cols} from cards where nid in ({ids}) order by id"))
    before_guids = source.execute(f"select id,guid from notes where id in ({ids}) order by id").fetchall()
    selected_reviews = source.execute(f"select count(*) from revlog where cid in (select id from cards where nid in ({ids}))").fetchone()[0]
    with tempfile.TemporaryDirectory(prefix="goethe-pilot-history-") as tmp:
        working_path = Path(tmp) / "collection.anki2"
        target = sqlite3.connect(working_path)
        source.backup(target)
        target.close()
        from anki.collection import Collection
        col = Collection(str(working_path))
        try:
            model = col.models.new("Goethe vocabulary · 20-entry demo")
            for name in FIELDS:
                col.models.add_field(model, col.models.new_field(name))
            for name, front in [("DE → EN", FRONT_DE), ("EN → DE", FRONT_EN)]:
                template = col.models.new_template(name)
                template.update(qfmt=front, afmt=BACK)
                col.models.add_template(model, template)
            model["css"] = CSS
            col.models.add(model)
            for entry in entries:
                nid = entry["source_note_id"]
                note = col.get_note(nid)
                old = note.note_type()
                info = col.models.change_notetype_info(old_notetype_id=old["id"], new_notetype_id=model["id"])
                request = info.input
                request.note_ids.append(nid)
                # Preserve both template directions. Map nonempty prompt fields
                # before replacing their content to avoid empty-card generation.
                request.new_templates[:] = [0, 1]
                old_fields = {field["name"]: field["ord"] for field in old["flds"]}
                if "de_word" in old_fields:
                    german, english = "de_word", "en_word"
                elif "Wort_DE" in old_fields:
                    german, english = "Wort_DE", "Wort_EN"
                else:
                    german, english = "base_d", "base_e"
                request.new_fields[:] = [-1] * len(FIELDS)
                request.new_fields[FIELDS.index("German")] = old_fields[german]
                request.new_fields[FIELDS.index("English")] = old_fields[english]
                col.models.change_notetype_of_notes(request)
                note = col.get_note(nid)
                data, media = field_values(entry, "qwen", allow_missing=args.allow_missing_audio)
                for path in media:
                    col.media.write_data(path.name, path.read_bytes())
                for name, value in data.items():
                    note[name] = value
                col.update_note(note)
                deck_id = col.decks.id(f"Goethe · 20-entry demo::{entry['level']}")
                col.set_deck([card.id for card in note.cards()], deck_id)
            after_revlog = digest_rows(col.db.execute("select * from revlog order by id"))
            after_other_notes = digest_rows(col.db.execute(f"select * from notes where id not in ({ids}) order by id"))
            after_other_cards = digest_rows(col.db.execute(f"select * from cards where nid not in ({ids}) order by id"))
            after_cards = digest_rows(col.db.execute(f"select {cols} from cards where nid in ({ids}) order by id"))
            after_guids = [tuple(r) for r in col.db.execute(f"select id,guid from notes where id in ({ids}) order by id")]
            checks = {
                "all_review_log_rows_unchanged": before_revlog == after_revlog,
                "other_notes_unchanged": before_other_notes == after_other_notes,
                "other_cards_unchanged": before_other_cards == after_other_cards,
                "selected_card_ids_scheduling_and_fsrs_unchanged": before_cards == after_cards,
                "selected_note_ids_and_guids_unchanged": before_guids == after_guids,
            }
            report = {"scope": "temporary-copy native Anki note-type conversion; no archiving performed",
                      "source": args.database.name, "notes": len(entries), "cards": before_cards["rows"],
                      "selected_review_log_rows": selected_reviews, "collection_review_log": before_revlog,
                      "checked_card_columns": columns, "checks": checks,
                      "source_note_ids": nids}
            output = PILOT / "out" / "history-validation.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n")
            if not all(checks.values()):
                raise AssertionError(json.dumps(checks))
            if args.export_pilot:
                from anki.collection import NoteIdsLimit
                from anki.import_export_pb2 import ExportAnkiPackageOptions
                package = PILOT / "out" / "Goethe-20-entry-pilot-WITH-HISTORY.apkg"
                col.export_anki_package(out_path=str(package),
                    options=ExportAnkiPackageOptions(with_scheduling=True, with_media=True, with_deck_configs=False),
                    limit=NoteIdsLimit(note_ids=nids))
                print(f"Exported original cards and full review history: {package}")
            print(json.dumps(report, indent=2))
        finally:
            col.close()
    source.close()


if __name__ == "__main__":
    main()
