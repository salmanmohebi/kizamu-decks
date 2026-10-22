"""vLLM audit of the 30B candidates with Qwen3 235B FP8 (tensor parallel over several GPUs)."""
from __future__ import annotations

import argparse
import json
import os
import time

from german.vocab.content_cuda import (
    AUDITED, GENERATED, MODEL as GENERATOR_MODEL, atomic_json, audit_prompt,
    validate_full,
)
from german.vocab.source import BUILD, VOCAB

MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"
GATE_IDS = ("00083a6e13bccdb3", "00261fc83bbd94e3")  # hart, freundlich

VERIFY_SYSTEM = """You are the skeptical final verifier of a German-English Goethe A1-B1 vocabulary card. The card has already been edited once, but assume it still contains a subtle error. Return ONLY corrected JSON, with no markdown and no wrapper object. Use exactly this schema:
{"english":"short common English equivalents","pos":"part of speech","grammar":"concise correct forms and grammar","meanings":["useful common meaning"],"related":["German word: English gloss (relationship)"],"usage":"specific verified usage tip, or a short neutral usage note","examples":[{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."},{"de":"German sentence.","en":"English translation."}]}

Verify each claim independently. In particular:
- Check the usage note for contradictions, invented restrictions, and incorrect linguistic categories. German adjectives can be used uninflected as adverbials with verbs; do not deny that normal use.
- Translate every German example literally enough to detect additions, omissions, wrong tense, wrong subject, or changed register, then give an exact natural English translation.
- Require three distinct, idiomatic, punctuated, complete German sentences or utterances with finite verbs; reject greetings, sign-offs, labels, and fragments.
- Check inflections, auxiliary, separability, cases, prepositions, spelling with ß, meanings, and related words.
- Prefer concise verified information. Rewrite any doubtful text instead of defending it.
"""


def known_quality_gate(result: dict) -> None:
    """Block regressions that caused earlier benchmark rejection."""
    usage = result["usage"].casefold()
    if result["id"] in GATE_IDS and not ("adverb" in usage or "adverbial" in usage):
        raise ValueError("Known adjective/adverb distinction was not addressed")
    if result["id"] == GATE_IDS[0]:
        for example in result["examples"]:
            if "home" in example["en"].casefold() and not any(
                marker in example["de"].casefold()
                for marker in ("zu hause", "nach hause", "heim")
            ):
                raise ValueError("English translation adds 'home' absent from German")
    if result["id"] == GATE_IDS[1] and any(
        "mit freundlichen grüßen" in example["de"].casefold()
        for example in result["examples"]
    ):
        raise ValueError("Sign-off fragment retained as an example sentence")


