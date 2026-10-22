# Authoring guide · kizamu-english C1 and C2

Content for the `kizamu-english::C1::…` and `kizamu-english::C2::…` Anki decks
(`<LEVEL>` below = `C1` or `C2`). The rules are the same for both levels; at C1 the
items are more frequent, so the examples can be simpler, but they must be just as
natural and the usage notes just as specific. One JSON file per deck part in
`english/<LEVEL>/content/<part_id>.json`. The list of entries for each part (ids, terms,
glosses, labels) is fixed in `english/<LEVEL>/catalogue.json`; you write the cards.

Check every file with:

```bash
python -m english.validate english/<LEVEL>/content/<part_id>.json
```

The validator must print `OK`. It checks structure, counts, lengths, gaps, duplicates and
British spellings. It cannot check whether the English is natural — that is your job,
and a second reviewer will check it again.

## Who reads the cards

An adult researcher (machine learning / scientific computing) who works in English every
day at C1+ level and wants to **sound like an educated native speaker of American
English**. They do not need simple English explained; they need the precise meaning,
the tone, and how natives really use the item. Write in **clear, simple, direct
sentences** (no idioms inside explanations, no rare words in explanations, no filler such
as "This is a great phrase!"). Precision beats length.

## Quality bar (read this twice)

1. **Every example must be something an educated American would really say or write
   today.** Natural word order, natural collocations, contractions where speech would
   use them (*I'm, it's, don't*), American spelling and vocabulary (*apartment, vacation,
   schedule, analyze, color, center, gray, toward*). If you are not sure a sentence is
   natural, write a different one.
2. **Meaning: 1–2 sentences.** Exact sense, not a vague synonym. If the item has several
   senses, describe only the sense in the catalogue gloss.
3. **Usage: 2–3 sentences.** Where it fits (conversation, email, paper, talk; formal or
   casual), its tone (critical, humorous, polite, dated-sounding …), typical grammar
   (*conflate A with B*, usually negative, usually passive, often with *keep -ing* …), and
   what to avoid. Specific to this item — never generic advice.
4. **Three examples, each in a different context** (e.g. one work or research, one
   everyday life, one news/society/relationships). 8–25 words each. The target is in
   `**bold**` (inflected forms are fine: **moved the goalposts**). Do not reuse the
   same sentence frame three times.
5. **The drill sentence is new** (not one of the examples) and has enough context that
   only the target fits.
6. **Correct facts only.** IPA, stress, origins, US/UK labels and grammar rules must be
   correct. If you are not sure about an origin, leave `origin` empty. Do not invent
   "common mistakes": give a mistake only when learners really make it.
7. **No duplicates** inside the file: no sentence may appear twice.
8. **No HTML.** Inline Markdown only: `**bold**` for the target, `*italic*` for words
   mentioned inside explanations.
9. **Vary the world of the sentences.** At most **one** research/tech sentence per entry
   (examples + drill together); the drill is a non-work sentence by default. Avoid the
   "reviewers / our paper / the dataset" frame — use family, friends, sports, travel,
   health, money, home, news, shopping, food, neighbors. (Work & academic entries are
   exempt, but vary their settings too: meetings, labs, hospitals, companies, schools.)
10. **The gap must have one answer.** Test the drill against the entry's own `related`
    items and against near-synonyms (*work out* for *pan out*, *stop by* for *swing by*,
    *that said* for *to be fair*). Rewrite the sentence so that only the target fits
    (a following preposition often helps: *to be fair **to him***), or exclude the rival
    in the hint: `turn out as hoped (not *work out*)`. The hint itself must never be a
    valid answer.
11. **Check every rule you state.** Usage notes and mistakes make claims about grammar
    ("never after *he/she/it*"). Check each claim against real usage; a wrong rule is
    worse than none.
