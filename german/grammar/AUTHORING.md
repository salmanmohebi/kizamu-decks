# Authoring guide · kizamu-german grammar & sentences

Content for the `kizamu-german::grammar::…` and `kizamu-german::sentences::…` Anki decks.
One JSON file per topic in `german/grammar/content/<topic_id>.json`, written from the
input file `$KIZAMU_DATA/german/grammar/build/inputs/<topic_id>.json`.

Check every file with:

```bash
python -m german.grammar.validate german/grammar/content/<topic_id>.json
```

The validator must print `OK`. It checks structure, counts and legacy text. It cannot check
German grammar — that is your job, and a second reviewer will check it again.

## Who reads the cards

An adult learner (a researcher, English is their working language) studying for Goethe
exams, A1 up to C1. They want precise grammar, not simplified grammar. Write explanations
in **clear, simple English sentences** with correct technical terms (Nominativ, Akkusativ,
Dativ, Genitiv, Partizip II, Konjunktiv II, Nebensatz, Satzklammer, Vorfeld, Mittelfeld …).
No idioms, no jokes, no filler ("Great job!", "Remember that German can be tricky").

## Quality bar (read this twice)

1. **Every German sentence must be correct, natural Standard German** that a native speaker
   would really say or write. No word-for-word translations from English. Check gender,
   case, adjective endings, verb position, separable prefixes, comma rules, spelling
   (ß/ss, capitalisation, new orthography). If you are not sure a sentence is natural,
   write a different one.
2. **Every explanation is specific to its own sentence.** Never paste the same explanation
   on two cards. Name the trigger in *this* sentence and derive the form step by step:
   *"helfen always takes the Dativ → the old man is the Dativ object. Masculine Dativ
   article: dem. After dem the adjective is weak: alt + -en → dem alten Mann."*
3. **The English is accurate and natural**, and the German–English pair matches
   in tense, number and politeness (du/ihr/Sie) as far as English allows.
4. **Level fits the topic.** A1 topics use A1 vocabulary and short sentences (5–10 words).
   B2/C1 topics use realistic B2/C1 sentences (work, society, science, media, daily life).
   Vary the content: people, places, work, family, travel, health, studies, news — avoid
   twenty sentences about the same café.
5. **Correct terminology and correct rules.** Do not invent rules. Mention real exceptions
   where they matter (e.g. *Kollege* is n-Deklination; *gefallen* has Dativ).
6. **No duplicates**: no item sentence may repeat another item sentence, an example, or a
   drill answer in the same file.

## File format

All prose fields accept *inline Markdown*: `**bold**`, `*italic*`. Use **bold** for the form
being taught, *italic* for German words inside English sentences. `rule.table` is a
Markdown table. No HTML. Use `→` for derivations, `✗` / `✓` are added by the template.
To bold an ending inside a word, bold only the ending and do not nest it in italics:
`nett**en**` (good), `*nett**en***` (avoid). A legacy review sentence that is close to a
legacy grammar sentence is fine; give both their own explanation.

A complete, reviewed example: `german/grammar/content/a2-08-adjektive-bestimmt.json`.
Read it before you start, and match its depth and style (not its content).

```jsonc
{
  "topic_id": "a2-08-adjektive-bestimmt",        // = input topic_id = file name
  "level": "A2",                                  // copy from input
  "title_de": "Adjektivdeklination nach bestimmtem Artikel",  // copy from input
  "title_en": "Adjective endings after the definite article",
  "rule": {
    "summary": "2–4 sentences: what the structure is, what it is for, when you need it.",
    "table": "| | m | f | n | Pl |\n|---|---|---|---|---|\n| Nom | der nett**e** Mann | … |",  // "" if a table does not help
    "steps": ["Short decision steps a learner can follow, 3–6 items"],
    "pitfalls": ["Typical learner mistakes, 2–5 items, each with ✗/✓ wording inside the text"]
  },
  "items": [ … ],     // fill-the-gap sentences (cloze), see below
  "drills": [ … ]     // other drill types, see below
}
```

### items (cloze cards; also feed the sentences deck)

