"""Write publishing/ankiweb.md: what to share on AnkiWeb, with title, tags and description.

AnkiWeb takes shared decks up to 250 MB (the size of the exported .apkg), so the large
decks are shared by subdeck: German grammar by level, American English by category.
Counts and topic names come from the packages in $KIZAMU_DATA/public/; every share is
exported once to check its size.

    python -m kizamu.ankiweb_listings
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from anki.collection import Collection, DeckIdLimit, ExportAnkiPackageOptions, ImportAnkiPackageOptions
from anki.collection import ImportAnkiPackageRequest

from kizamu.paths import DATA, ROOT

SOURCE = DATA / "public"
TARGET = ROOT / "publishing" / "ankiweb.md"
LIMIT_MB = 250
TITLE_MAX = 60  # AnkiWeb cuts longer titles

LINKS = """All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub."""
GERMAN_AUDIO = "Every German sentence has audio (a natural German voice, checked by speech recognition)."
ENGLISH_AUDIO = ("Every card shows the register (formal, neutral, informal, slang) and notes when an item is "
                 "American or British only. Every term and example has audio (a natural American English voice, "
                 "checked by speech recognition).")

VOCAB = {
    "A1": ("beginner", "Other levels: kizamu German Vocabulary A2 and B1."),
    "A2": ("elementary", "Other levels: kizamu German Vocabulary A1 and B1."),
    "B1": ("intermediate", "Other levels: kizamu German Vocabulary A1 and A2."),
}

GRAMMAR = {
    "A1": "A1", "A2": "A2", "B1": "B1", "B2": "B2",
    "Hard grammar": "Hard grammar (B1+ to C1)", "Verben": "Irregular verbs",
}

# Learner-facing one-liners per English category (level, number) → text.
ENGLISH = {
    ("C1", "01"): "Strong word partnerships that educated speakers use every day and learners often get "
                  "slightly wrong: raise awareness, meet a deadline, pose a threat, a heated debate.",
    ("C1", "02"): "The most frequent phrasal verbs of everyday and working life, in their main senses: come up "
                  "with, put off, figure out, bring up, turn down, cut back on.",
    ("C1", "03"): "Well-known idioms that every educated American knows and uses: break the ice, the last straw, "
                  "hit the nail on the head, a blessing in disguise, red tape.",
    ("C1", "04"): "Everyday spoken phrases and discourse markers that make conversation flow: how's it going, "
                  "I'd better get going, I see what you mean, sorry, what do you mean by …",
    ("C1", "05"): "Common informal American English that adults use daily: hang out, grab a bite, no worries, "
                  "a big deal, you guys, freak out, a bummer. No vulgar terms.",
    ("C1", "06"): "The core language of work and study: meetings, emails, academic writing, presentations, "
                  "feedback and negotiation.",
    ("C1", "07"): "Single words at B2–C1 that an educated speaker uses actively at work, in study and in the "
                  "news: assess, crucial, substantial, implement, reluctant, thorough.",
    ("C1", "08"): "Everyday word choice that learners get wrong: borrow vs. lend, rob vs. steal, say / tell / "
                  "speak / talk, raise vs. rise, remember vs. remind, false friends.",
    ("C1", "09"): "American pronunciation basics that still trouble advanced learners: th, v vs. w, ship / sheep, "
                  "-ed and -s endings, the schwa, silent letters, word and sentence stress, intonation.",
    ("C1", "10"): "B2–C1 grammar that must be automatic: tenses and aspect, verb patterns, conditionals, "
                  "passives and reported speech, clauses and linking, articles, quantifiers, modals.",
    ("C2", "01"): "Strong word partnerships that educated native speakers use and learners get wrong: wield "
                  "influence, draw a distinction, a sweeping generalization, a vested interest.",
    ("C2", "02"): "Phrasal verbs in their idiomatic senses that even C1 speakers rarely use actively: gloss over, "
                  "iron out, fob off, rein in, hash out, chime in, peter out.",
    ("C2", "03"): "Current idioms that Americans really use today: move the goalposts, a tall order, par for the "
                  "course, a hill to die on, the elephant in the room. No dated ones.",
    ("C2", "04"): "Spoken phrases that make speech sound native: hedging and softening (I'd argue, it's not "
                  "ideal), conceding (fair point), reacting (tell me about it), linking ideas (that said).",
    ("C2", "05"): "Casual and slang American English heard every day in conversation, on TV and online: bail on, "
                  "flake, sketchy, legit, low-key, a no-brainer, a side hustle. No vulgar terms.",
    ("C2", "06"): "Advanced expressions for work and research in English: meetings (circle back, take this "
                  "offline), emails (loop in, flag), papers (beyond the scope of), talks (the takeaway).",
    ("C2", "07"): "Single words at C1+/C2 that educated native speakers use in writing and serious "
                  "conversation: conflate, ostensibly, perfunctory, tenuous, galvanize, exacerbate.",
    ("C2", "08"): "Words that advanced speakers mix up or use with the wrong connotation: imply / infer, "
                  "comprise / compose, flaunt / flout, stubborn / tenacious / obstinate, literally, ironic.",
    ("C2", "09"): "American pronunciation that gives advanced speakers away: often mispronounced words "
                  "(epitome, hyperbole, segue, colonel), stress shift (REcord / reCORD) and connected speech.",
    ("C2", "10"): "C1–C2 grammar that makes writing and speech precise: inversion, cleft sentences, fronting, "
                  "mixed conditionals, wish / if only, modals of deduction, participle clauses, ellipsis.",
}
ENGLISH_TAGS = {
    "01": "collocations", "02": "phrasal-verbs", "03": "idioms", "04": "conversation speaking",
    "05": "slang informal", "06": "business-english academic-english", "07": "vocabulary",
    "08": "confusing-words", "09": "pronunciation", "10": "grammar",
}


def stats(col: Collection, deck: str) -> dict:
    did = col.decks.id_for_name(deck)
    ids = [did] + [child for _, child in col.decks.children(did)]
    rows = col.db.all(f"select nid from cards where did in ({','.join(map(str, ids))})")
    children = [name.split("::")[-1] for name, _ in col.decks.children(did)]
    return {"did": did, "notes": len({r[0] for r in rows}), "cards": len(rows), "children": children}


def size_mb(col: Collection, did: int, folder: Path) -> float:
    target = folder / f"{did}.apkg"
    col.export_anki_package(out_path=str(target), limit=DeckIdLimit(deck_id=did),
                            options=ExportAnkiPackageOptions(with_scheduling=False, with_deck_configs=True,
                                                             with_media=True))
    size = target.stat().st_size / 1e6
    target.unlink()
    return size


def topics(children: list[str]) -> str:
    return " · ".join(re.sub(r"^\d+\s+", "", name) for name in sorted(children))


def vocab_listing(level: str, s: dict) -> dict:
    kind, others = VOCAB[level]
    text = f"""{s['notes']:,} German {level} words, {s['cards']:,} cards: Deutsch → English and English → Deutsch.