12. **Keep examples out of divisive politics.** No examples about vaccines, abortion, gun
    rights, election fraud, immigration policy, specific politicians or parties, or
    religion. Society and news contexts are fine (a city budget, a new law on e-scooters,
    a court ruling on noise) as long as no side is taken.

## File format

```jsonc
{
  "part_id": "03-idioms-01",          // = file name, from the catalogue
  "category": "idioms",               // from the catalogue
  "entries": [ … ]                    // same ids, same order as the catalogue part
}
```

### Entry fields

| field | required | what |
|---|---|---|
| `id` | yes | copy from the catalogue |
| `term` | yes | copy from the catalogue (fix only an obvious typo) |
| `label` | yes | short label shown on the card, ≤ 30 characters: *idiom*, *verb + noun*, *adjective + noun*, *adverb + adjective*, *phrasal verb*, *phrasal verb (separable)*, *verb*, *noun*, *adjective*, *adverb*, *discourse marker*, *spoken phrase*, *slang*, *informal phrase*, *academic phrase*, *email phrase*, *grammar*, *mispronounced word*, *word stress*, *connected speech*, *confusable pair*, *near-synonyms*, *usage trap* … |
| `register` | yes | `formal` / `neutral` / `informal` / `slang` (catalogue value; correct it if wrong) |
| `region` | yes | `US` / `UK` / `both`. `US` = British speakers would notice it as American; `UK` = Americans would notice it as British |
| `ipa` | words, phrasal verbs, pronunciation parts 1–2 | General American IPA between slashes, primary stress marked: `/kənˈfleɪt/`. Optional elsewhere (use `""`). |
| `respelling` | pronunciation parts 1–2 | simple respelling, stressed syllable in capitals: `ih-PIT-uh-mee`. Optional for words. |
| `meaning` | yes | 1–2 sentences, ≤ 45 words |
| `usage` | yes | 2–3 sentences, ≤ 75 words |
| `pattern` | grammar; recommended for collocations, phrasal verbs, words | short structure line: `conflate A with B`, `wield + power / influence / authority`, `Never + auxiliary + subject + verb` |
| `examples` | yes | exactly 3 sentences with the target in `**bold**`; the first is shown on the front of the Meaning card, so it must make the meaning guessable from context |
| `drill` | yes | see below |
| `mistake` | nuance, grammar, pronunciation; elsewhere when a real learner error exists | `{"wrong": …, "right": …, "why": …}` — `why` is one sentence |
| `related` | optional | near-synonyms or opposites **with the difference**, ≤ 40 words |
| `origin` | optional, idioms | one sentence, only well-established origins |
| `spoken_term` | when `term` contains `/`, `(`, `:`, `…` or `vs.` | how the term is read aloud by TTS: `imply or infer`. For a noun/verb stress pair give context: `a record, to record` |
| `say_term` | grammar: `false` | `false` = no audio for the term itself |

### IPA convention

Broad (phonemic) General American IPA everywhere: *data* `/ˈdeɪtə/`, *subtle* `/ˈsʌtəl/`,
*water* `/ˈwɔtɚ/`, r-colored vowels as `ɚ` / `ɝ`. Do not write the flap as `ɾ` in a
phonemic transcription. The respelling shows the flap only when the flap is the point
of the card (*data* DAY-duh); otherwise use the standard form (*subtle* SUT-ul,
*epitome* ih-PIT-uh-mee). Only connected-speech entries (pronunciation part 3) may show
the reduced spoken form with `ɾ`, `ʔ` or a schwa in the IPA (`gotta` `/ˈɡɑɾə/`), because
that form is the point of the card.

### Audio text

Everything in `examples`, the drill sentence and the term (or `spoken_term`) is read
aloud by TTS. Lowercase *e.g.*, *i.e.*, *etc.*, *vs.* are read as *for example*, *that is*,
*et cetera*, *versus*. If a term must be heard as letters, write `spoken_term` in capitals
(`I.E. or E.G.`). Write numbers the way they should be spoken when it matters.

