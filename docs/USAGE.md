# XPS/XAS Local Agent MVP Usage

This is the dependency-free MVP for local XPS/XAS file parsing, XPS peak-fit draft generation, XPS evidence-table generation, XPS fitting-handoff generation, and report-bundle generation.

## Quick run

From the quest workspace:

```bash
python3 experiments/main/xas-xps-local-agent-mvp-v1/scripts/run_xas_xps_agent.py --input /path/to/xps_or_xas_file_or_folder
```

Default output:

```text
outputs/xas_xps_agent_mvp_v1/
```

To choose a different output folder:

```bash
python3 experiments/main/xas-xps-local-agent-mvp-v1/scripts/run_xas_xps_agent.py --input /path/to/data --output /path/to/report_bundle
```

## Codex backend entrypoint

For backend integration, use the thin wrapper below instead of starting a GUI or service:

```bash
.venv-xps-backend/bin/python experiments/main/xas-xps-local-agent-mvp-v1/scripts/codex_backend_agent.py --input /path/to/data --output /path/to/report_bundle
```

It writes the same report bundle plus:

```text
codex_response.json
```

`codex_response.json` is the compact integration response. It contains:

- `ok`, `status`, `input`, and `output_dir`
- key parser/QC/XPS backend metrics
- paths to `summary.md`, `results.json`, `xps_backend_fit_results.json`, `xps_reference_assignments.json`, and `xps_reference_gaps.json`
- safety boundaries that keep reference valence / chemical-state candidates separate from final chemical claims

The stable backend schema and field meanings are documented in `BACKEND_CONTRACT.md`.

The wrapper also accepts a JSON request:

```json
{
  "task_id": "example-xps-analysis",
  "input": "/path/to/data",
  "output": "outputs/example_report",
  "response_path": "outputs/example_report/codex_response.json"
}
```

An editable template is available at `examples/codex_backend_request.example.json`.

Run it with:

```bash
.venv-xps-backend/bin/python experiments/main/xas-xps-local-agent-mvp-v1/scripts/codex_backend_agent.py --request request.json
```

Verified local example:

```bash
python3 experiments/main/xas-xps-local-agent-mvp-v1/scripts/run_xas_xps_agent.py --input /root/WORK/Exp-data --output outputs/xas_xps_agent_mvp_v1_handoff_check
```

Verified Codex backend example:

```bash
.venv-xps-backend/bin/python experiments/main/xas-xps-local-agent-mvp-v1/scripts/codex_backend_agent.py --task-id codex-backend-gap-check --input /root/WORK/Exp-data --output outputs/xas_xps_agent_codex_backend_gap_check
```

## Report bundle

The command writes:

- `summary.md`: human-readable summary
- `results.json`: machine-readable full result
- `file_manifest.json` and `file_manifest.md`: discovered files and parse status
- `qc.json` and `qc.md`: QC findings
- `xps_peak_fits.json` and `xps_peak_fits.md`: dependency-free XPS peak-fit draft for numeric XPS sheets
- `xps_evidence_table.json` and `xps_evidence_table.md`: per-XPS-record evidence table with fit status, quality reason, range summary, and non-claim boundary
- `xps_fitting_handoff.json` and `xps_fitting_handoff.md`: backend-fitting preparation tasks and initial guesses only
- `xps_backend_probe.json` and `xps_backend_probe.md`: selected numerical backend and availability checks
- `xps_backend_fit_results.json` and `xps_backend_fit_results.md`: numerical backend fit outputs where available
- `xps_reference_assignments.json` and `xps_reference_assignments.md`: review-required reference valence / chemical-state candidates
- `xps_reference_gaps.json` and `xps_reference_gaps.md`: review-required fitted-record gaps where no current reference-library window matched
- `codex_response.json`: compact response when launched through `codex_backend_agent.py`
- `limitations.md`: unsupported claims and current boundaries
- `next_steps.md`: fitting/modeling preparation checklist
- `parsed/xps_records.csv`: parsed XPS record summaries
- `parsed/xas_records.csv`: parsed XAS record summaries

## Current scientific boundary

- XPS workbook sheets with numeric spectra get a dependency-free peak-fit draft using a linear background and Gaussian proxy peaks.
- XPS evidence rows explain why each XPS record is fitted, weak, or unfitted; they do not upgrade draft peaks into chemical-state claims.
- XPS fitting handoff rows identify which records are ready for a future approved backend fit and which remain blocked; they are not formal fits.
- XPS backend fit rows are numerical fits for backend triage and downstream review, not publication-grade chemical interpretation by themselves.
- XPS reference assignment rows are review-required candidates from common binding-energy windows, not final valence or chemical-state conclusions.
- XPS VMS metadata-only files remain explicitly `未拟合` until their numeric payload is reconstructed.
- XAS modeling status is explicitly `未建模`.
- The MVP does not infer final valence, oxidation state, chemical state, or coordination number from the peak-fit draft or reference-candidate table.

## Verified local sample

The current validation sample parsed 9/9 files:

- XPS: 4 files, 4810 numeric rows
- XAS: 5 files, 2165 rows
- QC: 0 errors, 4 warnings
- XPS fitting: 24 draft-fitted records, 4 unfitted records, 88 proxy peaks
- XPS evidence table: 28 rows, reason coverage = 1.0
- XPS fitting handoff: 28 tasks, 24 ready for a future approved backend fit, 4 blocked
- XPS backend: 24 lmfit-backed numerical fits succeeded, 0 failed
- XPS reference candidates: 15 review-required rows covering Pd, Al, O, and C
- XPS reference-library gaps: 10 review-required rows for fitted records that need reference-library review
