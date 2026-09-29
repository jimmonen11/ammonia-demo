from __future__ import annotations

import pytest

from ammonia_teaching.model import ScenarioInputs
from ammonia_teaching.sensitivity import run_sensitivity


def test_general_sensitivity_sweeps_selected_input_and_reports_key_outputs():
    results = run_sensitivity(
        ScenarioInputs(),
        input_field="hydrogen_price_per_kg",
        input_grid=[1.0, 2.0, 3.0],
    )

    assert results.input_field == "hydrogen_price_per_kg"
    assert results.data["input_value"].tolist() == [1.0, 2.0, 3.0]
    assert results.data["cost_usd_per_tonne"].is_monotonic_increasing
    assert results.data["recycle_kmol_h"].nunique() == 1
    assert {
        "fresh_h2_kg_per_tonne",
        "fresh_n2_kg_per_tonne",
        "h2_loss_kg_h",
        "recycle_to_fresh_ratio",
        "reactor_inlet_argon_mol_pct",
        "compressor_power_kw",
        "installed_capital_musd",
    }.issubset(results.data.columns)


def test_general_sensitivity_rejects_unknown_input_field():
    with pytest.raises(ValueError, match="Unknown sensitivity input"):
        run_sensitivity(ScenarioInputs(), "not_a_real_input", [1.0])
