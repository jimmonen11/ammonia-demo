"""Steady-state material-balance model for a simplified ammonia loop.

All component flow rates are stored in kmol/h.  The model deliberately uses a
user-specified single-pass nitrogen conversion; it does not predict conversion
from pressure, temperature, equilibrium, kinetics, catalyst, or inert dilution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


COMPONENTS = ("H2", "N2", "NH3", "Ar")
HOURS_PER_YEAR = 8_760.0

# kg/kmol (numerically equal to g/mol). Values use NIST standard atomic/molecular
# weights cited in the project README.
MOLECULAR_WEIGHTS = {
    "H2": 2.01588,
    "N2": 28.0134,
    "NH3": 17.03052,
    "Ar": 39.948,
}


class InfeasibleScenarioError(ValueError):
    """Raised when no finite steady state exists for the requested scenario."""


@dataclass(frozen=True)
class ScenarioInputs:
    """Process and economic assumptions for one scenario."""

    # Process basis
    single_pass_conversion: float = 0.20
    purge_fraction: float = 0.05
    fresh_argon_mole_fraction: float = 0.005
    annual_production_tonnes: float = 100_000.0

    # Prices
    hydrogen_price_per_kg: float = 2.00
    nitrogen_price_per_tonne: float = 50.0
    electricity_price_per_kwh: float = 0.0862

    # Compression and cooling
    fresh_feed_pressure_bar: float = 30.0
    loop_pressure_bar: float = 150.0
    loop_pressure_drop_bar: float = 5.0
    compressor_efficiency: float = 0.75
    compressor_inlet_temperature_k: float = 298.15
    heat_capacity_ratio: float = 1.40
    cooling_duty_kwh_th_per_kg_nh3: float = 0.80
    refrigeration_cop: float = 3.0

    # Simple straight-line capital annualization
    plant_life_years: int = 20

    # Illustrative installed-equipment reference costs and scaling bases
    fresh_compressor_ref_cost_musd: float = 12.0
    fresh_compressor_ref_size_kw: float = 5_000.0
    fresh_compressor_exponent: float = 0.70
    recycle_compressor_ref_cost_musd: float = 2.0
    recycle_compressor_ref_size_kw: float = 250.0
    recycle_compressor_exponent: float = 0.70
    reactor_loop_ref_cost_musd: float = 80.0
    reactor_loop_ref_size_kmol_h: float = 8_000.0
    reactor_loop_exponent: float = 0.65
    cooler_separator_ref_cost_musd: float = 30.0
    cooler_separator_ref_size_kmol_h: float = 7_000.0
    cooler_separator_exponent: float = 0.65
    ammonia_separator_ref_cost_musd: float = 12.0
    ammonia_separator_ref_size_kg_h: float = 12_500.0
    ammonia_separator_exponent: float = 0.65


@dataclass(frozen=True)
class Stream:
    """A named process stream with component molar flows in kmol/h."""

    name: str
    components_kmol_h: Mapping[str, float] = field(default_factory=dict)

    def component(self, species: str) -> float:
        return float(self.components_kmol_h.get(species, 0.0))

    @property
    def total_kmol_h(self) -> float:
        return sum(self.component(species) for species in COMPONENTS)

    @property
    def total_kg_h(self) -> float:
        return sum(
            self.component(species) * MOLECULAR_WEIGHTS[species]
            for species in COMPONENTS
        )

    def mole_fraction(self, species: str) -> float:
        if self.total_kmol_h == 0.0:
            return 0.0
        return self.component(species) / self.total_kmol_h


@dataclass(frozen=True)
class ProcessResults:
    """Solved process streams and derived teaching metrics."""

    inputs: ScenarioInputs
    streams: Mapping[str, Stream]
    production_kmol_h: float
    reaction_extent_kmol_h: float
    warnings: tuple[str, ...] = ()

    @property
    def fresh_hydrogen_kg_h(self) -> float:
        return self.streams["fresh_feed"].component("H2") * MOLECULAR_WEIGHTS["H2"]

    @property
    def fresh_nitrogen_kg_h(self) -> float:
        return self.streams["fresh_feed"].component("N2") * MOLECULAR_WEIGHTS["N2"]

    @property
    def purge_hydrogen_kg_h(self) -> float:
        return self.streams["purge_gas"].component("H2") * MOLECULAR_WEIGHTS["H2"]

    @property
    def recycle_to_fresh_ratio(self) -> float:
        fresh_total = self.streams["fresh_feed"].total_kmol_h
        return self.streams["recycle_gas"].total_kmol_h / fresh_total

    @property
    def reactor_inlet_argon_fraction(self) -> float:
        return self.streams["reactor_feed"].mole_fraction("Ar")


@dataclass(frozen=True)
class BalanceCheck:
    section: str
    quantity: str
    residual: float
    unit: str
    passed: bool


@dataclass(frozen=True)
class BalanceReport:
    checks: tuple[BalanceCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def maximum_absolute_residual(self) -> float:
        return max((abs(check.residual) for check in self.checks), default=0.0)

    def as_records(self) -> list[dict[str, object]]:
        return [
            {
                "Section": check.section,
                "Quantity": check.quantity,
                "Residual": check.residual,
                "Unit": check.unit,
                "Status": "Pass" if check.passed else "Fail",
            }
            for check in self.checks
        ]


def _stream(name: str, **components: float) -> Stream:
    return Stream(
        name=name,
        components_kmol_h={species: float(components.get(species, 0.0)) for species in COMPONENTS},
    )


def _validate_process_inputs(inputs: ScenarioInputs) -> None:
    if not 0.0 < inputs.single_pass_conversion <= 1.0:
        raise ValueError("Single-pass N2 conversion must be greater than 0 and at most 1.")
    if not 0.0 <= inputs.purge_fraction <= 1.0:
        raise ValueError("Purge fraction must be between 0 and 1.")
    if not 0.0 <= inputs.fresh_argon_mole_fraction < 1.0:
        raise ValueError("Fresh-feed argon mole fraction must be at least 0 and below 1.")
    if inputs.annual_production_tonnes <= 0.0:
        raise ValueError("Annual ammonia production must be positive.")


def solve_process(inputs: ScenarioInputs) -> ProcessResults:
    """Solve the fixed-conversion ammonia-loop material balance.

    Fresh-feed argon mole fraction is defined on total fresh H2 + N2 + Ar.
    The reactive fresh feed is fixed at H2:N2 = 3:1 molar. A positive argon
    feed with zero purge has no finite steady-state solution.
    """

    _validate_process_inputs(inputs)

    x = inputs.single_pass_conversion
    purge = inputs.purge_fraction
    y_argon = inputs.fresh_argon_mole_fraction

    if purge == 0.0 and y_argon > 0.0:
        raise InfeasibleScenarioError(
            "No finite steady state exists: fresh argon enters the loop but the purge is zero. "
            "Increase the purge fraction or set the fresh-feed argon fraction to zero."
        )

    nh3_kmol_h = (
        inputs.annual_production_tonnes
        * 1_000.0
        / MOLECULAR_WEIGHTS["NH3"]
        / HOURS_PER_YEAR
    )
    extent = nh3_kmol_h / 2.0

    reactor_n2 = extent / x
    reactor_h2 = 3.0 * reactor_n2
    fresh_n2 = reactor_n2 * (x + purge * (1.0 - x))
    fresh_h2 = 3.0 * fresh_n2
    fresh_argon = 4.0 * fresh_n2 * y_argon / (1.0 - y_argon)
    reactor_argon = fresh_argon / purge if purge > 0.0 else 0.0

    reactor_feed = _stream(
        "Reactor inlet",
        H2=reactor_h2,
        N2=reactor_n2,
        Ar=reactor_argon,
    )
    reactor_effluent = _stream(
        "Reactor effluent",
        H2=reactor_h2 - 3.0 * extent,
        N2=reactor_n2 - extent,
        NH3=nh3_kmol_h,
        Ar=reactor_argon,
    )
    ammonia_product = _stream("Separated ammonia", NH3=nh3_kmol_h)
    separator_offgas = _stream(
        "Separator off-gas",
        H2=reactor_effluent.component("H2"),
        N2=reactor_effluent.component("N2"),
        Ar=reactor_effluent.component("Ar"),
    )
    purge_gas = _stream(
        "Purge gas",
        H2=purge * separator_offgas.component("H2"),
        N2=purge * separator_offgas.component("N2"),
        Ar=purge * separator_offgas.component("Ar"),
    )
    recycle_gas = _stream(
        "Recycle gas",
        H2=(1.0 - purge) * separator_offgas.component("H2"),
        N2=(1.0 - purge) * separator_offgas.component("N2"),
        Ar=(1.0 - purge) * separator_offgas.component("Ar"),
    )
    fresh_feed = _stream(
        "Fresh feed",
        H2=fresh_h2,
        N2=fresh_n2,
        Ar=fresh_argon,
    )

    streams = {
        "fresh_feed": fresh_feed,
        "recycle_gas": recycle_gas,
        "reactor_feed": reactor_feed,
        "reactor_effluent": reactor_effluent,
        "ammonia_product": ammonia_product,
        "separator_offgas": separator_offgas,
        "purge_gas": purge_gas,
    }

    recycle_ratio = recycle_gas.total_kmol_h / fresh_feed.total_kmol_h
    inlet_argon = reactor_feed.mole_fraction("Ar")
    warnings: list[str] = []
    if inlet_argon > 0.10:
        warnings.append(
            "Reactor-inlet argon exceeds 10 mol%. This is an extreme dilution level for the teaching model."
        )
    if recycle_ratio > 10.0:
        warnings.append(
            "Recycle exceeds ten times the fresh-feed molar flow. Real equipment or operability limits may dominate."
        )
    if reactor_feed.total_kmol_h / nh3_kmol_h > 20.0:
        warnings.append(
            "Loop circulation is very large relative to ammonia production; treat this scenario as a limiting case."
        )

    return ProcessResults(
        inputs=inputs,
        streams=streams,
        production_kmol_h=nh3_kmol_h,
        reaction_extent_kmol_h=extent,
        warnings=tuple(warnings),
    )


def validate_balances(process: ProcessResults, tolerance: float = 1e-8) -> BalanceReport:
    """Check component balances for every unit and elements for the overall loop."""

    s = process.streams
    xi = process.reaction_extent_kmol_h
    checks: list[BalanceCheck] = []

    def add(section: str, quantity: str, residual: float, unit: str = "kmol/h") -> None:
        checks.append(
            BalanceCheck(
                section=section,
                quantity=quantity,
                residual=float(residual),
                unit=unit,
                passed=abs(residual) <= tolerance,
            )
        )

    for species in COMPONENTS:
        add(
            "Mixer",
            species,
            s["fresh_feed"].component(species)
            + s["recycle_gas"].component(species)
            - s["reactor_feed"].component(species),
        )

    reaction_change = {"H2": -3.0 * xi, "N2": -xi, "NH3": 2.0 * xi, "Ar": 0.0}
    for species in COMPONENTS:
        add(
            "Reactor",
            species,
            s["reactor_feed"].component(species)
            + reaction_change[species]
            - s["reactor_effluent"].component(species),
        )

    for species in COMPONENTS:
        add(
            "Separator",
            species,
            s["reactor_effluent"].component(species)
            - s["ammonia_product"].component(species)
            - s["separator_offgas"].component(species),
        )
        add(
            "Purge/recycle split",
            species,
            s["separator_offgas"].component(species)
            - s["purge_gas"].component(species)
            - s["recycle_gas"].component(species),
        )
        add(
            "Overall process",
            species,
            s["fresh_feed"].component(species)
            + reaction_change[species]
            - s["ammonia_product"].component(species)
            - s["purge_gas"].component(species),
        )

    overall_component_residual = {
        species: s["fresh_feed"].component(species)
        - s["ammonia_product"].component(species)
        - s["purge_gas"].component(species)
        for species in COMPONENTS
    }
    add(
        "Overall elements",
        "H atoms",
        2.0 * overall_component_residual["H2"] + 3.0 * overall_component_residual["NH3"],
        "kmol atoms/h",
    )
    add(
        "Overall elements",
        "N atoms",
        2.0 * overall_component_residual["N2"] + overall_component_residual["NH3"],
        "kmol atoms/h",
    )
    add(
        "Overall elements",
        "Ar atoms",
        overall_component_residual["Ar"],
        "kmol atoms/h",
    )
    mass_residual = sum(
        overall_component_residual[species] * MOLECULAR_WEIGHTS[species]
        for species in COMPONENTS
    )
    add("Overall process", "Mass", mass_residual, "kg/h")

    return BalanceReport(checks=tuple(checks))

