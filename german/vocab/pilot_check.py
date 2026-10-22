"""Import the pilot into a disposable Anki profile and verify cards and media."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import tempfile

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest, ImportAnkiPackageOptions

from german.vocab.pilot_build import PILOT, load_entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="qwen", choices=["qwen", "chatterbox"])
    args = parser.parse_args()
    package = PILOT / "out" / f"Goethe-20-entry-pilot-{args.engine}.apkg"
    entries = {e["id"]: e for e in load_entries()}
    with tempfile.TemporaryDirectory(prefix="goethe-pilot-import-") as tmp:
        col = Collection(str(Path(tmp) / "collection.anki2"))
        try:
            col.import_anki_package(ImportAnkiPackageRequest(
                package_path=str(package), options=ImportAnkiPackageOptions(with_scheduling=True)))
            assert col.note_count() == 20
            assert col.card_count() == 40
            for nid, in col.db.execute("select id from notes"):
                note = col.get_note(nid)
                entry = entries[note["EntryID"]]
                assert len(note.cards()) == 2
                for card in note.cards():
                    front = html.unescape(card.question())
                    back = html.unescape(card.answer())
                    assert entry["german"] in (front if card.ord == 0 else back)
                    assert entry["english"] in (front if card.ord == 1 else back)
                    assert "Forms & grammar" not in front
                    assert "Meaning" not in front
                    assert "Forms & grammar" in back
                    assert "{{" not in front and "{{" not in back
                    for example in entry["examples"]:
                        assert example["de"] in back and example["en"] in back
                    assert back.count("<audio ") == 3
            media_check = col.media.check()
            assert not media_check.missing, list(media_check.missing)
            assert not media_check.unused, list(media_check.unused)
            assert not col.db.scalar("select count(*) from revlog")
            report = {"package": package.name, "native_import": "passed", "notes": 20,
                      "cards": 40, "examples": 60, "both_directions_render": "passed",
                      "all_explanations_hidden_on_front": True,
                      "missing_media": list(media_check.missing),
                      "unused_media": list(media_check.unused),
                      "isolated_preview_has_no_copied_review_history": True}
            (PILOT / "out" / f"package-validation-{args.engine}.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
        finally:
            col.close()


if __name__ == "__main__":
    main()
