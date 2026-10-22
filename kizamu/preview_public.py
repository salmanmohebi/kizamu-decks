"""Preview pages for the shareable packages: sample cards with their real audio.

Reads the packages in $KIZAMU_DATA/public/ (see export_public.py), picks a few notes
from every deck group, renders both sides of each card with Anki's own renderer and
embeds the clips (base64 MP3). Writes one self-contained page per package and an
index page.

    python -m kizamu.preview_public --out <folder>
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import random
import re
import tempfile
from pathlib import Path

from anki.collection import Collection, ImportAnkiPackageOptions, ImportAnkiPackageRequest

from kizamu.paths import DATA

SOURCE = DATA / "public"
# Package → (page title, one-line description). Order = order on the index page.
PACKAGES = {
    "kizamu-german-vocab-A1": ("German vocabulary · A1", "Words both ways, with forms, usage and three examples."),
    "kizamu-german-vocab-A2": ("German vocabulary · A2", "Words both ways, with forms, usage and three examples."),
    "kizamu-german-vocab-B1": ("German vocabulary · B1", "Words both ways, with forms, usage and three examples."),
    "kizamu-german-grammar": ("German grammar · A1–C1", "Fill-the-gap and drills, an explanation on every card."),
    "kizamu-german-sentences": ("German sentences", "English → Deutsch, listening and situational phrases."),
    "kizamu-english-C1": ("American English · C1", "Collocations, phrasal verbs, idioms, conversation and more."),
    "kizamu-english-C2": ("American English · C2", "The advanced, native-like layer. No item repeats C1."),
}
TARGET_NOTES = 40

STYLE = """:root{--bg:#e8ebee;--panel:#f3f4f1;--ink:#22303c;--muted:#5d6d7a;--line:#cdd6de;--accent:#2f5d88;--on-accent:#f3f4f1;
--display:'Fraunces',Georgia,serif;--body:'IBM Plex Sans',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141a20;--panel:#1c232a;--ink:#e6ebef;--muted:#a7b4bf;--line:#33414d;--accent:#8cc8f5;--on-accent:#10202c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#141a20;--panel:#1c232a;--ink:#e6ebef;--muted:#a7b4bf;--line:#33414d;--accent:#8cc8f5;--on-accent:#10202c;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--body);margin:0;padding:24px max(16px,env(safe-area-inset-right,0px)) 48px max(16px,env(safe-area-inset-left,0px))}
.page{max-width:780px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
h1{font-family:var(--display);font-weight:600;font-size:clamp(26px,5vw,34px);line-height:1.15;margin:8px 0 0;text-wrap:balance}
.lede{color:var(--muted);line-height:1.55;font-size:15px;margin:0;max-width:65ch}
.stats{font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums;margin:0}
a{color:var(--accent)}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
__STYLE__
nav{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);flex:1 1 220px;min-width:0}
select,button{font:inherit;font-size:15px;padding:9px 12px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);text-transform:none;letter-spacing:0}
select{width:100%} button{cursor:pointer} #flip{background:var(--accent);color:var(--on-accent);border-color:var(--accent);font-weight:600}
button:focus-visible,select:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.side{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.frame{border-radius:14px;border:1px solid var(--line);overflow:hidden;min-width:0}
.frame .card{min-height:220px}
.deck{color:var(--muted);font-size:13px;overflow-wrap:anywhere;margin:0}
__CSS__
</style></head><body>
<div class="page">
<header><p class="stats">__STATS__</p><h1>__TITLE__</h1>
<p class="lede">__LEDE__ Sample cards from the package: pick one, then show the answer. <a href="index.html">All decks</a></p></header>
<nav aria-label="Card picker">
<label for="group">Deck<select id="group"></select></label>
<label for="pick">Card<select id="pick"></select></label>
<button id="prev" type="button" aria-label="Previous card">←</button><button id="flip" type="button">Show answer</button><button id="next" type="button" aria-label="Next card">→</button></nav>
<main><div class="side"><span id="side">Question</span><span id="pos"></span></div>
<div class="frame"><div id="card" class="card" aria-live="polite"></div></div>
<p class="deck" id="deck"></p></main></div>
<script>
const cards=__CARDS__;
const group=document.getElementById('group'),pick=document.getElementById('pick'),box=document.getElementById('card');let back=false;
[...new Set(cards.map(c=>c.group))].forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;group.append(o)});
const dark=matchMedia('(prefers-color-scheme: dark)');
function isDark(){const t=document.documentElement.dataset.theme;return t?t==='dark':dark.matches}
function list(){return cards.map((c,i)=>[c,i]).filter(([c])=>c.group===group.value)}
function fill(){pick.textContent='';list().forEach(([c,i])=>{const o=document.createElement('option');o.value=i;o.textContent=c.label;pick.append(o)})}
function draw(){const c=cards[+pick.value];box.innerHTML=back?c.back:c.front;box.classList.toggle('nightMode',isDark());
const l=list().map(([,i])=>i);document.getElementById('pos').textContent=(l.indexOf(+pick.value)+1)+' / '+l.length;
document.getElementById('side').textContent=back?'Answer':'Question';document.getElementById('flip').textContent=back?'Show question':'Show answer';
document.getElementById('deck').textContent=c.deck;
box.querySelectorAll('.hint-link').forEach(a=>a.onclick=e=>{e.preventDefault();a.nextElementSibling.hidden=false;a.hidden=true});}
function step(d){const l=list().map(([,i])=>i);const k=l.indexOf(+pick.value)+d;if(k>=0&&k<l.length){pick.value=l[k];back=false;draw()}}
group.onchange=()=>{fill();back=false;draw()};pick.onchange=()=>{back=false;draw()};
document.getElementById('flip').onclick=()=>{back=!back;draw()};
document.getElementById('prev').onclick=()=>step(-1);document.getElementById('next').onclick=()=>step(1);
dark.addEventListener('change',draw);new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
fill();draw();
</script></body></html>
"""

INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>kizamu decks</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
__STYLE__
ul{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px}
li a{display:block;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:var(--panel);text-decoration:none;color:var(--ink)}
li a:hover,li a:focus-visible{border-color:var(--accent)}
li strong{font-family:var(--display);font-weight:600;font-size:19px;display:block}
li span{color:var(--muted);font-size:14px;line-height:1.5}
</style></head><body>
<div class="page">
<header><p class="stats">Anki decks with audio</p><h1>kizamu decks</h1>
<p class="lede">German vocabulary, grammar and sentences, and American English for advanced learners.
Every card has audio. Open a deck to try sample cards; download the decks from the
<a href="__RELEASES__">releases</a>.</p></header>
<ul>__ITEMS__</ul>
</div></body></html>
"""

