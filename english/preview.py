"""Render a sample of built cards (front + back) into one self-contained HTML page.

    python -m english.preview [--per-part 2] [--embed-audio] [--out PATH]

--embed-audio puts the real clips of the sampled cards into the page (base64 MP3).
"""
from __future__ import annotations

import argparse
import base64
import json
import random
import re

from anki.collection import Collection

from english.audio import AUDIO
from english.build import CSS, MODEL_ID, PROFILE
from english.common import LEVEL, OUT

PAGE = """<title>English __LEVEL__ Cards</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
/* Layout: one study column; a deck picker above a single card, as in Anki's reviewer. */
:root{--bg:#e8ebee;--panel:#f3f4f1;--ink:#22303c;--muted:#5d6d7a;--line:#cdd6de;--accent:#2f5d88;--on-accent:#f3f4f1;
--display:'Fraunces',Georgia,serif;--body:'IBM Plex Sans',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141a20;--panel:#1c232a;--ink:#e6ebef;--muted:#a7b4bf;--line:#33414d;--accent:#8cc8f5;--on-accent:#10202c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#141a20;--panel:#1c232a;--ink:#e6ebef;--muted:#a7b4bf;--line:#33414d;--accent:#8cc8f5;--on-accent:#10202c;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:24px 48px}
.page{max-width:780px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
h1{font-family:var(--display);font-weight:600;font-size:clamp(26px,5vw,34px);line-height:1.15;margin:8px 0 0;text-wrap:balance}
.lede{color:var(--muted);line-height:1.55;font-size:15px;margin:0;max-width:65ch}
.stats{font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums;margin:0}
nav{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);flex:1 1 220px;min-width:0}
select,button{font:inherit;font-size:15px;padding:9px 12px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);text-transform:none;letter-spacing:0}
select{width:100%} button{cursor:pointer} #flip{background:var(--accent);color:var(--on-accent);border-color:var(--accent);font-weight:600}
button:focus-visible,select:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.side{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.frame{border-radius:14px;border:1px solid var(--line);overflow:hidden;min-width:0}
.frame .card{min-height:220px}
.audio-ph{display:inline-block;margin:8px 0;padding:3px 10px;border-radius:999px;border:1px solid currentColor;font-size:13px;opacity:.7}
.deck{color:var(--muted);font-size:13px;overflow-wrap:anywhere;margin:0}
__CSS__
</style>
<div class="page">
<header><p class="stats" id="stats"></p><h1>kizamu-english · __LEVEL__</h1>
<p class="lede">__LEDE__</p></header>
<nav aria-label="Card picker">
<label for="group">Category<select id="group"></select></label>
<label for="pick">Card<select id="pick"></select></label>
<button id="prev" type="button" aria-label="Previous card">←</button><button id="flip" type="button">Show answer</button><button id="next" type="button" aria-label="Next card">→</button></nav>
<main><div class="side"><span id="side">Front</span><span id="pos"></span></div>
<div class="frame"><div id="card" class="card" aria-live="polite"></div></div>
<p class="deck" id="deck"></p></main></div>
<script>
const cards=__CARDS__; const stats=__STATS__;
const group=document.getElementById('group'),pick=document.getElementById('pick'),box=document.getElementById('card');let back=false;
document.getElementById('stats').textContent=stats;
const groups=[...new Set(cards.map(c=>c.group))];
groups.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;group.append(o)});
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
</script>"""

SOUND = re.compile(r"\[sound:([^\]]+)\]|\[anki:play:[aq]:\d+\]")
HINT = re.compile(r'<a class=hint[^>]*>(.*?)</a>\s*<div id="hint[^"]*" class=hint style="display: none">(.*?)</div>',
                  re.DOTALL)