```jsonc
{
  "key": "g04",          // g00–g19 = legacy grammar sentences (same key as input)
                         // r00–rNN = legacy review sentences (same key as input)
                         // n01, n02, … = your new sentences
  "de": "Ich kenne den {{c1::netten::nett}} Mann.",
  "en": "I know the nice man.",
  "focus": "Akkusativ maskulin · nach *den*",   // short cue shown on the FRONT. Must NOT reveal the answer.
  "explanation": "*kennen* takes an Akkusativ object. *Mann* is masculine → Akkusativ article **den**. After *den* the adjective is weak, and masculine Akkusativ is an **-en** slot: nett + -en → **netten**.",
  "pattern": "den + Adj-**en** + Nomen (Akk. m.)",
  "mistake": {"wrong": "Ich kenne den nette Mann.", "why": "*-e* is only for Nominativ m/f/n and Akkusativ f/n. Masculine Akkusativ always takes *-en*."},
  "examples": [
    {"de": "Wir besuchen den neuen Kollegen.", "en": "We are visiting the new colleague."},
    {"de": "Hast du den roten Schirm gesehen?", "en": "Have you seen the red umbrella?"}
  ],
  "words": [{"de": "nett", "en": "nice, kind"}],   // 0–3 glosses of words a learner at this level may not know
  "production_cue": "",          // optional English cue for the EN→DE card, e.g. "(formal Sie)", "(Perfekt)"
  "sentence_card": true          // true: also make EN→DE + listening cards in the sentences deck
}
```

Rules for items:

- **Cloze syntax**: `{{c1::answer::hint}}`. The hint is shown in the gap on the front.
  Give a hint whenever the answer is a *form* of a word: the base form (`nett`, `gehen`,
  `der`), or for pronouns the person (`ich → Dat.`). If the answer is a *choice of word*
  (a connector, a preposition), the hint describes the function (`Grund`, `Ort/Ziel`)
  or is left out. A hint must never be the answer itself.
- One gap per sentence is normal (`c1`). Use `c2` only for a second, *independent* point
  (it creates a second card).
- **Legacy items** (`g..`, `r..`): include **every** legacy sentence of the input, with
  the same `key`. Keep the German text and the cloze answers exactly as in the input; you
  may only add hints. Keep the same cloze numbers (c1, c2 …). If a legacy sentence or its
  English is truly wrong, fix it and add `"correction": "what was wrong"`; this is rare.
  The English may be improved silently if it is inaccurate.
  For `r..` items, the input `old_tip` is a good start — rewrite it into the full format.
  `r..` items get `"sentence_card": false` (they are review gap-fills only).
- **New items** `n01…`: A1–B2 topics: exactly **12** new items. Hard-grammar topics:
  **30** new items. Cover the parts of the rule that the legacy sentences miss
  (other cases, persons, tenses, exceptions, word order variants). New items use
  `"sentence_card": true`.
- `focus` names the grammatical slot or trigger, e.g. `Dativ · nach *mit*`,
  `Perfekt · Bewegungsverb`, `Nebensatz · Verb am Ende`. Not the answer.
- `explanation`: 2–4 sentences, specific to this sentence (see Quality bar).
- `pattern`: a compact formula of the structure in this sentence.
- `mistake`: the most likely learner error for **this** sentence (a full wrong sentence)
  and why it is wrong. The wrong sentence must really be wrong, and the error must be a
  grammar error of this topic. A difference only in capitalisation or punctuation is not
  accepted (the validator ignores case and punctuation).
- `examples`: exactly 2 new sentences with the **same pattern** (different words), not
  copied from other items.

### drills (other drill types)

Each drill becomes one card. Every drill needs `key` (`d01`, `d02`, …), `type`,
`instruction` (English, specific), `prompt`, `answer`, `explanation` (2–4 sentences,
specific). A1–B2 topics: **at least 14 drills**; hard-grammar topics: **at least 18**.
Use at least 5 different types, including at least 3 `concept` drills.

