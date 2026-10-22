"""List near-copy sentences across the kizamu-english content of both levels.

The validator only finds identical sentences. This script compares the content words of every
example and drill sentence (Jaccard similarity, stop words and words under 3 letters ignored)
and prints pairs at or above the threshold. Pairs above ~0.55 are usually the same scene with
another target (e.g. "the map was so out of date" / "the map was so outdated"); rewrite one side.

Usage: python -m english.similar [--threshold 0.55] [content files ...]
(no files: all files of both levels)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOP = set("""the a an and or but to of in on at for with is are was were be been it its this that you
your i my we our they their he she his her me him them so if not do did have has had will would can
could just""".split())


def sentences(path: Path):
    for entry in json.loads(path.read_text())["entries"]:
        for text in entry.get("examples", []):
            yield entry["id"], text
        yield entry["id"], entry["drill"]["sentence"]


def words(text: str) -> set[str]:
    text = re.sub(r"\{\{|\}\}|\*", "", text.lower())
    return {w for w in re.findall(r"[a-z']+", text) if w not in STOP and len(w) > 2}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=float, default=0.55)
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    every = sorted(ROOT.glob("C*/content/*.json"))
    mine = [p.resolve() for p in args.files] or every
    pool, index = [], defaultdict(set)
    for path in every:
        tag = str(path.relative_to(ROOT))
        for eid, text in sentences(path):
            pool.append((tag, eid, text, words(text)))
            for w in pool[-1][3]:
                index[w].add(len(pool) - 1)
    seen, found = set(), 0
    for path in mine:
        tag0 = str(path.relative_to(ROOT))
        for eid, text in sentences(path):
            own = words(text)
            shared = defaultdict(int)
            for w in own:
                for i in index[w]:
                    shared[i] += 1
            for i, count in shared.items():
                tag, eid2, text2, other = pool[i]
                if (tag, eid2) == (tag0, eid) or count < 3:
                    continue
                score = count / len(own | other)
                key = frozenset([(tag0, eid, text), (tag, eid2, text2)])
                if score >= args.threshold and key not in seen:
                    seen.add(key)
                    found += 1
                    print(f"{score:.2f} {tag0}:{eid}\n    {text}\n  {tag}:{eid2}\n    {text2}")
    print(f"{found} pair(s) at >= {args.threshold}")


if __name__ == "__main__":
    main()
