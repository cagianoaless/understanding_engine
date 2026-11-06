"""Frozen, paired development evaluation with fresh worker processes."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

from understanding_engine.contracts import json_bytes
from understanding_engine.structure import reconstruct as original
from understanding_engine.structure_v2 import reconstruct as proposed, RobustSettings

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("score004", ROOT.parent / "004/run.py")
SCORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORE)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def worker(args, annotation):
    raw = args.source.read_bytes()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    output = (original(raw, page_numbers=[annotation["page_number"]]) if args.engine == "original" else
              proposed(raw, settings=RobustSettings(**json.loads((ROOT / "config.json").read_bytes())),
                       page_numbers=[annotation["page_number"]]))
    payload = json_bytes(output)
    duration = time.perf_counter() - started
    (args.output_dir / "structure.json").write_bytes(payload)
    page = output["pages"][0]
    result = SCORE.score(page, annotation)
    heading_refs = sum(r["type"] == "heading" for r in annotation["regions"])
    heading_preds = sum(r["type"] == "heading" and SCORE.in_windows(r, annotation["windows"]) for r in page["regions"])
    heading_tp = sum(d["type_correct"] and d["reference"]["type"] == "heading" for d in result["region_decisions"])
    original_page = json.loads(raw)["pages"][annotation["page_number"] - 1]
    refs = [ref for region in page["regions"] for ref in region["source_character_ids"]]
    result["metrics"].update(heading_references=heading_refs, heading_predictions=heading_preds,
                             heading_tp=heading_tp, heading_fp=heading_preds - heading_tp,
                             heading_fn=heading_refs - heading_tp)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result.update(document_id=annotation["document_id"], layout_type=annotation["layout"],
                  page_number=annotation["page_number"], engine=args.engine, verification="agent_visual_checked",
                  seconds=duration, output_bytes=len(payload), peak_process_rss_bytes=rss if sys.platform == "darwin" else rss * 1024,
                  source_characters=len(original_page["characters"]),
                  all_source_references_once=sorted(refs) == sorted(c["id"] for c in original_page["characters"]),
                  extraction_sha256=digest(raw), input_unchanged=args.source.read_bytes() == raw,
                  structure_sha256=digest(payload), implementation_sha256=output["algorithm"]["implementation_sha256"],
                  relation_count=len(page["relations"]), explicit_ambiguity_count=len(page["ambiguities"]))
    (args.output_dir / "result.json").write_bytes(json_bytes(result))
    print(json.dumps({"document": annotation["document_id"], "engine": args.engine, "metrics": result["metrics"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="append", default=[])
    parser.add_argument("--extraction", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--engine", choices=["original", "proposed"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--annotation-index", type=int)
    args = parser.parse_args()
    raw = (ROOT / "annotations.json").read_bytes()
    annotations = json.loads(raw)
    freeze = json.loads((ROOT / "freeze.json").read_bytes())
    if digest(raw) != freeze["annotations_sha256"]:
        raise ValueError("Frozen annotations changed")
    if args.worker:
        worker(args, annotations["documents"][args.annotation_index])
        return
    paths = {}
    expected_ids = {d["document_id"] for d in annotations["documents"]}
    for name in ["pdf", "extraction"]:
        items = [s.split("=", 1) for s in getattr(args, name)]
        paths[name] = {key: Path(value) for key, value in items}
        if len(items) != len(paths[name]) or set(paths[name]) != expected_ids:
            raise ValueError(f"Supply each PDF/extraction exactly once ({name})")
    hashes = {}
    for d in annotations["documents"]:
        name = d["document_id"]
        pdf_hash = digest(paths["pdf"][name].read_bytes())
        extraction = paths["extraction"][name].read_bytes()
        if pdf_hash != d["source_sha256"] or json.loads(extraction)["source_sha256"] != pdf_hash:
            raise ValueError("PDF/extraction hash provenance differs")
        hashes[name] = {"pdf": pdf_hash, "extraction": digest(extraction)}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    results, commands = [], []
    for i, d in enumerate(annotations["documents"]):
        for engine in ["original", "proposed"]:
            target = args.output_dir / f"{d['document_id']}-{engine}"
            argv = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--engine", engine,
                    "--source", str(paths["extraction"][d["document_id"]].absolute()),
                    "--annotation-index", str(i), "--output-dir", str(target)]
            with (args.output_dir / f"{d['document_id']}-{engine}.stdout.log").open("wb") as stdout, (args.output_dir / f"{d['document_id']}-{engine}.stderr.log").open("wb") as stderr:
                try:
                    run = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=300)
                    exit_code = run.returncode
                except subprocess.TimeoutExpired:
                    exit_code = 124
                    stderr.write(b"Evaluation worker exceeded the predeclared 300-second limit.\n")
            commands.append({"argv": argv, "exit_code": exit_code})
            if exit_code:
                # Failures keep the complete reference denominator and score as missing output.
                empty = {"regions": [], "relations": [], "lines": [], "columns": [], "layout": "unknown"}
                failure = SCORE.score(empty, d)
                failure["metrics"].update(heading_references=sum(r["type"] == "heading" for r in d["regions"]),
                                          heading_predictions=0, heading_tp=0, heading_fp=0,
                                          heading_fn=sum(r["type"] == "heading" for r in d["regions"]))
                failure.update(document_id=d["document_id"], page_number=d["page_number"], engine=engine,
                               layout_type=d["layout"], failed=True, all_source_references_once=False)
                results.append(failure)
            else:
                results.append(json.loads((target / "result.json").read_bytes()))
    for d in annotations["documents"]:
        name = d["document_id"]
        if digest(paths["pdf"][name].read_bytes()) != hashes[name]["pdf"] or digest(paths["extraction"][name].read_bytes()) != hashes[name]["extraction"]:
            raise ValueError("Input changed during evaluation")
    summary = {"experiment": "005: structural robustness", "annotations_sha256": digest(raw),
               "human_verified_count": 0, "verification": "agent_visual_checked", "source_hashes": hashes,
               "repository_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "python": platform.python_version(), "platform": platform.platform(), "commands": commands,
               "scope": "Single measured reconstruction per engine/document in a fresh process; cached v1 extraction read before timing; source validation, structure generation, contract validation and serialization timed; RSS is whole worker including imports/scoring, not incremental allocations",
               "results": results}
    (args.output_dir / "summary.json").write_bytes(json_bytes(summary))
    print(json.dumps([{"document": r["document_id"], "engine": r["engine"], "metrics": r["metrics"]} for r in results], indent=2))


if __name__ == "__main__":
    main()
