"""CUDA content generation and independent audit for the Goethe decks.

Run one process per GPU.  Shards are deterministic and write one atomic JSON
file per entry, so interrupted jobs can be resumed without repeating work.
The approved pilot entries are never regenerated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

from german.vocab.content import SYSTEM as FULL_CARD_SYSTEM, save_entry, assemble
from german.vocab.source import BUILD, VOCAB

MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
GENERATED = BUILD / "content-generated"
AUDITED = BUILD / "content-audited"
PILOT_METHOD = "reviewed pilot"

AUDIT_SYSTEM = """You are the final senior editor for German-English Goethe A1-B1 vocabulary cards. Return ONLY JSON, with no markdown. Treat the supplied card as untrusted: independently verify and actively rewrite every inaccurate, awkward, contradictory, or overbroad claim. Check every field for Standard German grammar, idiomatic usage, accurate English, correct learner level, and exact sentence translations. Preserve reliable dictionary/source inflections and the specified headword and sense; correct a supplied form only when clearly wrong. Remove obscure senses and invented related words.

Non-negotiable checks:
- Each of exactly three distinct German examples is a complete, natural standalone sentence or utterance with a finite verb, not a greeting, sign-off, title, label, or noun-phrase fragment. It must naturally contain the headword or an inflected/reflexive/separated form.
- Cross-check the usage note against the examples and grammar. Never invent a restriction. German adjectives normally have uninflected adverbial uses with verbs, so never claim an adjective cannot modify a verb merely because it is an adjective.
- Give exact English translations, not loose paraphrases that change the meaning or register.
- Prefer a short neutral usage note over a doubtful prescriptive rule.

