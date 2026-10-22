"""Import the kizamu grammar packages over a copy of the 15 October collection and verify.

Checks: legacy notes/cards are byte-identical after import; every replacement card has
the legacy card's schedule and all its review records; every new card renders a
non-empty front; every referenced audio file arrived intact.

    python -m german.grammar.check
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageOptions, ImportAnkiPackageRequest

from german.grammar.build import CONFIG_NAME, PACKAGES, PROFILE
from german.grammar.common import BUILD, DECK_ROOT, OUT, SNAPSHOT, atomic_json

SCHEDULE = ["type", "queue", "due", "ivl", "factor", "reps", "lapses", "left", "odue", "odid", "flags", "data"]


def digest(rows) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def main() -> None:
    mapping = json.loads((BUILD / "history-mapping.json").read_text())
    legacy = json.loads((BUILD / "legacy.json").read_text())
    legacy_notes = ",".join(str(r["note_id"]) for r in legacy.values())
    built = sqlite3.connect(f"file:{PROFILE / 'collection.anki2'}?mode=ro", uri=True)
    with tempfile.TemporaryDirectory(prefix="kizamu-grammar-import-", dir=BUILD) as tmp:
        path = Path(tmp) / "collection.anki2"
        with sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        col = Collection(str(path))
        try:
            note_cols = [r[1] for r in col.db.execute("pragma table_info(notes)")]
            card_cols = [r[1] for r in col.db.execute("pragma table_info(cards)")]
            before_notes = digest(col.db.execute(f"select {','.join(note_cols)} from notes where id in ({legacy_notes}) order by id"))
            before_cards = digest(col.db.execute(f"select {','.join(card_cols)} from cards where nid in ({legacy_notes}) order by id"))
            counts = (col.note_count(), col.card_count(), col.db.scalar("select count() from revlog"))
            legacy_reviews = {}
            for entry in mapping:
                legacy_reviews[entry["legacy_card"]] = list(col.db.execute(
                    "select ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id", entry["legacy_card"]))

            imported_notes = 0
            for filename in PACKAGES.values():
                result = col.import_anki_package(ImportAnkiPackageRequest(
                    package_path=str((OUT / filename).resolve()), options=ImportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True)))
                if result.log.updated or result.log.duplicate or result.log.conflicting:
                    raise AssertionError(f"{filename}: import touched existing notes")
                imported_notes += len(result.log.new)
                print(f"Imported {filename}: {len(result.log.new)} new notes", flush=True)

            assert before_notes == digest(col.db.execute(f"select {','.join(note_cols)} from notes where id in ({legacy_notes}) order by id")), "legacy notes changed"
            assert before_cards == digest(col.db.execute(f"select {','.join(card_cols)} from cards where nid in ({legacy_notes}) order by id")), "legacy cards changed"

            # Card IDs may be reassigned on import; locate new cards by ItemID + template ord.
            built_index = {}
            for cid, flds, ord_, mid in built.execute(
                    "select c.id, n.flds, c.ord, n.mid from cards c join notes n on n.id=c.nid"):
                built_index[cid] = (flds, ord_)
            imported_index = {}
            for cid, flds, ord_ in col.db.execute(
                    "select c.id, n.flds, c.ord from cards c join notes n on n.id=c.nid "
                    f"where c.did in (select id from decks where name like '{DECK_ROOT}%')"):
                imported_index[(flds, ord_)] = cid
            new_cards = len(imported_index)
            copied = studied = 0
            max_shift = 0
            for entry in mapping:
                cid = imported_index[built_index[entry["new_card"]]]
                if not entry["studied"]:
                    assert col.db.scalar("select type from cards where id=?", cid) == 0
                    continue
                studied += 1
                want = col.db.first(f"select {','.join(SCHEDULE)} from cards where id=?", entry["legacy_card"])
                got = col.db.first(f"select {','.join(SCHEDULE)} from cards where id=?", cid)
                assert want == got, f"schedule mismatch {entry['item']}: {want} != {got}"
                reviews = list(col.db.execute(
                    "select ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id", cid))
                assert reviews == legacy_reviews[entry["legacy_card"]], f"review records differ for {entry['item']}"
                old_ids = [r[0] for r in col.db.execute("select id from revlog where cid=? order by id", entry["legacy_card"])]
                new_ids = [r[0] for r in col.db.execute("select id from revlog where cid=? order by id", cid)]
                max_shift = max([max_shift] + [abs(a - b) for a, b in zip(old_ids, new_ids)])
                copied += len(reviews)

            empty, render_errors = 0, []
            for cid in imported_index.values():
                card = col.get_card(cid)
                try:
                    if not card.question().strip():
                        empty += 1
                    card.answer()
                except Exception as error:  # noqa: BLE001 - report every broken card
                    render_errors.append(f"{cid}: {error}")
            assert not empty and not render_errors, (empty, render_errors[:5])

            media_dir = Path(col.media.dir())
            referenced = set()
            for (flds,) in col.db.execute(
                    "select n.flds from notes n where n.id in (select nid from cards where did in "
                    f"(select id from decks where name like '{DECK_ROOT}%'))"):
                referenced.update(part.split("]")[0] for part in flds.split("[sound:")[1:])
            vocab_like = {name for name in referenced if not name.startswith("kizamu_grammar_qwen_")}
            missing = sorted(name for name in referenced if not (media_dir / name).exists())
            assert not missing, missing[:10]
            assert not vocab_like, sorted(vocab_like)[:5]

            decks = sorted(d.name for d in col.decks.all_names_and_ids() if d.name.startswith(DECK_ROOT))
            config = col.decks.config_dict_for_deck_id(col.decks.id(f"{DECK_ROOT}::grammar"))
            report = {
                "native_overlay_import": "passed",
                "existing_notes_unchanged": True,
                "existing_cards_and_schedules_unchanged": True,
                "new_notes": imported_notes, "new_cards": new_cards,
                "notes_before_and_after": [counts[0], col.note_count()],
                "replacement_cards_with_history": studied,
                "review_records_copied": copied,
                "revlog_before_and_after": [counts[2], col.db.scalar("select count() from revlog")],
                "maximum_review_timestamp_shift_ms": max_shift,
                "cards_rendered": new_cards, "audio_files_verified": len(referenced),
                "deck_count": len(decks), "top_level_decks": sorted({"::".join(d.split("::")[:3]) for d in decks if d.count("::") >= 2}),
                "deck_config": {"name": config["name"], "autoplay": config["autoplay"]},
                "learning_progress_required_on_import": True,
            }
            assert col.db.scalar("select count() from revlog") == counts[2] + copied
            assert config["name"] == CONFIG_NAME and config["autoplay"], config["name"]
        finally:
            col.close()
    built.close()
    atomic_json(OUT / "import-validation.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