| type | prompt | answer | notes |
|---|---|---|---|
| `concept` | an English question about the rule (*"After which articles does the adjective take the weak ending?"*) | short precise answer (inline Markdown, may list forms) | needs `examples`: 2 German sentences with English. Test understanding, not trivia. |
| `transform` | a German sentence | the transformed German sentence | instruction says exactly what to do: *"Rewrite in the Perfekt."*, *"Make the object a pronoun."*, *"Change to the passive (Präteritum)."* |
| `error` | a German sentence with **exactly one** grammar mistake of this topic | the corrected sentence | instruction: *"Find and correct the mistake."* Explanation names the mistake. |
| `order` | sentence parts in shuffled order, separated by ` / ` | the sentence | lowercase the first word unless it is a noun or a name; leave out the final punctuation. If several orders are correct, the instruction fixes the start (*"Start with: Gestern"*), or the explanation lists the other correct orders. |
| `choice` | German sentence with `___` | the full correct sentence | needs `options` (3–4 strings) and `correct` (one of the options). Explanation says why each wrong option is wrong. |
| `combine` | two German sentences | one combined sentence | instruction names the connector or structure: *"Join with weil."*, *"Make the second sentence a relative clause."* |

Every German `answer` (transform, error, order, choice, combine) is a normal full sentence:
capital first letter and final punctuation.

Drill content must not repeat item sentences. Concept drills cover the important rule
points: forms, triggers, exceptions, contrasts with similar structures.

## Topic-specific notes

- **Hard-grammar topics (`h..`)** have no legacy sentences. The input has a `scope`:
  cover all of it. Level is B1+ to C1; sentences should feel like real B2/C1 texts
  and conversations.
- **Avoid overlap**: the A1–B2 topics already exist (see the list in
  `$KIZAMU_DATA/german/grammar/build/inputs/`). Hard topics go deeper, not repeat basics.

## Themen files (`themen-…`)

Situational phrases. Output `german/grammar/content/<topic_id>.json`:

```jsonc
{
  "topic_id": "themen-02-restaurant", "level": "A1-A2", "title_de": "02 Restaurant & Café",
  "title_en": "Restaurant & café",
  "intro": "1–2 sentences: the situation and the register (du/Sie).",
  "phrases": [
    {"key": "t00",                       // legacy keys as in input; new: n01…
     "de": "Einen Tisch für zwei, bitte.", "en": "A table for two, please.",
     "usage": "When and how to use it; register; what people usually answer.",
     "grammar": "The grammar in this phrase, specific (e.g. *einen Tisch*: Akkusativ, the verb *Ich hätte gern* is left out).",
     "alternatives": [{"de": "Haben Sie einen Tisch für zwei Personen?", "en": "Do you have a table for two?"}],  // 1–2
     "words": [{"de": "der Tisch (-e)", "en": "table"}]}   // 0–3
  ]
}
```

Keep every legacy phrase (text unchanged unless truly wrong → `"correction"`), and add
**6 new** phrases (`n01`–`n06`) that the situation clearly needs.

## Verbs file (`verbs.json`)

```jsonc
{"topic_id": "verbs", "verbs": [
  {"key": "gehen",                        // legacy: the infinitive from input; new verbs too
   "infinitiv": "gehen", "meaning": "to go (on foot), to walk",
   "praesens": "er/sie/es geht",          // 3rd person singular; add du-form if it has a vowel change: "du fährst · er fährt"
   "praeteritum": "ging", "partizip2": "gegangen", "hilfsverb": "sein",
   "konjunktiv2": "ginge (usually: würde gehen)",
   "imperativ": "geh(e)! · geht! · gehen Sie!",
   "note": "Specific notes: haben/sein variation, common compounds (ausgehen, weggehen), fixed phrases.",
   "examples": [{"de": "Wir sind gestern ins Kino gegangen.", "en": "We went to the cinema yesterday."},
                {"de": "Sie ging langsam nach Hause.", "en": "She walked home slowly."}],
   "new": false}                           // true for added verbs
]}
```

Keep all 80 legacy verbs (fix wrong forms if any), and add **40 new** frequent strong,
mixed or irregular verbs (B1/B2 frequency) that are missing.