SOUND = re.compile(r"\[sound:([^\]]+)\]")
HINT = re.compile(r'<a class=hint[^>]*>(.*?)</a>\s*<div id="hint[^"]*" class=hint style="display: none">(.*?)</div>',
                  re.DOTALL)


def render(card, side: str) -> str:
    """One side of a card, with [sound:…] tags in place of Anki's play buttons."""
    output = card.render_output(reload=True)
    text = output.question_text if side == "q" else output.answer_text
    tags = output.question_av_tags if side == "q" else output.answer_av_tags

    def replace(match: re.Match) -> str:
        tag = tags[int(match.group(1))]
        return f"[sound:{tag.filename}]" if hasattr(tag, "filename") else ""

    return re.sub(r"\[anki:play:[aq]:(\d+)\]", replace, text)


def clean(text: str, media: Path, cache: dict[str, str]) -> str:
    def sound(match: re.Match) -> str:
        name = match.group(1)
        if name not in cache:
            path = media / name
            cache[name] = base64.b64encode(path.read_bytes()).decode() if path.exists() else ""
        if not cache[name]:
            return ""
        return f'<audio controls preload="none" src="data:audio/mpeg;base64,{cache[name]}"></audio>'

    text = re.sub(r"<style>.*?</style>", "", text, flags=re.DOTALL)
    text = HINT.sub(lambda m: f'<a class="hint-link" href="#">Show {m.group(1).strip().lower()}</a>'
                              f'<span hidden>{m.group(2)}</span>', text)
    return SOUND.sub(sound, text)


