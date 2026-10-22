"""Build the kizamu-german grammar + sentences packages with copied review history.

Side-by-side, like german/vocab/build.py: every note gets a new GUID,
note ID and card IDs, so nothing in the package can overwrite the legacy
`00 - German - grammar` notes. When a new card replaces a legacy card that was
studied, the legacy card's schedule, FSRS state and review records (with new,
collision-free IDs) are copied onto the new card.

    python -m german.grammar.build
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import markdown as md
from anki.collection import Collection, NoteIdsLimit
from anki.import_export_pb2 import ExportAnkiPackageOptions

from german.grammar.audio import AUDIO, MANIFEST, file_for
from german.grammar.common import (
    BUILD, DECK_ROOT, HARD, LEGACY_DECK_PREFIX, OUT, SNAPSHOT, atomic_json,
    auxiliary, load_content, strip_cloze, verb_forms_text,
)
from kizamu.paths import DATA

PROFILE = BUILD / "profile"
VOCAB_PROFILE = DATA / "german" / "vocab" / "build" / "side-by-side-profile" / "collection.anki2"
PACKAGES = {"grammar": "kizamu-german-grammar-WITH-HISTORY.apkg",
            "sentences": "kizamu-german-sentences-WITH-HISTORY.apkg"}
CONFIG_NAME = "kizamu-german · grammar"
KIZAMU = ('Continue learning with <a href="https://kizamu.app/">Kizamu</a>, '
          'an AI-enabled German learning app.')
DRILL_LABELS = {"concept": "Rule check", "transform": "Transform", "error": "Find the mistake",
                "order": "Word order", "choice": "Choose the form", "combine": "Join the sentences"}

CSS = """
.card { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 19px; line-height: 1.6; text-align: left; color: #233136;
  background: #f4f3ed; padding: 24px; }
.wrap { max-width: 720px; margin: auto; }
.eyebrow { color: #52746a; font-size: 12px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; margin-bottom: 12px; }
.word { font-size: 34px; font-weight: 650; line-height: 1.25; margin-bottom: 8px; }
.prompt { font-size: 27px; font-weight: 600; line-height: 1.4; margin: 6px 0 10px; }
.question { font-size: 22px; font-weight: 600; line-height: 1.45; margin: 6px 0 10px; }
.translation { font-size: 20px; color: #47615a; }
.instruction { font-size: 16px; color: #47615a; font-weight: 600; margin-bottom: 4px; }
.cue { color: #68787a; font-size: 16px; margin-top: 8px; }
.cloze { color: #1d6b52; font-weight: 700; }
.answer { font-size: 25px; font-weight: 650; line-height: 1.4; color: #1d6b52; margin: 4px 0 6px; }
.answer.en { color: #233136; font-size: 20px; font-weight: 500; }
.fix { background: #d9eee3; border-radius: 4px; padding: 0 3px; }
.chip { display: inline-block; border: 1px solid #b8c9be; border-radius: 999px; padding: 2px 12px;
  margin: 4px 6px 4px 0; background: #fffefa; font-size: 19px; }
.chip.correct { border-color: #1d6b52; background: #d9eee3; font-weight: 650; }
.section { margin-top: 22px; padding-top: 16px; border-top: 1px solid #d5ddd5; }
.section h3 { margin: 0 0 8px; font-size: 13px; color: #52746a;
  text-transform: uppercase; letter-spacing: .06em; }
.pattern { display: inline-block; margin-top: 10px; padding: 4px 10px; border-radius: 6px;
  background: #e6ece6; font-size: 16px; }
.wrong { color: #9b3b2f; text-decoration: line-through; text-decoration-thickness: 1px; }
.wrong::before { content: "✗ "; text-decoration: none; display: inline-block; }
.why { font-size: 17px; margin-top: 4px; }
ul, ol { padding-left: 23px; margin: 8px 0; }
li { margin-bottom: 6px; }
.example { margin: 15px 0; }
.example .en, .en { color: #68787a; font-size: 16px; margin-top: 3px; }
table { border-collapse: collapse; margin: 10px 0; font-size: 16px; }
td, th { border: 1px solid #ccd6ce; padding: 4px 9px; text-align: left; vertical-align: top; }
th { background: #e6ece6; }
.forms td:first-child { color: #52746a; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; }
.forms td { border: none; border-bottom: 1px solid #d5ddd5; padding: 6px 12px 6px 0; font-size: 19px; }
details summary { cursor: pointer; color: #52746a; font-weight: 600; font-size: 15px; }
audio { display: block; width: 100%; max-width: 350px; height: 34px; margin-top: 8px; }
.source { font-size: 12px; color: #73817b; margin-top: 28px; }
.nightMode.card { background: #1f2926; color: #e8ede8; }
.nightMode .translation, .nightMode .eyebrow, .nightMode .section h3, .nightMode .instruction,
.nightMode details summary, .nightMode .forms td:first-child { color: #a9cbbc; }
.nightMode .cue, .nightMode .example .en, .nightMode .en, .nightMode .source { color: #bdc8c1; }
.nightMode .cloze, .nightMode .answer { color: #8fd8b5; }
.nightMode .answer.en { color: #e8ede8; }
.nightMode .chip { background: #27332f; border-color: #4b5f57; }
.nightMode .chip.correct, .nightMode .fix { background: #2f5244; border-color: #8fd8b5; }
.nightMode .pattern, .nightMode th { background: #2b3934; }
.nightMode td, .nightMode th { border-color: #3d4d47; }
.nightMode .wrong { color: #f0a597; }
@media (max-width: 480px) { .card { padding: 16px; font-size: 17px; } .prompt { font-size: 23px; }
  .word { font-size: 29px; } .answer { font-size: 22px; } }
"""

SOURCE_BLOCK = '<div class="source">{{Source}}</div>'
RULE_BLOCK = ('{{#Rule}}<div class="section"><details><summary>Rule · {{Topic}}</summary>'
              '{{Rule}}</details></div>{{/Rule}}')

CLOZE_FRONT = """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · Fill the gap</div>
<div class="prompt" lang="de">{{cloze:Text}}</div><div class="translation">{{English}}</div>
{{#Focus}}<div class="cue">Focus: {{Focus}}</div>{{/Focus}}</div>"""
CLOZE_BACK = """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · Fill the gap</div>
<div class="prompt" lang="de">{{cloze:Text}}</div><div class="translation">{{English}}</div>{{Audio}}
<div class="section"><h3>Why this form</h3>{{Explanation}}{{#Pattern}}<div class="pattern">{{Pattern}}</div>{{/Pattern}}</div>
{{#Mistake}}<div class="section"><h3>Common mistake</h3>{{Mistake}}</div>{{/Mistake}}
<div class="section"><h3>More examples</h3>{{Examples}}</div>
{{#Words}}<div class="section"><h3>Words</h3>{{Words}}</div>{{/Words}}
""" + RULE_BLOCK + SOURCE_BLOCK + "</div>"

DRILL_FRONT = """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · {{DrillType}}</div>
<div class="instruction">{{Instruction}}</div>{{Prompt}}{{#Options}}<div>{{Options}}</div>{{/Options}}</div>"""
DRILL_BACK = """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · {{DrillType}}</div>
<div class="instruction">{{Instruction}}</div>{{Prompt}}{{#Options}}<div>{{Options}}</div>{{/Options}}
<div class="section"><h3>Answer</h3>{{Answer}}{{Audio}}</div>
<div class="section"><h3>Explanation</h3>{{Explanation}}</div>
{{#Examples}}<div class="section"><h3>Examples</h3>{{Examples}}</div>{{/Examples}}
""" + RULE_BLOCK + SOURCE_BLOCK + "</div>"

SENTENCE_BACK = """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}}</div>
<div class="prompt" lang="de">{{German}}</div><div class="translation">{{English}}</div>{{Audio}}
{{#Grammar}}<div class="section"><h3>Grammar in this sentence</h3>{{Grammar}}</div>{{/Grammar}}
{{#Notes}}<div class="section"><h3>Usage</h3>{{Notes}}</div>{{/Notes}}
{{#Words}}<div class="section"><h3>Words</h3>{{Words}}</div>{{/Words}}
""" + SOURCE_BLOCK + "</div>"
SENTENCE_TEMPLATES = [
    ("English → Deutsch", """<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · English → Deutsch</div>
<div class="question">{{English}}</div>{{#Cue}}<div class="cue">{{Cue}}</div>{{/Cue}}
<div class="cue">Say it in German.</div></div>"""),
    ("Listen", """{{#Listen}}<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · Listening</div>
{{Audio}}<div class="cue">Listen. Repeat it aloud, then say what it means.</div></div>{{/Listen}}"""),
    ("Deutsch → English", """{{#Read}}<div class="wrap"><div class="eyebrow">{{Level}} · {{Topic}} · Deutsch → English</div>
<div class="prompt" lang="de">{{German}}</div><div class="cue">What does it mean, and when do you use it?</div></div>{{/Read}}"""),
]

VERB_FRONT = """<div class="wrap"><div class="eyebrow">{{Level}} · Unregelmäßige Verben</div>
<div class="word" lang="de">{{Infinitiv}}</div><div class="translation">{{Meaning}}</div>{{AudioInf}}
<div class="cue">Give the Präsens (er/sie/es), Präteritum and Perfekt.</div></div>"""
VERB_BACK = """<div class="wrap"><div class="eyebrow">{{Level}} · Unregelmäßige Verben</div>
<div class="word" lang="de">{{Infinitiv}}</div><div class="translation">{{Meaning}}</div>
<table class="forms"><tr><td>Präsens</td><td lang="de">{{Praesens}}</td></tr>
<tr><td>Präteritum</td><td lang="de"><b>{{Praeteritum}}</b></td></tr>
<tr><td>Perfekt</td><td lang="de"><b>{{Perfekt}}</b></td></tr>
<tr><td>Konjunktiv II</td><td lang="de">{{Konjunktiv2}}</td></tr>
<tr><td>Imperativ</td><td lang="de">{{Imperativ}}</td></tr></table>{{AudioForms}}
{{#Note}}<div class="section"><h3>Notes</h3>{{Note}}</div>{{/Note}}
<div class="section"><h3>Examples</h3>{{Examples}}</div>""" + SOURCE_BLOCK + "</div>"

MODELS = {
    "cloze": ("kizamu-german · grammar cloze",
              ["Text", "English", "Focus", "Explanation", "Pattern", "Mistake", "Examples", "Words",
               "Rule", "Audio", "Level", "Topic", "ItemID", "Source"],
              [("Fill the gap", CLOZE_FRONT, CLOZE_BACK)]),
    "drill": ("kizamu-german · grammar drill",
              ["ItemID", "DrillType", "Instruction", "Prompt", "Options", "Answer", "Audio",
               "Explanation", "Examples", "Rule", "Level", "Topic", "Source"],
              [("Drill", DRILL_FRONT, DRILL_BACK)]),
    "sentence": ("kizamu-german · sentence",
                 ["German", "English", "Cue", "Audio", "Grammar", "Notes", "Words", "Level", "Topic",
                  "ItemID", "Source", "Listen", "Read"],
                 [(name, front, SENTENCE_BACK) for name, front in SENTENCE_TEMPLATES]),
    "verb": ("kizamu-german · verb",
             ["Infinitiv", "Meaning", "Praesens", "Praeteritum", "Perfekt", "Konjunktiv2", "Imperativ",
              "Note", "Examples", "AudioInf", "AudioForms", "Level", "ItemID", "Source"],
             [("Forms", VERB_FRONT, VERB_BACK)]),
}


# ---------------------------------------------------------------- rendering

def inline(text: str) -> str:
    rendered = md.markdown(html.escape(text, quote=False))
    return re.sub(r"^<p>(.*)</p>$", r"\1", rendered.strip(), flags=re.DOTALL)


def block(text: str) -> str:
    return md.markdown(html.escape(text, quote=False), extensions=["tables"]) if text.strip() else ""


def escape(text: str) -> str:
    return html.escape(text, quote=False)


class Media:
    def __init__(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        self.by_file = {record["file"]: record for record in self.manifest.values()}
        self.used: set[str] = set()
        self.missing: list[str] = []

    def sound(self, text: str) -> str:
        name = file_for(text)
        if name not in self.by_file or not (AUDIO / name).exists():
            self.missing.append(text)
            return ""
        self.used.add(name)
        return f"[sound:{name}]"


def examples_html(pairs: list[dict], media: Media) -> str:
    return "".join(
        f'<div class="example"><div lang="de">{escape(x["de"])}</div>'
        f'<div class="en">{escape(x["en"])}</div>{media.sound(x["de"])}</div>' for x in pairs)


def words_html(words: list[dict]) -> str:
    if not words:
        return ""
    return "<ul>" + "".join(f'<li><b lang="de">{escape(w["de"])}</b> — {escape(w["en"])}</li>' for w in words) + "</ul>"


def rule_html(data: dict) -> str:
    rule = data["rule"]
    parts = [f"<p>{inline(rule['summary'])}</p>", block(rule.get("table", ""))]
    if rule.get("steps"):
        parts.append("<p><b>How to build it</b></p><ol>" + "".join(f"<li>{inline(s)}</li>" for s in rule["steps"]) + "</ol>")
    if rule.get("pitfalls"):
        parts.append("<p><b>Watch out</b></p><ul>" + "".join(f"<li>{inline(s)}</li>" for s in rule["pitfalls"]) + "</ul>")
    return "".join(parts)


def marked_answer(prompt: str, answer: str) -> str:
    """Highlight the words that changed from the faulty prompt to the answer."""
    before, after = prompt.split(), answer.split()
    out = []
    for op, _, _, j1, j2 in difflib.SequenceMatcher(a=before, b=after).get_opcodes():
        chunk = escape(" ".join(after[j1:j2]))
        if chunk:
            out.append(chunk if op == "equal" else f'<span class="fix">{chunk}</span>')
    return " ".join(out)


def cloze_text(text: str) -> str:
    # Escape everything except the cloze markup itself.
    return escape(text)


# ---------------------------------------------------------------- legacy history

class History:
    """Copies legacy schedules and review records onto new cards."""

    def __init__(self, col: Collection) -> None:
        self.col = col
        self.legacy = json.loads((BUILD / "legacy.json").read_text())
        self.by_slot = {(r["kind"], r["topic"], r["index"]): r for r in self.legacy.values()}
        self.columns = [row[1] for row in col.db.execute("pragma table_info(cards)")
                        if row[1] not in {"id", "nid", "did", "ord", "mod", "usn"}]
        self.used = {row[0] for row in col.db.execute("select id from revlog")}
        if VOCAB_PROFILE.exists():
            # The kizamu vocab clones' review IDs may already be in the real collection.
            vocab = sqlite3.connect(f"file:{VOCAB_PROFILE}?mode=ro", uri=True)
            self.used |= {row[0] for row in vocab.execute("select id from revlog")}
            vocab.close()
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

    def copy(self, kind: str, topic: str, index, ord_: int, card, item_id: str) -> None:
        record = self.by_slot.get((kind, topic, index))
        if record is None:
            raise KeyError(f"No legacy note for {kind} {topic} {index}")
        source = next((c for c in record["cards"] if c["ord"] == ord_), None)
        if source is None:
            raise KeyError(f"No legacy card ord {ord_} for {kind} {topic} {index}")
        if source["id"] in self.claimed:
            raise ValueError(f"Legacy card {source['id']} mapped twice")
        self.claimed.add(source["id"])
        entry = {"item": item_id, "legacy_card": source["id"], "new_card": card.id, "reviews": 0}
        studied = source["reps"] > 0 or source["type"] > 0 or source["revlog"] > 0
        if studied:
            values = self.col.db.first(f"select {','.join(self.columns)} from cards where id=?", source["id"])
            assignments = ",".join(f"{name}=?" for name in self.columns)
            self.col.db.execute(f"update cards set {assignments} where id=?", *values, card.id)
            rows = list(self.col.db.execute(
                "select id,ease,ivl,lastIvl,factor,time,type from revlog where cid=? order by id", source["id"]))
            for row in rows:
                self.col.db.execute(
                    "insert into revlog(id,cid,usn,ease,ivl,lastIvl,factor,time,type) values(?,?,?,?,?,?,?,?,?)",
                    self.next_id(row[0]), card.id, -1, *row[1:])
            entry["reviews"] = len(rows)
        entry["studied"] = studied
        self.mapping.append(entry)


# ---------------------------------------------------------------- build

def ensure_models(col: Collection) -> dict[str, dict]:
    models = {}
    for key, (name, fields, templates) in MODELS.items():
        if col.models.by_name(name):
            raise RuntimeError(f"Note type {name!r} already exists in the build profile")
        model = col.models.new(name)
        if key == "cloze":
            model["type"] = 1  # MODEL_CLOZE
        for field in fields:
            col.models.add_field(model, col.models.new_field(field))
        for template_name, front, back in templates:
            template = col.models.new_template(template_name)
            template["qfmt"], template["afmt"] = front, back
            col.models.add_template(model, template)
        model["css"] = CSS
        model["sortf"] = 0
        col.models.add(model)
        models[key] = col.models.by_name(name)
    return models


def deck_config(col: Collection) -> dict:
    legacy_deck = next(d for d in col.decks.all_names_and_ids() if d.name.startswith(f"{LEGACY_DECK_PREFIX}::A1::"))
    source = col.decks.config_dict_for_deck_id(legacy_deck.id)
    config = col.decks.add_config(CONFIG_NAME, clone_from=source)
    config["autoplay"] = True
    config["replayq"] = False
    col.decks.update_config(config)
    return config


def topic_label(data: dict) -> str:
    return data["title_de"]


def build(args) -> dict:
    content = load_content()
    media = Media()
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    (PROFILE / "collection.media").mkdir(parents=True)
    with sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True) as src, \
            sqlite3.connect(PROFILE / "collection.anki2") as dst:
        src.backup(dst)
    col = Collection(str((PROFILE / "collection.anki2").resolve()))
    report = {"notes": {}, "cards": {}}
    note_ids = {"grammar": [], "sentences": []}
    try:
        models = ensure_models(col)
        config = deck_config(col)
        history = History(col)

        def deck(path: str) -> int:
            did = col.decks.id(f"{DECK_ROOT}::{path}")
            item = col.decks.get(did)
            item["conf"] = config["id"]
            col.decks.update(item)
            return did

        def add(model_key: str, fields: dict, did: int, tags: list[str], package: str):
            note = col.new_note(models[model_key])
            for name, value in fields.items():
                note[name] = value
            note.tags = sorted(set(["kizamu_german", f"kizamu_{package}"] + tags))
            col.add_note(note, did)
            note_ids[package].append(note.id)
            report["notes"][model_key] = report["notes"].get(model_key, 0) + 1
            report["cards"][model_key] = report["cards"].get(model_key, 0) + len(note.cards())
            return note

        topics = [d for d in content.values() if "items" in d]
        topics.sort(key=lambda d: (d["topic_id"].startswith("h"), d["topic_id"]))
        for data in topics:
            tid = data["topic_id"]
            hard = tid.startswith("h")
            number = tid.split("-")[0][1:] if hard else tid.split("-")[1]
            group = HARD if hard else data["level"]
            name = f"{number} {data['title_de']}"
            grammar_deck = deck(f"grammar::{group}::{name}")
            sentence_deck = deck(f"sentences::{group}::{name}")
            level, topic, rule = escape(data["level"]), escape(topic_label(data)), rule_html(data)
            base_tags = [data["level"].replace("+", "plus").lower(), tid, "hard_grammar" if hard else "core_grammar"]
            source_line = f"kizamu-german grammar · {escape(data['level'])} · {topic}. "

            def drill_note(drill: dict) -> None:
                kind = drill["type"]
                if kind == "concept":
                    prompt = f'<div class="question">{inline(drill["prompt"])}</div>'
                    answer = f'<div class="answer en">{inline(drill["answer"])}</div>'
                    audio, examples = "", examples_html(drill["examples"], media)
                else:
                    if kind == "order":
                        prompt = "<div>" + "".join(f'<span class="chip" lang="de">{escape(p)}</span>'
                                                   for p in drill["prompt"].split(" / ")) + "</div>"
                    else:
                        prompt = f'<div class="prompt" lang="de">{escape(drill["prompt"])}</div>'
                    shown = marked_answer(drill["prompt"], drill["answer"]) if kind == "error" else escape(drill["answer"])
                    answer = f'<div class="answer" lang="de">{shown}</div>'
                    audio, examples = media.sound(drill["answer"]), examples_html(drill.get("examples", []), media)
                options = ""
                if kind == "choice":
                    options = "".join(f'<span class="chip" lang="de">{escape(o)}</span>' for o in drill["options"])
                    answer = (f'<div><span class="chip correct" lang="de">{escape(drill["correct"])}</span></div>' + answer)
                add("drill", {
                    "ItemID": f"{tid}:{drill['key']}", "DrillType": DRILL_LABELS[kind],
                    "Instruction": inline(drill["instruction"]), "Prompt": prompt, "Options": options,
                    "Answer": answer, "Audio": audio, "Explanation": inline(drill["explanation"]),
                    "Examples": examples, "Rule": rule, "Level": level, "Topic": topic,
                    "Source": source_line + "Drill written for this deck. " + KIZAMU,
                }, grammar_deck, base_tags + ["drill", f"drill_{kind}"], "grammar")

            drills = data["drills"]
            for drill in (d for d in drills if d["type"] == "concept"):
                drill_note(drill)

            items = sorted(data["items"], key=lambda i: ({"g": 0, "n": 1, "r": 2}[i["key"][0]], i["key"]))
            for item in items:
                key = item["key"]
                plain = strip_cloze(item["de"])
                sound = media.sound(plain)
                explanation = inline(item["explanation"])
                mistake = item.get("mistake") or {}
                origin = {"g": "Sentence from your earlier grammar deck, rewritten with a new explanation. ",
                          "r": "Sentence from your earlier review deck, rewritten with a new explanation. ",
                          "n": "New sentence written for this deck. "}[key[0]]
                note = add("cloze", {
                    "Text": cloze_text(item["de"]), "English": escape(item["en"]),
                    "Focus": inline(item["focus"]), "Explanation": explanation,
                    "Pattern": inline(item.get("pattern", "")),
                    "Mistake": (f'<div class="wrong" lang="de">{escape(mistake["wrong"])}</div>'
                                f'<div class="why">{inline(mistake["why"])}</div>') if mistake else "",
                    "Examples": examples_html(item["examples"], media), "Words": words_html(item.get("words", [])),
                    "Rule": rule, "Audio": sound, "Level": level, "Topic": topic,
                    "ItemID": f"{tid}:{key}", "Source": source_line + origin + KIZAMU,
                }, grammar_deck, base_tags + ["cloze", "legacy" if key[0] in "gr" else "new"], "grammar")
                if key[0] in "gr":
                    kind = "cloze" if key[0] == "g" else "review"
                    for card in note.cards():
                        history.copy(kind, tid, int(key[1:]), card.ord, card, f"{tid}:{key}")
                if item.get("sentence_card"):
                    grammar_note = explanation + (f'<div class="pattern">{inline(item["pattern"])}</div>'
                                                  if item.get("pattern") else "")
                    sentence = add("sentence", {
                        "German": escape(plain), "English": escape(item["en"]),
                        "Cue": escape(item.get("production_cue", "")), "Audio": sound,
                        "Grammar": grammar_note, "Notes": "", "Words": words_html(item.get("words", [])),
                        "Level": level, "Topic": topic, "ItemID": f"{tid}:{key}",
                        "Source": source_line + origin + KIZAMU, "Listen": "1", "Read": "",
                    }, sentence_deck, base_tags + ["sentence", "legacy" if key[0] == "g" else "new"], "sentences")
                    if key[0] == "g":
                        cards = {card.ord: card for card in sentence.cards()}
                        history.copy("prod", tid, int(key[1:]), 0, cards[0], f"{tid}:{key}:en-de")
                        history.copy("listen", tid, int(key[1:]), 0, cards[1], f"{tid}:{key}:listen")

            for drill in (d for d in drills if d["type"] != "concept"):
                drill_note(drill)

        for data in sorted((d for d in content.values() if "phrases" in d), key=lambda d: d["topic_id"]):
            tid = data["topic_id"]
            did = deck(f"sentences::Themen::{data['title_de']}")
            intro = inline(data["intro"])
            for phrase in data["phrases"]:
                key = phrase["key"]
                notes = f"<p>{inline(phrase['usage'])}</p>"
                if phrase.get("alternatives"):
                    notes += "<p><b>Also possible</b></p>" + examples_html(phrase["alternatives"], media)
                note = add("sentence", {
                    "German": escape(phrase["de"]), "English": escape(phrase["en"]), "Cue": "",
                    "Audio": media.sound(phrase["de"]), "Grammar": inline(phrase["grammar"]), "Notes": notes,
                    "Words": words_html(phrase.get("words", [])), "Level": escape(data["level"]),
                    "Topic": escape(data["title_en"]), "ItemID": f"{tid}:{key}",
                    "Source": f"kizamu-german Themen · {escape(data['title_en'])}. {intro} " + KIZAMU,
                    "Listen": "", "Read": "1",
                }, did, ["themen", tid, "legacy" if key[0] == "t" else "new"], "sentences")
                if key[0] == "t":
                    cards = {card.ord: card for card in note.cards()}
                    history.copy("prod", tid, int(key[1:]), 0, cards[0], f"{tid}:{key}:en-de")
                    history.copy("de2en", tid, int(key[1:]), 0, cards[2], f"{tid}:{key}:de-en")

        verbs = content.get("verbs")
        if verbs:
            did = deck("grammar::Verben::Unregelmäßig")
            for verb in verbs["verbs"]:
                note = add("verb", {
                    "Infinitiv": escape(verb["infinitiv"]), "Meaning": escape(verb["meaning"]),
                    "Praesens": escape(verb["praesens"]), "Praeteritum": escape(verb["praeteritum"]),
                    "Perfekt": escape(f"{auxiliary(verb['hilfsverb'])} {verb['partizip2']}"),
                    "Konjunktiv2": escape(verb["konjunktiv2"]), "Imperativ": escape(verb["imperativ"]),
                    "Note": inline(verb.get("note", "")), "Examples": examples_html(verb["examples"], media),
                    "AudioInf": media.sound(verb["infinitiv"]), "AudioForms": media.sound(verb_forms_text(verb)),
                    "Level": "A1–B2", "ItemID": f"verbs:{verb['key']}",
                    "Source": "kizamu-german · irregular verbs. " + KIZAMU,
                }, did, ["verbs", "new" if verb.get("new") else "legacy"], "grammar")
                if not verb.get("new"):
                    history.copy("verb", "verbs", verb["key"], 0, note.cards()[0], f"verbs:{verb['key']}")

        # Parent decks (kizamu-german::grammar, ::grammar::A1 …) use the same options.
        # The kizamu-german root is shared with the vocab decks and is left alone.
        for item in col.decks.all_names_and_ids():
            if item.name.startswith((f"{DECK_ROOT}::grammar", f"{DECK_ROOT}::sentences")):
                parent = col.decks.get(item.id)
                parent["conf"] = config["id"]
                col.decks.update(parent)

        unclaimed = [r for r in history.legacy.values() for c in r["cards"] if c["id"] not in history.claimed]
        if unclaimed and not args.allow_partial:
            raise RuntimeError(f"{len(unclaimed)} legacy cards have no replacement card")
        if media.missing and not args.allow_missing_audio:
            raise RuntimeError(f"{len(media.missing)} audio clips missing (run the audio stage first)")

        media_dir = PROFILE / "collection.media"
        for name in sorted(media.used):
            os.link(AUDIO / name, media_dir / name)
        OUT.mkdir(parents=True, exist_ok=True)
        options = ExportAnkiPackageOptions(with_scheduling=True, with_media=True, with_deck_configs=True)
        for package, filename in PACKAGES.items():
            col.export_anki_package(out_path=str((OUT / filename).resolve()), options=options,
                                    limit=NoteIdsLimit(note_ids=note_ids[package]))
            print(f"Exported {OUT / filename}", flush=True)
    finally:
        col.close()

    atomic_json(BUILD / "history-mapping.json", history.mapping)
    report.update({
        "packages": PACKAGES, "deck_root": DECK_ROOT,
        "legacy_cards_replaced": len(history.claimed),
        "legacy_cards_with_history": sum(m["studied"] for m in history.mapping),
        "review_records_copied": sum(m["reviews"] for m in history.mapping),
        "audio_clips": len(media.used), "audio_missing": len(media.missing),
        "identity_policy": "new GUIDs, note IDs and card IDs; legacy notes and cards are untouched",
        "history_policy": "studied legacy cards: schedule, FSRS state and review records copied to the replacement card",
        "history_snapshot": "15 October 2026 collection snapshot",
    })
    atomic_json(OUT / "build-report.json", report)
    (OUT / "IMPORT.md").write_text(IMPORT_INSTRUCTIONS)
    (OUT / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}\n" for name in PACKAGES.values()))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


IMPORT_INSTRUCTIONS = """# Import into your existing Anki profile

These packages use new note and card identities. They do not update, move, suspend
or delete your old `00 - German - grammar` cards. Where a new card replaces an old
card you studied, the old card's schedule, FSRS state and review records (from the
15 October 2026 collection snapshot) are copied onto the new card.

1. Make a full Anki backup and sync all devices.
2. File → Import `kizamu-german-grammar-WITH-HISTORY.apkg`, then
   `kizamu-german-sentences-WITH-HISTORY.apkg`.
3. In the import dialog ENABLE **Import any learning progress** and
   **Import any deck presets**.
4. The new decks are under `kizamu-german::grammar` and `kizamu-german::sentences`,
   with the preset `kizamu-german · grammar` (a copy of your old grammar preset,
   with audio autoplay on).
5. Open Card Info on a few cards from A1/A2 topics and check the dated review records.
6. When you are happy, suspend or delete the old `00 - German - grammar` decks,
   or you will review the same sentences twice.

Reviews you made on the old cards after 15 October 2026 are not in these packages.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing-audio", action="store_true", help="preview builds only")
    parser.add_argument("--allow-partial", action="store_true", help="preview builds with incomplete content")
    build(parser.parse_args())
