"""One-variable sensitivity sweeps for the teaching interface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

import pandas as pd

from .economics import calculate_economics
from .model import InfeasibleScenarioError, MOLECULAR_WEIGHTS, ScenarioInputs, solve_process


@dataclass(frozen=True)
class SensitivityResults:
    input_field: str
    data: pd.DataFrame


def _evaluate(inputs: ScenarioInputs, value: float) -> dict[str, object]:
    try:
        process = solve_process(inputs)
        economics = calculate_economics(inputs, process)
    except (InfeasibleScenarioError, ValueError) as exc:
        return {
            "input_value": value,
            "valid": False,
            "message": str(exc),
            "cost_usd_per_tonne": float("nan"),
            "fresh_h2_kg_per_tonne": float("nan"),
            "fresh_n2_kg_per_tonne": float("nan"),
            "h2_loss_kg_h": float("nan"),
            "recycle_kmol_h": float("nan"),
            "recycle_to_fresh_ratio": float("nan"),
            "reactor_inlet_argon_mol_pct": float("nan"),
            "compressor_power_kw": float("nan"),
            "installed_capital_musd": float("nan"),
        }
    product_t_h = process.production_kmol_h * MOLECULAR_WEIGHTS["NH3"] / 1_000.0
    return {
        "input_value": value,
        "valid": True,
        "message": "",
        "cost_usd_per_tonne": economics.total_cost_per_tonne_usd,
        "fresh_h2_kg_per_tonne": process.fresh_hydrogen_kg_h / product_t_h,
        "fresh_n2_kg_per_tonne": process.fresh_nitrogen_kg_h / product_t_h,
        "h2_loss_kg_h": process.purge_hydrogen_kg_h,
        "recycle_kmol_h": process.streams["recycle_gas"].total_kmol_h,
        "recycle_to_fresh_ratio": process.recycle_to_fresh_ratio,
        "reactor_inlet_argon_mol_pct": 100.0 * process.reactor_inlet_argon_fraction,
        "compressor_power_kw": (
            economics.fresh_compressor_power_kw + economics.recycle_compressor_power_kw
        ),
        "installed_capital_musd": economics.total_installed_capital_usd / 1_000_000.0,
    }


def run_sensitivity(
    base_inputs: ScenarioInputs,
    input_field: str,
    input_grid: Iterable[float],
) -> SensitivityResults:
    """Sweep one ScenarioInputs field while holding every other input fixed."""

    if input_field not in ScenarioInputs.__dataclass_fields__:
        raise ValueError(f"Unknown sensitivity input: {input_field}")
    rows = [
        _evaluate(replace(base_inputs, **{input_field: float(value)}), float(value))
        for value in input_grid
    ]
    return SensitivityResults(
        input_field=input_field,
        data=pd.DataFrame(rows),
    )