### Mistakes in grammar entries

Use errors that learners from **many** first languages make, for example: missing
inversion after a fronted negative, wrong verb form after *did* (*Little did I knew*),
question word order inside a wh-clause (*What do I need is …*), plural verb in an
it-cleft, *was happened*, verb before subject after *where* (*That's where comes in
the budget*), wrong tense after *wish* / *it's time*, *would* in the *if*-clause in
writing. Avoid errors that belong to one first language only (dropped subjects,
resumptive *it*).

### Pronunciation entries

The card front must not give away the pronunciation. Write `term` in **normal spelling**,
without stress capitals: the catalogue's `inTERpret` becomes `interpret`, `REcord /
reCORD` becomes `record (noun) vs. record (verb)`. The stress goes into `ipa`,
`respelling`, `usage` and `mistake`. Connected-speech terms (part 3) stay as in the
catalogue (`gonna (going to)`), with `spoken_term` set to the reduced form.

**C1 pronunciation** (parts: sounds learners mix up; silent letters and tricky
spellings; word stress, sentence stress and intonation) uses the `say` drill in **all
three parts**: the learner reads the sentence aloud with the target in **bold**, then
hears it. The term names the sound, contrast, word or pattern
(`th: think vs. sink`, `knife, knee (silent k)`, `stress before -ic: economic`).
`ipa` is required in parts 1–2 and may list several forms: `/θɪŋk/ vs. /sɪŋk/`,
`/lid/ (verb), /lɛd/ (metal)`. `respelling` is optional. `spoken_term` reads the
example words, not the label (`think, sink`; `knife, knee`). For intonation items, the
examples and the drill sentence must show the pattern clearly (a question tag that
falls, a list that rises); describe the pattern in `usage`.

### Drill

The second card of each note. Three types:

- `gap` (default; all categories except pronunciation) — `sentence` contains exactly one
  `{{…}}` with the answer as it appears in the sentence (`{{moving the goalposts}}`).
  `hint` is a plain-English paraphrase of the missing part, written so it does **not**
  contain the answer's main words. The card also shows the first letters of the answer
  on request. For **grammar**, `hint` is the instruction plus the plain sentence to
  transform (`Rewrite with emphasis: I have never seen such a mess.`). For **nuance**,
  `hint` names the choice (`imply or infer? (she is drawing the conclusion)`).
- `say` (pronunciation parts 1–2) — `sentence` with the target in `**bold**`; `hint` says
  what to watch (stress, a silent letter …). The learner reads it aloud, then hears it.
- `listen` (C2 pronunciation part 3) — optional `spoken`: the same sentence in the casual
  spelling the TTS voice should say when the card text uses normal spelling
  (`sentence`: `**Would you** mind…`, `spoken`: `Wouldja mind…`).
- `listen` (pronunciation part 3) — `sentence` as it is spoken in relaxed American speech,
  target in `**bold**` (`I'm **gonna** grab a coffee.`); `hint` gives the careful form or
  what to listen for (`gonna = going to`). The learner first hears it without text.

## Complete examples

Match their depth and style, not their content.

```json
{
  "id": "conflate",
  "term": "conflate",
  "label": "verb",
  "register": "formal",
  "region": "both",
  "ipa": "/kənˈfleɪt/",
  "respelling": "kun-FLAYT",
  "meaning": "To treat two different things as if they were the same, so that the difference between them is lost.",
  "usage": "Common in academic writing, journalism and serious discussion, usually as a criticism of someone's reasoning. The normal patterns are *conflate A with B* and *conflate A and B*. In casual speech people more often say *mix up* or *lump together*.",
  "pattern": "conflate A with B / conflate A and B",
  "examples": [
    "Many news reports **conflate** correlation with causation.",
    "It's easy to **conflate** being busy with being productive.",
    "The debate keeps **conflating** immigration and crime, which are separate issues."
  ],
  "drill": {
    "type": "gap",
    "sentence": "The paper {{conflates}} benchmark accuracy with real-world usefulness, but they are not the same thing.",
    "hint": "treats two different things as if they were identical"
  },
  "mistake": {
    "wrong": "He conflated me with my brother at the party.",
    "right": "He mixed me up with my brother at the party.",
    "why": "For a simple mix-up between people, natives say *mix up* or *confuse*; *conflate* is for ideas and categories."
  },
  "related": "*confuse* — more general; *lump together* — informal, treat as one group; *distinguish* — the opposite."
}
```

