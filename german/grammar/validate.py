"""Structural validator for german/grammar/content/*.json (see german/grammar/AUTHORING.md).

Usage:
    python -m german.grammar.validate german/grammar/content/a1-01-sein.json [...]
    python -m german.grammar.validate --all
Exit status 1 if any file has errors. Warnings do not fail.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from german.grammar.common import CLOZE_RE, CONTENT, INPUTS, cloze_numbers, strip_cloze

DRILL_TYPES = {"concept", "transform", "error", "order", "choice", "combine"}
HTML_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def without_hints(text: str) -> str:
    return CLOZE_RE.sub(lambda m: f"{{{{c{m.group(1)}::{m.group(2)}}}}}", text)


def norm(text: str) -> str:
    return re.sub(r"[\s.,!?;:„“\"'’–-]+", " ", text).strip().lower()


class Report:
    def __init__(self, name: str):
        self.name, self.errors, self.warnings = name, [], []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def need_text(report: Report, where: str, obj: dict, *keys: str) -> None:
    for key in keys:
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip():
            report.error(where, f"missing or empty '{key}'")
        elif HTML_RE.search(value):
            report.error(where, f"HTML in '{key}' (use Markdown)")


def check_pairs(report: Report, where: str, pairs, count: tuple[int, int] = (2, 2)) -> list[str]:
    if not isinstance(pairs, list) or not count[0] <= len(pairs) <= count[1]:
        report.error(where, f"needs {count[0]}–{count[1]} entries with de/en")
        return []
    for i, pair in enumerate(pairs):
        need_text(report, f"{where}[{i}]", pair, "de", "en")
    return [pair.get("de", "") for pair in pairs]


def check_grammar(data: dict, source: dict, report: Report) -> None:
    hard = source["topic_id"].startswith("h")
    for key in ("topic_id", "level", "title_de", "title_en"):
        need_text(report, "topic", data, key)
    if data.get("topic_id") != source["topic_id"]:
        report.error("topic", "topic_id differs from input")
    rule = data.get("rule") or {}
    need_text(report, "rule", rule, "summary")
    for key, low in (("steps", 3), ("pitfalls", 2)):
        if not isinstance(rule.get(key), list) or len(rule[key]) < low:
            report.error("rule", f"'{key}' needs at least {low} entries")
    if not isinstance(rule.get("table", ""), str):
        report.error("rule", "'table' must be a string")

    items = data.get("items") or []
    keys = [item.get("key") for item in items]
    if len(keys) != len(set(keys)):
        report.error("items", "duplicate keys")
    legacy = {s["key"]: s for s in source["legacy_sentences"] + source["legacy_review_sentences"]}
    for key in sorted(set(legacy) - set(keys)):
        report.error("items", f"legacy item {key} is missing")
    new = [k for k in keys if isinstance(k, str) and re.fullmatch(r"n\d\d", k)]
    want = 30 if hard else 12
    if len(new) != want:
        report.error("items", f"expected exactly {want} new items n01…, found {len(new)}")
    for key in keys:
        if key not in legacy and key not in new:
            report.error("items", f"unexpected key {key!r}")

    german: dict[str, str] = {}

    def remember(where: str, text: str) -> None:
        key = norm(text)
        if key in german:
            report.error(where, f"duplicate German sentence (also {german[key]}): {text}")
        german[key] = where

    for item in items:
        where = f"item {item.get('key')}"
        need_text(report, where, item, "de", "en", "focus", "explanation", "pattern")
        de = item.get("de", "")
        numbers = cloze_numbers(de)
        if not numbers:
            report.error(where, "no cloze gap {{c1::…}}")
        elif numbers != list(range(1, len(numbers) + 1)):
            report.error(where, f"cloze numbers must start at c1 without holes: {numbers}")
        for match in CLOZE_RE.finditer(de):
            answer, hint = match.group(2), match.group(3)
            if hint and hint.strip().lower() == answer.strip().lower():
                report.error(where, f"hint equals answer: {answer}")
            if answer.lower() in item.get("focus", "").lower().replace("*", "") and len(answer) > 3:
                report.warn(where, f"focus may reveal the answer '{answer}'")
        if item.get("key") in legacy:
            old = legacy[item["key"]]
            if without_hints(de) != old["de"] and not item.get("correction"):
                report.error(where, f"legacy German changed without 'correction':\n    old: {old['de']}\n    new: {without_hints(de)}")
            if numbers != cloze_numbers(old["de"]):
                report.error(where, "cloze numbers must stay the same as the legacy note (review history)")
            want_card = not item["key"].startswith("r")
            if item.get("sentence_card") is not want_card:
                report.error(where, f"sentence_card must be {str(want_card).lower()}")
        elif item.get("sentence_card") is not True:
            report.error(where, "new items need sentence_card: true")
        mistake = item.get("mistake") or {}
        need_text(report, f"{where}.mistake", mistake, "wrong", "why")
        if norm(mistake.get("wrong", "")) == norm(strip_cloze(de)):
            report.error(where, "mistake.wrong equals the correct sentence")
        remember(where, strip_cloze(de))
        for i, text in enumerate(check_pairs(report, f"{where}.examples", item.get("examples"))):
            remember(f"{where}.examples[{i}]", text)
        words = item.get("words", [])
        if not isinstance(words, list) or len(words) > 3:
            report.error(where, "'words' must be a list of at most 3")
        else:
            for i, word in enumerate(words):
                need_text(report, f"{where}.words[{i}]", word, "de", "en")

    drills = data.get("drills") or []
    low = 18 if hard else 14
    if len(drills) < low:
        report.error("drills", f"need at least {low}, found {len(drills)}")
    types = [d.get("type") for d in drills]
    if len(set(types) & DRILL_TYPES) < 5:
        report.error("drills", f"need at least 5 different types, found {sorted(set(types))}")
    if types.count("concept") < 3:
        report.error("drills", "need at least 3 concept drills")
    dkeys = [d.get("key") for d in drills]
    if len(dkeys) != len(set(dkeys)) or not all(isinstance(k, str) and re.fullmatch(r"d\d\d", k) for k in dkeys):
        report.error("drills", "keys must be unique d01, d02, …")
    for drill in drills:
        where = f"drill {drill.get('key')} ({drill.get('type')})"
        if drill.get("type") not in DRILL_TYPES:
            report.error(where, "unknown type")
            continue
        need_text(report, where, drill, "instruction", "prompt", "answer", "explanation")
        kind = drill["type"]
        if kind == "concept":
            for i, text in enumerate(check_pairs(report, f"{where}.examples", drill.get("examples"))):
                remember(f"{where}.examples[{i}]", text)
            continue
        remember(f"{where}.answer", drill.get("answer", ""))
        if kind == "choice":
            options = drill.get("options")
            if not isinstance(options, list) or not 3 <= len(options) <= 4 or len(set(options)) != len(options):
                report.error(where, "needs 3–4 distinct options")
            elif drill.get("correct") not in options:
                report.error(where, "'correct' must be one of the options")
            if "___" not in drill.get("prompt", ""):
                report.error(where, "prompt needs ___")
        if kind == "order" and " / " not in drill.get("prompt", ""):
            report.error(where, "prompt parts must be separated by ' / '")
        if kind in {"error", "transform"} and norm(drill.get("prompt", "")) == norm(drill.get("answer", "")):
            report.error(where, "prompt and answer are identical")


def check_themen(data: dict, source: dict, report: Report) -> None:
    need_text(report, "topic", data, "topic_id", "title_de", "title_en", "intro")
    phrases = data.get("phrases") or []
    legacy = {p["key"]: p for p in source["legacy_phrases"]}
    keys = [p.get("key") for p in phrases]
    for key in sorted(set(legacy) - set(keys)):
        report.error("phrases", f"legacy phrase {key} missing")
    new = [k for k in keys if isinstance(k, str) and re.fullmatch(r"n\d\d", k)]
    if len(new) != 6:
        report.error("phrases", f"expected 6 new phrases, found {len(new)}")
    seen = {}
    for phrase in phrases:
        where = f"phrase {phrase.get('key')}"
        need_text(report, where, phrase, "de", "en", "usage", "grammar")
        if phrase.get("key") in legacy and phrase.get("de") != legacy[phrase["key"]]["de"] and not phrase.get("correction"):
            report.error(where, "legacy German changed without 'correction'")
        check_pairs(report, f"{where}.alternatives", phrase.get("alternatives"), (1, 2))
        key = norm(phrase.get("de", ""))
        if key in seen:
            report.error(where, f"duplicate of {seen[key]}")
        seen[key] = where


def check_verbs(data: dict, source: dict, report: Report) -> None:
    verbs = data.get("verbs") or []
    keys = [v.get("key") for v in verbs]
    if len(keys) != len(set(keys)):
        report.error("verbs", "duplicate keys")
    for verb in source["legacy_verbs"]:
        if verb["infinitiv"] not in keys:
            report.error("verbs", f"legacy verb {verb['infinitiv']} missing")
    if sum(bool(v.get("new")) for v in verbs) != 40:
        report.error("verbs", "expected 40 new verbs")
    for verb in verbs:
        where = f"verb {verb.get('key')}"
        need_text(report, where, verb, "infinitiv", "meaning", "praesens", "praeteritum",
                  "partizip2", "hilfsverb", "konjunktiv2", "imperativ")
        if verb.get("hilfsverb") not in {"haben", "sein", "haben/sein"}:
            report.error(where, "hilfsverb must be haben, sein or haben/sein")
        check_pairs(report, f"{where}.examples", verb.get("examples"))


def validate(path: Path) -> Report:
    report = Report(path.name)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        report.error("file", f"cannot read JSON: {error}")
        return report
    source_path = INPUTS / path.name
    if not source_path.exists():
        report.error("file", f"no input file {source_path.name}")
        return report
    source = json.loads(source_path.read_text())
    tid = source["topic_id"]
    if tid == "verbs":
        check_verbs(data, source, report)
    elif tid.startswith("themen"):
        check_themen(data, source, report)
    else:
        check_grammar(data, source, report)
    return report


def main(argv: list[str]) -> int:
    paths = sorted(CONTENT.glob("*.json")) if argv == ["--all"] else [Path(a) for a in argv]
    if not paths:
        print(__doc__)
        return 2
    failed = 0
    for path in paths:
        report = validate(path)
        for line in report.warnings:
            print(f"  warning · {report.name} · {line}")
        for line in report.errors:
            print(f"  ERROR · {report.name} · {line}")
        failed += bool(report.errors)
        print(f"{'OK' if not report.errors else 'FAILED'}  {report.name}"
              f"  ({len(report.errors)} errors, {len(report.warnings)} warnings)")
    if argv == ["--all"]:
        # A new sentence must not repeat a sentence of another topic (the
        # sentences deck would get two identical cards). Legacy pairs are kept.
        owners: dict[str, list[str]] = {}
        for path in paths:
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            for entry in data.get("items", []) + data.get("phrases", []):
                owners.setdefault(norm(strip_cloze(entry.get("de", ""))), []).append(f"{path.stem}:{entry.get('key')}")
        for text, where in owners.items():
            if len(where) > 1 and any(w.split(":")[1].startswith("n") for w in where):
                print(f"  ERROR · cross-topic duplicate sentence: {', '.join(where)} | {text}")
                failed += 1
        expected = {p.name for p in INPUTS.glob("*.json")}
        missing = sorted(expected - {p.name for p in paths})
        if missing:
            print(f"MISSING content files: {len(missing)}: {', '.join(missing[:10])}…")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
