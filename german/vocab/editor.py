"""Dictionary-first editing; generate only missing material, then audit edits.

Existing Goethe and collection examples remain the primary sentence source.
Inflection data is never replaced by a language model's unverified forms.
"""
from __future__ import annotations
import argparse
import collections
import json
import os
import re
import time

from german.vocab.content import save_entry, assemble, LEVELS
from german.vocab.source import BUILD, VOCAB

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
EDITOR = """You are a German-English teacher. Complete a vocabulary card. Return ONLY JSON, no markdown. German must be grammatical Standard German with ß. Preserve the specified headword and sense. Do NOT invent grammar rules. The supplied dictionary forms are authoritative. Give a concise useful usage tip in English (or an empty string if no useful tip). Correct the main English translation if necessary. Give exactly the requested number of NEW, DIFFERENT, short, natural German sentences with accurate English translations. Keep them at the indicated learner level. Each new example must use the German headword or an inflected form (both verb and prefix for separable verbs). Do not repeat supplied examples. Prefer simple everyday sentences of 5–10 words. Use this exact JSON schema: {"english":"concise English equivalents", "usage":"useful usage tip", "examples":[{"de":"German sentence.","en":"English translation."}]}"""


def first_gloss(word, dictionary):
    for record in dictionary.get(word, []):
        for sense in record.get("senses", []):
            if any(g.startswith(("(obsolete)", "(archaic)")) for g in sense.get("glosses", [])): continue
            for gloss in sense.get("glosses", []):
                if len(gloss) < 100: return gloss
    return ""


