"""Build an isolated 20-entry vocabulary preview and Anki package.

Preview GUIDs are deliberately separate from the user's original notes. History
migration is validated separately on a temporary database copy.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import zipfile

import chevron
import genanki

from kizamu.paths import DATA

PILOT = DATA / "german" / "vocab" / "pilot"
FIELDS = ["EntryID", "German", "English", "CueDE", "CueEN", "Level", "POS",
          "Grammar", "Meanings", "Related", "Usage", "Examples", "Audio", "Source", "History"]
CSS = """
.card { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 19px; line-height: 1.6; text-align: left; color: #233136;
  background: #f4f3ed; padding: 24px; }
.wrap { max-width: 720px; margin: auto; }
.eyebrow { color: #52746a; font-size: 12px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; margin-bottom: 12px; }
.word { font-size: 34px; font-weight: 650; line-height: 1.25; margin-bottom: 8px; }
.translation { font-size: 23px; color: #47615a; }
.cue { color: #68787a; font-size: 16px; margin-top: 8px; }
.section { margin-top: 22px; padding-top: 16px; border-top: 1px solid #d5ddd5; }
.section h3 { margin: 0 0 8px; font-size: 13px; color: #52746a;
  text-transform: uppercase; letter-spacing: .06em; }
ul { padding-left: 23px; margin: 8px 0; }
li { margin-bottom: 6px; }
.example { margin: 15px 0; }
.example .en { color: #68787a; font-size: 16px; margin-top: 3px; }
audio { display: block; width: 100%; max-width: 350px; height: 34px; margin-top: 8px; }
.source { font-size: 12px; color: #73817b; margin-top: 28px; }
.nightMode.card { background: #1f2926; color: #e8ede8; }
.nightMode .translation, .nightMode .eyebrow, .nightMode .section h3 { color: #a9cbbc; }
.nightMode .cue, .nightMode .example .en, .nightMode .source { color: #bdc8c1; }
@media (max-width: 480px) { .card { padding: 16px; font-size: 17px; } .word { font-size: 29px; } }
"""
FRONT_DE = """<div class="wrap"><div class="eyebrow">{{Level}} · Deutsch → English</div>
<div class="word" lang="de">{{German}}</div>{{#CueDE}}<div class="cue" lang="de">{{CueDE}}</div>{{/CueDE}}
<div class="cue">Give the English meaning.</div></div>"""
FRONT_EN = """<div class="wrap"><div class="eyebrow">{{Level}} · English → Deutsch</div>
<div class="word">{{English}}</div>{{#CueEN}}<div class="cue">{{CueEN}}</div>{{/CueEN}}
<div class="cue">Give the German word, including its article where applicable.</div></div>"""
BACK = """<div class="wrap"><div class="eyebrow">{{Level}} · {{POS}}</div>
<div class="word" lang="de">{{German}}</div><div class="translation">{{English}}</div>{{Audio}}
<div class="section"><h3>Forms & grammar</h3>{{Grammar}}</div>
<div class="section"><h3>Meaning</h3>{{Meanings}}</div>
<div class="section"><h3>Related words & contrasts</h3>{{Related}}</div>
<div class="section"><h3>Usage & common mistakes</h3>{{Usage}}</div>
<div class="section"><h3>Examples · tap to listen</h3>{{Examples}}</div>
<div class="section"><h3>Your previous study history</h3>{{History}}</div>
<div class="source">{{Source}}</div></div>"""


def load_entries():
    entries = json.loads((PILOT / "entries.json").read_text())
    assert len(entries) == 20 and len({e["id"] for e in entries}) == 20
    assert len({e["source_note_id"] for e in entries}) == 20
    for entry in entries:
        assert entry["level"] in {"A1", "A2", "B1"}
        assert len(entry["examples"]) == 3
        assert all(ex["de"].strip() and ex["en"].strip() for ex in entry["examples"])
        assert entry["meanings"] and entry["related"] and entry["grammar"]
    return entries


def audio_manifest(engine):
    path = PILOT / "audio" / engine / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else {}


def field_values(entry, engine, *, preview=False, allow_missing=False):
    manifest = audio_manifest(engine)
    check_path = PILOT / "out" / f"audio-check-{engine}.json"
    audio_checks = json.loads(check_path.read_text()) if check_path.exists() else {}
    media = []

    def sound(slot, *, word=False):
        key = f"{entry['id']}:{slot}"
        record = manifest.get(key)
        if record is None:
            if not allow_missing:
                raise ValueError(f"Missing {engine} audio: {key}")
            return '<div class="cue">Audio not generated for this voice.</div>'
        path = PILOT / "audio" / engine / record["file"]
        if not path.is_file():
            raise ValueError(f"Missing audio file: {path}")
        expected = entry["german"] if slot == "word" else entry["examples"][int(slot[1:])-1]["de"]
        if record["settings"]["text"] != expected:
            raise ValueError(f"Stale audio text for {key}; regenerate it first")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Audio checksum mismatch for {key}")
        media.append(path)
        check = audio_checks.get(key, {})
        warning = ('<div class="cue">Audio flagged for a listening check.</div>'
                   if check.get("sha256") == record["sha256"] and check.get("text_matches") is False else "")
        src = f"audio/{engine}/{path.name}" if preview else path.name
        if word and not preview:
            return f"[sound:{path.name}]" + warning
        label = html.escape(f"Listen in German: {record['settings']['text']}", quote=True)
        return f'<audio controls preload="none" aria-label="{label}" src="{html.escape(src, quote=True)}"></audio>' + warning

    def items(values):
        return "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in values) + "</ul>"

    examples = "".join(
        f'<div class="example"><div lang="de">{html.escape(ex["de"])}</div>'
        f'<div class="en">{html.escape(ex["en"])}</div>{sound(f"s{i}")}</div>'
        for i, ex in enumerate(entry["examples"], 1)
    )
    data = {
        "EntryID": entry["id"], "German": entry["german"], "English": entry["english"],
        "CueDE": entry["cue_de"], "CueEN": entry["cue_en"], "Level": entry["level"],
        "POS": entry["pos"], "Grammar": entry["grammar"], "Usage": entry["usage"],
        "Source": f"Goethe {entry['level']} vocabulary · rewritten pilot explanations and examples · {engine} audio",
    }
    data = {key: html.escape(value) for key, value in data.items()}
    history_path = PILOT / "history.json"
    histories = json.loads(history_path.read_text()) if history_path.exists() else {}
    history = histories.get(entry["id"])
    history_html = "History has not been extracted."
    if history:
        sections = []
        for card in history["cards"]:
            recent = "".join(f'<li>{r["date"]} · {r["rating"]}</li>' for r in card["recent_reviews"])
            sections.append(f'<p><strong>{card["direction"]}</strong>: {card["repetitions"]} repetitions · '
                f'last interval {card["interval_days"]} days · {card["review_log_records"]} history records</p>'
                + (f'<details><summary>Recent reviews</summary><ul>{recent}</ul></details>' if recent else '<p>Not yet studied.</p>'))
        history_html = ''.join(sections) + f'<div class="source">From your 15 October 2026 collection · original note {history["source_note_id"]}. Full review records are preserved in the history package.</div>'
    data.update(Meanings=items(entry["meanings"]), Related=items(entry["related"]),
                Examples=examples, Audio=sound("word", word=True), History=history_html)
    return data, media


def create_model():
    return genanki.Model(
        1947610020, "Goethe vocabulary · isolated pilot",
        fields=[{"name": field} for field in FIELDS],
        templates=[{"name": "DE → EN", "qfmt": FRONT_DE, "afmt": BACK},
                   {"name": "EN → DE", "qfmt": FRONT_EN, "afmt": BACK}], css=CSS)


def render_html(template, data):
    # Anki inserts field HTML verbatim. Chevron defaults to escaping it, so use
    # its raw syntax only for the known, already escaped/sanitized field values.
    raw_template = re.sub(r"\{\{(" + "|".join(FIELDS) + r")\}\}", r"{{{\1}}}", template)
    return chevron.render(raw_template, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["qwen", "chatterbox"], default="qwen")
    parser.add_argument("--allow-missing-audio", action="store_true", help="Content preview only")
    args = parser.parse_args()
    entries = load_entries()
    output = PILOT / "out"
    output.mkdir(exist_ok=True)
    model = create_model()
    decks = {level: genanki.Deck(1947610100+i, f"Goethe · 20-entry pilot::{level}")
             for i, level in enumerate(["A1", "A2", "B1"])}
    media = []
    for entry in entries:
        data, files = field_values(entry, args.engine, allow_missing=args.allow_missing_audio)
        media.extend(files)
        note = genanki.Note(model=model, fields=[data[f] for f in FIELDS],
            guid=genanki.guid_for("goethe-isolated-pilot-v1", entry["id"]),
            tags=["goethe-pilot", entry["level"].lower(), entry["id"]])
        decks[entry["level"]].add_note(note)
    package_path = output / f"Goethe-20-entry-pilot-{args.engine}.apkg"
    genanki.Package(list(decks.values()), media_files=[str(p) for p in sorted(set(media))]).write_to_file(package_path)

    rendered = []
    for entry in entries:
        variants = {}
        for engine in ["qwen", "chatterbox"]:
            data, _ = field_values(entry, engine, preview=True, allow_missing=True)
            variants[engine] = {
                "frontDE": render_html(FRONT_DE, data), "frontEN": render_html(FRONT_EN, data),
                "back": render_html(BACK, data)}
        rendered.append({"id": entry["id"], "label": entry["german"] + (f" · {entry['cue_de']}" if entry["cue_de"] else ""),
                         "level": entry["level"], "variants": variants})
    payload = json.dumps(rendered, ensure_ascii=False).replace("<", "\\u003c")
    preview = PREVIEW.replace("__CSS__", CSS).replace("__ENTRIES__", payload)
    (PILOT / "preview.html").write_text(preview)
    with zipfile.ZipFile(output / "Goethe-pilot-preview.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(PILOT / "preview.html", "preview.html")
        for engine in ["qwen", "chatterbox"]:
            for name in sorted({record["file"] for record in audio_manifest(engine).values()}):
                path = PILOT / "audio" / engine / name
                z.write(path, f"audio/{engine}/{path.name}")
    print(f"Built 20 notes / 40 cards / {len(set(media))} audio files: {package_path}")
    print(f"Preview: {PILOT / 'preview.html'}")


PREVIEW = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Goethe vocabulary · 20-entry pilot</title>
<style>__CSS__
*{box-sizing:border-box} body{margin:0;background:#f4f3ed;color:#233136;font-family:system-ui,sans-serif}
header,nav,main,footer{max-width:850px;margin:auto;padding:20px 28px} header{padding-top:38px}
h1{font-size:27px;line-height:1.25;margin:5px 0 12px} header p,footer{color:#68787a;font-size:14px;line-height:1.6}
nav{display:flex;gap:12px;flex-wrap:wrap;padding-top:4px;padding-bottom:12px}
label{font-size:12px;color:#52746a;display:flex;flex-direction:column;gap:5px}
select,button{font:inherit;border:1px solid #bdcec2;border-radius:8px;padding:10px 12px;background:white;color:#233136}
select{max-width:100%}#entry{width:280px}.panel{background:#fffefa;border:1px solid #dce2d9;border-radius:16px;min-height:240px;padding:28px}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}#reveal{background:#285b49;color:white;border-color:#285b49}
button{cursor:pointer}button:focus-visible,select:focus-visible{outline:3px solid #cba64d;outline-offset:2px}
button:disabled{opacity:.45;cursor:default}.pill{font-size:12px;letter-spacing:.08em;color:#52746a;text-transform:uppercase}
@media(max-width:480px){header,nav,main,footer{padding-left:16px;padding-right:16px}.panel{padding:20px}#entry{width:100%}}
</style></head><body>
<header><div class="pill">Goethe vocabulary · pilot</div><h1>Twenty entries. More useful answers.</h1>
<p>Two translation directions, clear forms, useful contrasts, and three examples per entry. Choose a voice to compare the same German text. All audio is generated locally.</p></header>
<nav aria-label="Preview controls">
<label>Entry<select id="entry"></select></label>
<label>Direction<select id="direction"><option value="frontDE">Deutsch → English</option><option value="frontEN">English → Deutsch</option></select></label>
<label>Audio model<select id="engine"><option value="qwen">Qwen3-TTS · German voice design</option><option value="chatterbox">Chatterbox v3 · Thorsten reference</option></select></label></nav>
<main><div id="position" class="pill" style="margin-bottom:12px"></div>
<article id="card" class="panel card" aria-live="polite"></article>
<div class="actions"><button id="previous" type="button">← Previous</button><button id="reveal" type="button">Reveal answer</button><button id="next" type="button">Next →</button></div></main>
<footer>History shown here comes from your old collection. The history-preserving Anki package also carries the original cards and full review records; the isolated preview packages use separate test cards. Audio naturalness review is pending your listening feedback.</footer>
<script>const entries=__ENTRIES__;
const entry=document.getElementById('entry'),direction=document.getElementById('direction'),engine=document.getElementById('engine'),card=document.getElementById('card');let revealed=false;
entries.forEach((e,i)=>{const option=document.createElement('option');option.value=i;option.textContent=e.level+' · '+e.label;entry.append(option)});
function draw(){const i=Number(entry.value),e=entries[i];card.innerHTML=e.variants[engine.value][revealed?'back':direction.value];document.getElementById('position').textContent=(i+1)+' / '+entries.length+' · '+(revealed?'Answer':'Prompt');document.getElementById('reveal').textContent=revealed?'Show prompt':'Reveal answer';document.getElementById('previous').disabled=i===0;document.getElementById('next').disabled=i===entries.length-1;}
entry.addEventListener('change',()=>{revealed=false;draw()});direction.addEventListener('change',()=>{revealed=false;draw()});engine.addEventListener('change',draw);
document.getElementById('reveal').onclick=()=>{revealed=!revealed;draw()};
document.getElementById('previous').onclick=()=>{entry.value=Number(entry.value)-1;revealed=false;draw()};
document.getElementById('next').onclick=()=>{entry.value=Number(entry.value)+1;revealed=false;draw()};draw();
</script></body></html>"""


if __name__ == "__main__":
    main()
