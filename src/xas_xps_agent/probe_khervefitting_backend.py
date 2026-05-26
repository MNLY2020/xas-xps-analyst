#!/usr/bin/env python3
"""Headless KherveFitting source/backend probe on real XPS samples.

This is a backend-callability check. It deliberately does not assign
chemical states, valence, oxidation states, or coordination numbers.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lmfit
import numpy as np


DEFAULT_KHERVE_SOURCE = Path(
    "/root/DeepScientist/quests/002/baselines/imported/"
    "khervefitting-1.80/source/KherveFitting-1.80"
)
DEFAULT_RUNNER = Path(
    "experiments/main/xas-xps-local-agent-mvp-v1/scripts/run_xas_xps_agent.py"
)


def import_runner(runner_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xas_xps_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not create import spec for {runner_path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses need the module to be registered while class decorators run.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def dependency_checks(module_names: list[str]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for name in module_names:
        try:
            module = __import__(name)
            checks[name] = {
                "available": True,
                "version": getattr(module, "__version__", None),
            }
        except Exception as exc:  # pragma: no cover - probe output path
            checks[name] = {"available": False, "error": repr(exc)}
    return checks


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def fit_one_spectrum(peak_functions: Any, label: str, series: Any) -> dict[str, Any]:
    x = np.asarray(series.x, dtype=float)
    y = np.asarray(series.y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if x.size < 20:
        return {
            "source": label,
            "status": "not_attempted",
            "reason": "too_few_points",
            "point_count": int(x.size),
        }

    baseline = np.linspace(float(y[0]), float(y[-1]), y.size)
    y_sub = y - baseline
    peak_idx = int(np.nanargmax(y_sub))
    x_min = float(np.nanmin(x))
    x_max = float(np.nanmax(x))
    x_span = max(x_max - x_min, 1.0)
    y_peak = max(float(y_sub[peak_idx]), 1.0)
    fwhm0 = max(x_span / 80.0, 0.5)
    area0 = max(y_peak * fwhm0, 1.0)

    model = lmfit.Model(
        peak_functions.gauss_lorentz_Area,
        independent_vars=["x"],
    )
    params = model.make_params(
        center=float(x[peak_idx]),
        area=area0,
        fwhm=fwhm0,
        fraction=0.5,
    )
    params["center"].set(min=x_min, max=x_max)
    params["area"].set(min=0)
    params["fwhm"].set(min=0.05, max=max(x_span, 0.1))
    params["fraction"].set(min=0, max=1)

    try:
        result = model.fit(y_sub, params, x=x, max_nfev=1000, nan_policy="omit")
    except Exception as exc:
        return {
            "source": label,
            "status": "failed",
            "backend": "KherveFitting.PeakFunctions.gauss_lorentz_Area + lmfit.Model",
            "point_count": int(x.size),
            "error": repr(exc),
        }

    y_fit = np.asarray(result.best_fit, dtype=float)
    residual = y_sub - y_fit
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    norm = float(np.nanmax(y_sub) - np.nanmin(y_sub)) or 1.0
    center = finite_float(result.params["center"].value)
    fwhm = finite_float(result.params["fwhm"].value)
    area = finite_float(result.params["area"].value)
    fraction = finite_float(result.params["fraction"].value)
    return {
        "source": label,
        "status": "kherve_peakfunction_lmfit_completed",
        "backend": "KherveFitting.PeakFunctions.gauss_lorentz_Area + lmfit.Model",
        "point_count": int(x.size),
        "lmfit_success": bool(result.success),
        "lmfit_message": str(result.message),
        "nfev": int(result.nfev or 0),
        "rmse": round(rmse, 6),
        "normalized_rmse": round(rmse / norm, 6),
        "center_ev": None if center is None else round(center, 6),
        "fwhm_ev": None if fwhm is None else round(fwhm, 6),
        "area": None if area is None else round(area, 6),
        "fraction": None if fraction is None else round(fraction, 6),
        "interpretation_boundary": (
            "numeric single-component probe only; not a chemical-state assignment"
        ),
    }


def collect_xps_series(runner: Any, input_dir: Path) -> tuple[int, list[tuple[str, Any]], int]:
    """Collect every headless-reconstructable XPS spectrum for heavier validation."""
    xps_series: list[tuple[str, Any]] = []
    records_seen = 0
    collection_errors = 0

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            records, representative = runner.parse_file(path, input_dir)
        except Exception:
            collection_errors += 1
            continue

        xps_records = [rec for rec in records if rec.get("modality") == "XPS"]
        if not xps_records:
            continue
        records_seen += len(xps_records)

        suffix = path.suffix.lower()
        if suffix == ".vms":
            try:
                lines = [line.strip() for line in path.read_text(errors="replace").splitlines()]
                block_starts = runner.vms_block_start_indices(lines)
                boundaries = block_starts + [len(lines)]
                for block_no, (start_idx, end_idx) in enumerate(
                    zip(boundaries, boundaries[1:]), start=1
                ):
                    block_lines = lines[start_idx:end_idx]
                    metadata = runner.vms_metadata_from_block(block_lines)
                    spectrum, reconstruction = runner.reconstruct_vms_spectrum(
                        block_lines, metadata
                    )
                    if spectrum is None or reconstruction.get("status") != "reconstructed":
                        continue
                    record_label = (
                        block_lines[0].strip() if block_lines else f"block_{block_no}"
                    )
                    sample = metadata.get("Sample") or (
                        block_lines[1].strip() if len(block_lines) > 1 else ""
                    )
                    label = f"{path.relative_to(input_dir)}::{sample} {record_label}".strip()
                    xps_series.append((label, spectrum))
            except Exception:
                collection_errors += 1
            continue

        if suffix in {".xlsx", ".xlsm"}:
            try:
                with runner.ZipFile(path) as zf:
                    strings = runner.xlsx_shared_strings(zf)
                    for sheet_name, sheet_path in runner.workbook_sheet_paths(zf):
                        sheet = runner.ET.fromstring(zf.read(sheet_path))
                        x: list[float] = []
                        y: list[float] = []
                        for row in sheet.findall(".//main:row", runner.NS):
                            values = []
                            for cell in row.findall("main:c", runner.NS):
                                value = runner.parse_float(runner.cell_text(cell, strings))
                                if value is not None:
                                    values.append(value)
                            if len(values) >= 2:
                                x.append(values[0])
                                y.append(values[1])
                        if x and y:
                            label = f"{path.relative_to(input_dir)}::{sheet_name}"
                            xps_series.append((label, runner.Series(x=x, y=y)))
            except Exception:
                collection_errors += 1
            continue

        if representative is not None:
            label = f"{xps_records[0].get('file')}::{xps_records[0].get('record')}"
            xps_series.append((label, representative))

    return records_seen, xps_series, collection_errors


def write_outputs(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    checks = payload["dependency_checks"]
    imports = payload["source_imports"]
    lines = [
        "# KherveFitting source/backend probe",
        "",
        f"- Input: `{payload['input']}`",
        f"- KherveFitting source: `{payload['kherve_source']}`",
        f"- Python: `{payload['python']}`",
        f"- Dependencies available: {sum(1 for v in checks.values() if v.get('available'))}/{len(checks)}",
        f"- Source import KherveFitting.py: {imports.get('KherveFitting', {}).get('ok')}",
        f"- Source import PeakFunctions: {imports.get('libraries.Peak_Functions.PeakFunctions', {}).get('ok')}",
        f"- XPS records seen: {payload['records_seen_xps']}",
        f"- XPS series sent to Kherve numeric probe: {payload['xps_series_attempted']}",
        f"- Kherve PeakFunctions numeric fits completed: {payload['kherve_numeric_fit_success_count']}/{payload['kherve_numeric_fit_result_count']}",
        f"- lmfit success flag true: {payload['kherve_numeric_fit_lmfit_success_count']}/{payload['kherve_numeric_fit_result_count']}",
        f"- Not attempted by numeric fitter: {payload['kherve_numeric_fit_not_attempted_count']}",
        "",
        "## Command",
        "",
        f"`{payload['run_command']}`",
        "",
        "## Boundary",
        "",
        "- GUI launch was not attempted in this headless validation.",
        "- The numeric probe uses KherveFitting PeakFunctions with lmfit on real XPS spectra; it is not a chemical-state assignment.",
        "- No valence, oxidation-state, chemical-state, or coordination conclusions are generated.",
        "",
        "## Main gap",
        "",
        "- To use full KherveFitting as an interactive GUI backend, a display/session-driven launch test is still needed.",
        "- To use KherveFitting as a production batch backend, its GUI-coupled fit workflow needs a stable headless adapter around its fit data structures.",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/root/WORK/Exp-data")
    parser.add_argument(
        "--output",
        default="outputs/xas_xps_agent_mvp_v1_kherve_probe",
    )
    parser.add_argument("--kherve-source", default=str(DEFAULT_KHERVE_SOURCE))
    parser.add_argument("--runner", default=str(DEFAULT_RUNNER))
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    kherve_source = Path(args.kherve_source)
    runner_path = Path(args.runner)
    if not runner_path.is_absolute():
        runner_path = Path.cwd() / runner_path

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input": str(input_dir),
        "output": str(output_dir),
        "kherve_source": str(kherve_source),
        "runner": str(runner_path),
        "python": sys.executable,
        "run_command": f"{sys.executable} " + " ".join(sys.argv),
        "dependency_checks": dependency_checks(
            ["wx", "numpy", "scipy", "lmfit", "lmfitxps", "matplotlib", "pandas", "openpyxl"]
        ),
        "source_imports": {},
        "gui_launch_status": "not_launched_headless_validation",
        "safety_boundary": (
            "No valence, oxidation-state, chemical-state, or coordination conclusions are generated."
        ),
        "records_seen_xps": 0,
        "xps_series_attempted": 0,
        "kherve_numeric_fit_result_count": 0,
        "kherve_numeric_fit_success_count": 0,
        "kherve_numeric_fit_lmfit_success_count": 0,
        "kherve_numeric_fit_failed_count": 0,
        "kherve_numeric_fit_not_attempted_count": 0,
        "xps_series_collection_method": (
            "all_supported_vms_blocks_and_numeric_xlsx_sheets_headless"
        ),
        "xps_series_collection_error_count": 0,
        "fit_rows": [],
        "limitations": [
            "KherveFitting GUI was not launched in this headless validation; only imports and numerical PeakFunctions were exercised.",
            "The declared requirements pin lmfitxps==0.2.3, which was unavailable from the configured package index; this validation uses the available lmfitxps package.",
            "The probe fits one Kherve gauss_lorentz_Area component per reconstructable XPS spectrum, so it is a backend-callability check rather than a chemically complete peak model.",
            "The heavier probe reconstructs every supported VMS block and numeric workbook sheet that can be represented as an X/Y spectrum.",
            "No valence, oxidation-state, chemical-state, or coordination conclusions are emitted.",
        ],
    }

    sys.path.insert(0, str(kherve_source))
    try:
        import KherveFitting  # noqa: F401

        payload["source_imports"]["KherveFitting"] = {
            "ok": True,
            "note": "module import only; GUI frame not instantiated",
        }
    except Exception as exc:
        payload["source_imports"]["KherveFitting"] = {"ok": False, "error": repr(exc)}

    peak_functions = None
    try:
        from libraries.Peak_Functions import PeakFunctions

        peak_functions = PeakFunctions
        payload["source_imports"]["libraries.Peak_Functions.PeakFunctions"] = {"ok": True}
    except Exception as exc:
        payload["source_imports"]["libraries.Peak_Functions.PeakFunctions"] = {
            "ok": False,
            "error": repr(exc),
        }

    try:
        runner = import_runner(runner_path)
        records_seen, xps_series, collection_errors = collect_xps_series(runner, input_dir)

        payload["records_seen_xps"] = records_seen
        payload["xps_series_attempted"] = len(xps_series)
        payload["xps_series_collection_error_count"] = collection_errors
        if peak_functions is not None:
            rows = [fit_one_spectrum(peak_functions, label, series) for label, series in xps_series]
        else:
            rows = []
        payload["fit_rows"] = rows
        payload["kherve_numeric_fit_result_count"] = len(rows)
        payload["kherve_numeric_fit_success_count"] = sum(
            1 for row in rows if row.get("status") == "kherve_peakfunction_lmfit_completed"
        )
        payload["kherve_numeric_fit_lmfit_success_count"] = sum(
            1 for row in rows if row.get("lmfit_success") is True
        )
        payload["kherve_numeric_fit_failed_count"] = sum(
            1 for row in rows if row.get("status") == "failed"
        )
        payload["kherve_numeric_fit_not_attempted_count"] = sum(
            1 for row in rows if row.get("status") == "not_attempted"
        )
    except Exception as exc:
        payload["probe_error"] = repr(exc)
    finally:
        write_outputs(output_dir, payload)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "summary_md": str(output_dir / "summary.md"),
                "results_json": str(output_dir / "results.json"),
                "xps_records_seen": payload["records_seen_xps"],
                "xps_series_attempted": payload["xps_series_attempted"],
                "fit_success": payload["kherve_numeric_fit_success_count"],
                "fit_total": payload["kherve_numeric_fit_result_count"],
                "source_imports": payload["source_imports"],
                "probe_error": payload.get("probe_error"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if "probe_error" not in payload else 1


if __name__ == "__main__":
    raise SystemExit(main())
