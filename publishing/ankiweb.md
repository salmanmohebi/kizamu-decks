# Sharing the decks on AnkiWeb

AnkiWeb shares a **copy without scheduling**, so the decks can be shared from the
personal collection: review history, due dates and learning progress stay private.

## Steps

1. Make `kizamu-decks-releases` public first. The descriptions link to it (and to
   <https://kizamu.app>), and the GitHub link does not work while the repo is private.
2. Sync Anki (desktop) so AnkiWeb has the current decks.
3. Log in at <https://ankiweb.net/decks>. Next to the deck, open the menu → **Share**.
   Share the decks below (each is a deck in the list, subdecks included).
4. Fill in the form with the title, tags and description of that deck (below).
5. After sharing, AnkiWeb shows the link of the shared deck
   (`https://ankiweb.net/shared/info/<number>`). Put the 7 links into the table at the
   end of this file and into the README of kizamu-decks-releases.

If AnkiWeb refuses a deck as too large, share its subdecks instead (for example
`kizamu-german::grammar::A1` … `::Verben`, or the ten categories of
`kizamu-english::C1`), with the same description and the part in the title.

**Updating later:** click **Share** again on the same deck. The deck must keep the
same name, or AnkiWeb creates a new shared deck instead of updating the old one.
Downloads and ratings are kept.

**Tag:** the English notes carry the tag `studied_before` (items from the old decks). It
is harmless, but to leave it out: Browse → `tag:studied_before` → select all →
Notes → Remove Tags, then sync before sharing.

---

## 1 · `kizamu-german::vocab::A1`

**Title:** kizamu German Vocabulary A1 · both directions · forms · 3 examples · audio

**Tags:** german deutsch vocabulary wortschatz A1 beginner audio kizamu

**Description:**

```
784 German A1 words, 1,568 cards: Deutsch → English and English → Deutsch.

Every answer shows:
- the word with its article and plural (der Abend, die Abende), or the verb forms
- the meaning, with a short cue where one spelling has two words (die Bank: bank or bench)
- related words and contrasts, and a usage note
- three example sentences with translations

Every word and every example sentence has audio (a natural German voice, checked by speech recognition).

Next levels: kizamu German Vocabulary A2 and B1. For grammar: kizamu German Grammar and kizamu German Sentences.

All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub.

The audio is synthetic. Definitions and inflections adapted from Wiktionary (CC BY-SA 4.0). Deck license: CC BY-SA 4.0.
```

## 2 · `kizamu-german::vocab::A2`

**Title:** kizamu German Vocabulary A2 · both directions · forms · 3 examples · audio

**Tags:** german deutsch vocabulary wortschatz A2 audio kizamu

**Description:** the A1 text with these changes:
- first line: `652 German A2 words, 1,304 cards: Deutsch → English and English → Deutsch.`
- "Next levels" line: `Other levels: kizamu German Vocabulary A1 and B1. For grammar: kizamu German Grammar and kizamu German Sentences.`

## 3 · `kizamu-german::vocab::B1`

**Title:** kizamu German Vocabulary B1 · both directions · forms · 3 examples · audio

**Tags:** german deutsch vocabulary wortschatz B1 intermediate audio kizamu

**Description:** the A1 text with these changes:
- first line: `1,481 German B1 words, 2,962 cards: Deutsch → English and English → Deutsch.`
- "Next levels" line: `Other levels: kizamu German Vocabulary A1 and A2. For grammar: kizamu German Grammar and kizamu German Sentences.`

## 4 · `kizamu-german::grammar`

**Title:** kizamu German Grammar A1–C1 · fill the gap + drills · explanation on every card · audio

**Tags:** german deutsch grammar grammatik cloze A1 A2 B1 B2 C1 audio kizamu

**Description:**

```
German grammar from A1 to B2, plus 22 hard topics up to C1 (word order, Konjunktiv II with modal verbs, Futur II, modal particles, verb clusters, ...). 5,291 notes, 5,320 cards, one subdeck per topic.

Card types:
- Fill the gap: a German sentence with a gap, an English context and a focus cue
- Rule check, Transform, Find the mistake, Word order, Choose the form, Join the sentences
- Irregular verbs (Verben::Unregelmäßig) with Präsens, Präteritum, Perfekt, Konjunktiv II and Imperativ

The back of every card explains this sentence (not only the general rule), shows a typical mistake and why it is wrong, and gives two more examples and the topic's rule table. New cards come in teaching order: rule checks first, then the gap sentences, then the other drills.

Every German sentence has audio (a natural German voice, checked by speech recognition).

Goes well with: kizamu German Sentences (the same topics as whole sentences to translate and to listen to) and kizamu German Vocabulary A1 / A2 / B1.

All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub.

The audio is synthetic. License: CC BY-SA 4.0.
```

## 5 · `kizamu-german::sentences`

**Title:** kizamu German Sentences A1–C1 · English → Deutsch · listening · everyday phrases · audio

**Tags:** german deutsch sentences saetze listening hoeren speaking phrases A1 A2 B1 B2 audio kizamu

**Description:**

```
Whole German sentences, from A1 to B2 and the hard grammar topics, plus situational phrases (Themen: greetings, at the doctor, on the phone, shopping, housing, emergencies, ...). 3,187 notes, 6,374 cards.

Card types:
- English → Deutsch: say or write the German sentence
- Listening: hear the sentence, understand it, then check the text
- Themen: phrases in both directions, with usage notes and alternatives (formal / informal, Austrian and Swiss variants where they matter)

Every sentence has audio (a natural German voice, checked by speech recognition).

Goes well with: kizamu German Grammar (the same topics as gap sentences and drills, with explanations) and kizamu German Vocabulary A1 / A2 / B1.

All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub.

The audio is synthetic. License: CC BY-SA 4.0.
```

## 6 · `kizamu-english::C1`

**Title:** kizamu American English C1 · 3,000 collocations, phrasal verbs, idioms, conversation · audio

**Tags:** english american-english vocabulary idioms phrasal-verbs collocations C1 advanced audio kizamu

**Description:**

```
American English for advanced learners who want to sound natural: the core that a strong C1 speaker uses with ease. 3,000 notes, 6,000 cards, in 60 subdecks of 50 notes.

Ten categories: collocations, phrasal verbs, idioms, conversation & discourse, informal American English, work & academic English, key words, nuance & confusables, pronunciation, grammar. In every category, Set 01 holds the most useful items.

Two cards per note:
- Meaning: the term in a real sentence → meaning, how to use it, pattern, three examples, common mistake, related items, origin
- Usage: a new sentence with a gap and a plain-English hint, or (pronunciation) a sentence to say aloud

Every card shows the register (formal, neutral, informal, slang) and notes when an item is American or British only. Every term and example has audio (a natural American English voice, checked by speech recognition).

Next level: kizamu American English C2 (no item appears in both levels).

All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub.

The audio is synthetic. License: CC BY-SA 4.0.
```

## 7 · `kizamu-english::C2`

**Title:** kizamu American English C2 · 3,000 advanced collocations, idioms, nuance, connected speech · audio

**Tags:** english american-english vocabulary idioms phrasal-verbs collocations C2 proficiency advanced audio kizamu

**Description:**

```
American English at C2: the advanced, native-like layer for learners who are already fluent. 3,000 notes, 6,000 cards, in 60 subdecks of 50 notes. No item repeats the C1 deck.

Ten categories: collocations, phrasal verbs, idioms, conversation & discourse, informal American English, work & academic English, advanced words, nuance & confusables, pronunciation & connected speech, advanced grammar. In every category, Set 01 holds the most useful items.

Two cards per note:
- Meaning: the term in a real sentence → meaning, how to use it, pattern, three examples, common mistake, related items, origin
- Usage: a new sentence with a gap and a plain-English hint; for pronunciation, a sentence to say aloud or (connected speech) audio only

Every card shows the register (formal, neutral, informal, slang) and notes when an item is American or British only. Every term and example has audio (a natural American English voice, checked by speech recognition).

Start with C1 if you are not sure: kizamu American English C1.

All kizamu decks, sample cards and downloads: https://github.com/salmanmohebi/kizamu-decks-releases
Kizamu (刻む), spaced repetition, active recall and AI tutoring: https://kizamu.app
Found a mistake? Please open an issue on GitHub.

The audio is synthetic. License: CC BY-SA 4.0.
```

---

## Links after sharing

| Deck | AnkiWeb |
|---|---|
| kizamu German Vocabulary A1 | |
| kizamu German Vocabulary A2 | |
| kizamu German Vocabulary B1 | |
| kizamu German Grammar | |
| kizamu German Sentences | |
| kizamu American English C1 | |
| kizamu American English C2 | |
