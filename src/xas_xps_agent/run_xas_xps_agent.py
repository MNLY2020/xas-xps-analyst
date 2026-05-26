#!/usr/bin/env python3
"""Dependency-free local XPS/XAS file parser and report-bundle generator."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RUN_ID = "xas-xps-local-agent-mvp-v1"
TEXT_SUFFIXES = {"", ".txt", ".dat", ".csv", ".xy", ".xmu", ".nor", ".chi"}
XPS_SUFFIXES = {".vms", ".xlsx", ".xlsm"}
XPS_FIT_METHOD = "stdlib_linear_baseline_local_maxima_gaussian_proxy"
XPS_BACKEND_STDLIB_METHOD = "stdlib_gaussian_coordinate_descent_lsq_v1"
XPS_BACKEND_LMFIT_METHOD = "lmfit_gaussian_least_squares_v1"
XPS_BACKEND_METHOD = "auto_lmfit_then_stdlib_gaussian_lsq_v1"
XPS_BACKEND_NOT_ATTEMPTED_METHOD = "not_attempted_before_backend_selection"
XPS_FIT_STATUS_DRAFT = "拟合草案"
XPS_FIT_STATUS_WEAK = "偏弱拟合草案"
XPS_FIT_STATUS_UNFITTED = "未拟合"
XPS_BACKEND_STATUS_SUCCEEDED = "backend_fit_succeeded"
XPS_BACKEND_STATUS_FAILED = "backend_fit_failed"
XPS_BACKEND_STATUS_NOT_ATTEMPTED = "backend_fit_not_attempted"
XPS_BACKEND_QUALITY_REFERENCE = "reference_candidate"
XPS_BACKEND_QUALITY_WEAK = "weak_fit"
XPS_BACKEND_QUALITY_REVIEW = "review_required"
XPS_BACKEND_QUALITY_SKIPPED = "skipped"
XPS_REFERENCE_ASSIGNMENT_LIBRARY = [
    {
        "element": "Pd",
        "region": "Pd 3d5/2",
        "energy_min_ev": 334.8,
        "energy_max_ev": 335.6,
        "candidate_state": "Pd(0) / metallic Pd",
        "chemical_state_note": "metallic palladium reference candidate",
        "basis": "common Pd 3d5/2 binding-energy window",
    },
    {
        "element": "Pd",
        "region": "Pd 3d5/2",
        "energy_min_ev": 336.2,
        "energy_max_ev": 337.2,
        "candidate_state": "Pd(II) / PdO-like",
        "chemical_state_note": "oxidized Pd(II) reference candidate",
        "basis": "common Pd 3d5/2 binding-energy window",
    },
    {
        "element": "Pd",
        "region": "Pd 3d5/2",
        "energy_min_ev": 337.8,
        "energy_max_ev": 338.8,
        "candidate_state": "Pd(IV) / PdO2-like",
        "chemical_state_note": "higher-valence Pd oxide reference candidate",
        "basis": "common Pd 3d5/2 binding-energy window",
    },
    {
        "element": "Al",
        "region": "Al 2p",
        "energy_min_ev": 72.2,
        "energy_max_ev": 73.2,
        "candidate_state": "Al(0) / metallic Al",
        "chemical_state_note": "metallic aluminum reference candidate",
        "basis": "common Al 2p binding-energy window",
    },
    {
        "element": "Al",
        "region": "Al 2p",
        "energy_min_ev": 74.0,
        "energy_max_ev": 75.0,
        "candidate_state": "Al(III) / Al2O3-like",
        "chemical_state_note": "oxidized aluminum reference candidate",
        "basis": "common Al 2p binding-energy window",
    },
    {
        "element": "O",
        "region": "O 1s",
        "energy_min_ev": 529.0,
        "energy_max_ev": 530.3,
        "candidate_state": "lattice O2- / oxide oxygen",
        "chemical_state_note": "oxide lattice oxygen reference candidate",
        "basis": "common O 1s binding-energy window",
    },
    {
        "element": "O",
        "region": "O 1s",
        "energy_min_ev": 531.0,
        "energy_max_ev": 532.2,
        "candidate_state": "hydroxyl / defect oxygen",
        "chemical_state_note": "surface hydroxyl or defect oxygen reference candidate",
        "basis": "common O 1s binding-energy window",
    },
    {
        "element": "O",
        "region": "O 1s",
        "energy_min_ev": 532.5,
        "energy_max_ev": 534.0,
        "candidate_state": "adsorbed water / carbonate-like oxygen",
        "chemical_state_note": "adsorbed water, carbonate, or high-binding-energy oxygen reference candidate",
        "basis": "common O 1s binding-energy window",
    },
    {
        "element": "C",
        "region": "C 1s",
        "energy_min_ev": 282.4,
        "energy_max_ev": 283.8,
        "candidate_state": "metal-carbide / low-binding-energy carbon",
        "chemical_state_note": "low-binding-energy carbon reference candidate",
        "basis": "common low-binding-energy C 1s window",
    },
    {
        "element": "C",
        "region": "C 1s",
        "energy_min_ev": 284.6,
        "energy_max_ev": 285.3,
        "candidate_state": "adventitious C-C/C-H",
        "chemical_state_note": "adventitious hydrocarbon reference candidate",
        "basis": "common C 1s binding-energy window",
    },
    {
        "element": "C",
        "region": "C 1s",
        "energy_min_ev": 286.0,
        "energy_max_ev": 286.8,
        "candidate_state": "C-O",
        "chemical_state_note": "single-bonded oxygenated carbon reference candidate",
        "basis": "common C 1s binding-energy window",
    },
    {
        "element": "C",
        "region": "C 1s",
        "energy_min_ev": 288.5,
        "energy_max_ev": 291.2,
        "candidate_state": "O-C=O / carbonate-like carbon",
        "chemical_state_note": "carboxylate, carbonate, or high-binding-energy carbon reference candidate",
        "basis": "common C 1s binding-energy window",
    },
]
ELEMENT_SYMBOLS = {
    "Ag", "Al", "Au", "C", "Ca", "Ce", "Cl", "Co", "Cu", "Fe", "K", "Mg",
    "Mn", "Mo", "N", "Na", "Ni", "O", "P", "Pd", "Pt", "S", "Si", "Ti",
    "V", "W", "Zn", "Zr",
}


@dataclass
class Series:
    x: list[float]
    y: list[float]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def finite_stats(values: Iterable[float]) -> dict[str, float | int | None]:
    vals = [v for v in values if math.isfinite(v)]
    if not vals:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": sum(vals) / len(vals),
    }


def numeric_tokens(line: str) -> list[float]:
    parts = [p for p in re.split(r"[\s,;\t]+", line.strip()) if p]
    if not parts:
        return []
    values: list[float] = []
    for part in parts:
        value = parse_float(part)
        if value is None:
            return []
        values.append(value)
    return values


def read_numeric_table(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="latin-1", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines:
        values = numeric_tokens(line)
        if len(values) >= 2:
            rows.append(values)
    return rows


def strictly_increasing(values: list[float]) -> bool:
    return all(b > a for a, b in zip(values, values[1:]))


def max_slope_energy(x: list[float], y: list[float]) -> float | None:
    best_x = None
    best_slope = None
    for x0, x1, y0, y1 in zip(x, x[1:], y, y[1:]):
        dx = x1 - x0
        if dx <= 0:
            continue
        slope = (y1 - y0) / dx
        if best_slope is None or slope > best_slope:
            best_slope = slope
            best_x = x0
    return best_x


def smooth(values: list[float], window: int = 5) -> list[float]:
    if window <= 1 or len(values) < 3:
        return list(values)
    radius = max(1, window // 2)
    smoothed = []
    for idx in range(len(values)):
        start = max(0, idx - radius)
        end = min(len(values), idx + radius + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def linear_baseline(x: list[float], y: list[float]) -> list[float]:
    if len(x) < 2 or len(y) < 2:
        return list(y)
    dx = x[-1] - x[0]
    if dx == 0:
        return [sum(y) / len(y)] * len(y)
    slope = (y[-1] - y[0]) / dx
    return [y[0] + slope * (xi - x[0]) for xi in x]


def median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if math.isfinite(v))
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def unfitted_xps_fit(source: str, reason: str, flags: list[str], point_count: int | None = None) -> dict[str, Any]:
    return {
        "status": XPS_FIT_STATUS_UNFITTED,
        "fit_status": XPS_FIT_STATUS_UNFITTED,
        "quality_grade": "未拟合",
        "quality_flags": flags,
        "method": XPS_FIT_METHOD,
        "source": source,
        "reason": reason,
        "unfitted_reason": reason,
        "point_count": point_count,
        "peak_count": 0,
        "peaks": [],
        "xps_backend_fit": {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_NOT_ATTEMPTED_METHOD,
            "reason": reason,
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        },
        "warnings": flags,
    }


def interpolate_crossing(x0: float, y0: float, x1: float, y1: float, target: float) -> float:
    if y1 == y0:
        return x0
    frac = (target - y0) / (y1 - y0)
    return x0 + frac * (x1 - x0)


def fwhm_bounds(x: list[float], corrected: list[float], center_idx: int, half_height: float) -> tuple[float, float, float]:
    left_idx = center_idx
    while left_idx > 0 and corrected[left_idx] > half_height:
        left_idx -= 1
    right_idx = center_idx
    while right_idx < len(corrected) - 1 and corrected[right_idx] > half_height:
        right_idx += 1

    left = x[left_idx]
    if left_idx < center_idx:
        left = interpolate_crossing(x[left_idx], corrected[left_idx], x[left_idx + 1], corrected[left_idx + 1], half_height)
    right = x[right_idx]
    if right_idx > center_idx:
        right = interpolate_crossing(x[right_idx - 1], corrected[right_idx - 1], x[right_idx], corrected[right_idx], half_height)
    return left, right, abs(right - left)


def gaussian_value(x_value: float, center: float, amplitude: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return amplitude * math.exp(-0.5 * ((x_value - center) / sigma) ** 2)


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def module_version(module_name: str) -> str | None:
    try:
        module = __import__(module_name)
    except Exception:
        return None
    version = getattr(module, "__version__", None)
    return str(version) if version is not None else None


def find_khervefitting_source() -> str | None:
    script_path = Path(__file__).resolve()
    candidates = [
        parent / "baselines/imported/khervefitting-1.80/source/KherveFitting-1.80"
        for parent in [Path.cwd().resolve(), *Path.cwd().resolve().parents, script_path.parent, *script_path.parents]
    ]
    for candidate in candidates:
        if (candidate / "KherveFitting.py").exists():
            return str(candidate)
    return None


def probe_xps_backends() -> dict[str, Any]:
    modules = {name: module_available(name) for name in ["numpy", "scipy", "lmfit", "matplotlib", "pandas", "wx"]}
    versions = {name: module_version(name) if available else None for name, available in modules.items()}
    kherve_source = find_khervefitting_source()
    lmfit_available = bool(modules["numpy"] and modules["scipy"] and modules["lmfit"])
    selected_backend = XPS_BACKEND_LMFIT_METHOD if lmfit_available else XPS_BACKEND_STDLIB_METHOD
    kherve_required = ["numpy", "matplotlib", "wx"]
    kherve_missing = [name for name in kherve_required if not modules.get(name)]
    return {
        "selected_backend": selected_backend,
        "selected_backend_available": True,
        "selected_backend_scope": (
            "headless lmfit Gaussian least-squares refinement over existing XPS handoff guesses"
            if selected_backend == XPS_BACKEND_LMFIT_METHOD
            else "headless standard-library Gaussian least-squares refinement over existing XPS handoff guesses"
        ),
        "external_backend_candidates": {
            "lmfit": {
                "available": lmfit_available,
                "required_modules": ["numpy", "scipy", "lmfit"],
                "versions": {name: versions.get(name) for name in ["numpy", "scipy", "lmfit"]},
            },
            "khervefitting_source": {
                "available": bool(kherve_source and not kherve_missing),
                "source_path": kherve_source,
                "required_modules": kherve_required,
                "missing_modules": kherve_missing,
                "headless_import_attempted": False,
                "note": (
                    "Local source is present, but this monolithic GUI-style source was not executed "
                    "headlessly unless required GUI/scientific-stack modules were available."
                ),
            },
        },
        "python_modules": modules,
        "python_module_versions": versions,
        "non_claim_boundary": "backend_probe_only_not_chemical_state_or_valence",
    }


def sum_gaussians(x_values: list[float], peaks: list[dict[str, float]]) -> list[float]:
    return [
        sum(gaussian_value(xi, peak["center"], peak["amplitude"], peak["sigma"]) for peak in peaks)
        for xi in x_values
    ]


def sse(values: list[float], fitted: list[float]) -> float:
    return sum((value - pred) ** 2 for value, pred in zip(values, fitted))


def classify_backend_quality(
    normalized_rmse: float | None,
    flags: list[str],
    point_count: int,
    peak_count: int,
) -> tuple[str, str, str]:
    if point_count < 20:
        return XPS_BACKEND_QUALITY_REVIEW, "需人工复核", "fewer than 20 fitted points"
    if peak_count <= 0:
        return XPS_BACKEND_QUALITY_REVIEW, "需人工复核", "no backend peaks returned"
    if normalized_rmse is None:
        return XPS_BACKEND_QUALITY_REVIEW, "需人工复核", "normalized RMSE unavailable"
    if flags:
        return XPS_BACKEND_QUALITY_WEAK, "偏弱", "quality flags present: " + ", ".join(flags)
    if normalized_rmse <= 0.2:
        return XPS_BACKEND_QUALITY_REFERENCE, "可参考", "normalized RMSE <= 0.2 and no backend quality flags"
    if normalized_rmse <= 0.35:
        return XPS_BACKEND_QUALITY_WEAK, "偏弱", "normalized RMSE between 0.2 and 0.35"
    return XPS_BACKEND_QUALITY_REVIEW, "需人工复核", "normalized RMSE > 0.35"


def estimate_amplitudes(x_values: list[float], values: list[float], peaks: list[dict[str, float]]) -> None:
    for idx, peak in enumerate(peaks):
        other = [
            sum(
                gaussian_value(xi, other_peak["center"], other_peak["amplitude"], other_peak["sigma"])
                for other_idx, other_peak in enumerate(peaks)
                if other_idx != idx
            )
            for xi in x_values
        ]
        basis = [gaussian_value(xi, peak["center"], 1.0, peak["sigma"]) for xi in x_values]
        numerator = sum((value - other_value) * basis_value for value, other_value, basis_value in zip(values, other, basis))
        denominator = sum(basis_value ** 2 for basis_value in basis)
        peak["amplitude"] = max(0.0, numerator / denominator) if denominator else 0.0


def fit_xps_backend_stdlib(
    x_values: list[float],
    corrected_values: list[float],
    draft_peaks: list[dict[str, Any]],
    source_label: str,
) -> dict[str, Any]:
    if not draft_peaks:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_STDLIB_METHOD,
            "reason": "no peak guesses available",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "no peak guesses available",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }
    if len(x_values) < 10 or len(corrected_values) < 10:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_STDLIB_METHOD,
            "reason": "fewer than 10 numeric points",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "fewer than 10 numeric points",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }

    axis_span = max(x_values) - min(x_values)
    median_step = median([abs(b - a) for a, b in zip(x_values, x_values[1:])]) or (axis_span / 200 if axis_span else 1.0)
    min_sigma = max(median_step * 0.5, 1e-9)
    max_sigma = max(axis_span, min_sigma)
    peaks: list[dict[str, float]] = []
    for peak in draft_peaks[:6]:
        center = parse_float(peak.get("center_ev"))
        sigma = parse_float(peak.get("sigma_ev"))
        amplitude = parse_float(peak.get("height_baseline_corrected"))
        if center is None or sigma is None or amplitude is None:
            continue
        peaks.append(
            {
                "center": min(max(center, min(x_values)), max(x_values)),
                "sigma": min(max(abs(sigma), min_sigma), max_sigma),
                "amplitude": max(0.0, amplitude),
                "initial_center": center,
                "initial_sigma": abs(sigma),
            }
        )
    if not peaks:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_STDLIB_METHOD,
            "reason": "no finite peak guesses available",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "no finite peak guesses available",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }

    estimate_amplitudes(x_values, corrected_values, peaks)
    initial_fit = sum_gaussians(x_values, peaks)
    initial_sse = sse(corrected_values, initial_fit)
    center_step = max(median_step, axis_span / 200 if axis_span else median_step)
    sigma_factor = 1.25
    current_sse = initial_sse
    for _ in range(5):
        improved = False
        for peak in peaks:
            for field, candidates in [
                ("center", [peak["center"] - center_step, peak["center"] + center_step]),
                ("sigma", [peak["sigma"] / sigma_factor, peak["sigma"] * sigma_factor]),
            ]:
                original = peak[field]
                best_value = original
                best_sse = current_sse
                for candidate in candidates:
                    if field == "center":
                        candidate = min(max(candidate, min(x_values)), max(x_values))
                    else:
                        candidate = min(max(abs(candidate), min_sigma), max_sigma)
                    peak[field] = candidate
                    estimate_amplitudes(x_values, corrected_values, peaks)
                    candidate_sse = sse(corrected_values, sum_gaussians(x_values, peaks))
                    if candidate_sse < best_sse:
                        best_sse = candidate_sse
                        best_value = candidate
                peak[field] = best_value
                estimate_amplitudes(x_values, corrected_values, peaks)
                if best_sse < current_sse:
                    current_sse = best_sse
                    improved = True
                else:
                    peak[field] = original
                    estimate_amplitudes(x_values, corrected_values, peaks)
        center_step *= 0.5
        sigma_factor = 1.0 + (sigma_factor - 1.0) * 0.5
        if not improved and center_step < max(median_step * 0.1, 1e-9):
            break

    fitted_values = sum_gaussians(x_values, peaks)
    final_sse = sse(corrected_values, fitted_values)
    final_rmse = math.sqrt(final_sse / len(fitted_values))
    initial_rmse = math.sqrt(initial_sse / len(fitted_values))
    signal_span = max(corrected_values) - min(corrected_values)
    normalized_rmse = final_rmse / signal_span if signal_span else None
    mean_abs_residual = sum(abs(value - pred) for value, pred in zip(corrected_values, fitted_values)) / len(fitted_values)
    sse_improvement_fraction = (initial_sse - final_sse) / initial_sse if initial_sse else None
    area_total = sum(peak["amplitude"] * peak["sigma"] * math.sqrt(2 * math.pi) for peak in peaks) or None
    result_peaks = []
    center_shifts = []
    sigma_ratios = []
    for idx, peak in enumerate(peaks, start=1):
        area = peak["amplitude"] * peak["sigma"] * math.sqrt(2 * math.pi)
        center_shifts.append(abs(peak["center"] - peak["initial_center"]))
        if peak["initial_sigma"]:
            sigma_ratios.append(max(peak["sigma"] / peak["initial_sigma"], peak["initial_sigma"] / peak["sigma"]))
        result_peaks.append(
            {
                "peak_id": f"b{idx}",
                "center_ev": compact_number(peak["center"]),
                "center_shift_from_guess_ev": compact_number(peak["center"] - peak["initial_center"]),
                "amplitude": compact_number(peak["amplitude"]),
                "sigma_ev": compact_number(peak["sigma"]),
                "fwhm_ev": compact_number(peak["sigma"] * 2.354820045),
                "area": compact_number(area),
                "relative_area": compact_number(area / area_total) if area_total else None,
            }
        )
    flags = []
    if normalized_rmse is not None and normalized_rmse > 0.35:
        flags.append("high_backend_normalized_rmse")
    if current_sse > initial_sse * 1.05:
        flags.append("backend_fit_worse_than_initial_guess")
    if sse_improvement_fraction is not None and sse_improvement_fraction < 0:
        flags.append("backend_sse_not_improved")
    max_center_shift = max(center_shifts) if center_shifts else None
    max_sigma_ratio = max(sigma_ratios) if sigma_ratios else None
    quality_category, quality_label_zh, quality_reason = classify_backend_quality(
        normalized_rmse, flags, len(x_values), len(result_peaks)
    )
    return {
        "status": XPS_BACKEND_STATUS_SUCCEEDED,
        "backend": XPS_BACKEND_STDLIB_METHOD,
        "source": source_label,
        "model_scope": "headless Gaussian least-squares refinement on baseline-corrected XPS data",
        "background_model": "linear_endpoint_from_current_runner",
        "peak_shape": "gaussian",
        "point_count": len(x_values),
        "peak_count": len(result_peaks),
        "initial_rmse": compact_number(initial_rmse),
        "rmse": compact_number(final_rmse),
        "normalized_rmse": compact_number(normalized_rmse),
        "sse_improvement_fraction": compact_number(sse_improvement_fraction),
        "mean_abs_residual": compact_number(mean_abs_residual),
        "max_center_shift_ev": compact_number(max_center_shift),
        "max_sigma_ratio": compact_number(max_sigma_ratio),
        "quality_category": quality_category,
        "quality_label_zh": quality_label_zh,
        "quality_reason": quality_reason,
        "diagnostics": {
            "initial_sse": compact_number(initial_sse),
            "final_sse": compact_number(final_sse),
            "initial_rmse": compact_number(initial_rmse),
            "final_rmse": compact_number(final_rmse),
            "normalized_rmse": compact_number(normalized_rmse),
            "sse_improvement_fraction": compact_number(sse_improvement_fraction),
            "mean_abs_residual": compact_number(mean_abs_residual),
            "max_center_shift_ev": compact_number(max_center_shift),
            "max_sigma_ratio": compact_number(max_sigma_ratio),
            "point_count": len(x_values),
            "peak_count": len(result_peaks),
        },
        "quality_flags": flags,
        "fit_parameters": result_peaks,
        "non_claim_boundary": "numerical_backend_fit_only_not_chemical_state_or_valence",
        "warnings": [
            "not_khervefitting_or_lmfit",
            "requires_human_review_before_chemical_interpretation",
        ] + flags,
    }


def fit_xps_backend_lmfit(
    x_values: list[float],
    corrected_values: list[float],
    draft_peaks: list[dict[str, Any]],
    source_label: str,
) -> dict[str, Any]:
    if not draft_peaks:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_LMFIT_METHOD,
            "reason": "no peak guesses available",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "no peak guesses available",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }
    if len(x_values) < 10 or len(corrected_values) < 10:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_LMFIT_METHOD,
            "reason": "fewer than 10 numeric points",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "fewer than 10 numeric points",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }

    try:
        import numpy as np
        from lmfit import Parameters, minimize
    except Exception as exc:
        return {
            "status": XPS_BACKEND_STATUS_FAILED,
            "backend": XPS_BACKEND_LMFIT_METHOD,
            "source": source_label,
            "reason": f"lmfit import failed: {exc}",
            "quality_category": XPS_BACKEND_QUALITY_REVIEW,
            "quality_label_zh": "需人工复核",
            "quality_reason": "lmfit import failed",
            "diagnostics": {},
            "quality_flags": ["lmfit_import_failed"],
            "fit_parameters": [],
            "non_claim_boundary": "numerical_backend_fit_only_not_chemical_state_or_valence",
        }

    axis_span = max(x_values) - min(x_values)
    median_step = median([abs(b - a) for a, b in zip(x_values, x_values[1:])]) or (axis_span / 200 if axis_span else 1.0)
    min_sigma = max(median_step * 0.5, 1e-9)
    max_sigma = max(axis_span, min_sigma)
    prepared: list[dict[str, float]] = []
    for peak in draft_peaks[:6]:
        center = parse_float(peak.get("center_ev"))
        sigma = parse_float(peak.get("sigma_ev"))
        amplitude = parse_float(peak.get("height_baseline_corrected"))
        if center is None or sigma is None or amplitude is None:
            continue
        prepared.append(
            {
                "center": min(max(center, min(x_values)), max(x_values)),
                "sigma": min(max(abs(sigma), min_sigma), max_sigma),
                "amplitude": max(0.0, amplitude),
                "initial_center": center,
                "initial_sigma": abs(sigma),
            }
        )
    if not prepared:
        return {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_LMFIT_METHOD,
            "reason": "no finite peak guesses available",
            "quality_category": XPS_BACKEND_QUALITY_SKIPPED,
            "quality_label_zh": "跳过",
            "quality_reason": "no finite peak guesses available",
            "diagnostics": {},
            "non_claim_boundary": "not_a_backend_fit_not_chemical_state_or_valence",
        }

    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(corrected_values, dtype=float)
    params = Parameters()
    for idx, peak in enumerate(prepared):
        params.add(f"amp_{idx}", value=peak["amplitude"], min=0.0)
        params.add(f"center_{idx}", value=peak["center"], min=min(x_values), max=max(x_values))
        params.add(f"sigma_{idx}", value=peak["sigma"], min=min_sigma, max=max_sigma)

    def model(pars: Any) -> Any:
        fitted = np.zeros_like(x_arr)
        for idx in range(len(prepared)):
            amp = pars[f"amp_{idx}"].value
            center = pars[f"center_{idx}"].value
            sigma = max(pars[f"sigma_{idx}"].value, min_sigma)
            fitted += amp * np.exp(-0.5 * ((x_arr - center) / sigma) ** 2)
        return fitted

    initial_fit = model(params)
    initial_sse = float(np.sum((y_arr - initial_fit) ** 2))
    try:
        result = minimize(lambda pars: model(pars) - y_arr, params, method="least_squares", max_nfev=1000)
    except Exception as exc:
        return {
            "status": XPS_BACKEND_STATUS_FAILED,
            "backend": XPS_BACKEND_LMFIT_METHOD,
            "source": source_label,
            "reason": f"lmfit minimization failed: {exc}",
            "quality_category": XPS_BACKEND_QUALITY_REVIEW,
            "quality_label_zh": "需人工复核",
            "quality_reason": "lmfit minimization failed",
            "diagnostics": {"initial_sse": compact_number(initial_sse), "point_count": len(x_values), "peak_count": len(prepared)},
            "quality_flags": ["lmfit_minimization_failed"],
            "fit_parameters": [],
            "non_claim_boundary": "numerical_backend_fit_only_not_chemical_state_or_valence",
        }

    fitted_values = model(result.params)
    final_sse = float(np.sum((y_arr - fitted_values) ** 2))
    final_rmse = math.sqrt(final_sse / len(fitted_values))
    initial_rmse = math.sqrt(initial_sse / len(fitted_values))
    signal_span = max(corrected_values) - min(corrected_values)
    normalized_rmse = final_rmse / signal_span if signal_span else None
    mean_abs_residual = float(np.mean(np.abs(y_arr - fitted_values)))
    sse_improvement_fraction = (initial_sse - final_sse) / initial_sse if initial_sse else None

    result_peaks = []
    center_shifts = []
    sigma_ratios = []
    areas = []
    for idx, peak in enumerate(prepared):
        center = float(result.params[f"center_{idx}"].value)
        sigma = float(result.params[f"sigma_{idx}"].value)
        amplitude = float(result.params[f"amp_{idx}"].value)
        area = amplitude * sigma * math.sqrt(2 * math.pi)
        center_shifts.append(abs(center - peak["initial_center"]))
        if peak["initial_sigma"]:
            sigma_ratios.append(max(sigma / peak["initial_sigma"], peak["initial_sigma"] / sigma))
        areas.append(area)
        result_peaks.append(
            {
                "peak_id": f"l{idx + 1}",
                "center_ev": compact_number(center),
                "center_shift_from_guess_ev": compact_number(center - peak["initial_center"]),
                "amplitude": compact_number(amplitude),
                "sigma_ev": compact_number(sigma),
                "fwhm_ev": compact_number(sigma * 2.354820045),
                "area": compact_number(area),
            }
        )
    area_total = sum(areas) or None
    if area_total:
        for row, area in zip(result_peaks, areas):
            row["relative_area"] = compact_number(area / area_total)

    flags = []
    if not getattr(result, "success", False):
        flags.append("lmfit_reported_unsuccessful_convergence")
    if normalized_rmse is not None and normalized_rmse > 0.35:
        flags.append("high_backend_normalized_rmse")
    if sse_improvement_fraction is not None and sse_improvement_fraction < 0:
        flags.append("backend_sse_not_improved")
    max_center_shift = max(center_shifts) if center_shifts else None
    max_sigma_ratio = max(sigma_ratios) if sigma_ratios else None
    quality_category, quality_label_zh, quality_reason = classify_backend_quality(
        normalized_rmse, flags, len(x_values), len(result_peaks)
    )
    return {
        "status": XPS_BACKEND_STATUS_SUCCEEDED,
        "backend": XPS_BACKEND_LMFIT_METHOD,
        "source": source_label,
        "model_scope": "headless lmfit Gaussian least-squares refinement on baseline-corrected XPS data",
        "background_model": "linear_endpoint_from_current_runner",
        "peak_shape": "gaussian",
        "point_count": len(x_values),
        "peak_count": len(result_peaks),
        "initial_rmse": compact_number(initial_rmse),
        "rmse": compact_number(final_rmse),
        "normalized_rmse": compact_number(normalized_rmse),
        "sse_improvement_fraction": compact_number(sse_improvement_fraction),
        "mean_abs_residual": compact_number(mean_abs_residual),
        "max_center_shift_ev": compact_number(max_center_shift),
        "max_sigma_ratio": compact_number(max_sigma_ratio),
        "quality_category": quality_category,
        "quality_label_zh": quality_label_zh,
        "quality_reason": quality_reason,
        "diagnostics": {
            "initial_sse": compact_number(initial_sse),
            "final_sse": compact_number(final_sse),
            "initial_rmse": compact_number(initial_rmse),
            "final_rmse": compact_number(final_rmse),
            "normalized_rmse": compact_number(normalized_rmse),
            "sse_improvement_fraction": compact_number(sse_improvement_fraction),
            "mean_abs_residual": compact_number(mean_abs_residual),
            "max_center_shift_ev": compact_number(max_center_shift),
            "max_sigma_ratio": compact_number(max_sigma_ratio),
            "point_count": len(x_values),
            "peak_count": len(result_peaks),
            "lmfit_success": bool(getattr(result, "success", False)),
            "lmfit_message": str(getattr(result, "message", "")),
            "lmfit_nfev": int(getattr(result, "nfev", 0) or 0),
        },
        "quality_flags": flags,
        "fit_parameters": result_peaks,
        "non_claim_boundary": "numerical_backend_fit_only_not_chemical_state_or_valence",
        "warnings": [
            "lmfit_headless_backend_not_khervefitting_gui",
            "requires_human_review_before_chemical_interpretation",
        ] + flags,
    }


def fit_xps_backend(
    x_values: list[float],
    corrected_values: list[float],
    draft_peaks: list[dict[str, Any]],
    source_label: str,
) -> dict[str, Any]:
    if module_available("numpy") and module_available("scipy") and module_available("lmfit"):
        return fit_xps_backend_lmfit(x_values, corrected_values, draft_peaks, source_label)
    return fit_xps_backend_stdlib(x_values, corrected_values, draft_peaks, source_label)


def fit_xps_series(x: list[float], y: list[float], source_label: str, max_peaks: int = 6) -> dict[str, Any]:
    clean = [(xi, yi) for xi, yi in zip(x, y) if math.isfinite(xi) and math.isfinite(yi)]
    if len(clean) < 10:
        return unfitted_xps_fit(source_label, "fewer than 10 finite x/y points", ["not_enough_numeric_points"], len(clean))

    clean.sort(key=lambda pair: pair[0])
    x_sorted = [pair[0] for pair in clean]
    y_sorted = [pair[1] for pair in clean]
    y_smooth = smooth(y_sorted, window=5)
    baseline = linear_baseline(x_sorted, y_smooth)
    corrected = [yi - bi for yi, bi in zip(y_smooth, baseline)]
    max_pos = max(corrected)
    min_neg = min(corrected)
    polarity = "positive"
    if abs(min_neg) > abs(max_pos):
        corrected = [-value for value in corrected]
        polarity = "negative_inverted"
        max_pos = max(corrected)

    if max_pos <= 0:
        return unfitted_xps_fit(
            source_label,
            "no positive peak-like signal after linear baseline correction",
            ["no_peak_like_signal"],
            len(x_sorted),
        )

    threshold = max_pos * 0.08
    min_separation = max(3, len(corrected) // 50)
    candidates = [
        idx
        for idx in range(1, len(corrected) - 1)
        if corrected[idx] >= corrected[idx - 1]
        and corrected[idx] >= corrected[idx + 1]
        and corrected[idx] >= threshold
    ]
    candidates.sort(key=lambda idx: corrected[idx], reverse=True)

    chosen: list[int] = []
    for idx in candidates:
        if all(abs(idx - existing) >= min_separation for existing in chosen):
            chosen.append(idx)
        if len(chosen) >= max_peaks:
            break
    if not chosen:
        chosen = [max(range(len(corrected)), key=lambda idx: corrected[idx])]

    peaks: list[dict[str, Any]] = []
    for peak_no, idx in enumerate(sorted(chosen, key=lambda item: x_sorted[item]), start=1):
        amplitude = corrected[idx]
        left, right, fwhm = fwhm_bounds(x_sorted, corrected, idx, amplitude / 2)
        if fwhm <= 0:
            step = abs(x_sorted[min(idx + 1, len(x_sorted) - 1)] - x_sorted[max(idx - 1, 0)]) or 1.0
            fwhm = step
            left = x_sorted[idx] - step / 2
            right = x_sorted[idx] + step / 2
        sigma = fwhm / 2.354820045
        area = amplitude * sigma * math.sqrt(2 * math.pi)
        peaks.append(
            {
                "peak_id": f"p{peak_no}",
                "center_ev": x_sorted[idx],
                "height_baseline_corrected": amplitude,
                "fwhm_ev": fwhm,
                "sigma_ev": sigma,
                "area_proxy": area,
                "left_half_max_ev": left,
                "right_half_max_ev": right,
            }
        )

    total_area = sum(max(0.0, float(peak["area_proxy"])) for peak in peaks) or None
    if total_area:
        for peak in peaks:
            peak["relative_area_proxy"] = max(0.0, float(peak["area_proxy"])) / total_area

    backend_fit = fit_xps_backend(x_sorted, corrected, peaks, source_label)

    fitted = []
    for xi, base in zip(x_sorted, baseline):
        signal = base + sum(
            gaussian_value(xi, float(peak["center_ev"]), float(peak["height_baseline_corrected"]), float(peak["sigma_ev"]))
            for peak in peaks
        )
        fitted.append(signal)
    rmse = math.sqrt(sum((yi - fi) ** 2 for yi, fi in zip(y_sorted, fitted)) / len(fitted))
    signal_span = max(y_sorted) - min(y_sorted)
    normalized_rmse = rmse / signal_span if signal_span else None
    axis_span = max(x_sorted) - min(x_sorted)
    median_step = median([abs(b - a) for a, b in zip(x_sorted, x_sorted[1:])])
    background_scale = max(abs(value) for value in baseline) if baseline else 0.0
    signal_to_background = max_pos / background_scale if background_scale else None

    quality_flags: list[str] = []
    if len(x_sorted) < 30:
        quality_flags.append("too_few_numeric_points_for_stable_fit")
    if signal_to_background is not None and signal_to_background < 0.03:
        quality_flags.append("low_signal_to_background")
    if normalized_rmse is not None and normalized_rmse > 0.35:
        quality_flags.append("high_normalized_rmse")
    if len(candidates) > max_peaks:
        quality_flags.append("crowded_or_many_candidate_peaks")
    for peak in peaks:
        fwhm = float(peak.get("fwhm_ev") or 0.0)
        if axis_span and fwhm > axis_span * 0.6:
            quality_flags.append("implausibly_broad_fwhm")
            break
        if median_step is not None and fwhm < median_step * 0.5:
            quality_flags.append("implausibly_narrow_fwhm")
            break
    centers = sorted(float(peak["center_ev"]) for peak in peaks)
    widths = sorted(float(peak.get("fwhm_ev") or 0.0) for peak in peaks)
    for left_center, right_center, left_width, right_width in zip(centers, centers[1:], widths, widths[1:]):
        if abs(right_center - left_center) < max(left_width, right_width):
            quality_flags.append("crowded_or_overlapping_peaks")
            break
    quality_flags = sorted(set(quality_flags))
    fit_status = XPS_FIT_STATUS_WEAK if quality_flags else XPS_FIT_STATUS_DRAFT
    quality_grade = "偏弱" if quality_flags else "可参考"

    return {
        "status": fit_status,
        "fit_status": fit_status,
        "quality_grade": quality_grade,
        "quality_flags": quality_flags,
        "method": XPS_FIT_METHOD,
        "source": source_label,
        "model_scope": "linear background plus Gaussian proxy peaks from local maxima; no nonlinear least-squares backend",
        "background_model": "linear_endpoint",
        "polarity": polarity,
        "point_count": len(x_sorted),
        "peak_count": len(peaks),
        "peaks": peaks,
        "xps_backend_fit": backend_fit,
        "quality": {
            "rmse": rmse,
            "normalized_rmse": normalized_rmse,
            "signal_to_background_proxy": signal_to_background,
            "median_axis_step_ev": median_step,
        },
        "warnings": [
            "heuristic_fit_not_khervefitting_or_lmfit",
            "no_chemical_state_assignment",
        ] + quality_flags,
    }


def common_root(input_path: Path) -> Path:
    return input_path if input_path.is_dir() else input_path.parent


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def discover_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    files = [p for p in input_path.rglob("*") if p.is_file()]
    return sorted(files)


def path_text(path: Path) -> str:
    return " ".join(part.lower() for part in path.parts)


def infer_modality(path: Path) -> str:
    suffix = path.suffix.lower()
    text = path_text(path)
    if "xps" in text or suffix == ".vms":
        return "XPS"
    if "xas" in text or "xanes" in text or "exafs" in text:
        return "XAS"
    if suffix in {".xlsx", ".xlsm"}:
        return "XPS"
    if suffix in TEXT_SUFFIXES:
        rows = read_numeric_table(path)
        if len(rows) >= 5:
            x = [row[0] for row in rows if len(row) >= 2]
            x_stats = finite_stats(x)
            span = (x_stats["max"] or 0) - (x_stats["min"] or 0)
            if span > 50:
                return "XAS"
    return "unknown"


def extract_element_hints(text: str) -> list[str]:
    hints = set()
    for token in re.findall(r"\b[A-Z][a-z]?\b", text):
        if token in ELEMENT_SYMBOLS:
            hints.add(token)
    for token in re.findall(r"\b([A-Z][a-z]?)[\s_-]?(?:1s|2p|3d|4f)\b", text):
        if token in ELEMENT_SYMBOLS:
            hints.add(token)
    return sorted(hints)


def infer_xps_region_hints_from_ranges(ranges: dict[str, Any]) -> list[str]:
    axis_min = parse_float(ranges.get("axis_min"))
    axis_max = parse_float(ranges.get("axis_max"))
    if axis_min is None or axis_max is None:
        return []
    range_min = min(axis_min, axis_max)
    range_max = max(axis_min, axis_max)
    hints: list[str] = []
    seen: set[str] = set()
    for ref in XPS_REFERENCE_ASSIGNMENT_LIBRARY:
        energy_min = parse_float(ref.get("energy_min_ev"))
        energy_max = parse_float(ref.get("energy_max_ev"))
        region = str(ref.get("region") or "")
        if energy_min is None or energy_max is None or not region:
            continue
        if energy_max < range_min or energy_min > range_max or region in seen:
            continue
        seen.add(region)
        hints.append(region)
    return hints


def xlsx_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall("main:si", NS):
        strings.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    return strings


def workbook_sheet_paths(zf: ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets = []
    for sheet in wb.find("main:sheets", NS) or []:
        name = sheet.attrib["name"]
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = relmap[rid]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        sheets.append((name, target.replace("xl//", "xl/")))
    return sheets


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    ctype = cell.attrib.get("t")
    if ctype == "inlineStr":
        return "".join(t.text or "" for t in cell.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
    value_node = cell.find("main:v", NS)
    if value_node is None:
        return ""
    value = value_node.text or ""
    if ctype == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    return value


def parse_xas(path: Path, root: Path) -> tuple[list[dict[str, Any]], Series | None]:
    rows = read_numeric_table(path)
    columns = max((len(row) for row in rows), default=0)
    x = [row[0] for row in rows if len(row) >= 2]
    y_col = 2 if columns >= 3 else 1
    y = [row[y_col] for row in rows if len(row) > y_col]
    cell_count = sum(len(row) for row in rows)
    finite_count = sum(1 for row in rows for val in row if math.isfinite(val))
    x_stats = finite_stats(x)
    y_stats = finite_stats(y)
    record = {
        "file": rel(path, root),
        "modality": "XAS",
        "source_type": "numeric_text",
        "record": "",
        "parse_status": "parsed" if rows else "no_numeric_rows",
        "row_count": len(rows),
        "column_count": columns,
        "column_roles": {
            "energy_column": 1,
            "absorption_or_signal_column": y_col + 1,
            "basis": "first numeric column as energy; third numeric column used when present, otherwise second",
        },
        "range_summary": {
            "energy_min": x_stats["min"],
            "energy_max": x_stats["max"],
            "signal_min": y_stats["min"],
            "signal_max": y_stats["max"],
            "signal_mean": y_stats["mean"],
        },
        "qc_features": {
            "finite_fraction": finite_count / cell_count if cell_count else 0.0,
            "energy_strictly_increasing": strictly_increasing(x),
            "simple_edge_marker_energy": max_slope_energy(x, y),
        },
        "element_hints": extract_element_hints(path.name),
        "modeling_status": "未建模",
    }
    series = Series(x=x, y=y) if len(x) >= 2 and len(y) >= 2 else None
    return [record], series


def first_number(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
    return parse_float(match.group(0)) if match else None


def is_numeric_line(text: str) -> bool:
    return parse_float(text.strip()) is not None


def vms_block_start_indices(lines: list[str]) -> list[int]:
    starts: list[int] = []
    excluded = {
        "creation",
        "settings",
        "excitation",
        "esca modes",
        "scan",
        "acquisition conditions",
        "xps",
        "kinetic energy",
        "intensity",
        "transmission",
        "pulse counting",
        "end of experiment",
    }
    for idx, line in enumerate(lines):
        label = line.strip()
        if not label or ":" in label or is_numeric_line(label) or label.lower() in excluded:
            continue
        if idx + 8 >= len(lines):
            continue
        sample = lines[idx + 1].strip()
        if not sample or is_numeric_line(sample):
            continue
        if not all(is_numeric_line(lines[pos]) for pos in range(idx + 2, min(idx + 9, len(lines)))):
            continue
        window = [item.strip() for item in lines[idx : min(idx + 140, len(lines))]]
        if "Creation" in window and any(item.startswith("Start :") for item in window) and "Kinetic energy" in window:
            starts.append(idx)
    return starts


def vms_metadata_from_block(block_lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in block_lines[:160]:
        if ":" in line:
            key, value = line.split(":", 1)
            if key.strip() and value.strip():
                metadata[key.strip()] = value.strip()
    return metadata


def vms_photon_energy(block_lines: list[str]) -> float | None:
    for idx, line in enumerate(block_lines):
        if "mono" not in line.lower():
            continue
        for candidate in block_lines[idx + 1 : idx + 6]:
            value = parse_float(candidate)
            if value is not None and 100.0 <= value <= 3000.0:
                return value
    return None


def reconstruct_vms_spectrum(block_lines: list[str], metadata: dict[str, str]) -> tuple[Series | None, dict[str, Any]]:
    """Recover a standard REGULAR VAMAS numeric spectrum without guessing unsupported layouts."""
    start_ev = first_number(metadata.get("Start", ""))
    end_ev = first_number(metadata.get("End", ""))
    step_ev = first_number(metadata.get("Step size", ""))
    number_steps_raw = first_number(metadata.get("Number Steps", ""))
    number_steps = int(number_steps_raw) if number_steps_raw is not None else None
    if start_ev is None or step_ev is None or number_steps is None:
        return None, {"status": "missing_axis_metadata"}

    try:
        kinetic_idx = next(idx for idx, line in enumerate(block_lines) if line.strip().lower() == "kinetic energy")
    except StopIteration:
        return None, {"status": "missing_scan_variable"}

    dependent_count = None
    if kinetic_idx + 4 < len(block_lines):
        raw_count = parse_float(block_lines[kinetic_idx + 4])
        if raw_count is not None:
            dependent_count = int(raw_count)
    if dependent_count is None or dependent_count < 1 or dependent_count > 8:
        return None, {"status": "unsupported_dependent_variable_count", "dependent_count": dependent_count}

    expected_points = number_steps + 1
    expected_values = expected_points * dependent_count
    pulse_idx = None
    for idx in range(kinetic_idx, min(kinetic_idx + 40, len(block_lines))):
        if block_lines[idx].strip().lower() == "pulse counting":
            pulse_idx = idx
            break
    if pulse_idx is None:
        return None, {"status": "missing_pulse_counting_marker"}

    data_count_idx = None
    for idx in range(pulse_idx + 1, min(pulse_idx + 35, len(block_lines))):
        value = parse_float(block_lines[idx])
        if value is not None and int(value) == expected_values:
            data_count_idx = idx
            break
    if data_count_idx is None:
        return None, {
            "status": "payload_count_not_matched",
            "expected_values": expected_values,
            "dependent_count": dependent_count,
        }

    payload_start = data_count_idx + 1 + 2 * dependent_count
    payload_end = payload_start + expected_values
    if payload_end > len(block_lines):
        return None, {
            "status": "payload_truncated",
            "expected_values": expected_values,
            "available_values": max(0, len(block_lines) - payload_start),
        }

    payload: list[float] = []
    for raw in block_lines[payload_start:payload_end]:
        value = parse_float(raw)
        if value is None:
            return None, {"status": "non_numeric_payload_value", "payload_line": raw}
        payload.append(value)

    intensity = payload[0::dependent_count]
    if len(intensity) != expected_points:
        return None, {"status": "intensity_length_mismatch", "point_count": len(intensity)}

    kinetic_axis = [start_ev + step_ev * idx for idx in range(expected_points)]
    photon_energy = vms_photon_energy(block_lines)
    if photon_energy is not None:
        axis = [photon_energy - value for value in kinetic_axis]
        axis_basis = "binding_energy_ev_from_photon_minus_kinetic_energy"
    else:
        axis = kinetic_axis
        axis_basis = "kinetic_energy_ev_from_vamas_regular_axis"

    if len(axis) < 10 or len(intensity) < 10:
        return None, {"status": "too_few_reconstructed_points", "point_count": len(axis)}
    if not all(math.isfinite(xi) and math.isfinite(yi) for xi, yi in zip(axis, intensity)):
        return None, {"status": "non_finite_reconstructed_values"}

    return Series(x=axis, y=intensity), {
        "status": "reconstructed",
        "axis_basis": axis_basis,
        "scan_variable": block_lines[kinetic_idx].strip(),
        "kinetic_start_ev": start_ev,
        "kinetic_end_ev": end_ev,
        "kinetic_step_ev": step_ev,
        "number_steps": number_steps,
        "dependent_count": dependent_count,
        "expected_values": expected_values,
        "point_count": len(axis),
        "photon_energy_ev": photon_energy,
    }


def parse_xps_vms(path: Path, root: Path) -> tuple[list[dict[str, Any]], Series | None]:
    try:
        lines = [line.strip() for line in path.read_text(errors="replace").splitlines()]
    except OSError:
        lines = []
    block_starts = vms_block_start_indices(lines)
    if not block_starts:
        text = "\n".join(lines[:200])
        reason = "VMS block structure was not recognized as a supported REGULAR numeric layout"
        return [
            {
                "file": rel(path, root),
                "modality": "XPS",
                "source_type": "vms_metadata",
                "record": "",
                "parse_status": "partial",
                "row_count": len(lines),
                "numeric_line_count": sum(1 for line in lines if parse_float(line) is not None),
                "column_roles": {},
                "range_summary": {},
                "element_hints": extract_element_hints(text + " " + path.name),
                "fitting_status": XPS_FIT_STATUS_UNFITTED,
                "xps_peak_fit": unfitted_xps_fit(rel(path, root), reason, ["vms_block_structure_not_recognized"]),
            }
        ], None

    records: list[dict[str, Any]] = []
    representative: Series | None = None
    boundaries = block_starts + [len(lines)]
    for block_no, (start_idx, end_idx) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        block_lines = lines[start_idx:end_idx]
        metadata = vms_metadata_from_block(block_lines)
        spectrum, reconstruction = reconstruct_vms_spectrum(block_lines, metadata)
        record_label = block_lines[0].strip() if block_lines else f"block_{block_no}"
        sample = metadata.get("Sample") or (block_lines[1].strip() if len(block_lines) > 1 else "")
        source_label = f"{sample} {record_label}".strip() or rel(path, root)
        start_ev = first_number(metadata.get("Start", ""))
        end_ev = first_number(metadata.get("End", ""))
        step_size = first_number(metadata.get("Step size", ""))
        number_steps = first_number(metadata.get("Number Steps", ""))
        xps_peak_fit = (
            fit_xps_series(spectrum.x, spectrum.y, source_label)
            if spectrum is not None
            else unfitted_xps_fit(
                source_label,
                f"VMS numeric spectrum was not reconstructed: {reconstruction.get('status', 'unknown_reason')}",
                ["vms_numeric_payload_not_reconstructed", str(reconstruction.get("status", "unknown_reason"))],
            )
        )
        x_stats = finite_stats(spectrum.x if spectrum is not None else [])
        y_stats = finite_stats(spectrum.y if spectrum is not None else [])
        if representative is None and spectrum is not None:
            representative = spectrum
        records.append(
            {
                "file": rel(path, root),
                "modality": "XPS",
                "source_type": "vms_regular_numeric" if spectrum is not None else "vms_metadata",
                "record": record_label,
                "sample": sample,
                "parse_status": "parsed" if spectrum is not None else "partial",
                "row_count": len(block_lines),
                "numeric_line_count": sum(1 for line in block_lines if parse_float(line) is not None),
                "numeric_row_count": reconstruction.get("point_count", 0) if spectrum is not None else 0,
                "column_roles": {
                    "energy_window_metadata": ["Start", "End", "Step size", "Number Steps"],
                    "axis": reconstruction.get("axis_basis"),
                    "intensity": "first VAMAS dependent variable named Intensity",
                    "basis": "REGULAR VAMAS numeric payload reconstructed when data-count and dependent-variable counts match metadata",
                },
                "range_summary": {
                    "axis_min": x_stats["min"],
                    "axis_max": x_stats["max"],
                    "intensity_min": y_stats["min"],
                    "intensity_max": y_stats["max"],
                    "intensity_mean": y_stats["mean"],
                    "kinetic_energy_start_ev": start_ev,
                    "kinetic_energy_end_ev": end_ev,
                    "step_size_ev": step_size,
                    "number_steps": int(number_steps) if number_steps is not None else None,
                },
                "vms_reconstruction": reconstruction,
                "element_hints": extract_element_hints(record_label + " " + sample + " " + path.name),
                "fitting_status": xps_peak_fit.get("fit_status", xps_peak_fit["status"]),
                "xps_peak_fit": xps_peak_fit,
            }
        )
    return records, representative


def parse_xps_xlsx(path: Path, root: Path) -> tuple[list[dict[str, Any]], Series | None]:
    records: list[dict[str, Any]] = []
    representative: Series | None = None
    try:
        with ZipFile(path) as zf:
            strings = xlsx_shared_strings(zf)
            for sheet_name, sheet_path in workbook_sheet_paths(zf):
                sheet = ET.fromstring(zf.read(sheet_path))
                row_count = 0
                numeric_rows = 0
                numeric_cells = 0
                x: list[float] = []
                y: list[float] = []
                for row in sheet.findall(".//main:row", NS):
                    row_count += 1
                    values = []
                    for cell in row.findall("main:c", NS):
                        value = parse_float(cell_text(cell, strings))
                        if value is not None:
                            values.append(value)
                    numeric_cells += len(values)
                    if len(values) >= 2:
                        numeric_rows += 1
                        x.append(values[0])
                        y.append(values[1])
                x_stats = finite_stats(x)
                y_stats = finite_stats(y)
                xps_peak_fit = (
                    fit_xps_series(x, y, sheet_name)
                    if len(x) >= 10 and len(y) >= 10
                    else unfitted_xps_fit(
                        sheet_name,
                        "not enough numeric rows for dependency-free peak fitting",
                        ["not_enough_numeric_rows", "too_few_numeric_points"],
                        len(x),
                    )
                )
                if representative is None and len(x) >= 10:
                    representative = Series(x=x, y=y)
                range_summary = {
                    "axis_min": x_stats["min"],
                    "axis_max": x_stats["max"],
                    "intensity_min": y_stats["min"],
                    "intensity_max": y_stats["max"],
                    "intensity_mean": y_stats["mean"],
                }
                region_hints = (
                    infer_xps_region_hints_from_ranges(range_summary)
                    if re.fullmatch(r"sheet\d+", sheet_name, re.IGNORECASE)
                    else []
                )
                records.append(
                    {
                        "file": rel(path, root),
                        "modality": "XPS",
                        "source_type": "xlsx_sheet",
                        "record": sheet_name,
                        "parse_status": "parsed" if numeric_rows else "no_numeric_rows",
                        "row_count": row_count,
                        "numeric_row_count": numeric_rows,
                        "numeric_cell_count": numeric_cells,
                        "column_roles": {
                            "binding_energy_or_axis_column": 1,
                            "intensity_column": 2,
                            "basis": "first two numeric cells per row are treated as axis/intensity candidate columns",
                        },
                        "range_summary": range_summary,
                        "element_hints": extract_element_hints(sheet_name + " " + path.name),
                        "region_hints": region_hints,
                        "fitting_status": xps_peak_fit.get("fit_status", xps_peak_fit["status"]),
                        "xps_peak_fit": xps_peak_fit,
                    }
                )
    except (BadZipFile, KeyError, ET.ParseError, OSError) as exc:
        records.append(
            {
                "file": rel(path, root),
                "modality": "XPS",
                "source_type": "xlsx_sheet",
                "record": "",
                "parse_status": "parse_error",
                "error": str(exc),
                "column_roles": {},
                "range_summary": {},
                "element_hints": extract_element_hints(path.name),
                "region_hints": [],
                "fitting_status": XPS_FIT_STATUS_UNFITTED,
                "xps_peak_fit": unfitted_xps_fit(rel(path, root), str(exc), ["xps_workbook_parse_error"]),
            }
        )
    return records, representative


def parse_file(path: Path, root: Path) -> tuple[list[dict[str, Any]], Series | None]:
    modality = infer_modality(path)
    suffix = path.suffix.lower()
    if modality == "XAS":
        return parse_xas(path, root)
    if modality == "XPS" and suffix == ".vms":
        return parse_xps_vms(path, root)
    if modality == "XPS" and suffix in {".xlsx", ".xlsm"}:
        return parse_xps_xlsx(path, root)
    return (
        [
            {
                "file": rel(path, root),
                "modality": modality,
                "source_type": "unsupported_or_unrecognized",
                "record": "",
                "parse_status": "skipped",
                "column_roles": {},
                "range_summary": {},
                "element_hints": extract_element_hints(path.name),
            }
        ],
        None,
    )


def qc_record(record: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    status = record.get("parse_status")
    modality = record.get("modality")
    ranges = record.get("range_summary") or {}
    features = record.get("qc_features") or {}
    if status not in {"parsed", "no_numeric_rows"}:
        findings.append({"severity": "error", "code": "parse_not_complete", "message": "File was not fully parsed."})
    if modality == "unknown":
        findings.append({"severity": "warning", "code": "unknown_modality", "message": "File modality could not be identified as XPS or XAS."})
    if modality == "XAS":
        if status != "parsed":
            findings.append({"severity": "error", "code": "xas_no_numeric_table", "message": "No numeric XAS table was found."})
        if (record.get("row_count") or 0) < 100:
            findings.append({"severity": "warning", "code": "xas_short_series", "message": "XAS series has fewer than 100 numeric rows."})
        energy_min = ranges.get("energy_min")
        energy_max = ranges.get("energy_max")
        if energy_min is None or energy_max is None or energy_max <= energy_min:
            findings.append({"severity": "error", "code": "xas_invalid_energy_range", "message": "XAS energy range is missing or invalid."})
        if features.get("energy_strictly_increasing") is False:
            findings.append({"severity": "warning", "code": "xas_nonmonotonic_energy", "message": "XAS energy axis is not strictly increasing."})
        if features.get("finite_fraction", 1.0) < 0.999:
            findings.append({"severity": "warning", "code": "xas_nonfinite_values", "message": "XAS table may contain non-finite values."})
    if modality == "XPS":
        if record.get("source_type") == "xlsx_sheet" and status == "no_numeric_rows":
            findings.append({"severity": "warning", "code": "xps_empty_sheet", "message": "XPS workbook sheet has no numeric rows."})
        if record.get("source_type") == "xlsx_sheet" and (record.get("numeric_row_count") or 0) < 5 and status == "parsed":
            findings.append({"severity": "warning", "code": "xps_sparse_sheet", "message": "XPS workbook sheet has very few numeric rows."})
        if record.get("source_type") == "vms_metadata":
            start = ranges.get("binding_energy_start_ev")
            end = ranges.get("binding_energy_end_ev")
            if start is None or end is None or end <= start:
                findings.append({"severity": "warning", "code": "xps_vms_energy_window_missing", "message": "VMS energy window metadata is missing or invalid."})
    return {
        "file": record.get("file"),
        "record": record.get("record", ""),
        "modality": modality,
        "parse_status": status,
        "warning_count": sum(1 for item in findings if item["severity"] == "warning"),
        "error_count": sum(1 for item in findings if item["severity"] == "error"),
        "findings": findings,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    flat_rows = []
    for row in rows:
        flat = {}
        for key, value in row.items():
            flat[key] = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
            if key not in fieldnames:
                fieldnames.append(key)
        flat_rows.append(flat)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)


def write_markdown_table(path: Path, title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    lines = [f"# {title}", "", "| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def md_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "\\|")


def compact_number(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def xps_energy_range_label(ranges: dict[str, Any]) -> str:
    candidates = [
        ("axis_min", "axis_max"),
        ("binding_energy_start_ev", "binding_energy_end_ev"),
        ("kinetic_energy_start_ev", "kinetic_energy_end_ev"),
    ]
    for start_key, end_key in candidates:
        start = ranges.get(start_key)
        end = ranges.get(end_key)
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            unit = "eV"
            return f"{compact_number(start)}-{compact_number(end)} {unit}"
    return ""


def xps_fit_reason(fit: dict[str, Any]) -> str:
    explicit = fit.get("unfitted_reason") or fit.get("reason")
    if explicit:
        return str(explicit)
    flags = fit.get("quality_flags") or []
    if flags:
        return "quality_flags=" + ",".join(str(flag) for flag in flags)
    if fit.get("peaks"):
        return "dependency_free_peak_proxy_available"
    return "no_peak_proxy_evidence"


def build_xps_evidence_rows(xps_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in xps_records:
        fit = record.get("xps_peak_fit") or {}
        quality = fit.get("quality") or {}
        peaks = fit.get("peaks") or []
        rows.append(
            {
                "file": record.get("file"),
                "record": record.get("record", ""),
                "source_type": record.get("source_type", ""),
                "parse_status": record.get("parse_status", ""),
                "numeric_rows": record.get("numeric_row_count") or record.get("row_count") or 0,
                "energy_range_ev": xps_energy_range_label(record.get("range_summary") or {}),
                "fit_status": fit.get("fit_status", fit.get("status", XPS_FIT_STATUS_UNFITTED)),
                "quality_grade": fit.get("quality_grade", "未拟合"),
                "peak_count": fit.get("peak_count", len(peaks)),
                "peak_centers_ev": [compact_number(peak.get("center_ev")) for peak in peaks[:8]],
                "normalized_rmse": compact_number(quality.get("normalized_rmse")),
                "signal_to_background_proxy": compact_number(quality.get("signal_to_background_proxy")),
                "quality_flags": fit.get("quality_flags") or [],
                "reason": xps_fit_reason(fit),
                "non_claim_boundary": "draft_only_not_chemical_state_or_valence",
            }
        )
    return rows


def write_xps_evidence_markdown(path: Path, evidence_rows: list[dict[str, Any]]) -> None:
    columns = [
        "file",
        "record",
        "source_type",
        "numeric_rows",
        "energy_range_ev",
        "fit_status",
        "quality_grade",
        "peak_count",
        "reason",
    ]
    lines = [
        "# XPS Evidence Table",
        "",
        "This table is a per-region inspection aid for the dependency-free XPS peak draft. It is not a final chemical-state, valence, oxidation-state, coordination-number, or publication-grade fit result.",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in evidence_rows:
        lines.append("| " + " | ".join(md_cell(row.get(column, "")) for column in columns) + " |")
    lines.extend(
        [
            "",
            "## Field notes",
            "",
            "- `fit_status` and `quality_grade` describe only the dependency-free peak-proxy draft.",
            "- `reason` explains why a region is usable, weak, or unfitted in this draft.",
            "- Peak centers and proxy areas remain in `xps_peak_fits.json/md` for fitting preparation only.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_xps_fit_markdown(path: Path, fit_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# XPS Peak Fit Draft",
        "",
        "This file reports dependency-free XPS peak-fit drafts only. The values are peak-center/FWHM/area proxies from a linear background and Gaussian local-maximum approximation; they are not final chemical-state assignments.",
        "",
        "| file | record | status | grade | peak_count | normalized_rmse | flags | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in fit_rows:
        fit = row.get("fit") or {}
        quality = fit.get("quality") or {}
        flags = ",".join(fit.get("quality_flags") or [])
        reason = fit.get("unfitted_reason") or fit.get("reason") or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("file", "")),
                    str(row.get("record", "")),
                    str(fit.get("fit_status", fit.get("status", ""))),
                    str(fit.get("quality_grade", "")),
                    str(fit.get("peak_count", 0)),
                    str(quality.get("normalized_rmse", "")),
                    flags,
                    reason,
                ]
            )
            + " |"
        )
    lines.extend(["", "## Peak details", ""])
    for row in fit_rows:
        fit = row.get("fit") or {}
        lines.append(f"### {row.get('file', '')} / {row.get('record', '')}")
        lines.append("")
        lines.append(f"- Status: {fit.get('fit_status', fit.get('status', ''))}; quality grade: {fit.get('quality_grade', '')}")
        if fit.get("quality_flags"):
            lines.append(f"- Quality flags: {', '.join(fit.get('quality_flags') or [])}")
        if fit.get("unfitted_reason") or fit.get("reason"):
            lines.append(f"- Reason: {fit.get('unfitted_reason') or fit.get('reason')}")
        if not fit.get("peaks"):
            lines.append("")
            continue
        for peak in fit["peaks"]:
            lines.append(
                "- {peak_id}: center={center_ev:.6g} eV, FWHM={fwhm_ev:.6g} eV, area_proxy={area_proxy:.6g}, relative_area_proxy={rel_area}".format(
                    peak_id=peak.get("peak_id", ""),
                    center_ev=float(peak.get("center_ev", 0.0)),
                    fwhm_ev=float(peak.get("fwhm_ev", 0.0)),
                    area_proxy=float(peak.get("area_proxy", 0.0)),
                    rel_area=peak.get("relative_area_proxy", ""),
                )
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_task_id(*parts: Any) -> str:
    raw = "__".join(str(part or "") for part in parts)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    return cleaned[:160] or "xps_fitting_task"


def build_xps_fitting_handoff(xps_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    handoff: list[dict[str, Any]] = []
    for record in xps_records:
        fit = record.get("xps_peak_fit") or {}
        peaks = fit.get("peaks") or []
        ranges = record.get("range_summary") or {}
        status = fit.get("fit_status", fit.get("status", XPS_FIT_STATUS_UNFITTED))
        ready = bool(peaks) and status in {XPS_FIT_STATUS_DRAFT, XPS_FIT_STATUS_WEAK}
        blocking_reasons: list[str] = []
        if not peaks:
            blocking_reasons.append(str(fit.get("unfitted_reason") or fit.get("reason") or "no_peak_proxy_evidence"))
        if status == XPS_FIT_STATUS_UNFITTED:
            blocking_reasons.append("record_is_unfitted")

        peak_guesses = []
        for peak in peaks:
            center = peak.get("center_ev")
            fwhm = peak.get("fwhm_ev")
            sigma = peak.get("sigma_ev")
            try:
                center_f = float(center)
                fwhm_f = abs(float(fwhm or 0.0))
                center_pad = max(0.2, fwhm_f * 0.75)
            except (TypeError, ValueError):
                center_f = None
                center_pad = 0.5
            peak_guesses.append(
                {
                    "peak_id": peak.get("peak_id"),
                    "center_ev_guess": compact_number(center),
                    "center_ev_bounds": (
                        [compact_number(center_f - center_pad), compact_number(center_f + center_pad)]
                        if center_f is not None
                        else None
                    ),
                    "height_guess": compact_number(peak.get("height_baseline_corrected")),
                    "sigma_ev_guess": compact_number(sigma),
                    "fwhm_ev_guess": compact_number(fwhm),
                    "area_proxy": compact_number(peak.get("area_proxy")),
                    "relative_area_proxy": compact_number(peak.get("relative_area_proxy")),
                    "shape_hint": "gaussian_initial_guess_only",
                }
            )

        handoff.append(
            {
                "task_id": safe_task_id(record.get("file"), record.get("record")),
                "task_status": "ready_for_backend_fit" if ready else "not_ready_for_backend_fit",
                "file": record.get("file"),
                "record": record.get("record", ""),
                "source_type": record.get("source_type", ""),
                "parse_status": record.get("parse_status", ""),
                "numeric_rows": record.get("numeric_row_count") or record.get("row_count") or 0,
                "energy_range_ev": xps_energy_range_label(ranges),
                "column_roles": record.get("column_roles") or {},
                "element_hints": record.get("element_hints") or [],
                "draft_fit_status": status,
                "draft_quality_grade": fit.get("quality_grade", ""),
                "draft_quality_flags": fit.get("quality_flags") or [],
                "backend_needed": "KherveFitting/lmfit-style nonlinear fitting backend with approved dependencies",
                "background_model_hint": "linear_endpoint_background_from_dependency_free_draft",
                "peak_model_hint": "Gaussian initial guesses only; choose final peak shapes manually before trusted fitting",
                "peak_guesses": peak_guesses,
                "blocking_reasons": sorted(set(reason for reason in blocking_reasons if reason)),
                "non_claim_boundary": "handoff_only_not_formal_fit_not_chemical_state_or_valence",
            }
        )
    return handoff


def write_xps_handoff_markdown(path: Path, handoff_rows: list[dict[str, Any]]) -> None:
    ready_count = sum(1 for row in handoff_rows if row.get("task_status") == "ready_for_backend_fit")
    lines = [
        "# XPS Fitting Handoff",
        "",
        "This file converts the dependency-free peak draft into backend-fitting preparation tasks. It is not a nonlinear fit result and must not be used as final chemical-state, valence, oxidation-state, or coordination evidence.",
        "",
        f"- Total XPS tasks: {len(handoff_rows)}",
        f"- Ready for a future approved backend fit: {ready_count}",
        f"- Not ready without more input/cleanup: {len(handoff_rows) - ready_count}",
        "",
        "| task_id | status | file | record | grade | peak_guesses | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in handoff_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(row.get("task_id", "")),
                    md_cell(row.get("task_status", "")),
                    md_cell(row.get("file", "")),
                    md_cell(row.get("record", "")),
                    md_cell(row.get("draft_quality_grade", "")),
                    md_cell(len(row.get("peak_guesses") or [])),
                    md_cell(row.get("blocking_reasons") or []),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## How to use",
            "",
            "- Use `peak_guesses` as initial values only after approving a real fitting backend and choosing background/peak-shape constraints.",
            "- Keep rows marked `not_ready_for_backend_fit` out of automated fitting until their blocking reasons are resolved.",
            "- Do not report final chemical-state or oxidation-state conclusions from this handoff file.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_xps_backend_fit_results(xps_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in xps_records:
        draft = record.get("xps_peak_fit") or {}
        backend_fit = draft.get("xps_backend_fit") or {
            "status": XPS_BACKEND_STATUS_NOT_ATTEMPTED,
            "backend": XPS_BACKEND_NOT_ATTEMPTED_METHOD,
            "reason": "no backend result present",
        }
        rows.append(
            {
                "task_id": safe_task_id(record.get("file"), record.get("record")),
                "file": record.get("file"),
                "record": record.get("record", ""),
                "source_type": record.get("source_type", ""),
                "parse_status": record.get("parse_status", ""),
                "element_hints": record.get("element_hints") or [],
                "region_hints": record.get("region_hints") or [],
                "draft_fit_status": draft.get("fit_status", draft.get("status", "")),
                "draft_quality_grade": draft.get("quality_grade", ""),
                "backend_status": backend_fit.get("status", ""),
                "backend": backend_fit.get("backend", XPS_BACKEND_NOT_ATTEMPTED_METHOD),
                "point_count": backend_fit.get("point_count"),
                "peak_count": backend_fit.get("peak_count", 0),
                "rmse": backend_fit.get("rmse"),
                "normalized_rmse": backend_fit.get("normalized_rmse"),
                "sse_improvement_fraction": backend_fit.get("sse_improvement_fraction"),
                "mean_abs_residual": backend_fit.get("mean_abs_residual"),
                "max_center_shift_ev": backend_fit.get("max_center_shift_ev"),
                "quality_category": backend_fit.get(
                    "quality_category",
                    XPS_BACKEND_QUALITY_SKIPPED
                    if backend_fit.get("status") == XPS_BACKEND_STATUS_NOT_ATTEMPTED
                    else XPS_BACKEND_QUALITY_REVIEW,
                ),
                "quality_label_zh": backend_fit.get(
                    "quality_label_zh",
                    "跳过" if backend_fit.get("status") == XPS_BACKEND_STATUS_NOT_ATTEMPTED else "需人工复核",
                ),
                "quality_reason": backend_fit.get("quality_reason", backend_fit.get("reason", "")),
                "diagnostics": backend_fit.get("diagnostics") or {},
                "quality_flags": backend_fit.get("quality_flags") or [],
                "reason": backend_fit.get("reason", ""),
                "fit_parameters": backend_fit.get("fit_parameters") or [],
                "non_claim_boundary": backend_fit.get(
                    "non_claim_boundary", "numerical_backend_fit_only_not_chemical_state_or_valence"
                ),
            }
        )
    return rows


def infer_xps_reference_region(row: dict[str, Any], peak_center_ev: float, ref: dict[str, Any]) -> tuple[str, str]:
    text = " ".join(
        str(part or "")
        for part in [
            row.get("record"),
            row.get("task_id"),
            row.get("file"),
            " ".join(str(item) for item in (row.get("region_hints") or [])),
            " ".join(str(item) for item in (row.get("element_hints") or [])),
        ]
    ).lower()
    element = str(ref.get("element", ""))
    region = str(ref.get("region", ""))
    element_seen = element.lower() in text
    region_token = region.lower().replace(" ", "")
    text_compact = re.sub(r"\s+", "", text)
    region_seen = region.lower() in text or region_token in text_compact
    if region_seen:
        return region, "record_or_file_region_hint_plus_binding_energy_window"
    if element_seen:
        return region, "element_hint_plus_binding_energy_window"
    return region, "binding_energy_window_only"


def xps_reference_assignment_confidence(row: dict[str, Any], evidence_basis: str, delta_ev: float) -> str:
    quality = str(row.get("quality_category") or "")
    flags = row.get("quality_flags") or []
    diagnostics = row.get("diagnostics") or {}
    lmfit_success = diagnostics.get("lmfit_success")
    has_region_hint = evidence_basis.startswith("record_or_file_region_hint")
    if quality == XPS_BACKEND_QUALITY_REFERENCE and lmfit_success is True and not flags and has_region_hint and delta_ev <= 0.25:
        return "medium_high"
    if quality in {XPS_BACKEND_QUALITY_REFERENCE, XPS_BACKEND_QUALITY_WEAK} and delta_ev <= 0.45:
        return "medium" if has_region_hint else "low_medium"
    return "low"


def build_xps_reference_assignments(backend_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    for row in backend_rows:
        if row.get("backend_status") != XPS_BACKEND_STATUS_SUCCEEDED:
            continue
        for peak in row.get("fit_parameters") or []:
            center = parse_float(peak.get("center_ev"))
            if center is None:
                continue
            for ref in XPS_REFERENCE_ASSIGNMENT_LIBRARY:
                energy_min = float(ref["energy_min_ev"])
                energy_max = float(ref["energy_max_ev"])
                if not energy_min <= center <= energy_max:
                    continue
                midpoint = (energy_min + energy_max) / 2.0
                delta_ev = abs(center - midpoint)
                inferred_region, basis_kind = infer_xps_reference_region(row, center, ref)
                confidence = xps_reference_assignment_confidence(row, basis_kind, delta_ev)
                assignments.append(
                    {
                        "task_id": row.get("task_id"),
                        "file": row.get("file"),
                        "record": row.get("record", ""),
                        "source": row.get("source") or row.get("task_id"),
                        "peak_id": peak.get("peak_id"),
                        "peak_center_ev": compact_number(center),
                        "fit_quality": row.get("quality_label_zh") or row.get("quality_category"),
                        "fit_quality_category": row.get("quality_category"),
                        "element": ref.get("element"),
                        "region": inferred_region,
                        "candidate_state": ref.get("candidate_state"),
                        "chemical_state_note": ref.get("chemical_state_note"),
                        "reference_window_ev": [compact_number(energy_min), compact_number(energy_max)],
                        "delta_from_window_midpoint_ev": compact_number(delta_ev),
                        "confidence": confidence,
                        "evidence_basis": f"{ref.get('basis')}; {basis_kind}; fit quality={row.get('quality_category')}",
                        "review_required": True,
                        "interpretation_boundary": (
                            "reference_candidate_only_not_final_valence_or_chemical_state_assignment"
                        ),
                    }
                )
    return assignments


def build_xps_reference_assignment_gaps(
    backend_rows: list[dict[str, Any]], assignments: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def classify_non_core_level_review(row: dict[str, Any], peak_centers: list[float]) -> dict[str, Any] | None:
        if not peak_centers:
            return None
        record_text = str(row.get("record") or "").strip().lower()
        has_vb_label = record_text == "vb" or record_text.startswith("vb ")
        low_be_window = min(peak_centers) >= -5.0 and max(peak_centers) <= 30.0 and len(peak_centers) >= 4
        if not (has_vb_label or low_be_window):
            return None
        basis = []
        if has_vb_label:
            basis.append("record_label=vb")
        if low_be_window:
            basis.append("peak_window<=30eV")
        return {
            "task_id": row.get("task_id"),
            "file": row.get("file"),
            "record": row.get("record", ""),
            "source": row.get("source") or row.get("task_id"),
            "element_hints": row.get("element_hints") or [],
            "fit_quality": row.get("quality_label_zh") or row.get("quality_category"),
            "fit_quality_category": row.get("quality_category"),
            "peak_count": len(peak_centers),
            "peak_centers_ev": [compact_number(center) for center in peak_centers[:12]],
            "classification": "non_core_level_review_only",
            "non_core_level_kind": "vb_or_low_binding_energy_window",
            "classification_basis": basis,
            "recommended_action": (
                "Review this row as a non-core-level / low-binding-energy window first; "
                "do not treat it as a missing core-level reference-library gap unless "
                "domain review shows the region label or energy scale is wrong."
            ),
            "review_required": True,
            "interpretation_boundary": (
                "non_core_level_review_only_not_final_valence_or_chemical_state_assignment"
            ),
        }

    assigned_task_ids = {str(row.get("task_id")) for row in assignments if row.get("task_id")}
    gaps: list[dict[str, Any]] = []
    non_core_level_reviews: list[dict[str, Any]] = []
    for row in backend_rows:
        if row.get("backend_status") != XPS_BACKEND_STATUS_SUCCEEDED:
            continue
        task_id = str(row.get("task_id") or "")
        if task_id in assigned_task_ids:
            continue
        peak_centers: list[float] = []
        for peak in row.get("fit_parameters") or []:
            center = parse_float(peak.get("center_ev"))
            if center is not None:
                peak_centers.append(center)
        non_core_level_review = classify_non_core_level_review(row, peak_centers)
        if non_core_level_review is not None:
            non_core_level_reviews.append(non_core_level_review)
            continue
        gaps.append(
            {
                "task_id": row.get("task_id"),
                "file": row.get("file"),
                "record": row.get("record", ""),
                "source": row.get("source") or row.get("task_id"),
                "element_hints": row.get("element_hints") or [],
                "fit_quality": row.get("quality_label_zh") or row.get("quality_category"),
                "fit_quality_category": row.get("quality_category"),
                "peak_count": len(peak_centers),
                "peak_centers_ev": [compact_number(center) for center in peak_centers[:12]],
                "gap_reason": (
                    "backend_fit_succeeded_but_no_peak_center_matched_current_reference_library_windows"
                ),
                "review_required": True,
                "recommended_action": (
                    "Review calibration, region labels, and expected chemistry; add a new "
                    "reference-library window only after domain review confirms the missing "
                    "element or chemical-state range."
                ),
                "interpretation_boundary": "reference_gap_only_not_absence_of_chemical_state_or_valence",
            }
        )
    return gaps, non_core_level_reviews


def write_xps_reference_assignments_markdown(path: Path, assignments: list[dict[str, Any]]) -> None:
    confidence_counts: dict[str, int] = {}
    for row in assignments:
        confidence = str(row.get("confidence", "unknown"))
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
    columns = [
        "file",
        "record",
        "peak_id",
        "peak_center_ev",
        "region",
        "candidate_state",
        "confidence",
        "fit_quality",
        "review_required",
    ]
    lines = [
        "# XPS Reference Valence/Chemical-State Candidates",
        "",
        "These rows are reference-library candidates from fitted peak centers and common binding-energy windows. They are not final chemical-state, oxidation-state, valence, coordination-number, or publication-grade assignments.",
        "",
        f"- Candidate rows: {len(assignments)}",
        f"- Confidence counts: {confidence_counts}",
        "- Review required: true for every row",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in assignments:
        lines.append("| " + " | ".join(md_cell(row.get(column, "")) for column in columns) + " |")
    lines.extend(
        [
            "",
            "## How to use",
            "",
            "- Treat `candidate_state` as a reference candidate for Codex/backend triage, not as a final scientific conclusion.",
            "- Use `confidence` to prioritize manual review; even `medium_high` still requires calibration and expert confirmation.",
            "- Inspect `evidence_basis` in the JSON file to see whether the match came from a region hint or only a binding-energy window.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xps_reference_gaps_markdown(path: Path, gaps: list[dict[str, Any]]) -> None:
    columns = [
        "file",
        "record",
        "fit_quality",
        "element_hints",
        "peak_count",
        "gap_reason",
        "review_required",
    ]
    lines = [
        "# XPS Reference Library Gaps",
        "",
        (
            "These rows identify backend-fitted XPS records that did not produce any "
            "reference-library valence/chemical-state candidate. A gap row is not evidence "
            "that a chemical state is absent; it only means the current small reference "
            "library did not match the fitted peak centers."
        ),
        "",
        f"- Gap rows: {len(gaps)}",
        "- Every gap is review-required before changing the reference library.",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in gaps:
        lines.append("| " + " | ".join(md_cell(row.get(column, "")) for column in columns) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xps_non_core_level_reviews_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "file",
        "record",
        "fit_quality",
        "peak_count",
        "non_core_level_kind",
        "classification_basis",
        "review_required",
    ]
    lines = [
        "# XPS Non-Core-Level Review Rows",
        "",
        (
            "These rows are review-only non-core-level or low-binding-energy windows that "
            "were intentionally separated from generic core-level reference-library gaps. "
            "They are not final valence, chemical-state, oxidation-state, or publication-grade claims."
        ),
        "",
        f"- Review-only non-core-level rows: {len(rows)}",
        "- Every row remains review-required before any scientific interpretation.",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_cell(row.get(column, "")) for column in columns) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xps_backend_probe_markdown(path: Path, probe: dict[str, Any]) -> None:
    modules = probe.get("python_modules") or {}
    external = probe.get("external_backend_candidates") or {}
    lines = [
        "# XPS Backend Probe",
        "",
        f"- Selected backend: `{probe.get('selected_backend', '')}`",
        f"- Selected backend available: {probe.get('selected_backend_available')}",
        f"- Scope: {probe.get('selected_backend_scope', '')}",
        "",
        "## Python modules",
        "",
        "| module | available |",
        "| --- | --- |",
    ]
    for name, available in sorted(modules.items()):
        lines.append(f"| {md_cell(name)} | {md_cell(available)} |")
    lines.extend(["", "## External backend candidates", "", "| backend | available | note |", "| --- | --- | --- |"])
    for name, info in sorted(external.items()):
        lines.append(f"| {md_cell(name)} | {md_cell(info.get('available'))} | {md_cell(info.get('note', ''))} |")
    lines.extend(
        [
            "",
            "This probe is not a fit result and does not support final chemical-state, valence, oxidation-state, or coordination claims.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xps_backend_fit_markdown(path: Path, backend_rows: list[dict[str, Any]]) -> None:
    success_count = sum(1 for row in backend_rows if row.get("backend_status") == XPS_BACKEND_STATUS_SUCCEEDED)
    category_counts: dict[str, int] = {}
    for row in backend_rows:
        category = str(row.get("quality_category", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1
    lines = [
        "# XPS Backend Fit Results",
        "",
        "These rows are numerical backend fit outputs where available. They are not final chemical-state, valence, oxidation-state, coordination-number, or publication-grade claims.",
        "",
        f"- Total XPS records: {len(backend_rows)}",
        f"- Backend fit succeeded: {success_count}",
        f"- Backend fit not succeeded: {len(backend_rows) - success_count}",
        f"- Quality categories: {category_counts}",
        "",
        "| task_id | backend_status | quality | record | peaks | normalized_rmse | flags/reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in backend_rows:
        flags_or_reason = row.get("quality_flags") or row.get("quality_reason") or row.get("reason", "")
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(row.get("task_id", "")),
                    md_cell(row.get("backend_status", "")),
                    md_cell(row.get("quality_label_zh", row.get("quality_category", ""))),
                    md_cell(row.get("record", "")),
                    md_cell(row.get("peak_count", 0)),
                    md_cell(row.get("normalized_rmse", "")),
                    md_cell(flags_or_reason),
                ]
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_manifest(files: list[Path], root: Path, records_by_file: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    manifest = []
    for path in files:
        name = rel(path, root)
        records = records_by_file.get(name, [])
        manifest.append(
            {
                "file": name,
                "size_bytes": path.stat().st_size,
                "modality": infer_modality(path),
                "suffix": path.suffix.lower() or "(none)",
                "record_count": len(records),
                "parse_statuses": sorted({str(row.get("parse_status")) for row in records}) if records else ["not_parsed"],
            }
        )
    return manifest


def aggregate(records: list[dict[str, Any]], qc: list[dict[str, Any]]) -> dict[str, Any]:
    xas = [r for r in records if r.get("modality") == "XAS"]
    xps = [r for r in records if r.get("modality") == "XPS"]
    vms_records = [r for r in xps if str(r.get("file", "")).lower().endswith(".vms")]
    vms_reconstructed = [
        r for r in vms_records if (r.get("vms_reconstruction") or {}).get("status") == "reconstructed"
    ]
    vms_unreconstructed = [r for r in vms_records if r not in vms_reconstructed]
    parsed_files = {r.get("file") for r in records if r.get("parse_status") == "parsed"}
    xas_ranges = [r.get("range_summary", {}) for r in xas if r.get("parse_status") == "parsed"]
    xps_ranges = [r.get("range_summary", {}) for r in xps if r.get("parse_status") == "parsed"]
    xps_fit_records = [r.get("xps_peak_fit") or {} for r in xps]
    xps_fitted_records = [fit for fit in xps_fit_records if fit.get("status") in {XPS_FIT_STATUS_DRAFT, XPS_FIT_STATUS_WEAK}]
    xps_unfitted_records = [fit for fit in xps_fit_records if fit.get("status") == XPS_FIT_STATUS_UNFITTED]
    xps_weak_fit_records = [fit for fit in xps_fit_records if fit.get("status") == XPS_FIT_STATUS_WEAK]
    xps_backend_records = [fit.get("xps_backend_fit") or {} for fit in xps_fit_records]
    xps_backend_success_records = [
        fit for fit in xps_backend_records if fit.get("status") == XPS_BACKEND_STATUS_SUCCEEDED
    ]
    xps_backend_not_attempted_records = [
        fit for fit in xps_backend_records if fit.get("status") == XPS_BACKEND_STATUS_NOT_ATTEMPTED
    ]
    xps_backend_failed_records = [
        fit for fit in xps_backend_records if fit.get("status") == XPS_BACKEND_STATUS_FAILED
    ]
    xps_backend_method_counts: dict[str, int] = {}
    for fit in xps_backend_records:
        backend = str(fit.get("backend") or "unknown")
        xps_backend_method_counts[backend] = xps_backend_method_counts.get(backend, 0) + 1
    dominant_backend_method = (
        max(xps_backend_method_counts.items(), key=lambda item: item[1])[0]
        if xps_backend_method_counts
        else XPS_BACKEND_METHOD
    )
    xps_backend_quality_counts: dict[str, int] = {}
    for fit in xps_backend_records:
        default_category = XPS_BACKEND_QUALITY_SKIPPED if fit.get("status") == XPS_BACKEND_STATUS_NOT_ATTEMPTED else "unknown"
        category = str(fit.get("quality_category", default_category))
        xps_backend_quality_counts[category] = xps_backend_quality_counts.get(category, 0) + 1
    xps_backend_diagnostics_coverage = (
        sum(1 for fit in xps_backend_success_records if fit.get("diagnostics")) / len(xps_backend_success_records)
        if xps_backend_success_records
        else 1.0
    )
    xps_backend_quality_category_coverage = (
        sum(
            1
            for fit in xps_backend_records
            if fit.get("quality_category") or fit.get("status") == XPS_BACKEND_STATUS_NOT_ATTEMPTED
        )
        / len(xps_backend_records)
        if xps_backend_records
        else 1.0
    )
    xps_fit_status_counts: dict[str, int] = {}
    xps_quality_grade_counts: dict[str, int] = {}
    for fit in xps_fit_records:
        status = str(fit.get("fit_status", fit.get("status", "unknown")))
        grade = str(fit.get("quality_grade", "unknown"))
        xps_fit_status_counts[status] = xps_fit_status_counts.get(status, 0) + 1
        xps_quality_grade_counts[grade] = xps_quality_grade_counts.get(grade, 0) + 1
    if xps_fitted_records and xps_unfitted_records:
        xps_fit_status = "部分拟合草案"
    elif xps_fitted_records:
        xps_fit_status = XPS_FIT_STATUS_WEAK if xps_weak_fit_records and len(xps_weak_fit_records) == len(xps_fitted_records) else XPS_FIT_STATUS_DRAFT
    else:
        xps_fit_status = XPS_FIT_STATUS_UNFITTED
    quality_grade_coverage = (
        sum(1 for fit in xps_fit_records if fit.get("quality_grade")) / len(xps_fit_records)
        if xps_fit_records
        else 1.0
    )
    weak_fit_flag_coverage = (
        sum(1 for fit in xps_weak_fit_records if fit.get("quality_flags")) / len(xps_weak_fit_records)
        if xps_weak_fit_records
        else 1.0
    )
    unfitted_reason_coverage = (
        sum(1 for fit in xps_unfitted_records if fit.get("unfitted_reason") or fit.get("reason")) / len(xps_unfitted_records)
        if xps_unfitted_records
        else 1.0
    )
    vms_unreconstructed_reason_coverage = (
        sum(
            1
            for r in vms_unreconstructed
            if (r.get("xps_peak_fit") or {}).get("unfitted_reason")
            or (r.get("xps_peak_fit") or {}).get("reason")
            or (r.get("vms_reconstruction") or {}).get("status")
        )
        / len(vms_unreconstructed)
        if vms_unreconstructed
        else 1.0
    )
    files_seen = len({r.get("file") for r in records})
    parsed_record_count = sum(1 for r in records if r.get("parse_status") == "parsed")
    return {
        "files_seen": files_seen,
        "files_parsed": len(parsed_files),
        "file_parse_success_rate": len(parsed_files) / files_seen if files_seen else 0.0,
        "record_parse_success_rate": parsed_record_count / len(records) if records else 0.0,
        "xas_records": len(xas),
        "xps_records": len(xps),
        "xas_files_parsed": len({r.get("file") for r in xas if r.get("parse_status") == "parsed"}),
        "xps_files_parsed": len({r.get("file") for r in xps if r.get("parse_status") == "parsed"}),
        "xas_total_rows": sum(int(r.get("row_count") or 0) for r in xas),
        "xps_numeric_rows": sum(
            int(r.get("numeric_row_count") or 0) for r in xps if r.get("source_type") == "xlsx_sheet"
        ),
        "xps_numeric_rows_total": sum(int(r.get("numeric_row_count") or 0) for r in xps),
        "qc_warning_count": sum(int(r.get("warning_count") or 0) for r in qc),
        "qc_error_count": sum(int(r.get("error_count") or 0) for r in qc),
        "xas_energy_range": {
            "min": min((r.get("energy_min") for r in xas_ranges if r.get("energy_min") is not None), default=None),
            "max": max((r.get("energy_max") for r in xas_ranges if r.get("energy_max") is not None), default=None),
        },
        "xps_axis_or_energy_range": {
            "min": min((r.get("axis_min", r.get("binding_energy_start_ev")) for r in xps_ranges if r.get("axis_min", r.get("binding_energy_start_ev")) is not None), default=None),
            "max": max((r.get("axis_max", r.get("binding_energy_end_ev")) for r in xps_ranges if r.get("axis_max", r.get("binding_energy_end_ev")) is not None), default=None),
        },
        "xps_fitting_status": xps_fit_status,
        "xps_fitted_records": len(xps_fitted_records),
        "xps_unfitted_records": len(xps_unfitted_records),
        "xps_weak_fit_records": len(xps_weak_fit_records),
        "xps_fit_status_counts": xps_fit_status_counts,
        "xps_quality_grade_counts": xps_quality_grade_counts,
        "xps_peak_count": sum(int(fit.get("peak_count") or 0) for fit in xps_fitted_records),
        "xps_fit_method": XPS_FIT_METHOD,
        "xps_backend_method": dominant_backend_method,
        "xps_backend_method_counts": xps_backend_method_counts,
        "xps_backend_fit_attempt_count": len(xps_backend_records) - len(xps_backend_not_attempted_records),
        "xps_backend_fit_success_count": len(xps_backend_success_records),
        "xps_backend_lmfit_success_count": sum(
            1 for fit in xps_backend_success_records if fit.get("backend") == XPS_BACKEND_LMFIT_METHOD
        ),
        "xps_backend_stdlib_success_count": sum(
            1 for fit in xps_backend_success_records if fit.get("backend") == XPS_BACKEND_STDLIB_METHOD
        ),
        "xps_backend_fit_failed_count": len(xps_backend_failed_records),
        "xps_backend_fit_not_attempted_count": len(xps_backend_not_attempted_records),
        "xps_backend_fit_result_count": len(xps_backend_records),
        "xps_backend_quality_category_counts": xps_backend_quality_counts,
        "xps_backend_quality_category_coverage": xps_backend_quality_category_coverage,
        "xps_backend_diagnostics_coverage": xps_backend_diagnostics_coverage,
        "xps_backend_reference_candidate_count": xps_backend_quality_counts.get(XPS_BACKEND_QUALITY_REFERENCE, 0),
        "xps_backend_weak_fit_count": xps_backend_quality_counts.get(XPS_BACKEND_QUALITY_WEAK, 0),
        "xps_backend_review_required_count": xps_backend_quality_counts.get(XPS_BACKEND_QUALITY_REVIEW, 0),
        "xps_backend_skipped_count": xps_backend_quality_counts.get(XPS_BACKEND_QUALITY_SKIPPED, 0),
        "xps_backend_missing_reason_coverage": (
            sum(1 for fit in xps_backend_not_attempted_records if fit.get("reason"))
            / len(xps_backend_not_attempted_records)
            if xps_backend_not_attempted_records
            else 1.0
        ),
        "vms_numeric_reconstruction_attempts": len(vms_records),
        "vms_numeric_reconstruction_successes": len(vms_reconstructed),
        "vms_unreconstructed_records": len(vms_unreconstructed),
        "vms_reconstructed_points": sum(int(r.get("numeric_row_count") or 0) for r in vms_reconstructed),
        "vms_unreconstructed_reason_coverage": vms_unreconstructed_reason_coverage,
        "quality_grade_coverage": quality_grade_coverage,
        "weak_fit_flag_coverage": weak_fit_flag_coverage,
        "unfitted_reason_coverage": unfitted_reason_coverage,
        "report_safety_check_passed": quality_grade_coverage == 1.0
        and weak_fit_flag_coverage == 1.0
        and unfitted_reason_coverage == 1.0
        and xps_backend_quality_category_coverage == 1.0
        and xps_backend_diagnostics_coverage == 1.0,
        "xas_modeling_status": "未建模",
    }


def limitations_text() -> str:
    return "\n".join(
        [
            "# Limitations",
            "",
            "- XPS: numeric workbook sheets receive a dependency-light peak-fit draft and, when an isolated fitting environment is used, a guarded lmfit Gaussian least-squares backend fit can be attempted.",
            "- XPS: supported REGULAR VAMAS/VMS numeric blocks are reconstructed into dependency-free peak-fit drafts; unsupported VMS layouts remain 未拟合 with a specific reason.",
            "- XPS: the selected backend is reported in `xps_backend_probe.*`; lmfit outputs are still numerical fits for triage/backend integration, not publication-grade chemical interpretation.",
            "- XPS: the fitting handoff file contains backend-preparation tasks and initial guesses; use `xps_backend_fit_results.*` for the actual numerical backend outputs where available.",
            "- XPS: `xps_reference_assignments.*` reports reference-library candidate valence/chemical-state matches from fitted peak centers and common binding-energy windows; every row remains 需人工确认.",
            "- XAS: 未建模。This run did not perform XANES linear-combination fitting, EXAFS fitting, coordination-number estimation, or valence assignment.",
            "- No final valence, chemical state, oxidation state, or coordination conclusion is made from the peak-fit draft or reference-candidate table.",
            "- Publication-grade or chemistry-claim-bearing XPS fitting still requires explicit background choice, constraints, backend provenance, and human review.",
            "",
        ]
    )


def next_steps_text() -> str:
    return "\n".join(
        [
            "# Next Steps",
            "",
            "1. Review `qc.md` and fix any parse errors or warning-heavy files.",
            "2. Review `xps_peak_fits.md` and use the centers/FWHM/area proxies only as a fitting draft, not as chemical-state evidence.",
            "3. Review `xps_backend_probe.md/json` to see which backend was used and whether lmfit/KherveFitting prerequisites were available.",
            "4. Review `xps_backend_fit_results.md/json` for real numerical backend fit outputs, failed fits, and quality flags.",
            "5. Review `xps_reference_assignments.md/json` for reference valence/chemical-state candidates; keep them as review-required hypotheses, not final assignments.",
            "6. For stronger XPS fitting, provide explicit background model, calibration reference, and peak constraints before treating any lmfit/KherveFitting-style numeric result as more than a diagnostic fit.",
            "7. XAS modeling remains deferred for this pass; only after a separate approved XAS backend run should the agent report valence or coordination-number conclusions.",
            "",
        ]
    )


def summary_text(input_path: Path, output_dir: Path, aggs: dict[str, Any], manifest: list[dict[str, Any]], qc: list[dict[str, Any]]) -> str:
    lines = [
        "# XPS/XAS Agent Summary",
        "",
        f"Input: `{input_path}`",
        f"Output: `{output_dir}`",
        "",
        "## Can it run?",
        "",
        "Yes. This dependency-free run parsed local files and generated a report bundle.",
        "",
        "## File recognition",
        "",
        f"- Files seen: {aggs['files_seen']}",
        f"- Files parsed: {aggs['files_parsed']}",
        f"- File parse success rate: {aggs['file_parse_success_rate']}",
        f"- Record parse success rate: {aggs['record_parse_success_rate']}",
        f"- XAS parsed files: {aggs['xas_files_parsed']}",
        f"- XPS parsed files: {aggs['xps_files_parsed']}",
        "",
        "## Data range summary",
        "",
        f"- XAS energy range: {aggs['xas_energy_range']}",
        f"- XPS axis/energy range: {aggs['xps_axis_or_energy_range']}",
        f"- XAS numeric rows: {aggs['xas_total_rows']}",
        f"- XPS numeric rows: {aggs['xps_numeric_rows']}",
        f"- XPS numeric rows including reconstructed VMS blocks: {aggs['xps_numeric_rows_total']}",
        f"- XPS fitted records: {aggs['xps_fitted_records']}",
        f"- XPS weak draft records: {aggs['xps_weak_fit_records']}",
        f"- XPS unfitted records: {aggs['xps_unfitted_records']}",
        f"- XPS fitted peak proxies: {aggs['xps_peak_count']}",
        f"- VMS numeric reconstruction: {aggs['vms_numeric_reconstruction_successes']} / {aggs['vms_numeric_reconstruction_attempts']}",
        f"- VMS reconstructed points: {aggs['vms_reconstructed_points']}",
        "",
        "## QC",
        "",
        f"- QC warnings: {aggs['qc_warning_count']}",
        f"- QC errors: {aggs['qc_error_count']}",
        "",
        "## Safety status",
        "",
        f"- XPS fitting status: {aggs['xps_fitting_status']} ({aggs['xps_fit_method']})",
        f"- XPS fit status counts: {aggs['xps_fit_status_counts']}",
        f"- XPS quality grade counts: {aggs['xps_quality_grade_counts']}",
        f"- Quality grade coverage: {aggs['quality_grade_coverage']}",
        f"- Weak-fit flag coverage: {aggs['weak_fit_flag_coverage']}",
        f"- Unfitted reason coverage: {aggs['unfitted_reason_coverage']}",
        f"- XPS evidence rows: {aggs.get('xps_evidence_row_count', 0)}",
        f"- XPS evidence reason coverage: {aggs.get('xps_evidence_reason_coverage', 0)}",
        f"- XPS fitting handoff tasks: {aggs.get('xps_fitting_handoff_task_count', 0)}",
        f"- XPS fitting handoff ready tasks: {aggs.get('xps_fitting_handoff_ready_count', 0)}",
        f"- XPS backend method: {aggs.get('xps_backend_method', '')}",
        f"- XPS backend fit attempts: {aggs.get('xps_backend_fit_attempt_count', 0)}",
        f"- XPS backend fit successes: {aggs.get('xps_backend_fit_success_count', 0)}",
        f"- XPS backend fit failures: {aggs.get('xps_backend_fit_failed_count', 0)}",
        f"- XPS backend fit not attempted: {aggs.get('xps_backend_fit_not_attempted_count', 0)}",
        f"- XPS backend quality categories: {aggs.get('xps_backend_quality_category_counts', {})}",
        f"- XPS backend diagnostics coverage: {aggs.get('xps_backend_diagnostics_coverage', 0)}",
        f"- XPS reference valence/chemical-state candidate rows: {aggs.get('xps_reference_assignment_count', 0)}",
        f"- XPS reference assignment confidence counts: {aggs.get('xps_reference_assignment_confidence_counts', {})}",
        f"- VMS unreconstructed reason coverage: {aggs['vms_unreconstructed_reason_coverage']}",
        f"- Report safety check passed: {aggs['report_safety_check_passed']}",
        "- XAS modeling status: 未建模",
        "- XPS reference assignments are review-required candidates only; no final valence, chemical-state, oxidation-state, or coordination-number conclusion is made.",
        "",
        "## Main outputs",
        "",
        "- `summary.md`: this human-readable summary",
        "- `results.json`: machine-readable complete results",
        "- `file_manifest.json` / `file_manifest.md`: file list and recognition status",
        "- `qc.json` / `qc.md`: QC findings",
        "- `limitations.md`: unsupported claims and current limits",
        "- `next_steps.md`: fitting/modeling preparation checklist",
        "- `xps_peak_fits.json` and `xps_peak_fits.md`: dependency-free XPS peak-fit draft where numeric XPS records are available",
        "- `xps_evidence_table.json` and `xps_evidence_table.md`: per-region XPS evidence, quality reason, and non-claim boundary table",
        "- `xps_fitting_handoff.json` and `xps_fitting_handoff.md`: backend-fitting preparation tasks and initial guesses only",
        "- `xps_backend_probe.json` and `xps_backend_probe.md`: backend availability probe and selected backend explanation",
        "- `xps_backend_fit_results.json` and `xps_backend_fit_results.md`: real numerical backend fit outputs and failures",
        "- `xps_reference_assignments.json` and `xps_reference_assignments.md`: review-required XPS reference valence/chemical-state candidates",
        "- `parsed/xas_records.csv` and `parsed/xps_records.csv`: parsed record summaries",
        "",
        "## Files",
        "",
    ]
    for item in manifest[:20]:
        lines.append(f"- `{item['file']}`: {item['modality']}, {','.join(item['parse_statuses'])}")
    if len(manifest) > 20:
        lines.append(f"- ... plus {len(manifest) - 20} more files")
    if qc:
        lines.extend(["", "## First QC findings", ""])
        shown = 0
        for row in qc:
            for finding in row.get("findings", []):
                lines.append(f"- `{row['file']}` {finding['severity']}: {finding['message']}")
                shown += 1
                if shown >= 10:
                    break
            if shown >= 10:
                break
        if shown == 0:
            lines.append("- No QC findings.")
    return "\n".join(lines) + "\n"


def run(input_path: Path, output_dir: Path) -> dict[str, Any]:
    root = common_root(input_path.resolve())
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir = output_dir / "parsed"
    files = discover_files(input_path.resolve())
    records: list[dict[str, Any]] = []
    representative: dict[str, str] = {}
    for path in files:
        parsed, series = parse_file(path, root)
        records.extend(parsed)
        if series and parsed:
            representative.setdefault(parsed[0].get("modality", "unknown"), parsed[0].get("file", ""))
    records_by_file: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_file.setdefault(str(record.get("file")), []).append(record)
    manifest = build_manifest(files, root, records_by_file)
    qc = [qc_record(record) for record in records]
    aggs = aggregate(records, qc)

    xas_records = [r for r in records if r.get("modality") == "XAS"]
    xps_records = [r for r in records if r.get("modality") == "XPS"]
    xps_peak_fits = [
        {
            "file": r.get("file"),
            "record": r.get("record", ""),
            "fit": r.get("xps_peak_fit") or {},
        }
        for r in xps_records
    ]
    xps_evidence_rows = build_xps_evidence_rows(xps_records)
    xps_fitting_handoff = build_xps_fitting_handoff(xps_records)
    xps_backend_probe = probe_xps_backends()
    xps_backend_fit_results = build_xps_backend_fit_results(xps_records)
    xps_reference_assignments = build_xps_reference_assignments(xps_backend_fit_results)
    xps_reference_gaps, xps_non_core_level_reviews = build_xps_reference_assignment_gaps(
        xps_backend_fit_results, xps_reference_assignments
    )
    reference_confidence_counts: dict[str, int] = {}
    for row in xps_reference_assignments:
        confidence = str(row.get("confidence", "unknown"))
        reference_confidence_counts[confidence] = reference_confidence_counts.get(confidence, 0) + 1
    reference_element_counts: dict[str, int] = {}
    for row in xps_reference_assignments:
        element = str(row.get("element", "unknown"))
        reference_element_counts[element] = reference_element_counts.get(element, 0) + 1
    aggs["xps_reference_assignment_count"] = len(xps_reference_assignments)
    aggs["xps_reference_assignment_confidence_counts"] = reference_confidence_counts
    aggs["xps_reference_assignment_element_counts"] = reference_element_counts
    aggs["xps_reference_assignment_review_required_count"] = sum(
        1 for row in xps_reference_assignments if row.get("review_required")
    )
    aggs["xps_reference_gap_count"] = len(xps_reference_gaps)
    aggs["xps_reference_gap_review_required_count"] = sum(
        1 for row in xps_reference_gaps if row.get("review_required")
    )
    aggs["xps_non_core_level_review_count"] = len(xps_non_core_level_reviews)
    aggs["xps_non_core_level_review_required_count"] = sum(
        1 for row in xps_non_core_level_reviews if row.get("review_required")
    )
    aggs["xps_reference_gap_coverage"] = (
        (aggs["xps_backend_fit_success_count"] - aggs["xps_reference_gap_count"])
        / aggs["xps_backend_fit_success_count"]
        if aggs["xps_backend_fit_success_count"]
        else 1.0
    )
    aggs["xps_evidence_row_count"] = len(xps_evidence_rows)
    aggs["xps_evidence_reason_coverage"] = (
        sum(1 for row in xps_evidence_rows if row.get("reason")) / len(xps_evidence_rows)
        if xps_evidence_rows
        else 1.0
    )
    aggs["xps_fitting_handoff_task_count"] = len(xps_fitting_handoff)
    aggs["xps_fitting_handoff_ready_count"] = sum(
        1 for row in xps_fitting_handoff if row.get("task_status") == "ready_for_backend_fit"
    )
    aggs["xps_fitting_handoff_blocked_count"] = (
        aggs["xps_fitting_handoff_task_count"] - aggs["xps_fitting_handoff_ready_count"]
    )
    write_csv(parsed_dir / "xas_records.csv", xas_records)
    write_csv(parsed_dir / "xps_records.csv", xps_records)
    write_json(output_dir / "file_manifest.json", manifest)
    write_json(output_dir / "qc.json", qc)
    write_json(output_dir / "xps_peak_fits.json", xps_peak_fits)
    write_json(output_dir / "xps_evidence_table.json", xps_evidence_rows)
    write_json(output_dir / "xps_fitting_handoff.json", xps_fitting_handoff)
    write_json(output_dir / "xps_backend_probe.json", xps_backend_probe)
    write_json(output_dir / "xps_backend_fit_results.json", xps_backend_fit_results)
    write_json(output_dir / "xps_reference_assignments.json", xps_reference_assignments)
    write_json(output_dir / "xps_reference_gaps.json", xps_reference_gaps)
    write_json(output_dir / "xps_non_core_level_reviews.json", xps_non_core_level_reviews)
    write_xps_fit_markdown(output_dir / "xps_peak_fits.md", xps_peak_fits)
    write_xps_evidence_markdown(output_dir / "xps_evidence_table.md", xps_evidence_rows)
    write_xps_handoff_markdown(output_dir / "xps_fitting_handoff.md", xps_fitting_handoff)
    write_xps_backend_probe_markdown(output_dir / "xps_backend_probe.md", xps_backend_probe)
    write_xps_backend_fit_markdown(output_dir / "xps_backend_fit_results.md", xps_backend_fit_results)
    write_xps_reference_assignments_markdown(output_dir / "xps_reference_assignments.md", xps_reference_assignments)
    write_xps_reference_gaps_markdown(output_dir / "xps_reference_gaps.md", xps_reference_gaps)
    write_xps_non_core_level_reviews_markdown(
        output_dir / "xps_non_core_level_reviews.md", xps_non_core_level_reviews
    )
    write_markdown_table(output_dir / "file_manifest.md", "File Manifest", manifest, ["file", "modality", "suffix", "record_count", "parse_statuses"])
    qc_rows = [
        {
            "file": row["file"],
            "record": row.get("record", ""),
            "modality": row["modality"],
            "warnings": row["warning_count"],
            "errors": row["error_count"],
        }
        for row in qc
    ]
    write_markdown_table(output_dir / "qc.md", "QC Findings", qc_rows, ["file", "record", "modality", "warnings", "errors"])
    (output_dir / "limitations.md").write_text(limitations_text(), encoding="utf-8")
    (output_dir / "next_steps.md").write_text(next_steps_text(), encoding="utf-8")

    results = {
        "run_id": RUN_ID,
        "generated_at": now_iso(),
        "input": str(input_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "aggregates": aggs,
        "records": records,
        "file_manifest": manifest,
        "qc": qc,
        "xps_evidence_table": xps_evidence_rows,
        "xps_fitting_handoff": xps_fitting_handoff,
        "xps_backend_probe": xps_backend_probe,
        "xps_backend_fit_results": xps_backend_fit_results,
        "xps_reference_assignments": xps_reference_assignments,
        "xps_reference_gaps": xps_reference_gaps,
        "xps_non_core_level_reviews": xps_non_core_level_reviews,
        "safety": {
            "xps_fitting_status": aggs["xps_fitting_status"],
            "xps_fit_method": XPS_FIT_METHOD,
            "xps_backend_method": aggs.get("xps_backend_method", XPS_BACKEND_METHOD),
            "xps_backend_method_counts": aggs.get("xps_backend_method_counts", {}),
            "xps_backend_selected": xps_backend_probe.get("selected_backend"),
            "xps_backend_selected_available": xps_backend_probe.get("selected_backend_available"),
            "xps_backend_fit_success_count": aggs["xps_backend_fit_success_count"],
            "xps_reference_assignment_count": aggs["xps_reference_assignment_count"],
            "xps_reference_gap_count": aggs["xps_reference_gap_count"],
            "xps_non_core_level_review_count": aggs["xps_non_core_level_review_count"],
            "xps_reference_assignment_boundary": "review_required_reference_candidates_not_final_claims",
            "xps_backend_non_claim_boundary": "numerical_backend_fit_only_not_final_chemical_state_or_valence",
            "xps_non_core_level_review_boundary": (
                "review_only_non_core_level_rows_not_final_valence_or_chemical_state_claims"
            ),
            "xps_fit_status_counts": aggs["xps_fit_status_counts"],
            "xps_quality_grade_counts": aggs["xps_quality_grade_counts"],
            "quality_grade_coverage": aggs["quality_grade_coverage"],
            "weak_fit_flag_coverage": aggs["weak_fit_flag_coverage"],
            "unfitted_reason_coverage": aggs["unfitted_reason_coverage"],
            "report_safety_check_passed": aggs["report_safety_check_passed"],
            "xas_modeling_status": "未建模",
            "unsupported_claims_rejected": [
                "final_valence",
                "final_chemical_state",
                "final_oxidation_state",
                "coordination_number",
                "final_chemical_state_from_peak_fit",
            ],
        },
        "representative_sources": representative,
        "outputs": {
            "summary_md": str((output_dir / "summary.md").resolve()),
            "results_json": str((output_dir / "results.json").resolve()),
            "file_manifest_json": str((output_dir / "file_manifest.json").resolve()),
            "file_manifest_md": str((output_dir / "file_manifest.md").resolve()),
            "qc_json": str((output_dir / "qc.json").resolve()),
            "qc_md": str((output_dir / "qc.md").resolve()),
            "xps_peak_fits_json": str((output_dir / "xps_peak_fits.json").resolve()),
            "xps_peak_fits_md": str((output_dir / "xps_peak_fits.md").resolve()),
            "xps_evidence_table_json": str((output_dir / "xps_evidence_table.json").resolve()),
            "xps_evidence_table_md": str((output_dir / "xps_evidence_table.md").resolve()),
            "xps_fitting_handoff_json": str((output_dir / "xps_fitting_handoff.json").resolve()),
            "xps_fitting_handoff_md": str((output_dir / "xps_fitting_handoff.md").resolve()),
            "xps_backend_probe_json": str((output_dir / "xps_backend_probe.json").resolve()),
            "xps_backend_probe_md": str((output_dir / "xps_backend_probe.md").resolve()),
            "xps_backend_fit_results_json": str((output_dir / "xps_backend_fit_results.json").resolve()),
            "xps_backend_fit_results_md": str((output_dir / "xps_backend_fit_results.md").resolve()),
            "xps_reference_assignments_json": str((output_dir / "xps_reference_assignments.json").resolve()),
            "xps_reference_assignments_md": str((output_dir / "xps_reference_assignments.md").resolve()),
            "xps_reference_gaps_json": str((output_dir / "xps_reference_gaps.json").resolve()),
            "xps_reference_gaps_md": str((output_dir / "xps_reference_gaps.md").resolve()),
            "xps_non_core_level_reviews_json": str((output_dir / "xps_non_core_level_reviews.json").resolve()),
            "xps_non_core_level_reviews_md": str((output_dir / "xps_non_core_level_reviews.md").resolve()),
            "limitations_md": str((output_dir / "limitations.md").resolve()),
            "next_steps_md": str((output_dir / "next_steps.md").resolve()),
            "parsed_xas_csv": str((parsed_dir / "xas_records.csv").resolve()),
            "parsed_xps_csv": str((parsed_dir / "xps_records.csv").resolve()),
        },
    }
    write_json(output_dir / "results.json", results)
    (output_dir / "summary.md").write_text(summary_text(input_path.resolve(), output_dir.resolve(), aggs, manifest, qc), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a dependency-free XPS/XAS report bundle from a local file or folder.")
    parser.add_argument("--input", type=Path, required=True, help="Local XPS/XAS file or directory.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/xas_xps_agent_mvp_v1"),
        help="Output directory for the report bundle. Defaults to outputs/xas_xps_agent_mvp_v1.",
    )
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input does not exist: {args.input}")
    results = run(args.input, args.output)
    print(json.dumps({"ok": True, "output_dir": results["output_dir"], "aggregates": results["aggregates"]}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