def main(args) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from vllm import LLM, SamplingParams

    groups = {x["id"]: x for x in json.loads((BUILD / "groups.json").read_text())}
    entries = []
    cached_gates = []
    for entry_id in sorted(groups):
        source = GENERATED / f"{entry_id}.json"
        target = AUDITED / f"{entry_id}.json"
        gate_valid = False
        if entry_id in GATE_IDS and target.exists() and not args.force:
            try:
                cached = json.loads(target.read_text())
                if not cached.get("content_audit", "").startswith("passed two-pass"):
                    raise ValueError("not a current two-pass result")
                known_quality_gate(cached)
                gate_valid = True
                cached_gates.append(entry_id)
            except Exception:
                gate_valid = False
        if source.exists() and (args.force or (entry_id in GATE_IDS and not gate_valid) or not target.exists()):
            entries.append(json.loads(source.read_text()))
    if cached_gates:
        print(f"Validated cached quality gates: {', '.join(cached_gates)}", flush=True)
    entries.sort(key=lambda entry: (entry["id"] not in GATE_IDS, entry["id"]))
    if args.limit is not None:
        entries = entries[:args.limit]
    print(f"235B audit: {len(entries)} candidates pending", flush=True)
    if not entries:
        return

    llm = LLM(
        model=args.model, tensor_parallel_size=args.tensor_parallel_size,
        dtype="auto", max_model_len=4096,
        gpu_memory_utilization=args.gpu_memory_utilization,
        distributed_executor_backend="mp", enforce_eager=args.enforce_eager,
        enable_prefix_caching=True,
    )
    tokenizer = llm.get_tokenizer()
    sampling = SamplingParams(temperature=args.temperature, max_tokens=args.max_tokens)
    failures = []
    began = time.monotonic()
    gate_count = sum(entry["id"] in GATE_IDS for entry in entries)
    batches = ([entries[:gate_count]] if gate_count else []) + [
        entries[offset : offset + args.batch_size]
        for offset in range(gate_count, len(entries), args.batch_size)
    ]
    done = 0
    for batch_number, batch in enumerate(batches):
        failures_before = len(failures)
        prompts = []
        for entry in batch:
            system, data = audit_prompt(entry, groups[entry["id"]])
            prompts.append(tokenizer.apply_chat_template(
                [{"role": "system", "content": system},
                 {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
                tokenize=False, add_generation_prompt=True,
            ))
        started = time.monotonic()
        outputs = llm.generate(prompts, sampling, use_tqdm=False)
        provisional = []
        verified_entries = []
        for entry, output in zip(batch, outputs):
            text = output.outputs[0].text
            try:
                result = validate_full(text, entry)
                provisional.append(result)
                verified_entries.append(entry)
            except Exception as error:
                failures.append({"id": entry["id"], "german": entry["german"],
                                 "error": f"editor pass: {error}", "output": text})
        verify_prompts = []
        for result in provisional:
            compact_card = {k: result[k] for k in (
                "english", "pos", "grammar", "meanings", "related", "usage", "examples"
            )}
            verify_prompts.append(tokenizer.apply_chat_template(
                [{"role": "system", "content": VERIFY_SYSTEM},
                 {"role": "user", "content": json.dumps({
                     "card_to_verify": compact_card,
                     "source_evidence": {k: groups[result["id"]][k] for k in (
                         "german", "headword", "level", "cue_en", "source_definitions",
                         "source_forms", "source_examples", "dictionary")},
                 }, ensure_ascii=False)}],
                tokenize=False, add_generation_prompt=True,
            ))
        verified_outputs = llm.generate(verify_prompts, sampling, use_tqdm=False) if verify_prompts else []
        for entry, output in zip(verified_entries, verified_outputs):
            text = output.outputs[0].text
            try:
                result = validate_full(text, entry, final_checks=True)
                known_quality_gate(result)
                result["editorial_method"] = (
                    f"{GENERATOR_MODEL} generation; {MODEL} independent editorial and verification passes"
                )
                result["content_audit"] = "passed two-pass 235B FP8 final audit and semantic lint"
                atomic_json(AUDITED / f"{entry['id']}.json", result)
            except Exception as error:
                failures.append({"id": entry["id"], "german": entry["german"],
                                 "error": f"verification pass: {error}", "output": text})
        atomic_json(BUILD / "content-audit-235b-failures.json", failures)
        done += len(batch)
        print(f"235B audit {done}/{len(entries)}; "
              f"batch {time.monotonic()-started:.1f}s; failures {len(failures)}; "
              f"elapsed {(time.monotonic()-began)/60:.1f}m", flush=True)
        if batch_number == 0 and gate_count:
            if len(failures) != failures_before:
                raise RuntimeError("Known-problem quality gate failed; production audit stopped")
            for entry_id in GATE_IDS:
                path = AUDITED / f"{entry_id}.json"
                if path.exists():
                    result = json.loads(path.read_text())
                    print("QUALITY_GATE " + json.dumps({
                        "german": result["german"], "usage": result["usage"],
                        "examples": result["examples"],
                    }, ensure_ascii=False), flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} 235B audit outputs failed; rerun resumes missing entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--enforce-eager", action="store_true")
    main(parser.parse_args())
