# Review guide · kizamu-english C2

Second pass over content files written by another agent. Read AUTHORING.md first. You
are the editor a careful American publisher would hire: you fix what is wrong or
unnatural and leave what is good alone.

## For every entry, check

1. **Naturalness.** Would an educated American say or write each example and the drill
   sentence exactly like this today? Fix stiff word order, wrong collocations, missing
   contractions in speech, British vocabulary or spelling (*flat, holiday, colour,
   organise, whilst*), and sentences that only exist to show the word.
2. **Correct sense.** The meaning matches the catalogue gloss and real usage. The
   examples use the item in that sense. Nothing is invented.
3. **Usage note quality.** 2–3 sentences, specific to this item: where it fits, tone,
   typical grammar, what to avoid. Generic advice ("Use it in formal contexts") is not
   enough — make it specific.
4. **Labels.** `register` and `region` are right. A slang item must not be marked
   neutral; a phrase that is mainly British must not be marked `both`.
5. **Drill.** Only the target fits the gap; the hint does not give the answer away and
   is not misleading; for grammar, the transformation is correct and natural; for
   `say`/`listen`, the sentence shows the sound point well.
6. **Facts.** IPA is General American and correct (stress mark position, /ɑ/ vs /ɔ/
   as Americans say it, flap not shown as /t/ only if you are sure it is phonemic form —
   use phonemic slashes consistently). Respellings match the IPA. Origins are
   well established; delete doubtful origins. Grammar rules are correct.
7. **Mistake.** A real learner error with a correct fix and a one-sentence reason. Delete
   invented mistakes (outside nuance, grammar and pronunciation, `mistake` is optional).
8. **Related.** Real near-synonyms with a real difference.
9. **No divisive politics** in examples (AUTHORING.md rule 12): replace sentences about
   vaccines, abortion, guns, election fraud, immigration policy, politicians, religion.
10. **Variety.** The three examples are in different contexts and different sentence
   frames; examples across the file do not all sound alike.

## How to work

- Edit the JSON file in place. Keep ids, order and the file structure.
- Run `python -m english.validate <file>` after editing; it must print `OK`
  (or `partial … OK` for a pilot file).
- At the end, report: number of entries changed, the most common problem types, and any
  entry you think should be replaced entirely (with the reason).
