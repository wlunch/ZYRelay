"""Run local or HTTP Relay benchmarks and save portable, inspectable results."""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
import tracemalloc
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import (
    BENCHMARK_ROOT,
    CASES_ROOT,
    RESULTS_ROOT,
    json_dump,
    json_load,
    load_yaml,
    now_utc,
)


def _sanitize(value: Any) -> Any:
    root = str(BENCHMARK_ROOT.parent.resolve())
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith(root):
        return value.replace(root, ".", 1)
    return value


def _evaluate(case: dict, result: dict) -> dict:
    payload = result.get("result", {})
    blocks = payload.get("blocks", [])
    conventions = payload.get("code_conventions", [])
    semantic_objects = payload.get("semantic_objects", [])
    model_executions = payload.get("model_executions", [])
    expected = case["expected"]
    expected_items = 0
    matched_items = 0
    checks: dict[str, bool] = {}
    for key, actual, minimum in [
        ("minimum_blocks", len(blocks), int(expected.get("minimum_blocks", 0))),
        (
            "minimum_conventions",
            len(conventions),
            int(expected.get("minimum_conventions", 0)),
        ),
    ]:
        checks[key] = actual >= minimum
        if minimum:
            expected_items += 1
            matched_items += int(checks[key])
    evidence_valid = (
        all(item.get("source_evidence") for item in conventions)
        if conventions
        else True
    )
    provenance_valid = (
        all(item.get("provenance_id") for item in conventions) if conventions else True
    )
    block_order_valid = all(
        block.get("sequence") == index for index, block in enumerate(blocks)
    )
    checks.update(
        evidence_valid=evidence_valid,
        provenance_valid=provenance_valid,
        block_order_valid=block_order_valid,
    )
    if expected.get("ocr_executed"):
        model_runs = payload.get("model_executions", [])
        ocr_blocks = [
            block
            for block in blocks
            if block.get("metadata", {}).get("source_method") == "ocr"
        ]
        checks["ocr_executed"] = bool(model_runs)
        checks["non_empty_ocr_text"] = bool(
            ocr_blocks and any(block.get("text", "").strip() for block in ocr_blocks)
        )
        checks["bbox_required"] = bool(
            ocr_blocks
            and all(block.get("metadata", {}).get("bbox") for block in ocr_blocks)
        )
        expected_items += 3
        matched_items += sum(
            int(checks[key])
            for key in ["ocr_executed", "non_empty_ocr_text", "bbox_required"]
        )
    forbidden = []
    if not evidence_valid:
        forbidden.append("evidence_missing")
    if not block_order_valid:
        forbidden.append("invalid_offset")
    semantic_by_type: dict[str, list[dict]] = {}
    for item in semantic_objects:
        semantic_by_type.setdefault(item.get("object_type", "unknown"), []).append(item)
    non_evidence = [
        item for item in semantic_objects if item.get("object_type") != "evidence"
    ]
    evidence_ids = {
        item.get("object_id") for item in semantic_by_type.get("evidence", [])
    }
    semantic_evidence_complete = all(
        item.get("evidence_ids")
        and set(item.get("evidence_ids", [])).issubset(evidence_ids)
        for item in non_evidence
    )
    stable_object_ids = (
        bool(semantic_objects)
        and len({item.get("object_id") for item in semantic_objects})
        == len(semantic_objects)
        and all(
            str(item.get("object_id", "")).startswith("SOBJ-")
            for item in semantic_objects
        )
    )
    expected_entities = set(expected.get("expected_entities", []))
    expected_rules = set(expected.get("expected_rules", []))
    entity_names = {item.get("name") for item in semantic_by_type.get("entity", [])}
    rule_names = {item.get("name") for item in semantic_by_type.get("rule", [])}
    entity_recall = (
        (len(expected_entities & entity_names) / len(expected_entities))
        if expected_entities
        else 1.0
    )
    rule_recall = (
        (len(expected_rules & rule_names) / len(expected_rules))
        if expected_rules
        else 1.0
    )
    if not semantic_evidence_complete:
        forbidden.append("semantic_evidence_incomplete")
    by_capability: dict[str, list[dict]] = {}
    for item in model_executions:
        by_capability.setdefault(item.get("capability", "unknown"), []).append(item)

    def model_metric(capability: str) -> dict[str, Any]:
        runs = by_capability.get(capability, [])
        completed = [item for item in runs if item.get("status") == "completed"]
        return {
            "run_count": len(runs),
            "executed_count": len(completed),
            "skipped_count": sum(item.get("status") == "skipped" for item in runs),
            "average_runtime_ms": round(
                sum(float(item.get("duration_ms", 0)) for item in completed)
                / len(completed),
                4,
            )
            if completed
            else 0.0,
        }

    return {
        "processing_success": result.get("status") in {"completed", "partial"},
        "checks": checks,
        "expected_item_recall": round(matched_items / expected_items, 4)
        if expected_items
        else 1.0,
        "evidence_valid_rate": 1.0 if evidence_valid else 0.0,
        "provenance_valid_rate": 1.0 if provenance_valid else 0.0,
        "forbidden_output_count": len(forbidden),
        "forbidden_outputs": forbidden,
        "block_count": len(blocks),
        "convention_count": len(conventions),
        "warning_count": len(result.get("warnings", [])),
        "error_count": len(result.get("errors", [])),
        "semantic_object_count": len(semantic_objects),
        "relation_count": len(semantic_by_type.get("relation", [])),
        "entity_recall": round(entity_recall, 4),
        "rule_recall": round(rule_recall, 4),
        "semantic_evidence_completeness": 1.0 if semantic_evidence_complete else 0.0,
        "stable_object_id": stable_object_ids,
        "model_metrics": {
            "layout": model_metric("layout"),
            "ocr": model_metric("ocr"),
            "classifier": model_metric("document_classifier"),
            "language": model_metric("language_detection"),
            "ner": model_metric("ner"),
            "code_detector": model_metric("code_detection"),
            "spell": model_metric("spell_correction"),
            "table": model_metric("table_recognition"),
        },
    }


