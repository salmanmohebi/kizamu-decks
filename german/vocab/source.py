"""Extract Goethe source data and a filtered, attributable dictionary cache."""
from __future__ import annotations
import argparse
import collections
import html
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import unicodedata
import zipfile

from kizamu.paths import DATA, ROOT

ENTRIES = Path(__file__).resolve().parent / "entries.json"
VOCAB = DATA / "german" / "vocab"
BUILD = VOCAB / "build"


def clean(text):
    text = re.sub(r"\[sound:[^\]]*\]", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    return unicodedata.normalize("NFC", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def connect(path):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.create_collation("unicase", lambda a, b: (a.casefold() > b.casefold()) - (a.casefold() < b.casefold()))
    return db


def extract(package):
    BUILD.mkdir(parents=True, exist_ok=True)
    target = BUILD / "source.anki21"
    if not target.exists():
        with zipfile.ZipFile(package) as archive, target.open("wb") as output:
            if "collection.anki21b" in archive.namelist():
                subprocess.run(["zstd", "-d", "-c"], input=archive.read("collection.anki21b"), stdout=output, check=True)
            else:
                output.write(archive.read("collection.anki21" if "collection.anki21" in archive.namelist() else "collection.anki2"))
    db = connect(target)
    rows = []
    for level in ["A1", "A2", "B1"]:
        deck = db.execute("select id,name from decks where name like ?", (f"%Goethe Institute {level} Wordlist",)).fetchone()
        for note in db.execute("select distinct n.* from notes n join cards c on c.nid=n.id where c.did=? order by n.id", (deck["id"],)):
            names = [r[0] for r in db.execute("select name from fields where ntid=? order by ord", (note["mid"],))]
            f = dict(zip(names, note["flds"].split(chr(31))))
            if level == "A1":
                raw, english, gender, plural = f["de_word"], f["en_word"], "", ""
                examples = [(f["de_sentence"], f["en_sentence"])]
                forms, usage, order = "", f["en_note"], f.get("Note ID", "")
                base = clean(raw).split(",")[0]
                match = re.match(r"^(der|die|das)\s+(.+)", base)
                if match: gender, base = match.groups()
            elif level == "A2":
                raw, english, gender, plural = f["Wort_DE"], f["Wort_EN"], f["Artikel"], f["Plural"]
                examples = [(f[f"Satz{i}_DE"], f[f"Satz{i}_EN"]) for i in range(1, 5)]
                forms, usage, order = f["Verbformen"], f["Hinweis"], f["Original_Order"]
                base = clean(raw)
            else:
                raw, english, gender, plural = f["full_d"], f["base_e"], f["artikel_d"], f["plural_d"]
                examples = [(f[f"s{i}"], f[f"s{i}e"]) for i in range(1, 10)]
                forms, usage, order = clean(raw), "", f["original_order"]
                base = clean(f["base_d"])
            cards = [dict(r) for r in db.execute("select * from cards where nid=? order by ord", (note["id"],))]
            reviews = [dict(r) for r in db.execute("select * from revlog where cid in (select id from cards where nid=?) order by id", (note["id"],))]
            rows.append({"nid": note["id"], "guid": note["guid"], "mid": note["mid"], "level": level,
                "deck_id": deck["id"], "deck": deck["name"].replace(chr(31), "::"),
                "raw": clean(raw), "base": clean(base), "english": clean(english), "gender": clean(gender),
                "plural": clean(plural), "forms": clean(forms), "usage": clean(usage), "order": order,
                "examples": [{"de": clean(a), "en": clean(b)} for a, b in examples if clean(a)],
                "cards": cards, "reviews": reviews, "tags": note["tags"].strip().split()})
    (BUILD / "source-notes.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"source_notes": len(rows), "cards": sum(len(n["cards"]) for n in rows), "review_records": sum(len(n["reviews"]) for n in rows)}, indent=2))
    db.close()


def dictionary():
    import requests
    rows = json.loads((BUILD / "source-notes.json").read_text())
    wanted = set()
    groups = BUILD / "groups.json"
    if groups.exists():
        wanted.update(e["headword"] for e in json.loads(groups.read_text()))
    for note in rows:
        for value in [note["base"], note["raw"].split(",")[0]]:
            value = re.sub(r"^(der|die|das)\s+", "", value)
            value = re.sub(r"\([^)]*\)", "", value).strip()
            value = re.sub(r"^sich\s+", "", value).strip()
            for part in re.split(r"\s*/\s*", value):
                wanted.add(part)
                if part.startswith("-"): wanted.add(part[1:])
    cache = BUILD / "dictionary.json"
    if cache.exists():
        print(f"Using dictionary cache: {cache}")
        return
    response = requests.get("https://kaikki.org/dictionary/German/index.html", timeout=60)
    response.raise_for_status()
    links = re.findall(r'href="([^"]+\.jsonl(?:\.gz)?)"', response.text)
    if not links: raise RuntimeError("Dictionary download link not found")
    from urllib.parse import urljoin
    url = urljoin(response.url, links[0])
    print(f"Filtering dictionary download: {url}", flush=True)
    response = requests.get(url, stream=True, timeout=(30, 180))
    response.raise_for_status()
    found = collections.defaultdict(list)
    total = 0
    for line in response.iter_lines(chunk_size=1024 * 1024):
        if not line: continue
        item = json.loads(line)
        total += 1
        if item.get("word") in wanted:
            senses = [s for s in item.get("senses", []) if not s.get("alt_of") and (not s.get("form_of") or "form-of" not in s.get("tags", []))]
            if senses:
                item["senses"] = senses
                # Avoid redistributing third-party literary quotation examples.
                for sense in senses:
                    sense["examples"] = [e for e in sense.get("examples", []) if e.get("type") not in {"quote", "quotation"}]
                found[item["word"]].append(item)
        if total % 50000 == 0: print(f"Dictionary records {total:,}; matched headwords {len(found):,}", flush=True)
    cache.write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n")
    (BUILD / "dictionary-provenance.json").write_text(json.dumps({"download": url, "website": "https://kaikki.org/dictionary/German/", "source": "English Wiktionary", "attribution": "Wiktionary contributors; extraction by Tatu Ylonen / Wiktextract", "license": "CC BY-SA 4.0; see https://en.wiktionary.org/wiki/Wiktionary:Copyrights", "matched_headwords": len(found), "records_scanned": total}, indent=2) + "\n")
    print(f"Dictionary complete: {len(found)} matched headwords", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["extract", "dictionary"])
    parser.add_argument("--collection", type=Path, help="Anki collection backup (.colpkg) with the source decks (for extract)")
    args = parser.parse_args()
    if args.command == "extract" and not args.collection:
        parser.error("extract needs --collection")
    extract(args.collection) if args.command == "extract" else dictionary()
