"""Transparent screening-level economics for the ammonia-loop model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .model import HOURS_PER_YEAR, MOLECULAR_WEIGHTS, ProcessResults, ScenarioInputs


R_KJ_PER_KMOL_K = 8.314462618


@dataclass(frozen=True)
class EconomicResults:
    annual_costs_usd: Mapping[str, float]
    costs_per_tonne_usd: Mapping[str, float]
    installed_capital_usd: Mapping[str, float]
    fresh_compressor_power_kw: float
    recycle_compressor_power_kw: float
    cooling_duty_kwh_th_per_year: float
    refrigeration_electricity_kwh_per_year: float

    @property
    def total_annual_cost_usd(self) -> float:
        return sum(self.annual_costs_usd.values())

    @property
    def total_cost_per_tonne_usd(self) -> float:
        return sum(self.costs_per_tonne_usd.values())

    @property
    def total_installed_capital_usd(self) -> float:
        return sum(self.installed_capital_usd.values())


def compressor_power_kw(
    molar_flow_kmol_h: float,
    inlet_pressure_bar: float,
    outlet_pressure_bar: float,
    efficiency: float,
    inlet_temperature_k: float,
    heat_capacity_ratio: float,
) -> float:
    """Ideal-gas adiabatic compressor shaft power in kW.

    This screening equation assumes a constant heat-capacity ratio, constant
    isentropic efficiency, no intercooling, and no mechanical-drive losses.
    """

    if molar_flow_kmol_h <= 0.0 or outlet_pressure_bar == inlet_pressure_bar:
        return 0.0
    if inlet_pressure_bar <= 0.0 or outlet_pressure_bar < inlet_pressure_bar:
        raise ValueError("Compressor outlet pressure must be at least the positive inlet pressure.")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("Compressor efficiency must be greater than 0 and at most 1.")
    if inlet_temperature_k <= 0.0:
        raise ValueError("Compressor inlet temperature must be positive.")
    if heat_capacity_ratio <= 1.0:
        raise ValueError("Heat-capacity ratio must be greater than 1.")

    exponent = (heat_capacity_ratio - 1.0) / heat_capacity_ratio
    specific_work_kj_per_kmol = (
        heat_capacity_ratio
        / (heat_capacity_ratio - 1.0)
        * R_KJ_PER_KMOL_K
        * inlet_temperature_k
        * ((outlet_pressure_bar / inlet_pressure_bar) ** exponent - 1.0)
        / efficiency
    )
    return molar_flow_kmol_h * specific_work_kj_per_kmol / 3_600.0


def _scaled_cost_usd(reference_cost_musd: float, size: float, reference_size: float, exponent: float) -> float:
    if reference_cost_musd < 0.0:
        raise ValueError("Reference equipment costs cannot be negative.")
    if size <= 0.0:
        return 0.0
    if reference_size <= 0.0:
        raise ValueError("Reference equipment sizes must be positive.")
    if exponent <= 0.0:
        raise ValueError("Equipment scaling exponents must be positive.")
    return reference_cost_musd * 1_000_000.0 * (size / reference_size) ** exponent


def calculate_economics(inputs: ScenarioInputs, process: ProcessResults) -> EconomicResults:
    """Calculate annualized plant-gate cost for separated ammonia product."""

    if inputs.electricity_price_per_kwh < 0.0:
        raise ValueError("Electricity price cannot be negative.")
    if inputs.refrigeration_cop <= 0.0:
        raise ValueError("Refrigeration COP must be positive.")
    if inputs.cooling_duty_kwh_th_per_kg_nh3 < 0.0:
        raise ValueError("Cooling duty cannot be negative.")
    if inputs.plant_life_years <= 0:
        raise ValueError("Plant life must be positive.")
    if inputs.loop_pressure_drop_bar < 0.0:
        raise ValueError("Loop pressure drop cannot be negative.")
    recycle_inlet_pressure = inputs.loop_pressure_bar - inputs.loop_pressure_drop_bar
    if recycle_inlet_pressure <= 0.0:
        raise ValueError("Loop pressure drop must be smaller than loop pressure.")

    fresh_power = compressor_power_kw(
        process.streams["fresh_feed"].total_kmol_h,
        inputs.fresh_feed_pressure_bar,
        inputs.loop_pressure_bar,
        inputs.compressor_efficiency,
        inputs.compressor_inlet_temperature_k,
        inputs.heat_capacity_ratio,
    )
    recycle_power = compressor_power_kw(
        process.streams["recycle_gas"].total_kmol_h,
        recycle_inlet_pressure,
        inputs.loop_pressure_bar,
        inputs.compressor_efficiency,
        inputs.compressor_inlet_temperature_k,
        inputs.heat_capacity_ratio,
    )

    product_kg_h = process.production_kmol_h * MOLECULAR_WEIGHTS["NH3"]
    annual_product_kg = product_kg_h * HOURS_PER_YEAR
    cooling_duty = annual_product_kg * inputs.cooling_duty_kwh_th_per_kg_nh3
    refrigeration_electricity = cooling_duty / inputs.refrigeration_cop

    installed_capital = {
        "Fresh-feed compressor": _scaled_cost_usd(
            inputs.fresh_compressor_ref_cost_musd,
            fresh_power,
            inputs.fresh_compressor_ref_size_kw,
            inputs.fresh_compressor_exponent,
        ),
        "Recycle compressor": _scaled_cost_usd(
            inputs.recycle_compressor_ref_cost_musd,
            recycle_power,
            inputs.recycle_compressor_ref_size_kw,
            inputs.recycle_compressor_exponent,
        ),
        "Reactor loop": _scaled_cost_usd(
            inputs.reactor_loop_ref_cost_musd,
            process.streams["reactor_feed"].total_kmol_h,
            inputs.reactor_loop_ref_size_kmol_h,
            inputs.reactor_loop_exponent,
        ),
        "Cooler and gas separator": _scaled_cost_usd(
            inputs.cooler_separator_ref_cost_musd,
            process.streams["reactor_effluent"].total_kmol_h,
            inputs.cooler_separator_ref_size_kmol_h,
            inputs.cooler_separator_exponent,
        ),
        "Ammonia separator": _scaled_cost_usd(
            inputs.ammonia_separator_ref_cost_musd,
            product_kg_h,
            inputs.ammonia_separator_ref_size_kg_h,
            inputs.ammonia_separator_exponent,
        ),
    }

    total_capital = sum(installed_capital.values())
    annual_h2 = (
        process.streams["fresh_feed"].component("H2")
        * MOLECULAR_WEIGHTS["H2"]
        * HOURS_PER_YEAR
        * inputs.hydrogen_price_per_kg
    )
    annual_n2 = (
        process.streams["fresh_feed"].component("N2")
        * MOLECULAR_WEIGHTS["N2"]
        * HOURS_PER_YEAR
        / 1_000.0
        * inputs.nitrogen_price_per_tonne
    )
    compressor_electricity = (
        (fresh_power + recycle_power)
        * HOURS_PER_YEAR
        * inputs.electricity_price_per_kwh
    )
    refrigeration_cost = refrigeration_electricity * inputs.electricity_price_per_kwh

    annual_costs = {
        "Purchased H2": annual_h2,
        "Purchased N2": annual_n2,
        "Compressor electricity": compressor_electricity,
        "Cooling / refrigeration": refrigeration_cost,
        "Annualized capital": total_capital / inputs.plant_life_years,
    }
    costs_per_tonne = {
        name: cost / inputs.annual_production_tonnes for name, cost in annual_costs.items()
    }

    return EconomicResults(
        annual_costs_usd=annual_costs,
        costs_per_tonne_usd=costs_per_tonne,
        installed_capital_usd=installed_capital,
        fresh_compressor_power_kw=fresh_power,
        recycle_compressor_power_kw=recycle_power,
        cooling_duty_kwh_th_per_year=cooling_duty,
        refrigeration_electricity_kwh_per_year=refrigeration_electricity,
    )

