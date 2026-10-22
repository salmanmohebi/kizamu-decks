"""Candidate pool for the kizamu-english C2 decks, from the old English decks in the snapshot.

Every term in the old `01 - English`, `02 - English` and `All English::…` decks, merged by
normalized form, with its sources, English Vocabulary Profile level and part of speech
(from the Cambridge decks), a wordfreq Zipf value for single words, and whether you
studied it. Selection agents use this as evidence; it is not the final list.

    python -m english.candidates
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
from collections import defaultdict

from wordfreq import zipf_frequency

from english.common import BUILD, LEVEL, SHARED, SNAPSHOT, atomic_json, level_dir, normalize

# deck prefix → (short source name, field holding the term, optional pos field, level field)
SOURCES = [
    ("All English::Cambridge C2", "evp-c2", "Front", "Part of Speech", "Level"),
    ("All English::Cambridge C1", "evp-c1", "Front", "Part of Speech", "Level"),
    ("All English::Cambridge B2", "evp-b2", "Front", "Part of Speech", "Level"),
    ("All English::CambridgeVocab", "evp-vocab", "Name", "Type", "Level"),
    ("All English::Advanced Vocab", "advanced-vocab", "Term", None, None),
    ("All English::Advanced Vocabulary Complete", "advanced-vocab-20", "Word", None, None),
    ("All English::Close-up Word List", "close-up-c1", "Back", None, None),
    ("01 - English", "vocab-8k", "Word", None, None),
    ("All English::Vocabulary+", "vocab-plus", "Word", None, None),
    ("All English::Essential Idioms", "essential-idioms", "Expression", None, None),
    ("02 - English::101 American English Idioms", "american-idioms", "Idiom", None, None),
    ("02 - English::250+ Common phrasal verbs", "phrasal-250", "Word", None, None),
    ("All English::English Vocabulary::Phrasal Verbs", "phrasal-1758", "Word", None, None),
    ("All English::PopularPhrasalVerbs", "phrasal-100", "Front", None, None),
    ("All English::Illustrated Everyday Expressions", "everyday-expressions", "Phrase", None, None),
]


def clean(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    db = sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True)
    decks = {did: name.replace("\x1f", "::") for did, name in db.execute("select id, name from decks")}
    fields: dict[int, list[str]] = defaultdict(list)
    for ntid, _, name in db.execute("select ntid, ord, name from fields order by ntid, ord"):
        fields[ntid].append(name)
    templates = {(ntid, ord_): name for ntid, ord_, name in db.execute("select ntid, ord, name from templates")}

    pool: dict[str, dict] = {}
    studied: list[dict] = []
    for prefix, source, term_field, pos_field, level_field in SOURCES:
        dids = [did for did, name in decks.items() if name == prefix or name.startswith(prefix)]
        rows = db.execute(
            f"select n.id, n.mid, n.flds, c.id, c.ord, c.type, c.reps from cards c join notes n on n.id = c.nid "
            f"where c.did in ({','.join(map(str, dids))})")
        for nid, mid, flds, cid, ord_, ctype, reps in rows:
            values = dict(zip(fields[mid], flds.split("\x1f")))
            term = clean(values.get(term_field, ""))
            if not term or len(term) > 80:
                continue
            key = normalize(term)
            if not key:
                continue
            record = pool.setdefault(key, {"term": term, "sources": [], "evp_level": "", "pos": ""})
            if source not in record["sources"]:
                record["sources"].append(source)
            if level_field and values.get(level_field, "").strip() in ("C1", "C2", "B2"):
                level = values[level_field].strip()
                if not record["evp_level"] or level > record["evp_level"]:
                    record["evp_level"] = level
            if pos_field and values.get(pos_field):
                record["pos"] = record["pos"] or clean(values[pos_field])
            if ctype > 0 or reps > 0:
                studied.append({"key": key, "term": term, "source": source, "deck": decks.get(
                    db.execute("select did from cards where id=?", (cid,)).fetchone()[0]),
                    "card_id": cid, "note_id": nid, "template": templates.get((mid, ord_), str(ord_)),
                    "reps": reps})
    for record in pool.values():
        words = re.sub(r"\([^)]*\)", "", record["term"]).split()
        record["zipf"] = zipf_frequency(words[0], "en") if len(words) == 1 else None
    atomic_json(SHARED / "candidates.json", dict(sorted(pool.items())))
    atomic_json(SHARED / "legacy-studied.json", studied)
    write_pools(pool)
    by_source = defaultdict(int)
    for record in pool.values():
        for source in record["sources"]:
            by_source[source] += 1
    print(json.dumps({"candidates": len(pool), "studied_cards": len(studied), "by_source": by_source}, indent=2))


IDIOM_SOURCES = {"advanced-vocab", "essential-idioms", "american-idioms", "everyday-expressions",
                 "advanced-vocab-20"}


def write_pools(pool: dict[str, dict]) -> None:
    """Evidence files for the selection agents of the current level (BUILD/pool-*.txt)."""
    taken: set[str] = set()
    if LEVEL == "C1":  # C2 items are already in the C2 decks
        catalogue = level_dir("C2") / "catalogue.json"
        taken = {normalize(e["term"]) for p in json.loads(catalogue.read_text())["parts"] for e in p["entries"]}

    def words_line(r: dict) -> str:
        return f"{r['term']} | {r['evp_level'] or '-'} | {r['pos'] or '-'} | {r['zipf']:.2f} | {len(r['sources'])}"

    def sources_line(r: dict) -> str:
        z = "-" if r["zipf"] is None else f"{r['zipf']:.2f}"
        return f"{r['term']} | {r['evp_level'] or '-'} | {r['pos'] or '-'} | {z} | {','.join(r['sources'])}"

    words, phrasal, multi = [], [], []
    for key, r in pool.items():
        if key in taken:
            continue
        pos = r["pos"].lower()
        if "phrasal" in pos or any(s.startswith("phrasal") for s in r["sources"]):
            phrasal.append(r)
        elif len(re.sub(r"\([^)]*\)", "", r["term"]).split()) > 1:
            if r["evp_level"] in ("C1", "C2", "B2") or set(r["sources"]) & IDIOM_SOURCES:
                multi.append(r)
        elif r["zipf"] is not None:
            z, evp, n = r["zipf"], r["evp_level"], len(r["sources"])
            if LEVEL == "C2" and ((evp in ("C1", "C2") and 2.0 <= z <= 5.0)
                                  or (n >= 2 and 2.0 <= z <= 4.0 and evp != "B2")):
                words.append(r)
            if LEVEL == "C1" and ((evp in ("B2", "C1") and 3.0 <= z <= 5.5)
                                  or (n >= 2 and 3.0 <= z <= 4.8 and evp != "C2")):
                words.append(r)
    header = "# term | EVP level | part of speech | Zipf (single words) | sources\n"
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "pool-words.txt").write_text(
        "# term (EVP sense) | EVP level | part of speech | Zipf | number of old decks containing it\n"
        + "\n".join(words_line(r) for r in sorted(words, key=lambda r: -r["zipf"])) + "\n")
    (BUILD / "pool-phrasal.txt").write_text(
        header + "\n".join(sources_line(r) for r in sorted(phrasal, key=lambda r: r["term"].lower())) + "\n")
    (BUILD / "pool-multiword.txt").write_text(
        header + "\n".join(sources_line(r) for r in sorted(multi, key=lambda r: r["term"].lower())) + "\n")
    print(f"{LEVEL} pools: {len(words)} words, {len(phrasal)} phrasal verbs, {len(multi)} multi-word items")


if __name__ == "__main__":
    main()
