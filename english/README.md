# kizamu-english · C1 + C2 (American English)

Anki decks for a C1+ learner who wants to sound like an educated native speaker of
American English. Two levels, each with 3,000 notes (6,000 cards) in 60 decks of 50 notes.
C1 holds the core that a strong C1 speaker must use with ease; C2 holds the advanced,
native-like layer. No item appears in both levels.

```
kizamu-english::<C1|C2>::01 Collocations::Set 01 … Set 09
                         02 Phrasal verbs::Set 01 … Set 06
                         03 Idioms::Set 01 … Set 09
                         04 Conversation & discourse::Set 01 … Set 06
                         05 Informal American English::Set 01 … Set 04
                         06 Work & academic English::01 Meetings … 05 Feedback, negotiation & teamwork
                         07 Key words (C1) / Advanced words (C2)::Set 01 … Set 10
                         08 Nuance & confusables::01 … 03
                         09 Pronunciation (C1) / Pronunciation & connected speech (C2)::01 … 03
                         10 Grammar (C1) / Advanced grammar (C2)::01 … 05
```

Ranked categories are cut by importance: **Set 01 holds the most useful items**. The full
lists are in [C1/CATALOGUE.md](C1/CATALOGUE.md) and [C2/CATALOGUE.md](C2/CATALOGUE.md).
Study tips, methods and resources are in [GUIDE.md](GUIDE.md).

## Cards

One note type per level (`kizamu-english · C1`, `kizamu-english · C2`), with two cards per
note:

| Card | Front | Back |
|---|---|---|
| **Meaning** | the term in a real sentence (term audio) | meaning, how to use it, pattern, 3 examples with audio, common mistake, related items, origin |
| **Usage** | *gap*: a new sentence with a gap + plain-English hint (first letters on request) · *say it* (pronunciation): read the sentence aloud · *listen* (C2 connected speech): audio only | the full sentence with audio, meaning, usage, mistake |

Labels on every card: type (idiom, phrasal verb …), register (formal / neutral /
informal / slang), and American or British when an item is not used in both.

Tags: `theme::…`, `register::…`, `region::…`, `importance::3–5`, the category and the
deck part, and `studied_before` for items from your old decks.

## Study order

Each level has its own preset (`kizamu-english · C1`, `kizamu-english · C2`): 20 new cards
a day, gathered by position. Positions interleave all ten categories by importance, so
studying the parent deck (`kizamu-english::C1`) gives a mix, starting with every
category's most useful items. The Usage card of a note comes about 30 notes after its
Meaning card (a few days later), and siblings are buried. To focus on one area, study a
subdeck or a filtered deck by tag. Starting with C1 and adding C2 later (or running both
with fewer new cards each) both work, since the levels share no items.

## Review history

New notes have new, stable GUIDs (derived from the catalogue id), so they never touch your
old English decks, and a later package updates notes from an earlier import in place.
Where an item matches an old English card you studied **in the same sense**, the old
card's schedule and review records from the 15 October 2026 snapshot are copied: old
definition → word cards to the Usage card, old word → definition cards to the Meaning
card (C1: 46 cards, 674 review records; C2: 37 cards, 527 review records; no old card is
copied to both levels). Old cards that
share the words but teach another sense (*turn on* a TV vs. *turn on someone*) are listed
in `<level>/selection/exclude.json` and get no copy.

## Pipeline

All scripts take the level from `KE_LEVEL` (`C1` or `C2`, default `C2`).

```bash
python -m english.candidates     # evidence pool from the old English decks
#   10 selection agents → <level>/selection/<category>.json (SELECTION.md)
python -m english.select_check   # check selections (C1: no C2 items)
python -m english.catalogue      # merge, de-duplicate, cut into 60 decks → <level>/catalogue.json
#   authoring agents → <level>/content/<part_id>.json (AUTHORING.md), reviewers (REVIEWING.md)
python -m english.validate --all # structure, lengths, gaps, US spelling, duplicates
python -m english.similar        # near-copy sentences across both levels
make english-audio KE_LEVEL=C1   # Qwen3-TTS + Whisper, one process per GPU
make english KE_LEVEL=C1         # build, import check, preview
```

Content was written and then reviewed by separate AI passes, and validated mechanically.
Audio is synthetic (Qwen3-TTS VoiceDesign, an American English voice). Every clip was
transcribed with Whisper large-v3-turbo; clips that still did not match after retries are
left out of the cards (no audio is better than wrong audio), and reviewed homophones and
transcription quirks are listed in `audio-accepted.json`. Whisper cannot check word stress,
vowel quality or pitch, so for pronunciation items the IPA and respelling on the card are
the reference; the heteronym items (*minute*, *read*, *lead*, *wind* …) and the C1
intonation items (pronunciation 03) are the clips most worth a human listen.
