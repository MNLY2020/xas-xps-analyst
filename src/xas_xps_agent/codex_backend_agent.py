#!/usr/bin/env python3
"""Thin Codex-facing backend entrypoint for the local XPS/XAS agent.

This wrapper keeps integration simple: one request in, one report bundle plus
one compact JSON response out. It intentionally reuses run_xas_xps_agent.py
instead of introducing a GUI, server, queue, or extra dependency layer.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .run_xas_xps_agent import run
except ImportError:  # pragma: no cover - supports direct script execution.
    from run_xas_xps_agent import run


DEFAULT_OUTPUT_DIR = Path("outputs/xas_xps_agent_codex_backend")
DEFAULT_RESPONSE_NAME = "codex_response.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_request(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid request JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Request JSON must be an object: {path}")
    return data


def path_from(value: Any, default: Path | None = None) -> Path | None:
    if value in (None, ""):
        return default
    return Path(str(value))


def compact_metrics(aggregates: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "files_seen",
        "files_parsed",
        "file_parse_success_rate",
        "record_parse_success_rate",
        "xas_files_parsed",
        "xps_files_parsed",
        "qc_warning_count",
        "qc_error_count",
        "xps_records",
        "xps_backend_method",
        "xps_backend_fit_attempt_count",
        "xps_backend_fit_success_count",
        "xps_backend_fit_failed_count",
        "xps_reference_assignment_count",
        "xps_reference_assignment_review_required_count",
        "xps_reference_gap_count",
        "xps_reference_gap_review_required_count",
        "xps_reference_gap_coverage",
        "report_safety_check_passed",
    ]
    return {key: aggregates.get(key) for key in keys if key in aggregates}


def compact_artifacts(outputs: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "summary_md",
        "results_json",
        "file_manifest_json",
        "qc_json",
        "xps_backend_probe_json",
        "xps_backend_fit_results_json",
        "xps_reference_assignments_json",
        "xps_reference_gaps_json",
        "limitations_md",
        "next_steps_md",
    ]
    return {key: outputs.get(key) for key in keys if outputs.get(key)}


def build_codex_response(
    *,
    task_id: str,
    input_path: Path,
    output_dir: Path,
    results: dict[str, Any],
) -> dict[str, Any]:
    aggregates = results.get("aggregates", {})
    safety = results.get("safety", {})
    outputs = results.get("outputs", {})
    reference_count = aggregates.get("xps_reference_assignment_count", 0)
    reference_gap_count = aggregates.get("xps_reference_gap_count", 0)
    backend_success = aggregates.get("xps_backend_fit_success_count", 0)
    backend_failed = aggregates.get("xps_backend_fit_failed_count", 0)
    qc_errors = aggregates.get("qc_error_count", 0)
    safety_passed = bool(aggregates.get("report_safety_check_passed"))

    return {
        "ok": True,
        "task_id": task_id,
        "generated_at": now_iso(),
        "input": str(input_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "status": "completed",
        "codex_summary": {
            "can_run": True,
            "short_answer": (
                "XPS/XAS folder analysis completed. XPS backend fits and "
                "review-required reference valence/chemical-state candidates "
                "are available when supported by parsed spectra."
            ),
            "xps_reference_candidate_boundary": (
                "Reference candidates are hypotheses for review, not final "
                "valence, chemical-state, oxidation-state, or coordination conclusions."
            ),
            "xas_modeling_status": safety.get("xas_modeling_status", "not_modeled"),
        },
        "metrics": compact_metrics(aggregates),
        "artifacts": compact_artifacts(outputs),
        "safety": {
            "passed": safety_passed,
            "qc_errors": qc_errors,
            "xps_backend_fit_success_count": backend_success,
            "xps_backend_fit_failed_count": backend_failed,
            "xps_reference_assignment_count": reference_count,
            "xps_reference_gap_count": reference_gap_count,
            "unsupported_claims_rejected": safety.get("unsupported_claims_rejected", []),
            "boundary": safety.get(
                "xps_reference_assignment_boundary",
                "review_required_reference_candidates_not_final_claims",
            ),
        },
        "recommended_next_actions": [
            "Read summary_md first for a human overview.",
            "Use xps_reference_assignments_json as review-required candidate evidence only.",
            "Use xps_reference_gaps_json to see fitted XPS records that need reference-library review.",
            "Require calibration/background/constraints/human review before final XPS state claims.",
            "Keep XAS valence or coordination claims disabled until a separate XAS modeling backend runs.",
        ],
    }


def build_error_response(task_id: str, input_path: Path | None, output_dir: Path | None, exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "task_id": task_id,
        "generated_at": now_iso(),
        "input": str(input_path.resolve()) if input_path else None,
        "output_dir": str(output_dir.resolve()) if output_dir else None,
        "status": "failed",
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        },
        "safety": {
            "passed": False,
            "boundary": "no_scientific_claims_emitted_after_failed_run",
        },
    }


def write_response(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the XPS/XAS agent and emit a compact Codex backend response.")
    parser.add_argument("--request", type=Path, help="Optional JSON request with input, output, response_path, and task_id.")
    parser.add_argument("--input", type=Path, help="Local XPS/XAS file or directory. Overrides request.input.")
    parser.add_argument("--output", type=Path, help="Report-bundle output directory. Overrides request.output.")
    parser.add_argument("--response", type=Path, help="Compact response JSON path. Defaults to OUTPUT/codex_response.json.")
    parser.add_argument("--task-id", default=None, help="Optional caller task id. Overrides request.task_id.")
    args = parser.parse_args()

    request = read_request(args.request)
    task_id = args.task_id or str(request.get("task_id") or "codex-xps-xas-analysis")
    input_path = path_from(args.input, path_from(request.get("input")))
    output_dir = path_from(args.output, path_from(request.get("output"), DEFAULT_OUTPUT_DIR))

    if input_path is None:
        raise SystemExit("Missing input path. Provide --input or request.input.")
    response_path = path_from(args.response, path_from(request.get("response_path"), output_dir / DEFAULT_RESPONSE_NAME))

    try:
        if not input_path.exists():
            raise FileNotFoundError(f"Input does not exist: {input_path}")
        results = run(input_path, output_dir)
        response = build_codex_response(task_id=task_id, input_path=input_path, output_dir=output_dir, results=results)
        write_response(response_path, response)
        print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        error_response = build_error_response(task_id, input_path, output_dir, exc)
        if response_path is not None:
            write_response(response_path, error_response)
        print(json.dumps(error_response, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
