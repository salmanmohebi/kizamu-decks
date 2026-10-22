# kizamu-german · grammar & sentences

Anki decks that replace the old `00 - German - grammar` decks, next to the
`kizamu-german::vocab` decks:

```
kizamu-german::grammar::A1 | A2 | B1 | B2 ::<NN topic>   fill-the-gap + drills, per-card explanations
kizamu-german::grammar::Hard grammar::<NN topic>          22 new deep-dive topics (B1+ to C1)
kizamu-german::grammar::Verben::Unregelmäßig              irregular verbs with all key forms
kizamu-german::sentences::A1 | A2 | B1 | B2 | Hard grammar::<NN topic>   English → Deutsch + listening
kizamu-german::sentences::Themen::<NN situation>          situational phrases, English ↔ Deutsch
```

## Card types

| Note type | Cards | What it trains |
|---|---|---|
| `kizamu-german · grammar cloze` | Fill the gap | the form, with an English context and a focus cue; the back explains *this* sentence, shows a typical mistake, two more examples with audio, words, and the topic rule |
| `kizamu-german · grammar drill` | Rule check · Transform · Find the mistake · Word order · Choose the form · Join the sentences | the rule from different directions |
| `kizamu-german · sentence` | English → Deutsch · Listening · Deutsch → English | producing and understanding whole sentences |
| `kizamu-german · verb` | Forms | Präsens, Präteritum, Perfekt, Konjunktiv II, Imperativ |

Within each topic deck, new cards come in teaching order: rule checks first, then the
gap sentences, then the other drills.

## Review history

New notes have new GUIDs, note IDs and card IDs, so they never overwrite your old
cards. When a new card replaces an old card you studied, the build copies that card's
schedule, FSRS state and review records onto the new card. The old card stays as it was.
Mapping:

| old card | new card |
|---|---|
| grammar cloze (each cloze number) | grammar cloze (same cloze number) |
| review gap-fill | grammar cloze |
| EN→DE production | sentence · English → Deutsch |
| listening | sentence · Listening |
| Themen EN→DE / DE→EN | sentence · English → Deutsch / Deutsch → English |
| irregular verb | verb · Forms |

The history comes from the 15 October 2026 collection snapshot
(`$KIZAMU_DATA/german/vocab/build/source.anki21`). Reviews made after that date stay on the old cards only.

## Pipeline

```bash
python -m german.grammar.prepare          # legacy inventory + authoring inputs
python -m german.grammar.validate --all   # content checks (see AUTHORING.md)
scripts/run-audio.sh german.grammar.audio # Qwen3-TTS + Whisper check, 1 process per GPU, then merge
python -m german.grammar.build            # packages in $KIZAMU_DATA/german/grammar/out/
python -m german.grammar.check            # overlay import test on a copy of the snapshot
```

Content lives in `content/*.json` (one file per topic). It was written and then
reviewed by separate AI passes against `AUTHORING.md`, and validated mechanically.
Audio is synthetic (Qwen3-TTS VoiceDesign, the same voice as the vocab decks). Every
clip was transcribed with Whisper large-v3-turbo and generated again if the transcript
did not match.
