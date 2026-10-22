"""Render a sample of built cards (front + back) into one self-contained HTML page.

    python -m german.grammar.preview [--per-type 2] [--out PATH]
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re

from anki.collection import Collection

from german.grammar.build import CSS, MODELS, PROFILE
from german.grammar.common import DECK_ROOT, OUT

PAGE = """<title>Kizamu Grammar Cards</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
/* Layout: one study column; a deck picker above a single card, as in Anki's reviewer. */
:root{--bg:#e9ebe4;--panel:#f4f3ed;--ink:#233136;--muted:#5f6f6d;--line:#cfd8d0;--accent:#285b49;--on-accent:#f4f3ed;
--display:'Fraunces',Georgia,serif;--body:'IBM Plex Sans',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151c1a;--panel:#1f2926;--ink:#e8ede8;--muted:#a9b7b0;--line:#34443e;--accent:#8fd8b5;--on-accent:#12201b;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#151c1a;--panel:#1f2926;--ink:#e8ede8;--muted:#a9b7b0;--line:#34443e;--accent:#8fd8b5;--on-accent:#12201b;color-scheme:dark}
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
.frame table{display:block;overflow-x:auto;max-width:100%}
__CSS__
</style>
<div class="page">
<header><p class="stats" id="stats"></p><h1>kizamu-german · grammar &amp; sentences</h1>
<p class="lede">Real cards from the build: every card type at every level. Pick a card, then show the answer. Audio buttons are placeholders on this page; in Anki every German sentence plays.</p></header>
<nav aria-label="Card picker">
<label for="group">Level<select id="group"></select></label>
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
document.getElementById('deck').textContent=c.deck;}
function step(d){const l=list().map(([,i])=>i);const k=l.indexOf(+pick.value)+d;if(k>=0&&k<l.length){pick.value=l[k];back=false;draw()}}
group.onchange=()=>{fill();back=false;draw()};pick.onchange=()=>{back=false;draw()};
document.getElementById('flip').onclick=()=>{back=!back;draw()};
document.getElementById('prev').onclick=()=>step(-1);document.getElementById('next').onclick=()=>step(1);
dark.addEventListener('change',draw);new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
fill();draw();
</script>"""

SOUND = re.compile(r"\[anki:play:[aq]:\d+\]|\[sound:[^\]]+\]")


def clean(text: str) -> str:
    text = re.sub(r"<style>.*?</style>", "", text, flags=re.DOTALL)
    return SOUND.sub('<span class="audio-ph">▶ audio</span>', text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-type", type=int, default=2)
    parser.add_argument("--out", default=str(OUT / "preview.html"))
    args = parser.parse_args()
    random.seed(7)
    col = Collection(str((PROFILE / "collection.anki2").resolve()))
    samples = []
    try:
        names = {key: spec[0] for key, spec in MODELS.items()}
        decks = {d.id: d.name for d in col.decks.all_names_and_ids()}
        groups: dict[tuple, list[int]] = {}
        for cid, mid, did, ord_, tags in col.db.execute(
                "select c.id, n.mid, c.did, c.ord, n.tags from cards c join notes n on n.id=c.nid"):
            deck = decks[did]
            if not deck.startswith(DECK_ROOT + "::"):
                continue
            group = deck.split("::")[2] if deck.count("::") >= 2 else ""
            drill = next((t for t in tags.split() if t.startswith("drill_")), "")
            groups.setdefault((mid, ord_, group, drill), []).append(cid)
        for key in sorted(groups, key=lambda k: (k[2], str(k))):
            for cid in random.sample(groups[key], min(args.per_type, len(groups[key]))):
                card = col.get_card(cid)
                model = card.note_type()["name"].replace("kizamu-german · ", "")
                template = card.template()["name"]
                kind = key[3].replace("drill_", "") if key[3] else template
                samples.append({"group": key[2], "label": f"{model} · {kind}", "deck": decks[card.did],
                                "front": clean(card.question()), "back": clean(card.answer())})
        counts = col.db.all(
            "select count(distinct n.id), count(c.id) from cards c join notes n on n.id=c.nid "
            "where c.did in (select id from decks where name like ?)", DECK_ROOT + "::%")[0]
        studied = col.db.scalar(
            "select count() from cards where type>0 and did in (select id from decks where name like ?)", DECK_ROOT + "::%")
        stats = f"Built: {counts[0]:,} notes · {counts[1]:,} cards · {studied:,} cards with copied review history."
    finally:
        col.close()
    payload = json.dumps(samples, ensure_ascii=False).replace("</", "<\\/")
    page = PAGE.replace("__CSS__", CSS).replace("__CARDS__", payload).replace("__STATS__", json.dumps(stats))
    with open(args.out, "w") as handle:
        handle.write(page)
    print(f"{len(samples)} sample cards → {args.out}")


if __name__ == "__main__":
    main()
