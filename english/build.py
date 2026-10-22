"""Build the kizamu-english package of one level (KE_LEVEL=C1 or C2, default C2).

Every note gets a new, stable GUID derived from its catalogue id, so the package never
overwrites your old English notes, and a later build updates the notes of an earlier
import (e.g. the pilot) in place. Where a new card covers an old English card you studied
(same normalized term), the old card's schedule and review records (with new,
collision-free review IDs) are copied onto the new card, as in the kizamu-german build.

New-card positions interleave all categories by importance (Set 01s first), so studying
the parent deck gives a mix; the Usage card of a note comes about USAGE_DELAY notes after
its Meaning card.

    python -m english.build [--parts 03-idioms-01 ...] [--pilot]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3

import markdown as md
from anki.collection import Collection, NoteIdsLimit
from anki.import_export_pb2 import ExportAnkiPackageOptions

from english.audio import AUDIO, MANIFEST, PREFIX, file_for
from english.common import (
    BUILD, BY_KEY, CATALOGUE, CATEGORIES, DECK_ROOT, LEVEL, LEVELS, OUT, SHARED, SNAPSHOT, atomic_json,
    level_build, load_content, normalize, strip_marks,
)
from kizamu.paths import DATA

PROFILE = BUILD / "profile"
# Review IDs cloned by the other builds may already be in the real collection.
OTHER_PROFILES = [DATA / "german" / "vocab" / "build" / "side-by-side-profile" / "collection.anki2",
                  DATA / "german" / "grammar" / "build" / "profile" / "collection.anki2"] + [
    level_build(other) / "profile" / "collection.anki2" for other in LEVELS if other != LEVEL]
PACKAGE = f"kizamu-english-{LEVEL}-WITH-HISTORY.apkg"
PILOT_PACKAGE = f"kizamu-english-{LEVEL}-PILOT.apkg"
MODEL_NAME = f"kizamu-english · {LEVEL}"
CONFIG_NAME = f"kizamu-english · {LEVEL}"
# Fixed IDs, so later packages (the full deck after the pilot) update the same note type and preset.
MODEL_ID, CONFIG_ID = {"C2": (1761040000417, 1761040000418), "C1": (1761040000427, 1761040000428)}[LEVEL]
USAGE_DELAY = 30
# Old card templates that asked for the English term (production) → our Usage card.
PRODUCTION = {("phrasal-250", "Card 1"), ("close-up-c1", "Card 1"), ("essential-idioms", "Card 1"),
              ("everyday-expressions", "Cloze"), ("advanced-vocab", "Backward")}
SMALL = set("a an the of to in on at for with by from and or but as is are be it its i you we "
            "he she they me him her us them my your our their this that not no so if do".split())

CSS = """
.card { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 19px; line-height: 1.6; text-align: left; color: #22303c;
  background: #f3f4f1; padding: 24px; }
.wrap { max-width: 720px; margin: auto; }
.eyebrow { color: #3f6185; font-size: 12px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; margin-bottom: 12px; }
.term { font-size: 32px; font-weight: 650; line-height: 1.25; margin-bottom: 6px; }
.chips { margin: 2px 0 10px; }
.chip { display: inline-block; border: 1px solid #b9c6d3; border-radius: 999px; padding: 0 10px;
  margin: 2px 6px 2px 0; background: #fcfcfa; font-size: 13px; color: #3f5468; }
.chip.reg-slang, .chip.reg-informal { border-color: #d5b98c; color: #7a5a22; }
.chip.reg-formal { border-color: #9fb8a6; color: #2f5c3d; }
.ipa { font-size: 17px; color: #4a6074; margin-bottom: 4px; }
.ipa .resp { margin-left: 10px; font-weight: 600; letter-spacing: .02em; }
.context { font-size: 22px; line-height: 1.5; margin: 14px 0 8px; }
.prompt { font-size: 23px; line-height: 1.5; margin: 6px 0 10px; }
.instruction { font-size: 15px; color: #4a6074; font-weight: 600; margin-bottom: 4px; }
.cue { color: #5f7080; font-size: 16px; margin-top: 8px; }
.hint { font-size: 16px; margin-top: 6px; color: #5f7080; }
.gap { display: inline-block; min-width: 2.6em; border-bottom: 2px solid #3f6185; margin: 0 2px; }
.cloze, b { color: #1f5d8f; font-weight: 700; }
.section { margin-top: 20px; padding-top: 14px; border-top: 1px solid #d6dde3; }
.section h3 { margin: 0 0 6px; font-size: 13px; color: #3f6185;
  text-transform: uppercase; letter-spacing: .06em; }
.pattern { display: inline-block; margin-top: 8px; padding: 3px 10px; border-radius: 6px;
  background: #e4eaf0; font-size: 16px; }
.example { margin: 10px 0; }
.wrong { color: #9b3b2f; }
.wrong::before { content: "✗ "; }
.right { color: #2f6b45; }
.right::before { content: "✓ "; }
.why { font-size: 17px; margin-top: 4px; }
.small { font-size: 17px; }
audio { display: block; width: 100%; max-width: 350px; height: 34px; margin-top: 8px; }
.source { font-size: 12px; color: #74818c; margin-top: 26px; }
.nightMode.card { background: #1c232a; color: #e6ebef; }
.nightMode .eyebrow, .nightMode .section h3, .nightMode .instruction { color: #9cc3e8; }
.nightMode .cue, .nightMode .hint, .nightMode .ipa, .nightMode .source { color: #b4c0ca; }
.nightMode .cloze, .nightMode b { color: #8cc8f5; }
.nightMode .chip { background: #24303a; border-color: #46596b; color: #c9d5df; }
.nightMode .chip.reg-slang, .nightMode .chip.reg-informal { border-color: #8a7140; color: #e3c48c; }
.nightMode .chip.reg-formal { border-color: #4f7a5c; color: #a8d8b5; }
.nightMode .pattern { background: #26333e; }
.nightMode .gap { border-color: #8cc8f5; }
.nightMode .section { border-color: #33414d; }
.nightMode .wrong { color: #f0a597; }
.nightMode .right { color: #93d6a8; }
@media (max-width: 480px) { .card { padding: 16px; font-size: 17px; } .term { font-size: 27px; }
  .context, .prompt { font-size: 20px; } }
"""

HEAD = """<div class="term">{{Term}}</div>{{#IPA}}<div class="ipa">{{IPA}}</div>{{/IPA}}{{Chips}}"""
DETAILS = """<div class="section"><h3>Meaning</h3>{{Meaning}}</div>
<div class="section"><h3>How to use it</h3>{{Usage}}{{#Pattern}}<div><span class="pattern">{{Pattern}}</span></div>{{/Pattern}}</div>"""
EXTRAS = """{{#Mistake}}<div class="section"><h3>Common mistake</h3>{{Mistake}}</div>{{/Mistake}}
{{#Related}}<div class="section"><h3>Related</h3><div class="small">{{Related}}</div></div>{{/Related}}"""
SOURCE = '<div class="source">{{Source}}</div>'

MEANING_FRONT = """<div class="wrap"><div class="eyebrow">{{Category}} · {{Set}} · Meaning</div>
<div class="term">{{Term}}</div>{{#FrontChips}}{{FrontChips}}{{/FrontChips}}
<div class="context">{{Context}}</div><div class="cue">{{Question}}</div>{{FrontAudio}}</div>"""
MEANING_BACK = """<div class="wrap"><div class="eyebrow">{{Category}} · {{Set}} · Meaning</div>
""" + HEAD + """{{BackAudio}}
""" + DETAILS + """
<div class="section"><h3>Examples</h3>{{Examples}}</div>
""" + EXTRAS + """
{{#Origin}}<div class="section"><h3>Origin</h3><div class="small">{{Origin}}</div></div>{{/Origin}}
""" + SOURCE + "</div>"

USAGE_FRONT = """<div class="wrap"><div class="eyebrow">{{Category}} · {{Set}} · Usage</div>
{{#Gap}}<div class="instruction">Complete the sentence.</div><div class="prompt">{{DrillFront}}</div>
<div class="cue">{{DrillHint}}</div><div class="hint">{{hint:First letters}}</div>{{/Gap}}
{{#Say}}<div class="instruction">Read it aloud, then check.</div><div class="prompt">{{DrillFront}}</div>
<div class="cue">{{DrillHint}}</div>{{/Say}}
{{#Listen}}<div class="instruction">Listen. What did you hear? Say it back, then check.</div>{{DrillAudio}}{{/Listen}}</div>"""
USAGE_BACK = """<div class="wrap"><div class="eyebrow">{{Category}} · {{Set}} · Usage</div>
<div class="prompt">{{DrillAnswer}}</div>{{DrillAudio}}
{{#Listen}}<div class="cue">{{DrillHint}}</div>{{/Listen}}
<div class="section">""" + HEAD + """</div>
""" + DETAILS + EXTRAS + SOURCE + "</div>"

FIELDS = ["Term", "Chips", "FrontChips", "IPA", "Question", "Context", "FrontAudio", "BackAudio",
          "Meaning", "Usage", "Pattern", "Examples", "Mistake", "Related", "Origin",
          "Gap", "Say", "Listen", "DrillFront", "DrillHint", "First letters", "DrillAnswer", "DrillAudio",
          "Category", "Set", "ItemID", "Source"]
TEMPLATES = [("Meaning", MEANING_FRONT, MEANING_BACK), ("Usage", USAGE_FRONT, USAGE_BACK)]

QUESTIONS = {"grammar": "What does this structure express, and when do you use it?",
             "nuance": "What is the difference, and which one fits here?"}


# ---------------------------------------------------------------- rendering

def escape(text: str) -> str:
    return html.escape(text, quote=False)


def inline(text: str) -> str:
    rendered = md.markdown(escape(text))
    return re.sub(r"^<p>(.*)</p>$", r"\1", rendered.strip(), flags=re.DOTALL)


class Media:
    def __init__(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        self.by_file = {record["file"]: record for record in self.manifest.values()}
        self.used: set[str] = set()
        self.missing: list[str] = []
        self.omitted: list[str] = []

    def sound(self, text: str) -> str:
        name = file_for(text)
        if name not in self.by_file or not (AUDIO / name).exists():
            self.missing.append(text)
            return ""
        if not self.by_file[name]["asr_match"]:
            # Whisper heard something else even after retries: no audio beats wrong audio.
            self.omitted.append(text)
            return ""
        self.used.add(name)
        return f"[sound:{name}]"


def initials(answer: str) -> str:
    out = []
    for word in answer.split():
        core = re.sub(r"[^\w'’-]", "", word)
        if core.lower() in SMALL or len(core) <= 2:
            out.append(word)
        else:
            out.append(core[0] + "_" * min(len(core) - 1, 8) + word[len(word.rstrip(".,;:!?")):])
    return " ".join(out)


def chips(entry: dict, front: bool = False) -> str:
    parts = [f'<span class="chip">{escape(entry["label"])}</span>']
    if not front:
        parts.append(f'<span class="chip reg-{entry["register"]}">{entry["register"]}</span>')
        if entry["region"] != "both":
            parts.append(f'<span class="chip">{"American" if entry["region"] == "US" else "British"}</span>')
    return '<div class="chips">' + "".join(parts) + "</div>"


def ipa_line(entry: dict) -> str:
    out = escape(entry.get("ipa", ""))
    if entry.get("respelling"):
        out += f'<span class="resp">{escape(entry["respelling"])}</span>'
    return out


def mistake_html(mistake: dict | None) -> str:
    if not mistake:
        return ""
    return (f'<div class="wrong">{inline(mistake["wrong"])}</div><div class="right">{inline(mistake["right"])}</div>'
            f'<div class="why">{inline(mistake["why"])}</div>')


def drill_fields(entry: dict, media: Media) -> dict:
    drill = entry["drill"]
    sentence = drill["sentence"]
    audio = media.sound(drill.get("spoken") or strip_marks(sentence))
    fields = {"Gap": "", "Say": "", "Listen": "", "DrillHint": inline(drill["hint"]), "DrillAudio": audio,
              "First letters": ""}
    if drill["type"] == "gap":
        answer = re.search(r"\{\{(.+?)\}\}", sentence).group(1)
        blanks = " ".join('<span class="gap"></span>' for _ in answer.split())
        before, after = sentence.split("{{" + answer + "}}")
        fields.update(Gap="1", DrillFront=escape(before) + blanks + escape(after),
                      DrillAnswer=escape(before) + f'<span class="cloze">{escape(answer)}</span>' + escape(after),
                      **{"First letters": escape(initials(answer))})
    else:
        fields.update({"Say" if drill["type"] == "say" else "Listen": "1",
                       "DrillFront": inline(sentence), "DrillAnswer": inline(sentence)})
    return fields


# ---------------------------------------------------------------- history

class History:
    """Copies the schedule and review records of studied old English cards onto new cards."""

    def __init__(self, col: Collection) -> None:
        self.col = col
        self.by_key: dict[str, list[dict]] = {}
        for record in json.loads((SHARED / "legacy-studied.json").read_text()):
            self.by_key.setdefault(record["key"], []).append(record)
        self.columns = [row[1] for row in col.db.execute("pragma table_info(cards)")
                        if row[1] not in {"id", "nid", "did", "ord", "mod", "usn"}]
        self.used = {row[0] for row in col.db.execute("select id from revlog")}
        for path in OTHER_PROFILES:
            # Review IDs cloned by the kizamu-german builds may already be in the real collection.
            if path.exists():
                other = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                self.used |= {row[0] for row in other.execute("select id from revlog")}
                other.close()
        self.claimed: set[int] = set()
        self.mapping: list[dict] = []

    def next_id(self, original: int) -> int:
        distance = 1
        while True:
            for candidate in (original + distance, original - distance):
                if candidate > 0 and candidate not in self.used:
                    self.used.add(candidate)
                    return candidate
            distance += 1

    def copy(self, entry: dict, cards: dict) -> None:
        records = self.by_key.get(normalize(entry["term"]), [])
        for ord_ in (0, 1):
            candidates = [r for r in records if ((r["source"], r["template"]) in PRODUCTION) == (ord_ == 1)
                          and r["card_id"] not in self.claimed]
            if not candidates:
                continue
            source = max(candidates, key=lambda r: r["reps"])
            self.claimed.add(source["card_id"])
            card = cards[ord_]
            values = self.col.db.first(f"select {','.join(self.columns)} from cards where id=?", source["card_id"])
            assignments = ",".join(f"{name}=?" for name in self.columns)
            self.col.db.execute(f"update cards set {assignments} where id=?", *values, card.id)
            rows = list(self.col.db.execute(
                "select id,ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id", source["card_id"]))
            for row in rows:
                self.col.db.execute(
                    "insert into revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) values(?,?,?,?,?,?,?,?,?)",
                    self.next_id(row[0]), card.id, -1, *row[1:])
            self.mapping.append({"item": entry["id"], "card": ["Meaning", "Usage"][ord_],
                                 "legacy_card": source["card_id"], "legacy_deck": source["deck"],
                                 "legacy_term": source["term"], "new_card": card.id, "reviews": len(rows)})


# ---------------------------------------------------------------- build

def ensure_model(col: Collection) -> dict:
    model = col.models.new(MODEL_NAME)
    for field in FIELDS:
        col.models.add_field(model, col.models.new_field(field))
    for name, front, back in TEMPLATES:
        template = col.models.new_template(name)
        template["qfmt"], template["afmt"] = front, back
        col.models.add_template(model, template)
    model["css"] = CSS
    model["sortf"] = 0
    temporary = col.models.add(model).id
    # Fixed ID: later packages (full deck after the pilot) update the same note type.
    for table, column in (("notetypes", "id"), ("fields", "ntid"), ("templates", "ntid")):
        col.db.execute(f"update {table} set {column}=? where {column}=?", MODEL_ID, temporary)
    return col.models.get(MODEL_ID)


def ensure_config(col: Collection) -> None:
    config = col.decks.add_config(CONFIG_NAME, clone_from=col.decks.get_config(1))
    config["new"]["perDay"] = 20
    config["new"]["bury"] = True
    config["rev"]["perDay"] = 9999
    config["rev"]["bury"] = True
    config["newGatherPriority"] = 1   # ascending position: most important first, all categories mixed
    config["newSortOrder"] = 1        # keep the gathered order
    config["autoplay"] = True
    config["replayq"] = False
    col.decks.update_config(config)
    col.db.execute("update deck_config set id=? where id=?", CONFIG_ID, config["id"])


def positions(catalogue: dict) -> dict[str, int]:
    """Interleave categories: an entry's key is its relative rank inside its category."""
    order = []
    for number, category in enumerate(CATEGORIES):
        ids = [e["id"] for p in catalogue["parts"] if p["category"] == category["key"] for e in p["entries"]]
        order += [((i + 0.5) / len(ids), number, eid) for i, eid in enumerate(ids)]
    return {eid: rank for rank, (_, _, eid) in enumerate(sorted(order))}


def build(args) -> dict:
    catalogue = json.loads(CATALOGUE.read_text())
    content = load_content()
    wanted = set(args.parts) if args.parts else {p["part_id"] for p in catalogue["parts"]}
    parts = [p for p in catalogue["parts"] if p["part_id"] in wanted]
    absent = [p["part_id"] for p in parts if p["part_id"] not in content]
    if absent and not args.allow_partial:
        raise SystemExit(f"{len(absent)} parts have no content yet: {absent[:5]}")
    rank = positions(catalogue)
    media = Media()
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    (PROFILE / "collection.media").mkdir(parents=True)
    with sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True) as src, \
            sqlite3.connect(PROFILE / "collection.anki2") as dst:
        src.backup(dst)
    col = Collection(str((PROFILE / "collection.anki2").resolve()))
    report = {"notes": 0, "cards": 0, "by_category": {}}
    note_ids = []
    try:
        if col.models.by_name(MODEL_NAME) or col.models.get(MODEL_ID):
            raise RuntimeError(f"Note type {MODEL_NAME!r} already exists in the snapshot")
        ensure_model(col)
        ensure_config(col)
        col.close()
        col = Collection(str((PROFILE / "collection.anki2").resolve()))  # reload after the ID change
        model = col.models.get(MODEL_ID)
        history = History(col)
        for part in parts:
            if part["part_id"] not in content:
                continue
            category = BY_KEY[part["category"]]
            did = col.decks.id(part["deck"])
            deck = col.decks.get(did)
            deck["conf"] = CONFIG_ID
            col.decks.update(deck)
            set_label = part["title"]
            meta = {e["id"]: e for e in part["entries"]}
            for entry in content[part["part_id"]]["entries"]:
                info = meta[entry["id"]]
                pronunciation = category["key"] == "pronunciation"
                term_sound = media.sound(entry.get("spoken_term") or entry["term"]) if entry.get("say_term", True) else ""
                question = QUESTIONS.get(category["key"], "What does it mean here, and when would you use it?")
                if pronunciation:
                    if part["index"] < 3:
                        question = "Say it aloud. What does it mean?"
                    elif LEVEL == "C1":  # stress, weak forms and intonation
                        question = "Say it aloud. Where do the stress and the pitch go?"
                    else:  # C2: connected speech and reductions
                        question = "What does it stand for, and how do Americans say it?"
                fields = {
                    "Term": escape(entry["term"]), "Chips": chips(entry), "FrontChips": chips(entry, front=True),
                    "IPA": ipa_line(entry), "Question": question, "Context": inline(entry["examples"][0]),
                    "FrontAudio": "" if pronunciation else term_sound,
                    "BackAudio": term_sound if pronunciation else "",
                    "Meaning": inline(entry["meaning"]), "Usage": inline(entry["usage"]),
                    "Pattern": inline(entry.get("pattern", "")),
                    "Examples": "".join(f'<div class="example">{inline(x)}{media.sound(strip_marks(x))}</div>'
                                        for x in entry["examples"]),
                    "Mistake": mistake_html(entry.get("mistake")), "Related": inline(entry.get("related", "")),
                    "Origin": inline(entry.get("origin", "")),
                    "Category": escape(category["title"]), "Set": escape(set_label),
                    "ItemID": f"{part['part_id']}:{entry['id']}",
                    "Source": (f"kizamu-english {LEVEL} · {escape(category['title'])} · {escape(set_label)}. "
                               "Written for this deck; audio by Qwen3-TTS (American English voice), "
                               "checked with Whisper."),
                }
                fields.update(drill_fields(entry, media))
                note = col.new_note(model)
                for name, value in fields.items():
                    note[name] = value
                seed = entry["id"] if LEVEL == "C2" else f"{LEVEL}:{entry['id']}"  # C2 kept the pilot's GUIDs
                note.guid = "kzen" + hashlib.sha1(seed.encode()).hexdigest()[:14]
                theme = re.sub(r"[^a-z]+", "-", info["theme"].lower()).strip("-")
                note.tags = sorted({"kizamu_english", category["key"], part["part_id"], f"theme::{theme}",
                                    f"register::{entry['register']}", f"region::{entry['region']}",
                                    f"importance::{info['importance']}"}
                                   | ({"studied_before"} if info["studied_before"] else set()))
                col.add_note(note, did)
                note_ids.append(note.id)
                cards = {card.ord: card for card in note.cards()}
                position = rank[entry["id"]]
                col.db.execute("update cards set due=? where id=?", 2 * position, cards[0].id)
                col.db.execute("update cards set due=? where id=?", 2 * (position + USAGE_DELAY) + 1, cards[1].id)
                if info["studied_before"]:  # same sense as an old studied card (catalogue decides)
                    history.copy({**entry, "term": info["term"]}, cards)
                report["notes"] += 1
                report["cards"] += len(cards)
                report["by_category"][category["key"]] = report["by_category"].get(category["key"], 0) + 1
        # Parent decks use the same options.
        for item in col.decks.all_names_and_ids():
            if item.name == DECK_ROOT or item.name.startswith(DECK_ROOT + "::"):
                deck = col.decks.get(item.id)
                deck["conf"] = CONFIG_ID
                col.decks.update(deck)
        if media.missing and not args.allow_missing_audio:
            raise RuntimeError(f"{len(media.missing)} audio clips missing (run the audio stage first)")
        media_dir = PROFILE / "collection.media"
        for name in sorted(media.used):
            os.link(AUDIO / name, media_dir / name)
        OUT.mkdir(parents=True, exist_ok=True)
        filename = PILOT_PACKAGE if args.pilot else PACKAGE
        options = ExportAnkiPackageOptions(with_scheduling=True, with_media=True, with_deck_configs=True)
        col.export_anki_package(out_path=str((OUT / filename).resolve()), options=options,
                                limit=NoteIdsLimit(note_ids=note_ids))
        print(f"Exported {OUT / filename}", flush=True)
    finally:
        col.close()

    atomic_json(BUILD / "history-mapping.json", history.mapping)
    report.update({
        "package": filename, "parts": len(parts), "audio_clips": len(media.used),
        "audio_missing": len(media.missing), "audio_omitted_after_whisper_check": media.omitted,
        "legacy_cards_with_history": len(history.mapping),
        "review_records_copied": sum(m["reviews"] for m in history.mapping),
        "identity_policy": "new stable GUIDs per catalogue id; old English notes and cards are untouched",
        "history_snapshot": "15 October 2026 collection snapshot",
    })
    atomic_json(OUT / ("build-report-pilot.json" if args.pilot else "build-report.json"), report)
    (OUT / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in sorted(OUT.glob("*.apkg"))))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parts", nargs="*", help="only these parts (default: all)")
    parser.add_argument("--pilot", action="store_true", help="write the pilot package name")
    parser.add_argument("--allow-missing-audio", action="store_true", help="preview builds only")
    parser.add_argument("--allow-partial", action="store_true", help="skip parts without content")
    build(parser.parse_args())
