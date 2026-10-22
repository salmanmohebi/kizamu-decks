"""Validate kizamu-english content files against AUTHORING.md and the catalogue.

    python -m english.validate english/C2/content/03-idioms-01.json [...]
    python -m english.validate --all

Prints OK per file or the problems. --all also checks duplicates across files and that
every catalogue part has a file. It cannot judge naturalness; a reviewer does that.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from english.common import (
    BUILD, BY_KEY, CATALOGUE, CONTENT, DRILLS, LEVEL, LEVELS, REGIONS, REGISTERS, bold_terms, normalize, strip_marks,
)

GAP = re.compile(r"\{\{(.+?)\}\}")
# One transcription, or a short list for contrasts: /θɪŋk/ vs. /sɪŋk/, /lid/ (verb), /lɛd/ (metal)
IPA = re.compile(r"^/[^/]+/(\s*\([^)]*\))?(\s*(,|;|vs\.|or)\s*/[^/]+/(\s*\([^)]*\))?)*$")
SPOKEN_NEEDED = re.compile(r"[/(:…]|\.\.\.|\bvs\b")
STOP = set("""a an the of to in on at for with by from and or but be is are was were been being am
it its it's this that these those as if so not no do does did done have has had having will would can
could should may might must shall up out off over into onto about you your yours i me my we our they
them their he him his she her one someone something somebody anything nothing""".split())
# British spellings that should not appear in American-English cards (whole words).
BRITISH = """colour colours coloured favour favourite favourites behaviour behaviours honour honoured
labour neighbour neighbours humour rumour flavour harbour endeavour centre centres theatre metre
litre fibre organise organised organising organisation realise realised realising recognise
recognised analyse analysed analysing apologise apologised criticise criticised emphasise
emphasised summarise summarised prioritise prioritised minimise maximise optimise optimised
utilise categorise characterise characterised specialise specialised standardise modernise
mobilise normalise jeopardise programme programmes travelled travelling cancelled cancelling
modelled modelling labelled labelling defence offence licence practise practised grey whilst
amongst learnt spelt dreamt catalogue dialogue cheque tyre kerb aluminium mum maths
fulfil enrol judgement ageing paediatric anaesthetic oestrogen manoeuvre sceptical sceptic
storey plough mould smoulder moustache pyjamas""".split()
BRITISH_RE = re.compile(r"\b(" + "|".join(BRITISH) + r")\b", re.IGNORECASE)
# Research / tech settings: at most one such sentence per entry (AUTHORING.md rule 9).
RESEARCH_RE = re.compile(r"\b(reviewers?|papers?|preprints?|datasets?|GPUs?|clusters?|benchmarks?|baselines?|"
                         r"codebase|pull requests?|servers?|pipelines?|arXiv|our lab|the lab|experiments?|"
                         r"models?|training run|deploy\w*|repo|PhD|thesis|algorithms?|grant|conference)\b",
                         re.IGNORECASE)


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’-]+", strip_marks(text)))


ABBREVIATION = re.compile(r"\b(e\.g|i\.e|etc|vs|Mr|Mrs|Ms|Dr|U\.S|a\.m|p\.m)\.", re.IGNORECASE)
# A sentence may also end inside italics or quotes: "…it.* Next", "…it." Next".
BOUNDARY = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][*\"”’)])|(?<=[.!?][*\"”’)]{2}))\s+(?=[A-Z*\"“(])")


def sentences(text: str) -> int:
    text = ABBREVIATION.sub(lambda m: m.group(0).replace(".", "·"), text.strip())
    return len([p for p in BOUNDARY.split(text) if p.strip()])


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) >= 4 and w not in STOP}


def catalogue() -> dict[str, dict]:
    path = CATALOGUE
    if not path.exists():
        return {}
    return {part["part_id"]: part for part in json.loads(path.read_text())["parts"]}


def check_file(path: Path, parts: dict[str, dict]) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        return [f"invalid JSON: {error}"], []
    part_id = path.stem
    if data.get("part_id") != part_id:
        problems.append(f"part_id must be {part_id!r}")
    part = parts.get(part_id)
    if part is None:
        return problems + [f"{part_id} is not in {LEVEL}/catalogue.json"], []
    category = BY_KEY[part["category"]]
    if data.get("category") != category["key"]:
        problems.append(f"category must be {category['key']!r}")
    entries = data.get("entries", [])
    want = [e["id"] for e in part["entries"]]
    got = [e.get("id") for e in entries]
    # A file may hold the first n entries of its part (pilot, or a part being written).
    if got and got == want[:len(got)] and len(got) < len(want):
        print(f"{path.name}: partial, {len(got)} of {len(want)} entries")
    elif got != want:
        missing = [i for i in want if i not in got]
        extra = [i for i in got if i not in want]
        problems.append(f"entry ids differ from the catalogue (missing {missing[:5]}, extra {extra[:5]}, "
                        f"or different order)")
    sentences_seen: dict[str, str] = {}
    texts: list[str] = []
    key = category["key"]
    for entry in entries:
        eid = entry.get("id", "?")
        p = lambda message: problems.append(f"{eid}: {message}")  # noqa: E731
        for name in ("id", "term", "label", "register", "region", "meaning", "usage", "examples", "drill"):
            if name not in entry:
                p(f"missing {name}")
        if any(name not in entry for name in ("term", "examples", "drill")):
            continue
        for name, value in entry.items():
            blob = json.dumps(value, ensure_ascii=False)
            if re.search(r"<[a-zA-Z/][^>]*>", blob):
                p(f"{name}: HTML is not allowed")
        if len(entry.get("label", "")) > 30:
            p("label longer than 30 characters")
        if entry.get("register") not in REGISTERS:
            p(f"register {entry.get('register')!r}")
        if entry.get("region") not in REGIONS:
            p(f"region {entry.get('region')!r}")
        meaning, usage = entry.get("meaning", ""), entry.get("usage", "")
        if not 1 <= sentences(meaning) <= 2 or words(meaning) > 45:
            p(f"meaning: 1-2 sentences and at most 45 words (has {sentences(meaning)} / {words(meaning)})")
        if not 2 <= sentences(usage) <= 3 or words(usage) > 75:
            p(f"usage: 2-3 sentences and at most 75 words (has {sentences(usage)} / {words(usage)})")
        if words(entry.get("related", "")) > 40:
            p("related: at most 40 words")
        if entry.get("origin") and key != "idioms":
            p("origin is for idioms only")
        part_index = part["index"]
        # C2 pronunciation: parts 1-2 are single words (IPA + respelling), part 3 connected speech.
        # C1 pronunciation: sounds, spellings, stress/intonation; IPA where a word or sound is taught.
        c2_words = LEVEL == "C2" and key == "pronunciation" and part_index in (1, 2)
        ipa_needed = key in ("words", "phrasal-verbs") or c2_words or (
            LEVEL == "C1" and key == "pronunciation" and part_index in (1, 2))
        ipa = entry.get("ipa", "")
        if ipa_needed and not ipa:
            p("ipa is required")
        if ipa and not IPA.match(ipa):
            p(f"ipa must look like /…/: {ipa!r}")
        if c2_words and not entry.get("respelling"):
            p("respelling is required")
        if key == "grammar":
            if entry.get("say_term", True) is not False:
                p("grammar entries need say_term: false")
            if not entry.get("pattern"):
                p("grammar entries need a pattern")
        elif entry.get("say_term", True) and SPOKEN_NEEDED.search(entry["term"]) and not entry.get("spoken_term"):
            p("spoken_term is required for this term")
        if c2_words and re.search(r"[a-z][A-Z]{2,}|^[A-Z]{2,}[a-z]", entry["term"]):
            p("pronunciation term must use normal spelling (no stress capitals) so the front does not give it away")
        mistake = entry.get("mistake")
        if key in ("nuance", "grammar", "pronunciation") and not mistake:
            p("mistake is required in this category")
        if mistake:
            if set(mistake) != {"wrong", "right", "why"} or not all(str(v).strip() for v in mistake.values()):
                p("mistake needs wrong, right and why")
            elif mistake["wrong"].strip() == mistake["right"].strip():
                p("mistake: wrong and right are identical")
        examples = entry["examples"]
        if not isinstance(examples, list) or len(examples) != 3:
            p("exactly 3 examples")
            examples = examples if isinstance(examples, list) else []
        for example in examples:
            if not bold_terms(example):
                p(f"example without **bold** target: {example[:50]!r}")
            if not 5 <= words(example) <= 30:
                p(f"example should have 5-30 words: {example[:50]!r}")
            texts.append(strip_marks(example))
        drill = entry["drill"]
        kind = drill.get("type")
        expected = {"pronunciation": "listen" if (LEVEL == "C2" and part_index == 3) else "say"}.get(key, "gap")
        if kind not in DRILLS or kind != expected:
            p(f"drill type must be {expected!r}")
        sentence = drill.get("sentence", "")
        if not drill.get("hint", "").strip():
            p("drill hint is missing")
        if kind == "gap":
            gaps = GAP.findall(sentence)
            if len(gaps) != 1:
                p("gap drill needs exactly one {{…}}")
            elif key not in ("grammar", "nuance"):
                leaked = content_words(gaps[0]) & content_words(drill.get("hint", ""))
                if leaked:
                    p(f"drill hint gives away the answer: {sorted(leaked)}")
            if "**" in sentence:
                p("gap drill sentence must not use **bold**")
        elif kind in ("say", "listen"):
            if GAP.search(sentence) or not bold_terms(sentence):
                p(f"{kind} drill: mark the target with **bold**, no {{…}}")
        if drill.get("spoken") is not None:
            if kind != "listen" or re.search(r"\*\*|\{\{", drill["spoken"]):
                p("drill.spoken is only for listen drills, as plain text (no ** or {{}})")
        if not 5 <= words(sentence) <= 32:
            p("drill sentence should have 5-32 words")
        texts.append(strip_marks(sentence))
        if key != "work-academic":
            # The target itself does not count (*in the pipeline* is not a research setting).
            research = [t for t in examples + [sentence]
                        if RESEARCH_RE.search(re.sub(r"\{\{.+?\}\}|\*\*.+?\*\*", "", t))]
            if len(research) > 1:
                p(f"{len(research)} research/tech sentences; at most 1 per entry (vary the contexts)")
        if entry.get("region") != "UK":
            # Explanations may mention a British form in italics ("British *maths*");
            # examples and the drill must be American throughout.
            mentions = re.sub(r"(?<!\*)\*[^*]+\*(?!\*)", " ", " ".join([meaning, usage, entry.get("related", "")]))
            blob = " ".join([mentions, sentence] + examples)
            british = sorted({m.group(1).lower() for m in BRITISH_RE.finditer(blob)})
            if british:
                p(f"British spelling: {british}")
    for text in texts:
        norm = re.sub(r"\W+", " ", text.lower()).strip()
        if norm in sentences_seen:
            problems.append(f"duplicate sentence: {text[:60]!r}")
        sentences_seen[norm] = text
    return problems, texts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    # The level follows the files (english/C1/content/… → C1), whatever KE_LEVEL says.
    levels = {part for f in args.files for part in Path(f).resolve().parts if part in LEVELS}
    if len(levels) == 1 and (level := levels.pop()) != LEVEL:
        os.execve(sys.executable, [sys.executable, "-m", "english.validate"] + sys.argv[1:], {**os.environ, "KE_LEVEL": level})
    parts = catalogue()
    if not parts:
        sys.exit(f"{CATALOGUE} is missing (run python -m english.catalogue)")
    paths = sorted(CONTENT.glob("*.json")) if args.all else [Path(f) for f in args.files]
    if args.all:
        print(f"level {LEVEL} (set KE_LEVEL=C1 or KE_LEVEL=C2 to choose)")
    failed = False
    global_texts: dict[str, str] = {}
    for path in paths:
        problems, texts = check_file(path, parts)
        for text in texts:
            norm = re.sub(r"\W+", " ", text.lower()).strip()
            if args.all and norm in global_texts and global_texts[norm] != path.stem:
                problems.append(f"sentence also in {global_texts[norm]}: {text[:60]!r}")
            global_texts.setdefault(norm, path.stem)
        if problems:
            failed = True
            print(f"{path.name}: {len(problems)} problems")
            for problem in problems[:60]:
                print("  -", problem)
        else:
            print(f"{path.name}: OK")
    if args.all:
        # Sentences must not repeat across levels either (C1 card = C2 card).
        for other in LEVELS:
            if other == LEVEL:
                continue
            for path in sorted((CONTENT.parent.parent / other / "content").glob("*.json")):
                try:
                    data = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                for entry in data.get("entries", []):
                    for text in entry.get("examples", []) + [entry.get("drill", {}).get("sentence", "")]:
                        norm = re.sub(r"\W+", " ", strip_marks(text).lower()).strip()
                        if norm in global_texts:
                            failed = True
                            print(f"{global_texts[norm]}.json: sentence also in {other}/{path.stem}: {strip_marks(text)[:60]!r}")
        missing = sorted(set(parts) - {p.stem for p in paths})
        if missing:
            print(f"{len(missing)} catalogue parts without a content file: {missing[:10]}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
