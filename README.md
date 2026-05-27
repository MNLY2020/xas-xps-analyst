# XAS/XPS Codex Backend Agent MVP

![status](https://img.shields.io/badge/status-MVP%20beta-orange)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![scope](https://img.shields.io/badge/scope-local%20backend-informational)

Codex-callable local backend MVP for chemistry characterization data.

This repository packages the Quest002 deliverable as a clean GitHub-ready
project. It focuses on local XAS/XPS file parsing, XPS fitting triage,
QC/report-bundle generation, and a compact JSON response surface for Codex or
another backend orchestrator.

## Release note

Initial public release of the Quest002 backend deliverable.

- Packaged as a clean standalone repository for GitHub publication.
- Keeps the Codex-callable local backend entrypoints and report bundle outputs.
- Includes a verified sample output bundle under `example-output/`.
- Excludes Quest runtime caches, orchestration state, and non-public workspace artifacts.

## What is supported

- Local folder/file recognition for XPS and XAS inputs.
- Real file parsing and report-bundle generation.
- QC output.
- XPS backend numerical fitting through `lmfit_gaussian_least_squares_v1` when
  the optional backend dependencies are installed.
- Review-required XPS reference valence / chemical-state candidates.
- Codex integration response through `codex_response.json`.

## Boundaries

This is a backend MVP / beta package. It does **not** claim:

- production deployment readiness;
- remote reliability or security validation;
- GUI KherveFitting workflow delivery;
- final XPS valence, oxidation-state, chemical-state, or coordination claims;
- XAS modeling, XANES fitting, EXAFS fitting, or coordination-number estimates;
- manuscript or paper readiness.

Reference-state outputs are candidate-level and review-required by default.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

For the optional XPS numerical backend:

```bash
python -m pip install -e ".[xps-backend]"
```

## Quick use

Run the local report generator:

```bash
xas-xps-agent --input /path/to/xps_or_xas_file_or_folder --output outputs/report
```

Run the Codex-facing wrapper:

```bash
xas-xps-codex-backend \
  --task-id example-analysis \
  --input /path/to/xps_or_xas_file_or_folder \
  --output outputs/example_report
```

Or use a JSON request:

```bash
xas-xps-codex-backend --request examples/codex_backend_request.example.json
```

## Output bundle

The backend writes:

- `summary.md`
- `results.json`
- `codex_response.json`
- `file_manifest.json` / `file_manifest.md`
- `qc.json` / `qc.md`
- `xps_peak_fits.json` / `xps_peak_fits.md`
- `xps_evidence_table.json` / `xps_evidence_table.md`
- `xps_fitting_handoff.json` / `xps_fitting_handoff.md`
- `xps_backend_probe.json` / `xps_backend_probe.md`
- `xps_backend_fit_results.json` / `xps_backend_fit_results.md`
- `xps_reference_assignments.json` / `xps_reference_assignments.md`
- `xps_reference_gaps.json` / `xps_reference_gaps.md`
- `limitations.md`
- `next_steps.md`
- `parsed/xas_records.csv`
- `parsed/xps_records.csv`

## Verified Quest002 sample result

The included `example-output/` directory is the verified Quest002 backend sample
output. It was generated from local sample data that is not included in this
repository.

Key validation metrics:

- files seen: 9
- files parsed: 9
- file parse success rate: 1.0
- record parse success rate: 0.9393939393939394
- QC errors: 0
- XPS backend fit attempts: 24
- XPS backend fit successes: 24
- XPS backend fit failures: 0
- XPS reference assignment rows: 15
- XPS reference-gap rows: 10

## Documentation

- Backend contract: `docs/BACKEND_CONTRACT.md`
- Usage notes: `docs/USAGE.md`
- Delivery manifest: `docs/delivery_manifest.json`

## License

Released under the `MIT` License. See `LICENSE`.
