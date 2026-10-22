# Review guide · second pass

You are the second, independent reviewer of a content file written by another author
according to `AUTHORING.md`. Assume there are mistakes. Your job is to find and fix them.

For every file:

1. Read `AUTHORING.md`, the input `$KIZAMU_DATA/german/grammar/build/inputs/<topic_id>.json`, the content file, and the
   author's notes in `$KIZAMU_DATA/german/grammar/build/author-notes/` if one mentions your topic (check those doubts first).
2. Check **every** German string (item sentences, examples, mistake.why, drill prompts/answers,
   alternatives, rule table): grammar, case, gender, endings, verb position, spelling, comma
   rules, naturalness. Check every cloze: is the answer the only good answer, given the
   English, the hint and the focus? Does the hint or focus give the answer away?
3. Check every explanation: is it correct, specific to *its* sentence, and does it derive the
   form? Is the English translation accurate?
4. Mistake sentences: must be clearly wrong. A sentence that is only "odd in context" is
   acceptable only if the `why` makes the clash explicit; prefer a clear grammar error.
5. Drills: `error` prompts must contain exactly one error; `choice` must have exactly one
   correct option; `order` drills must either have one correct order or list the others;
   `transform`/`combine` answers must be the most natural result.
6. Fix problems directly in the content file (keep keys, legacy German text, cloze numbers;
   use `correction` only for a real error in a legacy sentence). Run
   `python -m german.grammar.validate <file>` after editing: it must print OK.
7. Write `$KIZAMU_DATA/german/grammar/build/review/<topic_id>.md`: a short list of what you changed (key → what/why),
   and anything you were unsure about. If nothing needed fixing, say so.

Do not rewrite good content for style. Do not shorten explanations. Only edit your files.