```json
{
  "id": "move-the-goalposts",
  "term": "move the goalposts",
  "label": "idiom",
  "register": "informal",
  "region": "both",
  "ipa": "",
  "meaning": "To change the rules or the target of something after it has started, in a way that makes success harder for someone.",
  "usage": "A complaint about bosses, institutions or opponents who keep changing what they expect, common at work and in politics. It sounds critical, so you rarely say it about your own decisions. Often used as *keep moving the goalposts* or *move the goalposts on someone*.",
  "pattern": "move the goalposts (on someone)",
  "examples": [
    "Every time we hit the target, management **moves the goalposts**.",
    "The reviewers accepted our first analysis and then **moved the goalposts**, asking for three new baselines.",
    "I'm happy to negotiate, but you can't **move the goalposts** after we've signed."
  ],
  "drill": {
    "type": "gap",
    "sentence": "We agreed on three experiments, and now they want five. They keep {{moving the goalposts}}.",
    "hint": "changing what counts as success after the work has started"
  },
  "related": "*shift the goalposts* — same meaning, more common in British English; *change the rules of the game* — plainer, less critical.",
  "origin": "From soccer and football: moving the posts during a game would make scoring unfair."
}
```

```json
{
  "id": "that-said",
  "term": "that said",
  "label": "discourse marker",
  "register": "neutral",
  "region": "both",
  "ipa": "",
  "meaning": "Introduces a point that limits or contrasts with what you have just said, while you still stand by it.",
  "usage": "Put it at the start of a new sentence, after a point you still believe. It sounds balanced and fair, so it is very common in meetings, reviews and conversation, where *however* can sound stiff. *Having said that* means the same and is a little more formal.",
  "examples": [
    "The results look strong. **That said**, the sample is quite small.",
    "I love my job. **That said**, I wouldn't mind a shorter commute.",
    "He's a brilliant engineer. **That said**, he's not the easiest person to work with."
  ],
  "drill": {
    "type": "gap",
    "sentence": "I really like living downtown. {{That said}}, the noise at night can be a lot.",
    "hint": "however — introducing a limitation in a relaxed, spoken style"
  },
  "mistake": {
    "wrong": "That said, I agree with you completely.",
    "right": "I agree with you completely.",
    "why": "*That said* must introduce a contrast or a limitation; it is not a general linking phrase like *so*."
  },
  "related": "*having said that* — same, slightly more formal; *then again* — introduces an opposite thought that also seems true."
}
```

```json
{
  "id": "negative-inversion-never-have-i",
  "term": "negative inversion: Never have I …",
  "label": "grammar",
  "say_term": false,
  "register": "formal",
  "region": "both",
  "ipa": "",
  "meaning": "Putting *never* at the start of the clause and inverting auxiliary and subject adds strong emphasis: the experience is presented as unique.",
  "usage": "Mainly in formal writing, speeches and storytelling for dramatic effect. In everyday conversation it sounds theatrical unless you are emphasizing on purpose or joking. The auxiliary comes before the subject, exactly as in a question.",
  "pattern": "Never + auxiliary (have / had / did / will) + subject + main verb",
  "examples": [
    "**Never have I seen** such a disorganized conference.",
    "**Never had** the company **faced** a crisis on this scale.",
    "**Never will I** agree to those conditions again."
  ],
  "drill": {
    "type": "gap",
    "sentence": "{{Never have I read}} such a clear explanation of the problem.",
    "hint": "Rewrite with emphasis: I have never read such a clear explanation of the problem."
  },
  "mistake": {
    "wrong": "Never I have seen such a mess.",
    "right": "Never have I seen such a mess.",
    "why": "After a fronted negative adverb, the auxiliary must come before the subject."
  }
}
```

