"""Shared paths, legacy parsing and the topic catalogue for the kizamu grammar decks.

Stdlib + PyYAML only, so the validator also runs with the system python3.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

from kizamu.paths import DATA

CONTENT = Path(__file__).resolve().parent / "content"
WORK = DATA / "german" / "grammar"
BUILD = WORK / "build"
INPUTS = BUILD / "inputs"
AUDIO = WORK / "audio" / "qwen"
OUT = WORK / "out"
# The old grammar notes (Markdown) that the legacy cards were made from: grammar/<level>/,
# review/<level>/, themen/ and reference/irregular-verbs.md. Only prepare.py reads them.
LEGACY_NOTES = WORK / "legacy-notes"
SNAPSHOT = DATA / "german" / "vocab" / "build" / "source.anki21"

LEVELS = ["A1", "A2", "B1", "B2"]
HARD = "Hard grammar"
DECK_ROOT = "kizamu-german"
LEGACY_DECK_PREFIX = "00 - German - grammar"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
CLOZE_RE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.+?))?\}\}")
FILE_PREFIX_RE = re.compile(r"^(\d+)-")

# New hard-grammar topics. Scopes are deliberately disjoint from the A1-B2
# topics in grammar/; the authoring guide lists those too.
HARD_TOPICS = [
    ("h01-satzklammer-mittelfeld", "B1+", "Wortstellung: Satzklammer und Mittelfeld",
     "Verb-second and the sentence bracket (Satzklammer) in main clauses; order inside the Mittelfeld: pronouns before nouns, Dativ before Akkusativ for nouns but Akkusativ pronoun before Dativ pronoun, TeKaMoLo (temporal-kausal-modal-lokal), position of nicht (sentence vs. part negation), what goes into the Vorfeld and why (inversion), Nachfeld (comparisons, long phrases)."),
    ("h02-verbcluster-nebensatz", "B2", "Verbcluster im Nebensatz",
     "Verb order at the end of subordinate clauses with 2-3 verbs: modal + infinitive (dass er kommen muss), Passiv + modal (weil es repariert werden muss), Perfekt of modals with Ersatzinfinitiv where 'hat/hätte' moves BEFORE the infinitives (dass er hat kommen müssen; obwohl ich es hätte wissen sollen), Futur + modal (dass sie wird arbeiten müssen)."),
    ("h03-konjunktiv-2-modal-vergangenheit", "B2", "Konjunktiv II der Vergangenheit mit Modalverben",
     "hätte + Infinitiv + Modalverb-Infinitiv: Ich hätte früher kommen sollen / können / müssen / dürfen. Functions: regret (Bedauern), reproach (Vorwurf: Du hättest anrufen können!), missed possibility, unreal past conditions with modals; Passiv: Das hätte gemacht werden müssen. Contrast with indicative Präteritum of modals (ich sollte vs. ich hätte ... sollen)."),
    ("h04-als-ob-irreale-vergleiche", "B2", "Irreale Vergleichssätze (als ob, als wenn, als + Verb)",
     "Unreal comparisons with Konjunktiv II (and Konjunktiv I in formal writing): Er tut so, als ob er krank wäre / als wäre er krank (verb directly after 'als'), present vs. past (als ob er es nicht gewusst hätte), typical main-clause verbs (aussehen, klingen, sich verhalten, tun so, es scheint), contrast with real comparisons (wie)."),
    ("h05-wunsch-bedingung-ohne-wenn", "B2", "Irreale Wünsche und Bedingungen ohne „wenn“",
     "Wunschsätze: Wenn ich doch mehr Zeit hätte! / Hätte ich doch mehr Zeit! / Wäre ich nur früher gegangen! (doch/nur/bloß); conditions with verb-first instead of wenn: Hätte ich das gewusst, wäre ich gekommen; Sollten Sie Fragen haben, rufen Sie an; Kommt er zu spät, (dann) fangen wir ohne ihn an. 'so' or 'dann' at the start of the main clause."),
    ("h06-futur-2-vermutung", "B2", "Futur II und Vermutungen über die Vergangenheit",
     "Futur II (werden + Partizip II + haben/sein): completed future (Bis Montag werde ich den Bericht geschrieben haben) and, much more common, assumptions about the past (Er wird den Zug verpasst haben). Alternatives: dürfte/müsste/könnte + Partizip II + haben/sein (Sie dürfte schon angekommen sein), wohl/sicher/vermutlich + Perfekt. Futur I for present assumptions (Er wird krank sein)."),
    ("h07-sollen-wollen-behauptung", "B2", "sollen und wollen als Behauptung (Fremd- und Eigenbehauptung)",
     "Subjective sollen = 'it is said that' (Er soll sehr reich sein; Das Hotel soll 1890 gebaut worden sein) and subjective wollen = 'claims that he himself' (Er will nichts gesehen haben). Present vs. past forms with Infinitiv Perfekt (gemacht haben / gegangen sein), passive (gestohlen worden sein), contrast with objective sollen (obligation) and wollen (wish)."),
    ("h08-modalpartikeln", "B1+", "Modalpartikeln (doch, ja, mal, eben, halt, denn, wohl, schon, eigentlich)",
     "Meaning and tone of the most frequent modal particles in speech: ja (shared knowledge, surprise), doch (contradiction, urging, reminder), mal (softens requests), eben/halt (resignation, that's how it is), denn (interest in questions), wohl (assumption), schon (reassurance, concession), eigentlich (by the way, actually), bloß/nur (warnings, wishes). Position in the Mittelfeld, combinations (doch mal, ja wohl), unstressed vs. stressed DOCH."),
    ("h09-relativsaetze-wer-was-wo", "B2", "Relativsätze mit wer, was, wo und wo(r)+Präposition",
     "Free relatives: Wer zu spät kommt, (der) muss draußen warten; Wem das nicht gefällt, der kann gehen (case agreement of wer/der). 'was' after alles, nichts, etwas, vieles, das, superlatives (das Beste, was) and referring to a whole clause (Er kam pünktlich, was mich überraschte). 'wo' for places and times; wo(r)+preposition for things/clauses (worüber, womit, woran) vs. preposition + Relativpronomen for people."),
    ("h10-temporale-nebensaetze", "B1+", "Temporale Nebensätze und Zeitenfolge",
     "nachdem (+ Plusquamperfekt in the past / Perfekt in the present), bevor, während, seit/seitdem, sobald, bis, solange, sooft, als vs. wenn vs. wann recap only briefly. Tense sequence (Nachdem er gegessen hatte, ging er), common errors (nachdem with same tense), word order with Nebensatz first (verb-verb: Sobald ich ankomme, rufe ich an). Prepositions vs. conjunctions: vor/bevor, nach/nachdem, seit/seitdem, während (both)."),
    ("h11-korrelat-da-praeposition", "B2", "Präpositionale Ergänzungen mit Nebensatz: darauf, dass … / daran, … zu",
     "Verbs, adjectives and nouns with fixed prepositions followed by a clause: Ich freue mich darauf, dass du kommst / dich zu sehen; Ich bin stolz darauf, dass …; Er hat Angst davor, … zu …; Es kommt darauf an, ob …. When the da(r)-Korrelat is obligatory, optional (sich erinnern (daran), dass) or used with W-questions (Es hängt davon ab, wann …). Same subject → zu-Infinitiv; different subject → dass."),
    ("h12-infinitiv-ohne-zu", "B2", "Infinitiv ohne „zu“: sehen, hören, lassen, bleiben, gehen, lernen",
     "Verbs that take a bare infinitive: Modalverben, werden, lassen, sehen, hören, fühlen, spüren, bleiben (sitzen bleiben, liegen bleiben), gehen/kommen/fahren (einkaufen gehen, essen gehen), lernen/lehren/helfen (both with and without zu). Perfekt with Ersatzinfinitiv: Ich habe ihn kommen sehen / Ich habe das Auto reparieren lassen; 'gesehen' also possible with sehen/hören in speech. Contrast with verbs needing zu."),
    ("h13-infinitiv-perfekt-passiv", "B2", "Infinitivsätze in Vergangenheit und Passiv; anstatt/ohne/um … zu",
     "Infinitiv Perfekt in zu-clauses (Er behauptet, das Buch gelesen zu haben / rechtzeitig angekommen zu sein), Infinitiv Passiv (Sie hofft, eingeladen zu werden; Er bedauert, nicht informiert worden zu sein), anticipating time relation, and the three infinitive conjunctions um … zu / ohne … zu / (an)statt … zu vs. their dass-counterparts (damit / ohne dass / (an)statt dass) when subjects differ."),
    ("h14-passiv-vertiefung", "B2", "Passiv-Vertiefung: unpersönliches Passiv, Dativ im Passiv, von/durch",
     "Impersonal passive without subject (Hier wird nicht geraucht; Am Sonntag wird nicht gearbeitet; Es wird getanzt — 'es' only in the Vorfeld), Dativ objects stay Dativ (Mir wurde geholfen, not Ich wurde geholfen), von (agent/person) vs. durch (means, cause), passive with modal verbs in all tenses (hat repariert werden müssen), bekommen-Passiv (Er bekommt das Paket geschickt), when NOT to use passive (reflexive, haben/bekommen as main verbs)."),
    ("h15-adjektivdeklination-komplett", "B1+", "Adjektivdeklination komplett: alle Typen, Zahlwörter, substantivierte Adjektive",
     "Mixed practice of the three declensions (after der-words, ein-words, no article) across all cases including Genitiv; adjectives after viele, einige, wenige, mehrere, ein paar (strong) vs. alle, beide, keine, meine (weak -en); several adjectives in a row (same ending); substantivised adjectives (der Deutsche / ein Deutscher / die Deutschen / Deutsche; der/die Angestellte, das Gute, etwas Neues, nichts Besonderes); special stems (teuer → teure, dunkel → dunkle, hoch → hohe, rosa/lila undeclined, -er city adjectives: Berliner)."),
    ("h16-genitiv-vertiefung", "B2", "Genitiv-Vertiefung: Attribute, Eigennamen, n-Deklination, wessen",
     "Genitive attributes and their order (das Auto meines Bruders), -s vs. -es ending (des Tages, des Hauses, des Computers), n-Deklination in the Genitiv (des Studenten, des Herrn, des Namens), Eigennamen (Annas Buch, Peters Auto; die Werke Goethes; apostrophe only after s/x/z: Max' Hund), 'wessen', von + Dativ as spoken substitute and when it is required (no article: der Preis von Häusern), Genitiv of plural without article."),
    ("h17-je-desto-vergleiche", "B1+", "je … desto / umso, immer + Komparativ, Vergleichssätze",
     "je + Komparativ (Nebensatz, verb last) + desto/umso + Komparativ (verb second after the comparative group): Je länger ich hier wohne, desto besser gefällt es mir; with nouns (je mehr Leute, desto …); immer + Komparativ (Es wird immer kälter); so … wie / anders als / als with a subordinate clause (Es war teurer, als ich gedacht hatte); umso + Komparativ, als (umso wichtiger, als …)."),
    ("h18-partizipialsaetze", "C1", "Partizipialsätze (verkürzte Nebensätze)",
     "Participle clauses replacing subordinate clauses, mainly in writing: Partizip II (Im Hotel angekommen, rief sie ihren Mann an = Nachdem sie im Hotel angekommen war, …; Von der Kritik enttäuscht, gab er auf), Partizip I (Laut lachend verließ sie den Raum), fixed phrases (genau genommen, offen gesagt, abgesehen davon, im Grunde genommen, verglichen mit). Comma rules, subject must equal main-clause subject; transforming into full clauses and back."),
    ("h19-nominal-verbal-umformung", "C1", "Umformung: Präpositionalgruppe ↔ Nebensatz",
     "Converting between Nominalstil and Verbalstil, a classic Goethe/telc B2-C1 task: wegen/aufgrund ↔ weil/da; trotz ↔ obwohl; bei ↔ wenn/als; vor ↔ bevor; nach ↔ nachdem; während ↔ während; seit ↔ seit(dem); bis zu ↔ bis; zur/zum/für ↔ um … zu / damit; durch ↔ indem / dadurch, dass; ohne ↔ ohne dass / ohne … zu; im Falle ↔ falls; statt ↔ statt dass. Genitive/von after the nominalised verb (die Ankunft des Zuges), subject → Genitiv, object → Genitiv or von."),
    ("h20-indirekte-rede-vertiefung", "B2", "Indirekte Rede: Vergangenheit, Fragen und Aufforderungen",
     "Reported speech beyond the present: past (Er sagte, er habe das nicht gewusst / sei krank gewesen), future (sie werde kommen), questions (Sie fragte, ob/wann …), commands with sollen (Sie sagte, ich solle warten) and polite requests with mögen (er möge warten), Konjunktiv II replacement when Konjunktiv I = indicative (sie hätten, nicht sie haben), würde-Form, pronoun and time-adverb shifts (morgen → am nächsten Tag)."),
    ("h21-reflexiv-vertiefung", "B2", "Reflexive Verben Vertiefung: Dativ-Reflexiv, reziprok, sich lassen",
     "Reflexive pronoun in the Dativ when there is also an Akkusativ object (Ich wasche mir die Hände; Ich kaufe mir ein Auto; Das kann ich mir vorstellen), verbs that are always Dativ-reflexive (sich etwas merken, sich etwas leisten, sich etwas wünschen), reciprocal sich / einander (Sie lieben sich / einander; miteinander, voneinander), 'sich lassen' as a passive alternative (Das lässt sich leicht erklären), position of the reflexive pronoun in the Mittelfeld (Dann hat sich der Lehrer entschuldigt / Dann hat er sich entschuldigt)."),
    ("h22-konnektoren-c1", "C1", "Konnektoren für Fortgeschrittene (zumal, sofern, es sei denn, geschweige denn …)",
     "Advanced connectors and their word order: zumal (especially since, verb last), sofern / soweit (provided that), es sei denn (unless, verb second after it), geschweige denn (let alone), wohingegen / während (whereas), insofern … als, vorausgesetzt, dass, angenommen, dass, nichtsdestotrotz / dennoch (adverbs, verb second), immerhin, allerdings, folglich, infolgedessen, andernfalls."),
]


def stable_guid(*parts: str) -> str:
    """The legacy builders' GUID scheme (the old German study-kit deck builders)."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def strip_cloze(text: str) -> str:
    return CLOZE_RE.sub(lambda m: m.group(2), text)