def _local_relay(entry: dict, case: dict, data_root: Path) -> dict:
    from zyrelay.app.core.config import Settings
    from zyrelay.relay import RelayRequest, RelayService
    from zyrelay.relay.models import RelayInput, RelayMode

    path = BENCHMARK_ROOT.parent / entry["local_path"]
    relay = RelayService(Settings(data_root=data_root))
    request = RelayRequest(
        request_id=f"BENCH-{entry['benchmark_id']}",
        enterprise_id="benchmark",
        mode=RelayMode(case["relay"]["mode"]),
        ground_profile_id=case["relay"].get("ground_profile_id"),
        enable_ocr=case["relay"].get("enable_ocr", True),
        output_detail="full",
        input=RelayInput(file_name=path.name, file_path=str(path)),
        metadata={"benchmark_id": entry["benchmark_id"]},
    )
    result = relay.process(request).model_dump(mode="json")
    execution_id = result["execution_id"]
    ground = relay.get_ground(execution_id)
    resources = relay.get_resources(execution_id).model_dump(mode="json")
    models = [item.model_dump(mode="json") for item in relay.get_models(execution_id)]
    provenance = {}
    for convention in result.get("result", {}).get("code_conventions", []):
        identifier = convention.get("provenance_id")
        if identifier:
            provenance[identifier] = relay.get_provenance(identifier).model_dump(
                mode="json"
            )
    return {
        "relay_result": result,
        "ground": ground,
        "resources": resources,
        "models": models,
        "provenance": provenance,
    }


def _http_relay(entry: dict, case: dict, relay_url: str) -> dict:
    import urllib.request
    import uuid

    path = BENCHMARK_ROOT.parent / entry["local_path"]
    boundary = f"----zyrelay{uuid.uuid4().hex}"
    fields = {
        "enable_ocr": str(case["relay"].get("enable_ocr", True)).lower(),
        "output_detail": "full",
        "mode": case["relay"]["mode"],
    }
    chunks = []
    for key, value in fields.items():
        chunks += [
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        ]
    chunks += [
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/pdf\r\n\r\n'.encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        relay_url.rstrip("/") + "/api/v1/relay/process",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        import json

        result = json.loads(response.read())
    return {
        "relay_result": result,
        "ground": {},
        "resources": {},
        "models": result.get("result", {}).get("model_executions", []),
        "provenance": {},
    }


def run_case(
    entry: dict, case: dict, output: Path, local: bool, relay_url: str
) -> dict:
    case_dir = output / entry["benchmark_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    data_root = case_dir / "runtime_data"
    tracemalloc.start()
    execution = (
        _local_relay(entry, case, data_root)
        if local
        else _http_relay(entry, case, relay_url)
    )
    _, peak_memory_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result = _sanitize(execution["relay_result"])
    evaluation = _evaluate(case, result)
    json_dump(case_dir / "relay_result.json", result)
    json_dump(case_dir / "uom.json", result.get("result", {}))
    json_dump(case_dir / "ground.json", _sanitize(execution["ground"]))
    json_dump(case_dir / "resources.json", _sanitize(execution["resources"]))
    json_dump(case_dir / "models.json", _sanitize(execution["models"]))
    json_dump(case_dir / "provenance.json", _sanitize(execution["provenance"]))
    json_dump(case_dir / "metrics.json", _sanitize(result.get("metrics", {})))
    json_dump(case_dir / "evaluation.json", evaluation)
    shutil.rmtree(data_root, ignore_errors=True)
    return {
        "case_id": entry["benchmark_id"],
        "status": result.get("status"),
        **evaluation,
        "duration_ms": result.get("metrics", {}).get("total_duration_ms", 0),
        "peak_memory_bytes": peak_memory_bytes,
        "plugin_comparison": {
            name: metrics.get("executed_count", 0)
            for name, metrics in evaluation.get("model_metrics", {}).items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="all")
    parser.add_argument("--case-id")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--relay-url", default="http://127.0.0.1:8000")
    parser.add_argument("--local", action="store_true", default=True)
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    manifest = json_load(BENCHMARK_ROOT / "manifest.json", {"entries": []})["entries"]
    output = args.output or (RESULTS_ROOT / ("baseline" if args.baseline else "latest"))
    selected = [
        entry
        for entry in manifest
        if (
            args.suite == "all"
            or entry["category"] == args.suite
            or (args.suite == "scanned_document" and entry["is_scanned"])
        )
        and (not args.case_id or entry["benchmark_id"] == args.case_id)
    ]
    summaries = []
    for entry in selected:
        folder = "scanned_document" if entry["is_scanned"] else entry["category"]
        case = load_yaml(CASES_ROOT / folder / f"{entry['benchmark_id']}.yaml")
        try:
            summaries.append(
                run_case(entry, case, output, not args.http, args.relay_url)
            )
        except Exception as exc:
            summaries.append(
                {
                    "case_id": entry["benchmark_id"],
                    "status": "failed",
                    "error": str(exc),
                }
            )
            if args.fail_fast:
                break
    report = {
        "generated_at": now_utc(),
        "relay_version": __import__("zyrelay").__version__,
        "python": sys.version,
        "platform": platform.platform(),
        "cases": summaries,
    }
    json_dump(output / "summary.json", report)
    print(
        f"cases={len(summaries)} success={sum(item.get('status') in {'completed', 'partial'} for item in summaries)}"
    )
    return 1 if any(item.get("status") == "failed" for item in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