Every answer shows:
- the word with its article and plural (der Abend, die Abende), or the verb forms
- the meaning, with a short cue where one spelling has two words (die Bank: bank or bench)
- related words and contrasts, and a usage note
- three example sentences with translations

Every word and every example sentence has audio (a natural German voice, checked by speech recognition).

{others} For grammar: kizamu German Grammar and kizamu German Sentences."""
    return {"title": f"kizamu German Vocabulary {level} · with audio",
            "tags": f"german deutsch vocabulary wortschatz {level} {kind} audio kizamu", "text": text}


def sentences_listing(s: dict) -> dict:
    text = f"""Whole German sentences, from A1 to B2 and the hard grammar topics, plus situational phrases (Themen: greetings, at the doctor, on the phone, shopping, housing, emergencies, ...). {s['notes']:,} notes, {s['cards']:,} cards.

Card types:
- English → Deutsch: say or write the German sentence
- Listening: hear the sentence, understand it, then check the text
- Themen: phrases in both directions, with usage notes and alternatives (formal / informal, Austrian and Swiss variants where they matter)

Every sentence has audio (a natural German voice, checked by speech recognition).

Goes well with: kizamu German Grammar (the same topics as gap sentences and drills, with explanations) and kizamu German Vocabulary A1 / A2 / B1."""
    return {"title": "kizamu German Sentences A1–C1 · with audio",
            "tags": "german deutsch sentences listening speaking phrases A1 A2 B1 B2 audio kizamu", "text": text}


def grammar_listing(part: str, s: dict) -> dict:
    family = ("Part of kizamu German Grammar (6 decks): A1 · A2 · B1 · B2 · Hard grammar (B1+ to C1) · "
              "Irregular verbs. Goes well with kizamu German Sentences (the same topics as whole sentences) "
              "and kizamu German Vocabulary A1 / A2 / B1.")
    if part == "Verben":
        text = f"""{s['notes']:,} irregular German verbs with all key forms: Präsens, Präteritum, Perfekt (with haben or sein), Konjunktiv II and Imperativ. {s['cards']:,} cards, with audio.

