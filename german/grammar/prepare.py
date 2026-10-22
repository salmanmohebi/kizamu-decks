"""Inventory the legacy grammar notes and write one authoring input per topic.

Reads the 15 October 2026 collection snapshot read-only. Every legacy note is
matched to its source line by the legacy GUID scheme, so the build can later
copy each studied card's schedule and review records to its replacement.

Outputs ($KIZAMU_DATA/german/grammar/build/):
  legacy.json           GUID -> {kind, topic, index, cards[{ord, id, reps, revlog}]}
  inputs/<topic>.json   what the authors start from
"""
from __future__ import annotations

import json
import sqlite3

from german.grammar.common import (
    BUILD, HARD_TOPICS, INPUTS, LEGACY_DECK_PREFIX, SNAPSHOT, atomic_json,
    cloze_numbers, grammar_topics, legacy_verbs, stable_guid, strip_cloze, themen_topics,
)


def snapshot_cards() -> dict[str, dict]:
    db = sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True)
    decks = {did: name.replace("\x1f", "::") for did, name in db.execute("select id, name from decks")}
    legacy = [did for did, name in decks.items() if name.startswith(LEGACY_DECK_PREFIX)]
    marks = ",".join("?" * len(legacy))
    notes: dict[str, dict] = {}
    for nid, guid, cid, ord_, reps, ctype in db.execute(
        f"select n.id, n.guid, c.id, c.ord, c.reps, c.type from cards c join notes n on n.id = c.nid "
        f"where c.did in ({marks}) order by c.ord", legacy,
    ):
        revlog = db.execute("select count() from revlog where cid = ?", (cid,)).fetchone()[0]
        note = notes.setdefault(guid, {"note_id": nid, "cards": []})
        note["cards"].append({"ord": ord_, "id": cid, "reps": reps, "type": ctype, "revlog": revlog})
    db.close()
    return notes


def main() -> None:
    cards = snapshot_cards()
    legacy: dict[str, dict] = {}

    def claim(guid: str, **info) -> dict:
        if guid not in cards:
            raise KeyError(f"Legacy note missing from snapshot: {info}")
        legacy[guid] = {**info, **cards[guid]}
        return legacy[guid]

    def studied(record: dict) -> int:
        return sum(card["revlog"] for card in record["cards"])

    INPUTS.mkdir(parents=True, exist_ok=True)
    for topic in grammar_topics():
        tid = topic["topic_id"]
        sentences = []
        for index, (de, en) in enumerate(topic["sentences"]):
            records = [claim(stable_guid(tid, str(index), kind), kind=kind, topic=tid, index=index)
                       for kind in ("cloze", "prod", "listen")]
            cloze = records[0]
            if sorted(card["ord"] + 1 for card in cloze["cards"]) != cloze_numbers(de):
                raise ValueError(f"Cloze ordinals differ from snapshot: {tid}#{index}")
            sentences.append({"key": f"g{index:02d}", "de": de, "en": en,
                              "plain": strip_cloze(de), "review_records": sum(map(studied, records))})
        reviews = []
        if topic["review"]:
            rid = topic["review"]["topic_id"]
            for index, (de, en, tip) in enumerate(topic["review"]["sentences"]):
                record = claim(stable_guid("review", rid, str(index)), kind="review", topic=tid,
                               review_topic=rid, index=index)
                reviews.append({"key": f"r{index:02d}", "de": de, "en": en, "old_tip": tip,
                                "plain": strip_cloze(de), "review_records": studied(record)})
        atomic_json(INPUTS / f"{tid}.json", {
            "topic_id": tid, "level": topic["level"], "number": topic["number"],
            "title_de": topic["title"], "tags": topic["tags"], "source": topic["path"],
            "old_explanation_md": topic["explanation_md"],
            "legacy_sentences": sentences, "legacy_review_sentences": reviews,
        })

    for number, (tid, level, title, scope) in enumerate(HARD_TOPICS, 1):
        atomic_json(INPUTS / f"{tid}.json", {
            "topic_id": tid, "level": level, "number": f"{number:02d}", "title_de": title,
            "scope": scope, "legacy_sentences": [], "legacy_review_sentences": [],
        })

    for topic in themen_topics():
        tid = topic["topic_id"]
        phrases = []
        for index, (de, en) in enumerate(topic["sentences"]):
            records = [claim(stable_guid(tid, str(index), kind), kind=kind, topic=tid, index=index)
                       for kind in ("prod", "de2en")]
            phrases.append({"key": f"t{index:02d}", "de": strip_cloze(de), "en": en,
                            "review_records": sum(map(studied, records))})
        atomic_json(INPUTS / f"{tid}.json", {
            "topic_id": tid, "level": topic["level"], "number": topic["number"] or tid.split("-")[1],
            "title_de": topic["title"], "source": topic["path"],
            "old_explanation_md": topic["explanation_md"], "legacy_phrases": phrases,
        })

    verbs = []
    for verb in legacy_verbs():
        claim(stable_guid("verb", verb["infinitiv"]), kind="verb", topic="verbs", index=verb["infinitiv"])
        verbs.append(verb)
    atomic_json(INPUTS / "verbs.json", {"topic_id": "verbs", "legacy_verbs": verbs})

    missing = set(cards) - set(legacy)
    if missing:
        raise ValueError(f"{len(missing)} snapshot notes in legacy decks were not matched to a source line")
    atomic_json(BUILD / "legacy.json", legacy)
    kinds: dict[str, list[int]] = {}
    for record in legacy.values():
        stats = kinds.setdefault(record["kind"], [0, 0, 0])
        stats[0] += 1
        stats[1] += len(record["cards"])
        stats[2] += studied(record)
    print(json.dumps({kind: dict(zip(["notes", "cards", "review_records"], v)) for kind, v in kinds.items()}, indent=2))
    print(f"inputs: {len(list(INPUTS.glob('*.json')))} files in {INPUTS}")


if __name__ == "__main__":
    main()