class Sounds:
    def __init__(self, embed: bool) -> None:
        self.embed = embed
        self.cache: dict[str, str] = {}

    def __call__(self, match: re.Match) -> str:
        name = match.group(1)
        if not self.embed or not name or not (AUDIO / name).exists():
            return '<span class="audio-ph">▶ audio</span>'
        if name not in self.cache:
            self.cache[name] = base64.b64encode((AUDIO / name).read_bytes()).decode()
        return f'<audio controls preload="none" src="data:audio/mpeg;base64,{self.cache[name]}"></audio>'


def clean(text: str, sounds: Sounds) -> str:
    text = re.sub(r"<style>.*?</style>", "", text, flags=re.DOTALL)
    text = HINT.sub(lambda m: f'<a class="hint-link" href="#">Show {m.group(1).strip().lower()}</a><span hidden>{m.group(2)}</span>', text)
    return SOUND.sub(sounds, text)


def render(card, side: str) -> str:
    """Render one side with the [sound:…] tags kept, so clips can be embedded."""
    output = card.render_output(reload=True)
    text = output.question_text if side == "q" else output.answer_text
    tags = output.question_av_tags if side == "q" else output.answer_av_tags

    def replace(match: re.Match) -> str:
        index = int(match.group(0).split(":")[-1].rstrip("]"))
        tag = tags[index]
        return f"[sound:{tag.filename}]" if hasattr(tag, "filename") else ""

    return re.sub(r"\[anki:play:[aq]:\d+\]", replace, text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-part", type=int, default=3, help="notes per category (both cards each)")
    parser.add_argument("--embed-audio", action="store_true")
    parser.add_argument("--out", default=str(OUT / "preview.html"))
    args = parser.parse_args()
    random.seed(11)
    sounds = Sounds(args.embed_audio)
    col = Collection(str((PROFILE / "collection.anki2").resolve()))
    samples = []
    try:
        decks = {d.id: d.name for d in col.decks.all_names_and_ids()}
        by_category: dict[str, list[int]] = {}
        for nid, did in col.db.execute(
                "select distinct n.id, c.did from notes n join cards c on c.nid=n.id where n.mid=?", MODEL_ID):
            category = decks[did].split("::")[2]
            by_category.setdefault(category, []).append(nid)
        for category in sorted(by_category):
            nids = by_category[category]
            for nid in random.sample(nids, min(args.per_part, len(nids))):
                note = col.get_note(nid)
                for card in sorted(note.cards(), key=lambda c: c.ord):
                    kind = card.template()["name"]
                    if kind == "Usage":
                        kind += " · " + ("listen" if note["Listen"] else "say it" if note["Say"] else "gap")
                    samples.append({
                        "group": category, "label": f"{re.sub('<[^>]+>', '', note['Term'])} · {kind}",
                        "deck": decks[card.did],
                        "front": clean(render(card, "q"), sounds), "back": clean(render(card, "a"), sounds)})
        notes = col.db.scalar("select count() from notes where mid=?", MODEL_ID)
        cards = col.db.scalar("select count() from cards c join notes n on n.id=c.nid where n.mid=?", MODEL_ID)
        studied = col.db.scalar(
            "select count() from cards c join notes n on n.id=c.nid where n.mid=? and c.type>0", MODEL_ID)
        stats = f"Built: {notes:,} notes · {cards:,} cards · {studied:,} cards with copied review history."
    finally:
        col.close()
    count = {1: "one note", 2: "two notes", 3: "three notes"}.get(args.per_part, f"{args.per_part} notes")
    lede = (f"Real cards from the build: {count} per category, each with its Meaning and Usage card. "
            "Pick a card, then show the answer. "
            + ("Audio is the real American English voice." if args.embed_audio else
               "Audio buttons are placeholders here; in Anki every term and sentence plays."))
    payload = json.dumps(samples, ensure_ascii=False).replace("</", "<\\/")
    page = (PAGE.replace("__LEVEL__", LEVEL).replace("__CSS__", CSS).replace("__LEDE__", lede)
            .replace("__CARDS__", payload).replace("__STATS__", json.dumps(stats)))
    with open(args.out, "w") as handle:
        handle.write(page)
    print(f"{len(samples)} sample cards → {args.out} ({len(page) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
