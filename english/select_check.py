"""Check selection files (english/<level>/selection/<category>.json) against SELECTION.md.

    python -m english.select_check [category ...]

Prints OK per file, or the problems. Also lists terms that appear in more than one
category (warnings; the merge step keeps the first category in catalogue order).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from english.common import (
    BY_KEY, CATEGORIES, LEVEL, LEVELS, REGIONS, REGISTERS, SELECTION, level_dir, normalize,
)

THEMES = {"argument & ideas", "communication", "work & careers", "research & academia",
          "business & money", "society & politics", "change & progress", "problems & solutions",
          "emotions & attitudes", "character & behavior", "relationships & social life",
          "success & failure", "risk & decisions", "time & pace", "everyday life", "quantity & degree"}


def higher_level_terms() -> dict[str, str]:
    """Terms already taught at a higher level (normalized → level)."""
    taken = {}
    for higher in LEVELS[LEVELS.index(LEVEL) + 1:]:
        path = level_dir(higher) / "catalogue.json"
        for part in json.loads(path.read_text())["parts"] if path.exists() else []:
            for entry in part["entries"]:
                taken[normalize(entry["term"])] = higher
                if ":" in entry["term"]:
                    taken[normalize(entry["term"].split(":")[0])] = higher
    return taken


HIGHER = higher_level_terms()


def check(category: dict) -> tuple[list[str], list[str]]:
    path = SELECTION / f"{category['key']}.json"
    if not path.exists():
        return [f"{path.name}: missing"], []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        return [f"{path.name}: invalid JSON: {error}"], []
    problems, keys = [], []
    if data.get("category") != category["key"]:
        problems.append(f"category must be {category['key']!r}")
    items = data.get("items", [])
    target = category["parts"] * 50
    if len(items) < target:
        problems.append(f"only {len(items)} items; target {target} + reserves")
    seen: dict[str, str] = {}
    last_importance, last_part = 9, 0
    for i, item in enumerate(items):
        where = f"item {i} ({item.get('term', '?')!r})"
        for name in ("term", "gloss", "importance", "register", "region", "theme", "part"):
            if name not in item:
                problems.append(f"{where}: missing {name}")
        if item.get("importance") not in (3, 4, 5):
            problems.append(f"{where}: importance must be 3, 4 or 5")
        if item.get("register") not in REGISTERS:
            problems.append(f"{where}: register {item.get('register')!r}")
        if item.get("region") not in REGIONS:
            problems.append(f"{where}: region {item.get('region')!r}")
        if item.get("theme") not in THEMES:
            problems.append(f"{where}: theme {item.get('theme')!r}")
        if category["ranked"]:
            if item.get("part") != 0:
                problems.append(f"{where}: part must be 0 in a ranked category")
            if isinstance(item.get("importance"), int) and item["importance"] > last_importance:
                problems.append(f"{where}: not sorted by importance")
            last_importance = item.get("importance", last_importance)
        else:
            part = item.get("part")
            if not isinstance(part, int) or not 1 <= part <= category["parts"]:
                problems.append(f"{where}: part must be 1..{category['parts']}")
            elif part < last_part:
                problems.append(f"{where}: not sorted by part")
            else:
                last_part = part
        key = normalize(str(item.get("term", "")))
        if key in HIGHER:
            problems.append(f"{where}: already in the {HIGHER[key]} decks; choose another item")
        if key in seen:
            problems.append(f"{where}: duplicate of {seen[key]!r}")
        seen[key] = item.get("term", "")
        keys.append(key)
    if not category["ranked"]:
        for part in range(1, category["parts"] + 1):
            count = sum(1 for item in items if item.get("part") == part)
            if count < 50:
                problems.append(f"part {part}: only {count} items (need 50 + reserves)")
    return problems, keys


def main() -> None:
    wanted = sys.argv[1:] or [c["key"] for c in CATEGORIES]
    print(f"level {LEVEL} ({SELECTION})")
    owners: dict[str, list[str]] = defaultdict(list)
    failed = False
    for key in wanted:
        problems, keys = check(BY_KEY[key])
        for k in keys:
            owners[k].append(key)
        if problems:
            failed = True
            print(f"{key}: {len(problems)} problems")
            for problem in problems[:40]:
                print("  -", problem)
        else:
            print(f"{key}: OK ({len(keys)} items)")
    if len(wanted) == 1:
        # Compare against the other categories that already exist.
        for category in CATEGORIES:
            if category["key"] != wanted[0] and (SELECTION / f"{category['key']}.json").exists():
                _, keys = check(category)
                for k in keys:
                    owners[k].append(category["key"])
    shared = {k: v for k, v in owners.items() if len(set(v)) > 1}
    if shared:
        print(f"warning: {len(shared)} terms in more than one category, e.g.:")
        for k, v in list(shared.items())[:25]:
            print(f"  {k!r}: {sorted(set(v))}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