def label(note) -> str:
    keys = note.keys()
    field = next((key for key in ("German", "Term") if key in keys), keys[0])
    text = re.sub(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}", r"\1", note[field])
    text = html.unescape(re.sub(r"<[^>]+>|\[sound:[^\]]+\]", "", text)).strip()
    return text if len(text) <= 60 else text[:57] + "…"


def preview(package: Path, title: str, lede: str, target: Path) -> dict:
    random.seed(11)
    with tempfile.TemporaryDirectory() as tmp:
        col = Collection(str(Path(tmp) / "collection.anki2"))
        try:
            col.import_anki_package(ImportAnkiPackageRequest(
                package_path=str(package.resolve()),
                options=ImportAnkiPackageOptions(with_scheduling=False, with_deck_configs=False)))
            decks = {d.id: d.name for d in col.decks.all_names_and_ids()}
            groups: dict[str, list[int]] = {}
            for nid, did in col.db.execute("select distinct nid, did from cards"):
                parts = decks[did].split("::")
                groups.setdefault(parts[2] if len(parts) > 2 else parts[-1], []).append(nid)
            per_group = max(2, math.ceil(TARGET_NOTES / len(groups)))
            media, cache, cards, css = Path(col.media.dir()), {}, [], {}
            for name in sorted(groups):
                nids = sorted(set(groups[name]))
                for nid in random.sample(nids, min(per_group, len(nids))):
                    note = col.get_note(nid)
                    css[note.mid] = note.note_type()["css"]
                    for card in sorted(note.cards(), key=lambda c: c.ord):
                        cards.append({"group": name, "label": f"{label(note)} · {card.template()['name']}",
                                      "deck": decks[card.did],
                                      "front": clean(render(card, "q"), media, cache),
                                      "back": clean(render(card, "a"), media, cache)})
            notes = col.db.scalar("select count() from notes")
            total = col.db.scalar("select count() from cards")
        finally:
            col.close()
    stats = f"{notes:,} notes · {total:,} cards" + (f" · {len(groups)} deck groups" if len(groups) > 1 else "")
    payload = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    page = (PAGE.replace("__STYLE__", STYLE).replace("__CSS__", "\n".join(css.values()))
            .replace("__TITLE__", html.escape(title)).replace("__LEDE__", html.escape(lede))
            .replace("__STATS__", html.escape(stats)).replace("__CARDS__", payload))
    target.write_text(page)
    return {"page": target.name, "title": title, "lede": lede, "stats": stats, "sample_cards": len(cards),
            "megabytes": round(len(page.encode()) / 1e6, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="folder for the pages (e.g. docs/)")
    parser.add_argument("--releases", default="https://github.com/salmanmohebi/kizamu-decks-releases/releases")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pages = []
    for name, (title, lede) in PACKAGES.items():
        pages.append(preview(SOURCE / f"{name}.apkg", title, lede, args.out / f"{name}.html"))
        print(json.dumps(pages[-1], ensure_ascii=False), flush=True)
    items = "".join(f'<li><a href="{p["page"]}"><strong>{html.escape(p["title"])}</strong>'
                    f'<span>{html.escape(p["lede"])} {html.escape(p["stats"])}</span></a></li>' for p in pages)
    (args.out / "index.html").write_text(INDEX.replace("__STYLE__", STYLE).replace("__ITEMS__", items)
                                         .replace("__RELEASES__", args.releases))


if __name__ == "__main__":
    main()