{family}"""
        return {"title": "kizamu German Irregular Verbs · with audio",
                "tags": "german deutsch grammar grammatik verbs verben irregular unregelmaessig audio kizamu",
                "text": text}
    level = "B1+ to C1" if part == "Hard grammar" else part
    intro = (f"{len(s['children'])} deep-dive topics from B1+ to C1" if part == "Hard grammar"
             else f"German grammar at {part}: {len(s['children'])} topics")
    text = f"""{intro}, {s['notes']:,} notes, {s['cards']:,} cards, one subdeck per topic:
{topics(s['children'])}

Card types: Fill the gap (a German sentence with a gap, an English context and a focus cue), Rule check, Transform, Find the mistake, Word order, Choose the form, Join the sentences.

The back of every card explains this sentence (not only the general rule), shows a typical mistake and why it is wrong, and gives two more examples and the topic's rule table. New cards come in teaching order: rule checks first, then the gap sentences, then the other drills.

{GERMAN_AUDIO}

{family}"""
    title = "kizamu German Grammar · Hard topics B1+–C1" if part == "Hard grammar" else f"kizamu German Grammar {part} · with audio"
    return {"title": title,
            "tags": f"german deutsch grammar grammatik cloze {level.replace(' to ', ' ').replace('+', '')} audio kizamu",
            "text": text}


def english_listing(level: str, category: str, s: dict, all_categories: list[str]) -> dict:
    number = category[:2]
    children = sorted(s["children"])
    if all(re.match(r"Set \d+", c) for c in children):
        layout = f"in {len(children)} sets of 50; Set 01 holds the most useful items"
    else:
        layout = f"in {len(children)} parts: {topics(children)}"
    usage = "a new sentence with a gap and a plain-English hint"
    if number == "09":
        usage = ("a sentence to say aloud" if level == "C1"
                 else "a sentence to say aloud, or (connected speech) audio only")
    other = "C2" if level == "C1" else "C1"
    text = f"""{ENGLISH[(level, number)]} {s['notes']:,} notes, {s['cards']:,} cards, {layout}.

Two cards per note:
- Meaning: the term in a real sentence → meaning, how to use it, pattern, three examples, common mistake, related items, origin
- Usage: {usage}

{ENGLISH_AUDIO}

