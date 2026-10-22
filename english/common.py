"""Shared paths and the deck catalogues for the kizamu-english C1 and C2 decks.

The level comes from the environment: KE_LEVEL=C1 or C2 (default C2). Each level has
its own source folder english/<level>/ (selection, content, catalogue) and its own data
folder $KIZAMU_DATA/english/<level>/ (build, out); the evidence pool from the old decks
(shared/) and the audio clips (audio/) are shared by both levels.

Stdlib only, so the validator also runs with the system python3.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from kizamu.paths import DATA

SRC = Path(__file__).resolve().parent
WORK = DATA / "english"
LEVELS = ["C1", "C2"]
LEVEL = os.environ.get("KE_LEVEL", "C2").upper()
if LEVEL not in LEVELS:
    raise SystemExit(f"KE_LEVEL must be one of {LEVELS}, not {LEVEL!r}")
LEVEL_DIR = SRC / LEVEL
CONTENT = LEVEL_DIR / "content"
SELECTION = LEVEL_DIR / "selection"
CATALOGUE = LEVEL_DIR / "catalogue.json"
BUILD = WORK / LEVEL / "build"
OUT = WORK / LEVEL / "out"
SHARED = WORK / "shared"
AUDIO = WORK / "audio" / "qwen"
SNAPSHOT = DATA / "german" / "vocab" / "build" / "source.anki21"

DECK_ROOT = f"kizamu-english::{LEVEL}"
SET_SIZE = 50


def level_dir(level: str) -> Path:
    return SRC / level


def level_build(level: str) -> Path:
    return WORK / level / "build"


# Ranked categories are cut into sets of SET_SIZE notes by importance (Set 01 = most
# useful). Topical categories have fixed parts. `parts` is the number of decks.
C2_CATEGORIES = [
    {"key": "collocations", "number": "01", "title": "Collocations", "kind": "collocation",
     "ranked": True, "parts": 9,
     "scope": "Strong word partnerships that educated native speakers use and learners get wrong: "
              "verb + noun (wield influence, draw a distinction), adjective + noun (a sweeping "
              "generalization, a vested interest), adverb + adjective (bitterly disappointed, "
              "painfully aware), noun + noun / noun + of (a stroke of luck), verb + adverb "
              "(categorically deny). Not idioms, not phrasal verbs."},
    {"key": "phrasal-verbs", "number": "02", "title": "Phrasal verbs", "kind": "phrasal verb",
     "ranked": True, "parts": 6,
     "scope": "Phrasal and prepositional verbs in their idiomatic senses that a C1 speaker often "
              "does not use actively (gloss over, iron out, fob off, rein in, hash out, chime in, "
              "peter out). No basic ones a C1 speaker knows (give up, find out, look after)."},
    {"key": "idioms", "number": "03", "title": "Idioms", "kind": "idiom",
     "ranked": True, "parts": 9,
     "scope": "Current idioms and fixed figurative expressions that Americans really use today "
              "(move the goalposts, a tall order, par for the course, a hill to die on, the "
              "elephant in the room). No dated or rare ones (raining cats and dogs, the bee's "
              "knees), no idioms every intermediate learner knows (piece of cake, break the ice)."},
    {"key": "conversation", "number": "04", "title": "Conversation & discourse", "kind": "expression",
     "ranked": True, "parts": 6,
     "scope": "Spoken phrases that make speech sound native: hedging and softening (I'd argue, "
              "it's not ideal), agreeing / disagreeing / conceding (fair point, I'm not sure I buy "
              "that), reacting (tell me about it, that tracks), linking ideas in speech (that said, "
              "if anything, by the same token), emphasis and understatement (to put it mildly, not "
              "exactly), polite requests and refusals (I'll pass, take a rain check)."},
    {"key": "informal", "number": "05", "title": "Informal American English", "kind": "informal",
     "ranked": True, "parts": 4,
     "scope": "Casual and slang American English an adult hears every day in conversation, TV and "
              "online, still current in the 2020s (bail on, flake, sketchy, legit, low-key, a "
              "no-brainer, swing by, a side hustle, bummed). Mark slang clearly. No vulgar terms, "
              "no short-lived teen slang."},
    {"key": "work-academic", "number": "06", "title": "Work & academic English", "kind": "expression",
     "ranked": False, "parts": 5,
     "part_titles": ["Meetings & discussion", "Emails & written messages", "Academic writing",
                     "Presentations & talks", "Feedback, negotiation & teamwork"],
     "scope": "Expressions for a researcher working in English: meetings (circle back, take this "
              "offline), emails (follow up on, loop in, flag), papers (to the best of our knowledge, "
              "beyond the scope of, corroborate, a caveat), talks (bear with me, the takeaway), "
              "feedback and negotiation (push back on, a non-starter, meet halfway)."},
    {"key": "words", "number": "07", "title": "Advanced words", "kind": "word",
     "ranked": True, "parts": 10,
     "scope": "Single words at C1+/C2 that educated native speakers use in writing and serious "
              "conversation (conflate, ostensibly, perfunctory, tenuous, galvanize, myopic, "
              "exacerbate, ubiquitous). Neither basic nor obscure: no showy GRE words that natives "
              "rarely say (sesquipedalian, pulchritude)."},
    {"key": "nuance", "number": "08", "title": "Nuance & confusables", "kind": "nuance",
     "ranked": False, "parts": 3,
     "part_titles": ["Commonly confused words", "Near-synonyms with different connotations",
                     "Words natives use differently from the dictionary"],
     "scope": "Pairs and groups that C1 speakers mix up or use with the wrong connotation: "
              "imply/infer, comprise/compose, flaunt/flout, discreet/discrete; stubborn/tenacious/"
              "obstinate, frugal/stingy, notorious/famous; literally, ironic, decimate, nauseous, "
              "begs the question, enormity."},
    {"key": "pronunciation", "number": "09", "title": "Pronunciation & connected speech",
     "kind": "pronunciation", "ranked": False, "parts": 3,
     "part_titles": ["Commonly mispronounced words", "Word stress and stress shift",
                     "Connected speech in American English"],
     "scope": "American pronunciation that gives C1 speakers away: words often mispronounced "
              "(epitome, hyperbole, segue, debris, suite, colonel, hierarchy, determine); stress "
              "and stress shift (REcord / reCORD, PHOtograph / phoTOGraphy, CAtegory); connected "
              "speech (gonna, wanna, flap t in water/better, glottal stop in button, can vs. can't, "
              "didja, whaddaya, linking, weak forms of function words)."},
    {"key": "grammar", "number": "10", "title": "Advanced grammar", "kind": "grammar",
     "ranked": False, "parts": 5,
     "part_titles": ["Emphasis: inversion, cleft sentences & fronting",
                     "Conditionals, wishes & hypothetical meaning",
                     "Modals: deduction, speculation & the past",
                     "Clauses: participles, ellipsis & substitution",
                     "Nouns, articles, quantifiers & agreement"],
     "scope": "C1-C2 grammar points that make writing and speech sound native and precise: "
              "negative inversion, cleft sentences, fronting; mixed conditionals, were to, should "
              "you, but for, if it weren't for, wish / if only, it's (high) time; must have, can't "
              "have, might well, needn't have vs. didn't need to, be bound to, would rather; "
              "participle clauses, reduced relatives, ellipsis and substitution (so / not / do so); "
              "zero article with abstract nouns, the + adjective, a number of / the number of, "
              "none of + verb agreement, collective nouns in American English, whom."},
]
C1_CATEGORIES = [
    {"key": "collocations", "number": "01", "title": "Collocations", "kind": "collocation",
     "ranked": True, "parts": 9,
     "scope": "Frequent strong collocations at B2-C1 that educated speakers use every day and "
              "learners often get slightly wrong: verb + noun (raise awareness, meet a deadline, "
              "reach an agreement, pose a threat, take something into account), adjective + noun "
              "(a heated debate, a major setback, a key factor, a strong argument), adverb + "
              "adjective (deeply concerned, highly recommended, fully aware, widely used), "
              "preposition phrases (on purpose, in charge of, at risk, under pressure). Not idioms, "
              "not phrasal verbs, nothing a B1 learner knows (make a mistake, take a photo)."},
    {"key": "phrasal-verbs", "number": "02", "title": "Phrasal verbs", "kind": "phrasal verb",
     "ranked": True, "parts": 6,
     "scope": "The most frequent phrasal verbs of everyday and working life in their main "
              "senses (come up with, put off, figure out, bring up, turn down, cut back on, run "
              "into, look into, set up, take over, point out, end up, go through, carry on, sort "
              "out, get across). No A2-B1 basics (get up, look for, turn on the light)."},
    {"key": "idioms", "number": "03", "title": "Idioms", "kind": "idiom",
     "ranked": True, "parts": 9,
     "scope": "Well-known idioms that every educated American knows and uses (break the ice, "
              "the last straw, hit the nail on the head, a blessing in disguise, red tape, a rule "
              "of thumb, turn a blind eye, cost an arm and a leg, under the weather, get the hang "
              "of something, in the long run, on the fence, call it a day, cut to the chase, the "
              "ball is in your court). Current, not dated."},
    {"key": "conversation", "number": "04", "title": "Conversation & discourse", "kind": "expression",
     "ranked": True, "parts": 6,
     "scope": "Everyday spoken phrases and discourse markers that make conversation flow: "
              "opening and closing (how's it going, I'd better get going), agreeing and disagreeing "
              "politely (I see what you mean, I'm not so sure), asking for clarification (what do "
              "you mean by, sorry, I didn't catch that), giving opinions (if you ask me, I'd say), "
              "checking understanding (does that make sense?), changing topic (by the way, "
              "anyway), polite requests, offers and refusals (would you mind, I'm afraid I can't)."},
    {"key": "informal", "number": "05", "title": "Informal American English", "kind": "informal",
     "ranked": True, "parts": 4,
     "scope": "Common informal American English that adults use daily (hang out, grab a bite, no "
              "worries, a big deal, stuff, awesome, you guys, totally, freak out, chill, a "
              "bummer, hit the road, crash, be beat). Current and widely used; no vulgar terms."},
    {"key": "work-academic", "number": "06", "title": "Work & academic English", "kind": "expression",
     "ranked": False, "parts": 5,
     "part_titles": ["Meetings & discussion", "Emails & written messages", "Academic writing",
                     "Presentations & talks", "Feedback, negotiation & teamwork"],
     "scope": "Core functional language of work and study: meetings (let's get started, the "
              "next item on the agenda, can I just add something), emails (I'm writing to, please "
              "find attached, as discussed, let me know if, I look forward to), academic writing "
              "(according to, this suggests that, in contrast, a significant increase, the aim of "
              "this study), talks (I'd like to start by, as you can see, to sum up), feedback and "
              "negotiation (could you clarify, I'd suggest, we've reached an agreement)."},
    {"key": "words", "number": "07", "title": "Key words", "kind": "word",
     "ranked": True, "parts": 10,
     "scope": "Single words at B2-C1 that an educated speaker uses actively in work, study and "
              "the news (assess, crucial, substantial, implement, adequate, controversial, "
              "enhance, inevitable, reluctant, thorough, vague, reliable, emerge, acknowledge, "
              "sustainable, priority, bias, insight). Mostly Zipf 3.3-4.8, many from the Academic "
              "Word List and EVP C1. Not basic (important, decide) and not C2."},
    {"key": "nuance", "number": "08", "title": "Nuance & confusables", "kind": "nuance",
     "ranked": False, "parts": 3,
     "part_titles": ["Commonly confused words", "Choosing the right word",
                     "False friends and common usage errors"],
     "scope": "Everyday word choice that learners get wrong: borrow vs. lend, rob vs. steal, say / "
              "tell / speak / talk, make vs. do, raise vs. rise, remember vs. remind, bring vs. "
              "take, lose vs. loose, advice vs. advise; job / work / career, trip / travel / "
              "journey, chance / opportunity / possibility, fun vs. funny; false friends of German "
              "and other European speakers (gift, chef, handy, sympathetic) and usage errors "
              "(explain me, discuss about, since three years)."},
    {"key": "pronunciation", "number": "09", "title": "Pronunciation", "kind": "pronunciation",
     "ranked": False, "parts": 3,
     "part_titles": ["Sounds learners mix up", "Silent letters and tricky spellings",
                     "Word stress, sentence stress and intonation"],
     "scope": "American pronunciation basics that still trouble C1 speakers: th (think / this), "
              "v vs. w, ship / sheep, full / fool, bad / bat (final voiced consonants), -ed and -s "
              "endings, the schwa; silent letters and spellings (knife, debt, though / through / "
              "tough, -ough); word stress rules (-tion, -ic, compound nouns), sentence stress on "
              "content words, contrastive stress, rising and falling intonation."},
    {"key": "grammar", "number": "10", "title": "Grammar", "kind": "grammar",
     "ranked": False, "parts": 5,
     "part_titles": ["Tenses and aspect", "Verb patterns",
                     "Conditionals, passives & reported speech", "Clauses & linking",
                     "Articles, quantifiers, modals & comparison"],
     "scope": "B2-C1 grammar that must be automatic: present perfect vs. past simple, present "
              "perfect continuous, past perfect, future forms, stative verbs; gerund vs. "
              "infinitive (stop / remember / try + -ing or to), make / let / allow, used to / be "
              "used to / get used to, causative have / get; zero to third conditionals, unless, in "
              "case, passives in all tenses, It is said that, reported speech and reporting verbs; "
              "defining and non-defining relative clauses, although / despite / however / "
              "whereas, so that / in order to, so / such, too / enough; articles, much / many / "
              "few / little, present modals of obligation and deduction, comparatives with "
              "intensifiers, question tags, indirect questions."},
]
CATEGORIES = C1_CATEGORIES if LEVEL == "C1" else C2_CATEGORIES
BY_KEY = {c["key"]: c for c in CATEGORIES}

REGISTERS = ["formal", "neutral", "informal", "slang"]
REGIONS = ["US", "UK", "both"]
DRILLS = ["gap", "say", "listen"]


def part_titles(category: dict) -> list[str]:
    if category.get("part_titles"):
        return category["part_titles"]
    return [f"Set {i:02d}" for i in range(1, category["parts"] + 1)]


def part_id(category: dict, index: int) -> str:
    """File stem of one deck part, e.g. 03-idioms-02 (index starts at 1)."""
    return f"{category['number']}-{category['key']}-{index:02d}"


def all_parts() -> list[dict]:
    parts = []
    for category in CATEGORIES:
        for index, title in enumerate(part_titles(category), 1):
            parts.append({"part_id": part_id(category, index), "category": category["key"],
                          "index": index, "title": title,
                          "deck": f"{DECK_ROOT}::{category['number']} {category['title']}::"
                                  f"{index:02d} {title}" if not category["ranked"] else
                                  f"{DECK_ROOT}::{category['number']} {category['title']}::{title}"})
    return parts


def normalize(term: str) -> str:
    """Key for duplicate detection: case, accents, sb/sth placeholders and punctuation removed."""
    text = unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode().casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(sb|sth|someone|somebody|something|one's|oneself|your|yourself|my|his|her|their)\b", " ", text)
    text = re.sub(r"^(to|a|an|the)\s+", "", text.strip())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def bold_terms(text: str) -> list[str]:
    return re.findall(r"\*\*(.+?)\*\*", text)


def strip_marks(text: str) -> str:
    """Plain text of a sentence: **bold** and {{gap}} markers removed."""
    text = re.sub(r"\{\{(.+?)\}\}", r"\1", text)
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def load_content(skip_invalid: bool = False) -> dict[str, dict]:
    content = {}
    for path in sorted(CONTENT.glob("*.json")):
        try:
            content[path.stem] = json.loads(path.read_text())
        except json.JSONDecodeError:
            if not skip_invalid:
                raise
    return content


def spoken_texts(data: dict) -> list[str]:
    """Every English string that gets an audio clip, in card order."""
    texts: list[str] = []
    for entry in data["entries"]:
        if entry.get("say_term", True):
            texts.append(entry.get("spoken_term") or entry["term"])
        texts += [strip_marks(x) for x in entry["examples"]]
        # A listen drill may give the casual spelling the voice should say ("Wouldja mind…").
        texts.append(entry["drill"].get("spoken") or strip_marks(entry["drill"]["sentence"]))
    return texts


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