def cloze_numbers(text: str) -> list[int]:
    return sorted({int(m.group(1)) for m in CLOZE_RE.finditer(text)})


def parse_markdown(path: Path, *, fields: int = 2) -> dict:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"{path}: missing YAML frontmatter")
    meta = yaml.safe_load(match.group(1)) or {}
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in match.group(2).splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1).strip()
            sections[current] = []
        else:
            sections[current].append(line)
    sentence_lines = sections.get("Sätze") if "Sätze" in sections else sections[""]
    sentences = []
    for line in sentence_lines:
        if not re.match(r"^\s*-\s+", line):
            continue
        parts = [part.strip() for part in re.sub(r"^\s*-\s+", "", line).split(" | ")]
        if len(parts) != fields:
            raise ValueError(f"{path}: expected {fields} fields: {line}")
        sentences.append(parts)
    prefix = FILE_PREFIX_RE.match(path.name)
    return {
        "path": str(path.relative_to(LEGACY_NOTES)),
        "title": str(meta.get("title", path.stem)),
        "level": str(meta.get("level", "")),
        "topic_id": str(meta.get("topic_id", path.stem)),
        "tags": list(meta.get("tags", [])),
        "number": prefix.group(1) if prefix else "",
        "explanation_md": "\n".join(sections.get("Erklärung", [])).strip(),
        "sentences": sentences,
    }