Part {int(number)} of 10 of kizamu American English {level}: {" · ".join(all_categories)}. No item repeats the {other} level."""
    name = re.sub(r"^\d+\s+", "", category)
    return {"title": f"kizamu English {level} · {category}",
            "tags": f"english american-english {ENGLISH_TAGS[number]} {level} advanced audio kizamu",
            "text": text, "name": name}


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    shares = []  # (deck, size, listing)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        def open_package(name: str) -> Collection:
            folder = tmp / name
            folder.mkdir()
            col = Collection(str(folder / "collection.anki2"))
            col.import_anki_package(ImportAnkiPackageRequest(
                package_path=str((SOURCE / f"{name}.apkg").resolve()),
                options=ImportAnkiPackageOptions(with_scheduling=False, with_deck_configs=True)))
            return col

        def add(col: Collection, deck: str, make) -> None:
            s = stats(col, deck)
            shares.append((deck, size_mb(col, s["did"], tmp), make(s)))
            print(f"{deck}: {s['notes']} notes, {shares[-1][1]:.1f} MB", flush=True)

        for level in VOCAB:
            col = open_package(f"kizamu-german-vocab-{level}")
            add(col, f"kizamu-german::vocab::{level}", lambda s, level=level: vocab_listing(level, s))
            col.close()
        col = open_package("kizamu-german-grammar")
        for part in GRAMMAR:
            add(col, f"kizamu-german::grammar::{part}", lambda s, part=part: grammar_listing(part, s))
        col.close()
        col = open_package("kizamu-german-sentences")
        add(col, "kizamu-german::sentences", sentences_listing)
        col.close()
        for level in ["C1", "C2"]:
            col = open_package(f"kizamu-english-{level}")
            root = f"kizamu-english::{level}"
            categories = sorted(name.split("::")[-1] for name, _ in col.decks.children(col.decks.id_for_name(root))
                                if name.count("::") == 2)
            for category in categories:
                add(col, f"{root}::{category}",
                    lambda s, c=category, level=level: english_listing(level, c, s, categories))
            col.close()

    too_big = [deck for deck, size, _ in shares if size >= LIMIT_MB]
    assert not too_big, too_big
    long = [listing["title"] for _, _, listing in shares if len(listing["title"]) > TITLE_MAX]
    assert not long, long
    lines = [HEADER.format(count=len(shares)), "| # | Deck to share | Size |", "|---|---|---|"]
    lines += [f"| {i} | `{deck}` | {size:.0f} MB |" for i, (deck, size, _) in enumerate(shares, 1)]
    for i, (deck, size, listing) in enumerate(shares, 1):
        lines += ["", "---", "", f"## {i} · `{deck}`", "", f"**Title:** {listing['title']}", "",
                  f"**Tags:** {listing['tags']}", "", "**Description:**", "", "```",
                  listing["text"], "", LINKS, "", LICENSE[deck.startswith("kizamu-german::vocab")], "```"]
    lines += ["", "---", "", "## Links after sharing", "", "| # | Deck | AnkiWeb |", "|---|---|---|"]
    lines += [f"| {i} | `{deck}` | |" for i, (deck, _, _) in enumerate(shares, 1)]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines) + "\n")
    print(f"{len(shares)} listings → {TARGET}")


LICENSE = {
    True: "The audio is synthetic. Definitions and inflections adapted from Wiktionary (CC BY-SA 4.0). "
          "Deck license: CC BY-SA 4.0.",
    False: "The audio is synthetic. License: CC BY-SA 4.0.",
}

HEADER = """# Sharing the decks on AnkiWeb

AnkiWeb shares a **copy without scheduling**, so the decks can be shared from the
personal collection: review history, due dates and learning progress stay private.
A shared deck can be at most **250 MB** (the size of its exported `.apkg`). The large
decks are therefore shared by subdeck: German grammar by level, American English by
category. That makes {count} shares. Every share below was exported once to check its size.

This file is generated by `python -m kizamu.ankiweb_listings`; edit the texts there.

## Steps

1. Make `kizamu-decks-releases` public first. The descriptions link to it (and to
   <https://kizamu.app>), and the GitHub link does not work while the repo is private.
2. Sync Anki (desktop) so AnkiWeb has the current decks.
3. Log in at <https://ankiweb.net/decks>. Open the subdecks, and next to the deck to share
   open its menu → **Share**. Fill in the form with the title, tags and description below.
4. After the first share, download it once from AnkiWeb into an empty Anki profile and
   check the deck name and the audio.
5. AnkiWeb then shows the link of the shared deck (`https://ankiweb.net/shared/info/<number>`).
   Put the links into the table at the end of this file.

**Updating later:** click **Share** again on the same deck. The deck must keep the same
name, or AnkiWeb creates a new shared deck instead of updating the old one. Downloads and
ratings are kept.

**Tag:** the English notes carry the tag `studied_before` (items from the old decks). It is
harmless, but to leave it out: Browse → `tag:studied_before` → select all → Notes →
Remove Tags, then sync before sharing.

## What to share
"""


if __name__ == "__main__":
    main()
