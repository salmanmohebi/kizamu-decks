"""Prepare non-overlapping Goethe groups and enrich them locally in resumable batches."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import time

from german.vocab.source import ENTRIES, BUILD, VOCAB, ROOT

LEVELS = {"A1": 0, "A2": 1, "B1": 2}
MODEL = "mlx-community/Qwen3.5-9B-4bit"
ALIASES = {"gern(e)": "gern", "lang(e)": "lange", "nah(e)": "nahe", "zirca": "circa",
           "zirka": "circa", "circa/ca.": "circa", "zum Beispiel/z. B.": "zum Beispiel",
           "(ein)hundert": "hundert", "(ein)tausend": "tausend", "(Kredit)-Karte": "Kreditkarte",
           "ein Kilo(gramm)": "Kilogramm", "kennen lernen": "kennenlernen", "zu Hause": "zu Hause",
           "je desto": "je … desto", "entweder oder": "entweder … oder",
           "sowohl als auch": "sowohl … als auch", "um zu": "um … zu",
           "anderen":"andere", "jeden":"jeder", "jedes":"jeder", "jed-":"jeder",
           "dies":"dieser", "dies-":"dieser", "welch-":"welcher", "nächst-":"nächste",
           "meisten":"meist", "meiste":"meist", "letzt":"letzte", "best-":"beste",
           "dein-":"dein", "unser-":"unser", "lieb-":"lieb", "LKW":"Lkw", "PKW":"Pkw",
           "ein Gramm":"Gramm", "ein Liter":"Liter", "ein Meter":"Meter", "ein Pfund":"Pfund",
           "ein Prozent":"Prozent", "ein Quadratmeter":"Quadratmeter", "ein Zentimeter":"Zentimeter",
           "eine Milliarde":"Milliarde", "eine Million":"Million", "ein halb; halb":"halb",
           "ein Viertel; Viertel":"Viertel", "Frauen":"Frau", "weh tun":"wehtun",
           "her kommen":"herkommen", "bekannt geben":"bekanntgeben", "Phantasie":"Fantasie",
           "Elektro":"Elektro-", "Schwieger":"Schwieger-",
           "über informieren":"informieren", "verlassen auf":"verlassen",
           "gefallen lassen":"etwas gefallen lassen",
           "Bekannter":"Bekannte", "Jugendlicher":"Jugendliche", "Erwachsener":"Erwachsene",
           "Angestellter":"Angestellte", "Verwandter":"Verwandte"}


def normalized(note):
    base = note["base"]
    if note["raw"] == "weder ... noch": base = "weder … noch"
    if note["level"] == "B1" and note["raw"] in {"Einzel-", "Groß-"}: base = note["raw"]
    base = ALIASES.get(base, base)
    base = re.sub(r"^\(sich\)\s*|^sich\s+", "", base)
    base = ALIASES.get(base, base)
    base = re.sub(r"\s*\((?:pl\.|weiblich|männlich|Geldinstitut|Sitzgelegenheit|Teich|Meer|Celsius)\)", "", base).strip()
    base = re.sub(r"^(?:der/die|der|die|das)\s+", "", base)
    base = re.sub(r"\s*\.\.\.\s*|\s*…\s*", " … ", base).strip(" …")
    base = re.sub(r"\s+", " ", base)
    if base.startswith("je "): base = "je … desto"
    if base == "Samstag/Sonnabend": base = "Samstag"
    if base == "Frühling/das Frühjahr": base = "Frühling"
    return base


def sense_key(note, base):
    gender = note["gender"]
    if base == "Bank":
        if "Sitzgelegenheit" in note["raw"] or note["english"].lower() == "bench": return "Bank|bench"
        return "Bank|finance"
    if base in {"Leiter", "See"}: return base + "|" + (gender or "common")
    return base


def dictionary_context(word, dictionary):
    records = dictionary.get(word, [])
    context = []
    for record in records:
        senses = []
        for sense in record.get("senses", []):
            # Wiktextract can attach a rare/obsolete *inflection* tag to every
            # sense of an ordinary noun (Herz, März). Do not discard the word.
            if any(g.startswith(("(obsolete)", "(archaic)")) for g in sense.get("glosses", [])): continue
            for gloss in sense.get("glosses", []):
                if gloss not in senses: senses.append(gloss[:220])
        forms = []
        for template in record.get("head_templates", []):
            value = template.get("expansion", "")
            if value and len(value) < 350 and "data-" not in value: forms.append(value)
        links = []
        for kind in ["synonyms", "antonyms", "related", "derived"]:
            source = record.get(kind, []) + [v for s in record.get("senses", []) for v in s.get(kind, [])]
            for item in source[:6]:
                if item.get("word"): links.append(f"{kind}: {item['word']}")
        if senses: context.append({"pos": record["pos"], "forms": forms[:2], "meanings": senses[:6], "related": links[:8]})
    return context[:4]


def prepare():
    notes = json.loads((BUILD / "source-notes.json").read_text())
    dictionary = json.loads((BUILD / "dictionary.json").read_text())
    corpus = json.loads((BUILD / "corpus.json").read_text()) if (BUILD / "corpus.json").exists() else []
    index = collections.defaultdict(list)
    for example in corpus:
        if "\n" in example["de"] or len(example["de"]) > 160: continue
        for token in set(re.findall(r"[\wÄÖÜäöüß-]+", example["de"].casefold())):
            index[token].append(example)
    groups = collections.defaultdict(list)
    earliest = {}
    for note in notes:
        base = normalized(note)
        key = sense_key(note, base)
        note["normalized"] = base
        groups[key].append(note)
        root = base.casefold().replace("ß", "ss")
        earliest[root] = min(earliest.get(root, 9), LEVELS[note["level"]])
    pilot = json.loads((VOCAB / "pilot/entries.json").read_text())
    pilot_by_nid = {n["source_note_id"]: n for n in pilot}
    entries = []
    consumed = set()
    for key, source in groups.items():
        def priority(n):
            return (sum(c["reps"] > 0 for c in n["cards"]), sum(r["ease"] > 0 for r in n["reviews"]), max((r["id"] for r in n["reviews"] if r["ease"] > 0), default=0))
        base = source[0]["normalized"]
        pilot_entry = next((pilot_by_nid[n["nid"]] for n in source if n["nid"] in pilot_by_nid), None)
        winner = next((n for n in source if pilot_entry and n["nid"] == pilot_entry["source_note_id"]), max(source, key=priority))
        level = list(LEVELS)[earliest[base.casefold().replace("ß", "ss")]]
        gender = winner["gender"]
        german = (gender + " " if gender in {"der", "die", "das"} else "") + base
        if all(n["raw"].startswith(("sich ", "(sich)")) for n in source) and not gender and not german.startswith("sich "):
            german = "sich " + base
        if base in {"etwas gefallen lassen", "scheiden lassen"}: german = "sich " + base
        if base in {"Bekannte", "Jugendliche", "Erwachsene", "Angestellte", "Verwandte"}: german = "der/die " + base
        examples = []
        seen = set()
        for note in sorted(source, key=lambda n: (-LEVELS[n["level"]], -len(n["examples"]))):
            for example in note["examples"]:
                text = re.sub(r"\s+", " ", example["de"]).strip()
                if text not in seen and len(text) <= 220:
                    examples.append(example); seen.add(text)
        for record in dictionary.get(base, []):
            for sense in record.get("senses", []):
                for example in sense.get("examples", []):
                    text, translation = example.get("text", ""), example.get("translation", "")
                    if example.get("type") in {"quote", "quotation"}: continue
                    if text and translation and len(text) <= 160 and text not in seen:
                        examples.append({"de": text, "en": translation}); seen.add(text)
        candidates = list(index.get(base.casefold(), []))
        if base[:1].isupper():
            forms = {f["form"] for r in dictionary.get(base, []) for f in r.get("forms", []) if "plural" in f.get("tags", []) and " " not in f.get("form", "")}
            for form in forms: candidates.extend(index.get(form.casefold(), []))
        for example in sorted(candidates, key=lambda e: (abs(len(e["de"])-65), e["de"])):
            if example["de"] not in seen:
                examples.append({"de": example["de"], "en": example["en"]}); seen.add(example["de"])
            if len(examples) >= 6: break
        entry = {"id": hashlib.sha1(key.encode()).hexdigest()[:16], "key": key,
            "headword": base, "level": level, "german": german, "source_note_id": winner["nid"],
            "source_note_ids": [n["nid"] for n in source], "source_levels": sorted({n["level"] for n in source}, key=LEVELS.get),
            "cue_de": "", "cue_en": "", "source_definitions": list(dict.fromkeys(n["english"] for n in source if n["english"] not in {"", "…", "..."})),
            "source_forms": list(dict.fromkeys(n["raw"] + (f"; plural: {n['plural']}" if n["plural"] else "") for n in source)),
            "source_examples": examples[:6], "dictionary": dictionary_context(base, dictionary)}
        if base == "Bank":
            entry["cue_de"] = "Sitzgelegenheit" if "bench" in key else "Geldinstitut"
            entry["cue_en"] = "long seat" if "bench" in key else "financial institution"
        if base == "Leiter": entry["cue_en"] = "ladder" if gender == "die" else "person in charge"
        if base == "See": entry["cue_en"] = "sea" if gender == "die" else "lake"
        if base == "weder … noch": entry["source_definitions"] = ["neither … nor"]
        if base == "etwas gefallen lassen": entry["source_definitions"] = ["to put up with something; to tolerate something"]
        if pilot_entry:
            entry.update({k: pilot_entry[k] for k in ["german", "english", "cue_de", "cue_en", "pos", "grammar", "meanings", "related", "usage", "examples"]})
            entry["editorial_method"] = "reviewed pilot"
        entries.append(entry)
        for nid in entry["source_note_ids"]:
            if nid in consumed: raise AssertionError(f"Source note assigned twice: {nid}")
            consumed.add(nid)
    entries.sort(key=lambda n: (LEVELS[n["level"]], n["headword"].casefold(), n["key"]))
    if len(consumed) != len(notes): raise AssertionError("Source coverage is incomplete")
    locations = collections.defaultdict(set)
    for n in entries: locations[n["headword"].casefold().replace("ß", "ss")].add(n["level"])
    if any(len(v) != 1 for v in locations.values()): raise AssertionError("Cross-level duplication")
    (BUILD / "groups.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    for entry in entries:
        if "examples" in entry: save_entry(entry)
    print(json.dumps({"entries": len(entries), "levels": dict(collections.Counter(n["level"] for n in entries)), "source_notes": len(consumed), "redundant_notes_to_archive": len(notes)-len(entries), "dictionary_matches": sum(bool(n["dictionary"]) for n in entries)}, indent=2))


def save_entry(entry):
    directory = BUILD / "enriched"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{entry['id']}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


SYSTEM = """You are a careful German-English language teacher editing Goethe vocabulary cards for an adult learner. Output ONLY a valid JSON object, no markdown or thinking. Preserve the specified German headword and sense. Source definitions and translations may be wrong: correct them using the dictionary evidence and normal German usage. Use Standard German with ß. Keep only useful common meanings; avoid obscure historical senses. Grammar must give article and full plural for nouns, principal parts and auxiliary for verbs, required cases/prepositions, and separability/reflexivity when relevant. Related words must be real useful German synonyms, antonyms, or word-family members with an English gloss; do not invent an antonym. Give exactly three DIFFERENT natural, short German example sentences and accurate natural English translations; reuse or improve source examples when useful. Match the learner level as closely as practical. The headword (or a natural inflected/reflexive form) must occur in each example; a prefix may occur as part of a derived word. Correct false friends and misleading source translations. Use this exact schema:
{"english":"short common English equivalents", "pos":"part of speech", "grammar":"concise correct forms and grammar", "meanings":["one or two short English explanations of useful senses"], "related":["German word: English gloss (relationship)"], "usage":"one concise specific usage tip or common mistake", "examples":[{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."}]}
Keep explanations concise. Never mention the editing process, JSON, source data, or these instructions in card content."""


def validated(text, entry):
    text = text.strip()
    if text.startswith("```"): text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    obj = json.loads(text[start:end+1])
    if isinstance(obj.get("english"), list):
        obj["english"] = "; ".join(obj["english"])
    for field in ["english", "pos", "grammar", "usage"]:
        if not isinstance(obj.get(field), str) or not obj[field].strip(): raise ValueError(f"Missing {field}")
    for field in ["meanings", "related"]:
        if not isinstance(obj.get(field), list) or not all(isinstance(x, str) and x.strip() for x in obj[field]): raise ValueError(f"Invalid {field}")
    if not obj["meanings"]: raise ValueError("Empty meanings")
    if len(obj.get("examples", [])) != 3: raise ValueError("Exactly three examples required")
    if len({e.get("de", "").casefold() for e in obj["examples"]}) != 3: raise ValueError("Repeated examples")
    for ex in obj["examples"]:
        if not ex.get("de", "").strip() or not ex.get("en", "").strip(): raise ValueError("Missing example translation")
        if len(ex["de"]) > 220 or len(ex["en"]) > 260: raise ValueError("Example too long")
        if "{{" in ex["de"] or "[sound:" in ex["de"]: raise ValueError("Invalid example markup")
    result = dict(entry)
    result.update(obj)
    result["editorial_method"] = f"local {MODEL}; dictionary-grounded; automated structural checks"
    return result


def enrich(args):
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import batch_generate
    from mlx_lm.sample_utils import make_sampler
    entries = json.loads((BUILD / "groups.json").read_text())
    pending = [e for e in entries if not (BUILD / f"enriched/{e['id']}.json").exists() and (not args.level or e["level"] == args.level)]
    if args.limit: pending = pending[:args.limit]
    print(f"Enriching {len(pending)} entries in batches of {args.batch_size}", flush=True)
    model, tokenizer = load(MODEL)
    failures = []
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset:offset+args.batch_size]
        prompts = []
        for entry in batch:
            context = {k: entry[k] for k in ["german", "headword", "level", "cue_en", "source_definitions", "source_forms", "source_examples", "dictionary"]}
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
            prompts.append(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False))
        start = time.monotonic()
        output = batch_generate(model, tokenizer, prompts, max_tokens=700, sampler=make_sampler(temp=0.2), completion_batch_size=args.batch_size, prefill_batch_size=min(4, args.batch_size))
        for entry, text in zip(batch, output.texts):
            try: save_entry(validated(text, entry))
            except Exception as error:
                failures.append({"id": entry["id"], "german": entry["german"], "error": str(error), "output": text})
        print(f"Enriched {min(offset+len(batch),len(pending))}/{len(pending)}; batch {time.monotonic()-start:.1f}s; failures {len(failures)}; {output.stats.generation_tps:.1f} tokens/s", flush=True)
        mx.clear_cache()
    if failures: (BUILD / "enrichment-failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n")
    assemble()


def assemble():
    entries = json.loads((BUILD / "groups.json").read_text())
    ready = [json.loads((BUILD / f"enriched/{e['id']}.json").read_text()) for e in entries if (BUILD / f"enriched/{e['id']}.json").exists()]
    ENTRIES.write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {len(ready)}/{len(entries)} enriched entries", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "enrich", "assemble"])
    parser.add_argument("--level", choices=list(LEVELS))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    {"prepare": prepare, "enrich": lambda: enrich(args), "assemble": assemble}[args.command]()