def draft_entries():
    groups = json.loads((BUILD / "groups.json").read_text())
    dictionary = json.loads((BUILD / "dictionary.json").read_text())
    targets = {g["headword"] for g in groups}
    notes = {n["nid"]: n for n in json.loads((BUILD / "source-notes.json").read_text())}
    drafts = []
    for group in groups:
        path = BUILD / f"enriched/{group['id']}.json"
        if path.exists() and json.loads(path.read_text()).get("editorial_method") == "reviewed pilot":
            continue
        e = dict(group)
        evidence = e["dictionary"]
        desired = "noun" if e["german"].startswith(("der ", "die ", "das ")) else None
        selected = next((d for d in evidence if d["pos"] == desired), evidence[0] if evidence else {})
        pos = selected.get("pos", "phrase" if " " in e["headword"] else "word")
        e["pos"] = {"adj":"adjective", "adv":"adverb", "prep":"preposition", "conj":"conjunction", "pron":"pronoun", "num":"number", "intj":"interjection", "name":"proper noun"}.get(pos, pos)
        forms = selected.get("forms", [])
        if pos == "noun" and forms and not e["german"].startswith(("der ","die ","das ","der/die ")):
            match = re.search(r"\b([mfnp])(?:\s|\b)", forms[0][len(e["headword"]):])
            if match: e["german"] = {"m":"der", "f":"die", "n":"das", "p":"die"}[match[1]] + " " + e["headword"]
        e["grammar"] = "; ".join(forms) or "; ".join(e["source_forms"][:2]) or e["german"]
        meanings = selected.get("meanings", [])
        e["meanings"] = meanings[:3] or e["source_definitions"][:3]
        if not e["meanings"]: raise ValueError(f"No definition evidence: {e['headword']}")
        e["english"] = next((m for m in meanings if len(m)<100), "; ".join(e["source_definitions"][:2]))
        # Keep the source's learner-facing translation as input to the editor;
        # dictionary senses are displayed separately and ground corrections.
        if e["source_definitions"]: e["english"] = e["source_definitions"][0]
        related = []
        for item in selected.get("related", []):
            kind, word = item.split(": ", 1)
            if word not in targets or word == e["headword"]: continue
            gloss = first_gloss(word, dictionary)
            label = {"synonyms":"synonym", "antonyms":"antonym", "related":"related word", "derived":"word family"}[kind]
            related.append(f"{word}: {gloss} ({label})" if gloss else f"{word} ({label})")
        e["related"] = list(dict.fromkeys(related))[:4]
        existing = [x for x in e["source_examples"] if len(x["de"].split())>=3 and x.get("en") and len(x["en"])<250 and "\n" not in x["de"] and not x["de"].endswith(("...", ":"))]
        e["examples"] = existing[:3]
        e["usage"] = next((notes[nid]["usage"] for nid in e["source_note_ids"] if notes[nid]["usage"] and len(notes[nid]["usage"])<400), "")
        e["editorial_method"] = "Goethe/collection examples; English Wiktionary definitions and inflections; local editing"
        drafts.append(e)
    (BUILD / "drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=2)+"\n")
    print(f"Drafted {len(drafts)} entries; {sum(3-len(e['examples']) for e in drafts)} additional sentences needed",flush=True)


def validate_edit(text, entry):
    start, end = text.find("{"), text.rfind("}")
    edit = json.loads(text[start:end+1])
    english = edit.get("english", "")
    if isinstance(english,list): english = "; ".join(english)
    if not isinstance(english,str) or not english.strip(): raise ValueError("Missing English")
    new = edit.get("examples",[])
    if len(new)!=3-len(entry["examples"]): raise ValueError("Wrong number of new examples")
    all_examples = entry["examples"] + new
    if len({x["de"].casefold() for x in all_examples})!=3: raise ValueError("Repeated example")
    for example in new:
        if not isinstance(example.get("de"),str) or not isinstance(example.get("en"),str): raise ValueError("Invalid example")
        if not 8<len(example["de"])<=160 or not 5<len(example["en"])<=220: raise ValueError("Example length")
    result = dict(entry, english=english.strip(), examples=all_examples)
    result["usage"] = edit.get("usage", "") or entry["usage"]
    if not isinstance(result["usage"],str): raise ValueError("Invalid usage")
    result["generated_examples"] = len(new)
    result["content_audit"] = "pending"
    return result


def edit_entries(args):
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import batch_generate
    from mlx_lm.sample_utils import make_sampler
    entries = json.loads((BUILD / "drafts.json").read_text())
    pending = [e for e in entries if not (BUILD / f"enriched/{e['id']}.json").exists()]
    # Similar output lengths share a batch; complete source entries require
    # only a translation and usage check, not three regenerated examples.
    pending.sort(key=lambda e: (-len(e["examples"]),e["id"]))
    if args.limit: pending=pending[:args.limit]
    print(f"Editing {len(pending)} entries, batch size {args.batch_size}",flush=True)
    model,tokenizer=load(MODEL)
    failures=[]
    for offset in range(0,len(pending),args.batch_size):
        batch=pending[offset:offset+args.batch_size]
        prompts=[]
        for e in batch:
            data={"headword":e["german"],"level":e["level"],"sense":e["cue_en"],"english":e["english"],"dictionary":e["meanings"],"forms":e["grammar"],"existing_examples":e["examples"],"new_examples_needed":3-len(e["examples"])}
            prompts.append(tokenizer.apply_chat_template([{"role":"system","content":EDITOR},{"role":"user","content":json.dumps(data,ensure_ascii=False)}],tokenize=True,add_generation_prompt=True,enable_thinking=False))
        start=time.monotonic()
        response=batch_generate(model,tokenizer,prompts,max_tokens=420,sampler=make_sampler(temp=.2),completion_batch_size=args.batch_size,prefill_batch_size=min(8,args.batch_size))
        for e,output in zip(batch,response.texts):
            try: save_entry(validate_edit(output,e))
            except Exception as error: failures.append({"id":e["id"],"headword":e["german"],"error":str(error),"output":output})
        (BUILD / "editor-failures.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2)+"\n")
        print(f"Edited {min(offset+len(batch),len(pending))}/{len(pending)}; {time.monotonic()-start:.1f}s; {response.stats.generation_tps:.1f} tokens/s; failures {len(failures)}",flush=True)
        mx.clear_cache()
    assemble()
    if failures: raise RuntimeError(f"{len(failures)} entries need repair; rerun resumes pending entries")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["draft","edit"])
    p.add_argument("--batch-size",type=int,default=8)
    p.add_argument("--limit",type=int)
    a=p.parse_args()
    draft_entries() if a.command=="draft" else edit_entries(a)