```json
{
  "id": "epitome",
  "term": "epitome",
  "label": "mispronounced word",
  "register": "neutral",
  "region": "both",
  "ipa": "/ɪˈpɪtəmi/",
  "respelling": "ih-PIT-uh-mee",
  "meaning": "A perfect example of a quality or a type of thing.",
  "usage": "Four syllables with stress on the second; the final *e* is a full syllable, *mee*. It is used almost always as *the epitome of* + a quality or type.",
  "examples": [
    "She is the **epitome** of grace under pressure.",
    "That hotel was the **epitome** of old-fashioned luxury.",
    "For many people, the lab's founder was the **epitome** of a careful scientist."
  ],
  "drill": {
    "type": "say",
    "sentence": "Her calm reply was the **epitome** of professionalism.",
    "hint": "Four syllables; stress on the second; the last syllable is *mee*."
  },
  "mistake": {
    "wrong": "EP-i-tome /ˈɛpɪtoʊm/",
    "right": "ih-PIT-uh-mee /ɪˈpɪtəmi/",
    "why": "Learners read the ending like *tome*; in this Greek word the final *e* is pronounced."
  }
}
```

```json
{
  "id": "gonna-going-to",
  "term": "gonna (going to)",
  "spoken_term": "gonna",
  "label": "connected speech",
  "register": "informal",
  "region": "both",
  "ipa": "/ˈɡʌnə/",
  "meaning": "The normal relaxed pronunciation of *going to* for the future: *I'm gonna* = *I'm going to*.",
  "usage": "Almost every American says it in relaxed speech, and you hear it constantly on TV and in podcasts. It replaces *going to* only before a verb, never before a place. Write *going to* in emails and formal texts.",
  "examples": [
    "I'm **gonna** grab a coffee before the meeting.",
    "Is it **gonna** be a problem if I join late?",
    "They're **gonna** announce the results on Friday."
  ],
  "drill": {
    "type": "listen",
    "sentence": "I think it's **gonna** rain later, so take an umbrella.",
    "hint": "gonna = going to"
  },
  "mistake": {
    "wrong": "I'm gonna the office now.",
    "right": "I'm going to the office now.",
    "why": "*Gonna* only replaces *going to* before a verb; before a place, keep *going to*."
  }
}
```

```json
{
  "id": "imply-vs-infer",
  "term": "imply vs. infer",
  "spoken_term": "imply or infer",
  "label": "confusable pair",
  "register": "neutral",
  "region": "both",
  "ipa": "",
  "meaning": "The speaker or the evidence *implies* (suggests something without saying it); the listener *infers* (draws a conclusion from it).",
  "usage": "Use *imply* for the person or data that sends the hidden message and *infer* for the person who works it out. Many natives say *infer* for *imply* in speech, but editors and careful writers treat that as an error.",
  "examples": [
    "Are you **implying** that I didn't do my share?",
    "From his tone, I **inferred** that he was unhappy with the plan.",
    "The results **imply** a strong seasonal effect."
  ],
  "drill": {
    "type": "gap",
    "sentence": "From her manager's two-word reply, she {{inferred}} that he was annoyed.",
    "hint": "imply or infer? (she is the one drawing the conclusion)"
  },
  "mistake": {
    "wrong": "What are you inferring?",
    "right": "What are you implying?",
    "why": "The speaker implies; the listener infers."
  }
}
```

## Before you finish a file

- Run the validator until it prints `OK`.
- Read every example once more as an American would hear it. Fix anything stiff.
