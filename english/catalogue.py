"""Merge the selection files into the fixed deck catalogue.

Removes items that appear in more than one category (the category earlier in
PRIORITY keeps the item), gives every item a stable id, cuts ranked categories into
sets of SET_SIZE by importance, and keeps the best SET_SIZE items per topical part.
Writes <level>/catalogue.json (input for authoring and the build) and CATALOGUE.md
(the readable list).

    python -m english.catalogue [--force]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

from english.common import (
    BUILD, CATALOGUE, CATEGORIES, CONTENT, LEVEL, LEVEL_DIR, LEVELS, SELECTION, SET_SIZE, SHARED, all_parts,
    atomic_json, level_dir, normalize,
)

# Topical and narrow categories first: an item that is both a pronunciation trap and an
# advanced word is taught where its specific point is.
PRIORITY = ["pronunciation", "nuance", "grammar", "work-academic", "informal", "conversation",
            "idioms", "phrasal-verbs", "collocations", "words"]


def slug(term: str) -> str:
    text = unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60].rstrip("-") or "item"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even though content exists")
    args = parser.parse_args()
    if CATALOGUE.exists() and any(CONTENT.glob("*.json")) and not args.force:
        sys.exit("content already exists for this catalogue; use --force only if you know why")

    selections = {c["key"]: json.loads((SELECTION / f"{c['key']}.json").read_text())["items"]
                  for c in CATEGORIES}
    # Hand-checked near-duplicates (same item, different form, other category keeps it).
    exclude_path = SELECTION / "exclude.json"
    exclude = json.loads(exclude_path.read_text()) if exclude_path.exists() else {}
    # Old cards with the same words but another sense (turn on a TV / turn on someone):
    # no history copy for these.
    different_sense = set(exclude.get("_history_different_sense", []))
    for key, terms in exclude.items():
        if key.startswith("_"):
            continue
        missing = set(terms) - {item["term"] for item in selections[key]}
        if missing:
            sys.exit(f"exclude.json: {key} has no items {sorted(missing)}")
        selections[key] = [item for item in selections[key] if item["term"] not in set(terms)]
    legacy = {r["key"] for r in json.loads((SHARED / "legacy-studied.json").read_text())}
    owner: dict[str, str] = {}
    # "let alone: I can't boil an egg…" (grammar) is the same item as "let alone" (idioms).
    # Aliases only count across categories; inside grammar many terms share a prefix.
    alias_owner: dict[str, str] = {}
    # Items of a higher level's catalogue stay there (C1 must not repeat C2).
    for higher in LEVELS[LEVELS.index(LEVEL) + 1:]:
        path = level_dir(higher) / "catalogue.json"
        if not path.exists():
            sys.exit(f"build the {higher} catalogue first ({path})")
        for part in json.loads(path.read_text())["parts"]:
            for entry in part["entries"]:
                owner[normalize(entry["term"])] = higher
                alias_owner[normalize(entry["term"])] = higher
                if ":" in entry["term"]:
                    alias_owner[normalize(entry["term"].split(":")[0])] = higher
    for key in PRIORITY:
        for item in selections[key]:
            norm = normalize(item["term"])
            alias = normalize(item["term"].split(":")[0]) if ":" in item["term"] else None
            elsewhere = owner.get(norm) or next(
                (o for k in (norm, alias) if k for o in [alias_owner.get(k)] if o and o != key), None)
            owner.setdefault(norm, elsewhere or key)
            if alias:
                alias_owner.setdefault(alias, key)
            alias_owner.setdefault(norm, key)

    ids: set[str] = set()
    parts_out = []
    dropped = []
    by_part = {p["part_id"]: p for p in all_parts()}
    for category in CATEGORIES:
        key = category["key"]
        kept = []
        for item in selections[key]:
            norm = normalize(item["term"])
            if owner[norm] != key:
                dropped.append({"term": item["term"], "from": key, "kept_in": owner[norm]})
                continue
            owner[norm] = f"{key}:taken"  # also drops a second copy inside the same file
            kept.append(item)
        if category["ranked"]:
            kept.sort(key=lambda item: -item["importance"])  # stable: keeps the agent's order inside a level
            chunks = [kept[i * SET_SIZE:(i + 1) * SET_SIZE] for i in range(category["parts"])]
        else:
            chunks = [[item for item in kept if item["part"] == n][:SET_SIZE]
                      for n in range(1, category["parts"] + 1)]
        for index, chunk in enumerate(chunks, 1):
            part_id = f"{category['number']}-{key}-{index:02d}"
            if len(chunk) < SET_SIZE:
                print(f"warning: {part_id} has only {len(chunk)} items", file=sys.stderr)
            entries = []
            for item in chunk:
                base = slug(item["term"])
                entry_id, n = base, 2
                while entry_id in ids:
                    entry_id, n = f"{base}-{n}", n + 1
                ids.add(entry_id)
                entries.append({"id": entry_id, "term": item["term"], "gloss": item["gloss"],
                                "importance": item["importance"], "register": item["register"],
                                "region": item["region"], "theme": item["theme"],
                                "studied_before": normalize(item["term"]) in legacy
                                and item["term"] not in different_sense})
            meta = by_part[part_id]
            parts_out.append({"part_id": part_id, "category": key, "index": index,
                              "title": meta["title"], "deck": meta["deck"], "entries": entries})

    atomic_json(CATALOGUE, {"parts": parts_out, "dropped_duplicates": dropped})
    total = sum(len(p["entries"]) for p in parts_out)
    lines = [f"# kizamu-english {LEVEL} · item list", "",
             f"{total} notes in {len(parts_out)} decks. Ranked categories: Set 01 holds the most "
             "useful items. ★ = importance (5 = weekly in American English, 4 = monthly, "
             "3 = several times a year). ↺ = you studied this item in an old deck; its review "
             "history is copied.", ""]
    current = None
    for part in parts_out:
        category = next(c for c in CATEGORIES if c["key"] == part["category"])
        if category["key"] != current:
            current = category["key"]
            count = sum(len(p["entries"]) for p in parts_out if p["category"] == current)
            lines += [f"## {category['number']} {category['title']} ({count})", ""]
        lines += [f"### {part['title']}", ""]
        for entry in part["entries"]:
            mark = " ↺" if entry["studied_before"] else ""
            lines.append(f"- **{entry['term']}** — {entry['gloss']} · {'★' * entry['importance']} · "
                         f"{entry['register']}{'' if entry['region'] == 'both' else ', ' + entry['region']}{mark}")
        lines.append("")
    (LEVEL_DIR / "CATALOGUE.md").write_text("\n".join(lines))
    print(json.dumps({"notes": total, "decks": len(parts_out), "dropped_duplicates": len(dropped),
                      "studied_before": sum(e["studied_before"] for p in parts_out for e in p["entries"])}, indent=2))


if __name__ == "__main__":
    main()
