# Selection guide · kizamu-english C1 and C2

Step 1 of the pipeline: choose **which items** go into the decks. Step 2 (AUTHORING.md)
writes the cards. One selection file per category and level:
`english/<LEVEL>/selection/<category>.json` (`<LEVEL>` = `C1` or `C2`). Run the
scripts with `KE_LEVEL=C1` for the C1 decks (C2 is the default).

The guide below was written for C2. **For C1, read "Level C1" at the end first**; it
changes what counts as too easy and what to leave out.

## The learner

An adult researcher who works in English every day. Level C1, a little above. Reads
papers and writes emails without problems. Wants to **sound like an educated native
speaker of American English**: in meetings, in conversation, in writing. Every item
must be worth months of spaced repetition for this person.

## What "important" means

Rank by how often an **educated American adult** meets the item today (2020s) in
conversation, TV and podcasts, news, workplace and academic life, and by how much using
it correctly makes a C1 speaker sound native.

| importance | meaning |
|---|---|
| 5 | an educated American hears or uses it **every week**; a C1 speaker very likely does not use it actively |
| 4 | heard or read **every month**; clearly useful |
| 3 | several times a year; good to know at C2 |
| 2 | rare, dated, regional or showy — **do not select** |

Do **not** select:

- items a C1 speaker certainly already uses (*give up, find out, piece of cake,
  break the ice, important, however*);
- dated or rare items (*raining cats and dogs, the bee's knees, as cool as a cucumber*),
  unless the category is about exactly that;
- "impressive" words that natives rarely say (*sesquipedalian, pulchritude,
  defenestration*); a rare word in the wrong place makes a learner sound *less* native;
- British-only items, unless they are also common in American media (mark region);
- vulgar or offensive items; slurs; short-lived teen slang;
- duplicates: one entry per expression. Do not list two variants of the same idiom
  (*move the goalposts / shift the goalposts*) as two items — pick the American one.

## Evidence you have

The learner's old Anki decks were merged into candidate files (one line per term):
`term | EVP level | part of speech | Zipf | sources or number of decks`.

- `$KIZAMU_DATA/english/<LEVEL>/build/pool-words.txt` — single words. *EVP level* is the Cambridge
  English Vocabulary Profile (American English) level of that sense (the word in
  parentheses names the sense, e.g. `render (CAUSE TO BE)`). *Zipf* is word frequency
  (wordfreq): about 5.5+ = very common, 4 = common, 3 = educated vocabulary, 2.2 = rare.
  For single words aim mostly at **Zipf 2.3–4.0**; EVP C1/C2 senses of more common
  words (e.g. *observe (OBEY)*) are fine too.
- `$KIZAMU_DATA/english/<LEVEL>/build/pool-phrasal.txt` — phrasal verbs from 5 decks and EVP.
- `$KIZAMU_DATA/english/<LEVEL>/build/pool-multiword.txt` — idioms, phrases, collocations, expressions.

Use the pool as evidence (an EVP C1/C2 tag or presence in several decks suggests
importance), **not** as the list: many pool items are too easy, too rare or wrong for
the category, and many important items are missing from it. Add items from your own
knowledge of current American English. You may compute Zipf values with
`uv run python -c "from wordfreq import zipf_frequency as z; print(z('word','en'))"`.

## Category boundaries (avoid overlap)

- **collocations**: literal or nearly literal word partnerships (*draw a distinction,
  a vested interest, bitterly disappointed*). If the meaning is figurative → idioms.
- **phrasal-verbs**: verb + particle(s) (*gloss over, iron out*). A phrasal verb inside
  a longer fixed idiom (*throw in the towel*) → idioms.
- **idioms**: figurative fixed expressions (*a tall order, move the goalposts*).
- **conversation**: speech formulas and discourse markers (*that said, fair enough,
  tell me about it*). Neutral to informal.
- **informal**: casual / slang American words and phrases (*sketchy, bail on, legit*).
  A slang phrasal verb goes here, not into phrasal-verbs.
- **work-academic**: phrases tied to meetings, emails, papers, talks, negotiation.
  A general idiom used at work (*a tall order*) stays in idioms.
- **words**: single words only (hyphenated compounds allowed).
- **nuance**: pairs or groups — the item is the contrast (*imply vs. infer*).
- **pronunciation**: the item is about how it sounds, not what it means.
- **grammar**: one structure per item, finely cut (*Never have I …* and *Not until …
  did …* are two items; *mixed conditional: past condition → present result* and
  *present condition → past result* are two items).

## Output format

Write `english/<LEVEL>/selection/<category>.json`, valid JSON:

```json
{
  "category": "idioms",
  "items": [
    {"term": "move the goalposts",
     "gloss": "change the rules or targets unfairly after something has started",
     "importance": 5, "register": "informal", "region": "both",
     "theme": "work & careers", "part": 0}
  ]
}
```

- `term`: the citation form an American dictionary would use. Use *someone* /
  *something* (not *sb/sth*) where an object slot is part of the expression
  (*fob someone off*, *gloss over something*). For grammar, a short name with an
  example in it: `"negative inversion: Never have I …"`.
- `gloss`: 4–15 words, plain English. It must identify the sense you mean.
- `importance`: 3, 4 or 5 (see table).
- `register`: `formal` | `neutral` | `informal` | `slang`. `region`: `US` | `UK` | `both`.
- `theme`: exactly one of: `argument & ideas`, `communication`, `work & careers`,
  `research & academia`, `business & money`, `society & politics`, `change & progress`,
  `problems & solutions`, `emotions & attitudes`, `character & behavior`,
  `relationships & social life`, `success & failure`, `risk & decisions`,
  `time & pace`, `everyday life`, `quantity & degree`.
- `part`: for ranked categories `0`. For topical categories (work-academic, nuance,
  pronunciation, grammar) the part number 1…N from the catalogue.
- Order: ranked categories — most important first (all 5s, then 4s, then 3s; inside a
  level, the more useful first). Topical categories — by part, then most important first.
- Number of items: the target in your task **plus about 15 % reserves** (reserves replace
  items that turn out to be duplicates in another category).

Check the file before you finish: valid JSON, no duplicate terms (case-insensitive), all
fields present and from the allowed values.

## Level C1

The C1 decks (`kizamu-english::C1`) are for the same learner, but they cover the
**core** of educated English: items at CEFR B2–C1 that must be automatic in active use.
The learner understands most of them; the cards train using them correctly and
naturally. Differences from C2:

- **Too easy** now means A2–B1: *make a mistake, take a photo, get up, look for, by the
  way* is fine at C1 only if learners often misuse it. Items like *break the ice*, *come
  up with*, *crucial*, *I see what you mean* belong in C1.
- **Already in C2:** the 3,000 C2 items are taken. `english/select_check.py`
  rejects any term that is in the C2 catalogue (`english/C2/catalogue.json`,
  readable list in `english/C2/CATALOGUE.md`); choose another item.
- **Importance** keeps the same scale, but at C1 most items are 5 or 4: they are the
  frequent core. Use 3 for the reserves.
- **Single words:** mostly Zipf 3.3–4.8 (common educated vocabulary, much of the
  Academic Word List and EVP C1); the C1 word pool has EVP B2/C1 words.
- The evidence pools in `$KIZAMU_DATA/english/C1/build/` already exclude C2 items.

