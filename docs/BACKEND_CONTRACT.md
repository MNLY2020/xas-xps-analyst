# Codex Backend Contract

This file is the stable no-GUI integration contract for the XPS/XAS local
analysis Agent. It is intentionally small: a backend gives the Agent one local
file or folder, and the Agent writes a report bundle plus one compact JSON
response for Codex or another orchestrator.

## Stable command

From the quest workspace:

```bash
.venv-xps-backend/bin/python experiments/main/xas-xps-local-agent-mvp-v1/scripts/codex_backend_agent.py --task-id codex-backend-gap-check --input /root/WORK/Exp-data --output outputs/xas_xps_agent_codex_backend_gap_check
```

Replace `--input` with the user-provided file or folder and `--output` with the
desired report-bundle directory.

## JSON request mode

The same entrypoint accepts a request file:

```json
{
  "task_id": "example-xps-analysis",
  "input": "/path/to/xps_or_xas_file_or_folder",
  "output": "outputs/example_report",
  "response_path": "outputs/example_report/codex_response.json"
}
```

An editable template is available at:

```text
experiments/main/xas-xps-local-agent-mvp-v1/examples/codex_backend_request.example.json
```

Run it with:

```bash
.venv-xps-backend/bin/python experiments/main/xas-xps-local-agent-mvp-v1/scripts/codex_backend_agent.py --request request.json
```

## Response shape

The backend wrapper always writes `codex_response.json`. Backend callers should
consume these top-level fields first:

| Field | Meaning |
| --- | --- |
| `ok` | Boolean success flag for the wrapper run. |
| `status` | Current task status, normally `completed` after a successful run. |
| `task_id` | Caller-supplied task id or generated default. |
| `input` | Resolved input path. |
| `output_dir` | Resolved report-bundle path. |
| `generated_at` | UTC generation timestamp. |
| `codex_summary` | Short user-facing summary and current scientific boundary. |
| `metrics` | Parser, QC, XPS backend fit, and reference-candidate counters. |
| `artifacts` | Absolute paths to the key files in the report bundle. |
| `safety` | Explicit non-final-claim boundary and rejected unsupported claims. |
| `recommended_next_actions` | Practical next steps for a downstream Agent. |

## Key metrics

The most useful fields for automated checks are:

| Metric | Current verified sample value | Meaning |
| --- | ---: | --- |
| `files_seen` | 9 | Files discovered under the input. |
| `files_parsed` | 9 | Files parsed successfully. |
| `file_parse_success_rate` | 1.0 | File-level parser success rate. |
| `record_parse_success_rate` | 0.9393939393939394 | Record-level parser success rate. |
| `qc_error_count` | 0 | Hard QC errors. |
| `xps_backend_fit_success_count` | 24 | XPS backend numerical fits completed. |
| `xps_backend_fit_failed_count` | 0 | XPS backend numerical fits failed. |
| `xps_reference_assignment_count` | 15 | Review-required reference valence / chemical-state candidates. |
| `xps_reference_gap_count` | 10 | Fitted XPS records without a current reference-library match. |

## Artifact contract

Backend callers should treat these artifacts as the stable read surface:

| Artifact key | Use |
| --- | --- |
| `summary_md` | Human overview. Read this first for an operator-facing answer. |
| `results_json` | Full machine-readable result bundle. |
| `file_manifest_json` | Input file inventory and parse status. |
| `qc_json` | QC findings and warnings. |
| `xps_backend_probe_json` | Numerical backend availability and selected method. |
| `xps_backend_fit_results_json` | XPS numerical fit outputs where available. |
| `xps_reference_assignments_json` | Review-required reference valence / chemical-state candidates. |
| `xps_reference_gaps_json` | Fitted XPS records needing reference-library review. |
| `limitations_md` | Scientific and implementation limitations. |
| `next_steps_md` | Recommended next actions. |

## Scientific boundary for callers

- `xps_reference_assignments_json` contains reference hypotheses only.
- Every reference candidate must be treated as `review_required=true`.
- `xps_reference_gaps_json` does not mean "no chemical state exists"; it only
  means the current small reference library did not match that fitted record.
- The Agent rejects final valence, final chemical state, final oxidation state,
  and coordination-number claims unless a later reviewed backend provides the
  required evidence.
- XAS remains explicitly `未建模`; do not infer XAS valence or coordination
  claims from this MVP output.