def grammar_topics() -> list[dict]:
    """All A1-B2 topics, each with its matching cumulative review file (A1/A2)."""
    topics = []
    for level in LEVELS:
        reviews = {}
        review_dir = LEGACY_NOTES / "review" / level
        if review_dir.is_dir():
            for path in sorted(review_dir.glob("*.md")):
                review = parse_markdown(path, fields=3)
                reviews[review["number"]] = review
        for path in sorted((LEGACY_NOTES / "grammar" / level).glob("*.md")):
            topic = parse_markdown(path)
            topic["level"] = level
            topic["review"] = reviews.pop(topic["number"], None)
            topics.append(topic)
        if reviews:
            raise ValueError(f"Unmatched review files for {level}: {sorted(reviews)}")
    return topics


def themen_topics() -> list[dict]:
    return [parse_markdown(path) for path in sorted((LEGACY_NOTES / "themen").glob("*.md"))]


def legacy_verbs() -> list[dict]:
    rows = []
    section = ""
    for line in (LEGACY_NOTES / "reference" / "irregular-verbs.md").read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        # A verb row has haben/sein as helper.
        if len(cells) == 5 and cells[3].lower() in ("haben", "sein"):
            rows.append({"infinitiv": cells[0], "praeteritum": cells[1], "partizip2": cells[2],
                         "helper": cells[3], "meaning": cells[4], "section": section})
    return rows


