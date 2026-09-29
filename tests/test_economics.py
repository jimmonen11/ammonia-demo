from __future__ import annotations

import pytest

from ammonia_teaching.economics import (
    calculate_economics,
    compressor_power_kw,
)
from ammonia_teaching.model import HOURS_PER_YEAR, ScenarioInputs, solve_process


def test_capital_is_spread_evenly_over_plant_life():
    inputs = ScenarioInputs(plant_life_years=25)
    economics = calculate_economics(inputs, solve_process(inputs))

    assert economics.annual_costs_usd["Annualized capital"] == pytest.approx(
        economics.total_installed_capital_usd / 25.0
    )


def test_recycle_compressor_only_restores_loop_pressure_drop():
    inputs = ScenarioInputs()
    process = solve_process(inputs)
    economics = calculate_economics(inputs, process)
    expected = compressor_power_kw(
        process.streams["recycle_gas"].total_kmol_h,
        inputs.loop_pressure_bar - inputs.loop_pressure_drop_bar,
        inputs.loop_pressure_bar,
        inputs.compressor_efficiency,
        inputs.compressor_inlet_temperature_k,
        inputs.heat_capacity_ratio,
    )

    assert economics.recycle_compressor_power_kw == pytest.approx(expected)


def test_once_through_case_has_no_recycle_compressor_cost_or_capital():
    inputs = ScenarioInputs(purge_fraction=1.0)
    economics = calculate_economics(inputs, solve_process(inputs))

    assert economics.recycle_compressor_power_kw == pytest.approx(0.0)
    assert economics.installed_capital_usd["Recycle compressor"] == pytest.approx(0.0)


def test_cost_breakdown_is_complete_and_sums_without_cooling_double_count():
    inputs = ScenarioInputs()
    economics = calculate_economics(inputs, solve_process(inputs))

    assert set(economics.annual_costs_usd) == {
        "Purchased H2",
        "Purchased N2",
        "Compressor electricity",
        "Cooling / refrigeration",
        "Annualized capital",
    }
    assert economics.total_cost_per_tonne_usd == pytest.approx(
        economics.total_annual_cost_usd / inputs.annual_production_tonnes
    )
    expected_compressor_electricity = (
        economics.fresh_compressor_power_kw + economics.recycle_compressor_power_kw
    ) * HOURS_PER_YEAR * inputs.electricity_price_per_kwh
    assert economics.annual_costs_usd["Compressor electricity"] == pytest.approx(
        expected_compressor_electricity
    )
    assert economics.annual_costs_usd["Cooling / refrigeration"] == pytest.approx(
        economics.refrigeration_electricity_kwh_per_year * inputs.electricity_price_per_kwh
    )