Use Standard German spelling with ß. Keep explanations concise. Use exactly this schema:
{"english":"short common English equivalents","pos":"part of speech","grammar":"concise correct forms and grammar","meanings":["useful common meaning"],"related":["German word: English gloss (relationship)"],"usage":"specific usage tip, or a short neutral usage note","examples":[{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."}]}"""


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def shard_for(entry_id: str, count: int) -> int:
    return int(hashlib.sha256(entry_id.encode()).hexdigest()[:16], 16) % count


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object")
    payload = text[start : end + 1]
    # A rare Qwen typo closes the final example object with ')' instead of '}'.
    # Repair only that unambiguous end-of-document shape; the validator still
    # checks the complete schema immediately afterwards.
    payload = re.sub(r"\)\s*\]\s*\}\s*$", "}]}", payload)
    return json.loads(payload)


def validate_full(text: str, entry: dict, final_checks: bool = False) -> dict:
    obj = parse_json(text)
    if isinstance(obj.get("english"), list):
        obj["english"] = "; ".join(obj["english"])
    for field in ("english", "pos", "grammar", "usage"):
        if not isinstance(obj.get(field), str) or not obj[field].strip():
            raise ValueError(f"Missing {field}")
    for field in ("meanings", "related"):
        if not isinstance(obj.get(field), list) or not all(isinstance(x, str) and x.strip() for x in obj[field]):
            raise ValueError(f"Invalid {field}")
    if not obj["meanings"]:
        raise ValueError("Empty meanings")
    examples = obj.get("examples")
    if not isinstance(examples, list) or len(examples) != 3:
        raise ValueError("Exactly three examples required")
    if len({x.get("de", "").strip().casefold() for x in examples}) != 3:
        raise ValueError("Repeated examples")
    for example in examples:
        if not isinstance(example.get("de"), str) or not isinstance(example.get("en"), str):
            raise ValueError("Invalid example")
        if not 8 < len(example["de"]) <= 220 or not 5 < len(example["en"]) <= 260:
            raise ValueError("Example length")
        if example["de"].rstrip()[-1:] not in ".?!" or example["en"].rstrip()[-1:] not in ".?!":
            raise ValueError("Examples must be punctuated complete sentences")
        if "{{" in example["de"] or "[sound:" in example["de"]:
            raise ValueError("Invalid markup")
    if final_checks and re.search(
        r"\b(?:cannot|can't|does not|doesn't|must not)\s+(?:directly\s+)?modify\s+verbs?\b",
        obj["usage"], re.IGNORECASE,
    ):
        raise ValueError("False or misleading restriction on German adverbial adjective use")
    result = dict(entry)
    result.update(obj)
    return result


def generation_prompt(entry: dict, group: dict) -> tuple[str, dict]:
    evidence = {k: group[k] for k in (
        "german", "headword", "level", "cue_en", "source_definitions",
        "source_forms", "source_examples", "dictionary"
    )}
    evidence["dictionary_first_draft"] = {k: entry[k] for k in (
        "english", "pos", "grammar", "meanings", "related", "usage", "examples"
    )}
    return FULL_CARD_SYSTEM, evidence


def audit_prompt(entry: dict, group: dict) -> tuple[str, dict]:
    evidence = {k: group[k] for k in (
        "german", "headword", "level", "cue_en", "source_definitions",
        "source_forms", "source_examples", "dictionary"
    )}
    return AUDIT_SYSTEM, {"card": entry, "source_evidence": evidence}


def load_inputs(stage: str) -> list[dict]:
    groups = json.loads((BUILD / "groups.json").read_text())
    group_by_id = {x["id"]: x for x in groups}
    if stage == "generate":
        values = []
        for entry in json.loads((BUILD / "drafts.json").read_text()):
            pilot = BUILD / "enriched" / f"{entry['id']}.json"
            if pilot.exists() and json.loads(pilot.read_text()).get("editorial_method") == PILOT_METHOD:
                continue
            values.append(entry)
        return values
    if stage == "audit":
        values = []
        for group in groups:
            pilot = BUILD / "enriched" / f"{group['id']}.json"
            if pilot.exists() and json.loads(pilot.read_text()).get("editorial_method") == PILOT_METHOD:
                continue
            path = GENERATED / f"{group['id']}.json"
            if path.exists():
                values.append(json.loads(path.read_text()))
        return values
    raise ValueError(stage)


def run(args) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    destination = GENERATED if args.stage == "generate" else AUDITED
    groups = {x["id"]: x for x in json.loads((BUILD / "groups.json").read_text())}
    entries = [x for x in load_inputs(args.stage)
               if shard_for(x["id"], args.shard_count) == args.shard_index
               and (args.force or not (destination / f"{x['id']}.json").exists())]
    entries.sort(key=lambda x: x["id"])
    if args.limit is not None:
        entries = entries[:args.limit]
    print(f"{args.stage}: shard {args.shard_index}/{args.shard_count}, {len(entries)} pending", flush=True)
    if not entries:
        return

    tokenizer = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    device_map = "auto" if args.device_map == "auto" else {"": 0}
    load_options = {
        "dtype": args.dtype, "device_map": device_map,
        "attn_implementation": "sdpa", "low_cpu_mem_usage": True,
    }
    if args.device_map == "auto" and args.max_memory_per_gpu:
        load_options["max_memory"] = {index: args.max_memory_per_gpu for index in range(torch.cuda.device_count())}
    model = AutoModelForCausalLM.from_pretrained(args.model, **load_options).eval()
    failures = []
    began = time.monotonic()
    for offset in range(0, len(entries), args.batch_size):
        batch = entries[offset : offset + args.batch_size]
        texts = []
        for entry in batch:
            system, data = (generation_prompt(entry, groups[entry["id"]]) if args.stage == "generate"
                            else audit_prompt(entry, groups[entry["id"]]))
            texts.append(tokenizer.apply_chat_template(
                [{"role": "system", "content": system},
                 {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
                tokenize=False, add_generation_prompt=True,
            ))
        inputs = tokenizer(texts, return_tensors="pt", padding=True).to(model.device)
        started = time.monotonic()
        with torch.inference_mode():
            outputs = model.generate(
                **inputs, max_new_tokens=args.max_new_tokens, do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        decoded = tokenizer.batch_decode(outputs[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        for entry, text in zip(batch, decoded):
            try:
                if args.stage == "generate":
                    result = validate_full(text, entry)
                    result["editorial_method"] = f"{args.model}; dictionary-grounded CUDA generation"
                    result["content_audit"] = "pending independent second pass"
                else:
                    result = validate_full(text, entry)
                    result["editorial_method"] = f"{args.model}; dictionary-grounded generation plus independent audit"
                    result["content_audit"] = "passed automated second-pass audit"
                atomic_json(destination / f"{entry['id']}.json", result)
            except Exception as error:
                failures.append({"id": entry["id"], "german": entry["german"],
                                 "error": str(error), "output": text})
        atomic_json(BUILD / f"content-{args.stage}-failures-shard-{args.shard_index}.json", failures)
        done = min(offset + len(batch), len(entries))
        print(f"{args.stage} {done}/{len(entries)}; batch {time.monotonic()-started:.1f}s; "
              f"failures {len(failures)}; elapsed {(time.monotonic()-began)/60:.1f}m", flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} {args.stage} outputs failed validation; rerun resumes missing entries")


def promote() -> None:
    groups = json.loads((BUILD / "groups.json").read_text())
    missing = []
    for group in groups:
        current = BUILD / "enriched" / f"{group['id']}.json"
        if current.exists() and json.loads(current.read_text()).get("editorial_method") == PILOT_METHOD:
            continue
        audited = AUDITED / f"{group['id']}.json"
        if not audited.exists():
            missing.append(group["id"])
            continue
        result = json.loads(audited.read_text())
        validate_full(json.dumps({k: result[k] for k in ("english", "pos", "grammar", "meanings", "related", "usage", "examples")}, ensure_ascii=False), result, final_checks=True)
        save_entry(result)
    if missing:
        raise RuntimeError(f"Cannot promote: {len(missing)} audited entries missing")
    assemble()
    atomic_json(BUILD / "content-production-summary.json", {
        "entries": len(groups), "approved_pilot_entries": 20,
        "audited_production_entries": len(groups) - 20,
        "generation_model": MODEL,
        "audit_model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "audit": "independent final audit (Qwen3 235B) plus structural validation",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["generate", "audit", "promote"])
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--dtype", default="bfloat16", choices=["auto", "bfloat16"])
    parser.add_argument("--device-map", default="single", choices=["single", "auto"])
    parser.add_argument("--max-memory-per-gpu", help="with --device-map auto, e.g. 40GiB (default: let accelerate decide)")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=700)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    if not 0 <= arguments.shard_index < arguments.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    promote() if arguments.stage == "promote" else run(arguments)
