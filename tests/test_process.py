from __future__ import annotations

import pytest

from ammonia_teaching.model import (
    COMPONENTS,
    HOURS_PER_YEAR,
    MOLECULAR_WEIGHTS,
    InfeasibleScenarioError,
    ScenarioInputs,
    solve_process,
    validate_balances,
)


@pytest.mark.parametrize(
    "conversion,purge,argon",
    [
        (0.10, 0.02, 0.002),
        (0.20, 0.05, 0.005),
        (0.45, 0.20, 0.010),
        (0.80, 1.00, 0.000),
    ],
)
def test_all_unit_component_and_element_balances_pass(conversion, purge, argon):
    process = solve_process(
        ScenarioInputs(
            single_pass_conversion=conversion,
            purge_fraction=purge,
            fresh_argon_mole_fraction=argon,
        )
    )

    report = validate_balances(process)

    assert report.passed
    assert report.maximum_absolute_residual < 1e-8
    sections = {check.section for check in report.checks}
    assert {
        "Mixer",
        "Reactor",
        "Separator",
        "Purge/recycle split",
        "Overall process",
        "Overall elements",
    }.issubset(sections)


def test_no_purge_and_no_inert_has_stoichiometric_fresh_feed_without_reactant_loss():
    process = solve_process(
        ScenarioInputs(purge_fraction=0.0, fresh_argon_mole_fraction=0.0)
    )
    fresh = process.streams["fresh_feed"]

    assert fresh.component("N2") == pytest.approx(process.reaction_extent_kmol_h)
    assert fresh.component("H2") == pytest.approx(3.0 * process.reaction_extent_kmol_h)
    assert process.streams["purge_gas"].total_kmol_h == pytest.approx(0.0)
    assert process.purge_hydrogen_kg_h == pytest.approx(0.0)
    assert validate_balances(process).passed


def test_once_through_purge_of_one_has_no_recycle():
    process = solve_process(
        ScenarioInputs(purge_fraction=1.0, fresh_argon_mole_fraction=0.01)
    )

    assert process.streams["recycle_gas"].total_kmol_h == pytest.approx(0.0)
    for species in COMPONENTS:
        assert process.streams["fresh_feed"].component(species) == pytest.approx(
            process.streams["reactor_feed"].component(species)
        )
        assert process.streams["purge_gas"].component(species) == pytest.approx(
            process.streams["separator_offgas"].component(species)
        )


@pytest.mark.parametrize("purge", [0.0, 0.01, 0.10, 1.0])
def test_zero_inert_stays_zero_for_all_valid_purge_values(purge):
    process = solve_process(
        ScenarioInputs(purge_fraction=purge, fresh_argon_mole_fraction=0.0)
    )

    assert all(stream.component("Ar") == pytest.approx(0.0) for stream in process.streams.values())


def test_positive_inert_with_zero_purge_is_explicitly_infeasible():
    with pytest.raises(InfeasibleScenarioError, match="fresh argon.*purge is zero"):
        solve_process(ScenarioInputs(purge_fraction=0.0, fresh_argon_mole_fraction=0.005))


def test_inert_accumulation_and_recycle_increase_as_purge_decreases():
    high_purge = solve_process(ScenarioInputs(purge_fraction=0.10))
    low_purge = solve_process(ScenarioInputs(purge_fraction=0.02))

    assert low_purge.reactor_inlet_argon_fraction > high_purge.reactor_inlet_argon_fraction
    assert (
        low_purge.streams["recycle_gas"].total_kmol_h
        > high_purge.streams["recycle_gas"].total_kmol_h
    )


def test_hydrogen_loss_decreases_as_purge_decreases_at_fixed_production_and_conversion():
    high_purge = solve_process(ScenarioInputs(purge_fraction=0.10))
    low_purge = solve_process(ScenarioInputs(purge_fraction=0.02))

    assert low_purge.purge_hydrogen_kg_h < high_purge.purge_hydrogen_kg_h


def test_fresh_feed_argon_fraction_uses_total_fresh_feed_basis():
    inputs = ScenarioInputs(fresh_argon_mole_fraction=0.012)
    fresh = solve_process(inputs).streams["fresh_feed"]

    assert fresh.mole_fraction("Ar") == pytest.approx(inputs.fresh_argon_mole_fraction)
    assert fresh.component("H2") / fresh.component("N2") == pytest.approx(3.0)


def test_annual_production_uses_continuous_operation():
    inputs = ScenarioInputs(annual_production_tonnes=100_000.0)
    process = solve_process(inputs)

    expected = 100_000.0 * 1_000.0 / MOLECULAR_WEIGHTS["NH3"] / HOURS_PER_YEAR
    assert process.production_kmol_h == pytest.approx(expected)