def load_content(skip_invalid: bool = False) -> dict[str, dict]:
    content = {}
    for path in sorted(CONTENT.glob("*.json")):
        try:
            content[path.stem] = json.loads(path.read_text())
        except json.JSONDecodeError:
            if not skip_invalid:
                raise
    return content


def auxiliary(hilfsverb: str) -> str:
    return {"haben": "hat", "sein": "ist"}.get(hilfsverb, "hat / ist")


def verb_forms_text(verb: dict) -> str:
    return f"{verb['infinitiv']}, {verb['praeteritum']}, {auxiliary(verb['hilfsverb'])} {verb['partizip2']}"


def spoken_texts(data: dict) -> list[str]:
    """Every German string that gets an audio clip, in card order."""
    texts: list[str] = []
    if data.get("topic_id") == "verbs":
        for verb in data["verbs"]:
            texts += [verb["infinitiv"], verb_forms_text(verb)] + [x["de"] for x in verb["examples"]]
    elif "phrases" in data:
        for phrase in data["phrases"]:
            texts += [phrase["de"]] + [x["de"] for x in phrase.get("alternatives", [])]
    else:
        for item in data["items"]:
            texts += [strip_cloze(item["de"])] + [x["de"] for x in item["examples"]]
        for drill in data["drills"]:
            if drill["type"] == "concept":
                texts += [x["de"] for x in drill["examples"]]
            else:
                texts.append(drill["answer"])
    return texts


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
