"""Streamlit interface for the simplified ammonia-loop teaching model."""

from __future__ import annotations

from dataclasses import fields

import numpy as np
import pandas as pd
import streamlit as st

from ammonia_teaching.charts import (
    make_cost_figure,
    make_process_flow_figure,
    make_sensitivity_figure,
)
from ammonia_teaching.economics import calculate_economics
from ammonia_teaching.model import (
    COMPONENTS,
    MOLECULAR_WEIGHTS,
    InfeasibleScenarioError,
    ProcessResults,
    ScenarioInputs,
    solve_process,
)
from ammonia_teaching.sensitivity import run_sensitivity


st.set_page_config(
    page_title="Ammonia Loop Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #ffffff 26%, #ffffff 100%);
        color: #111827;
      }
      .stApp [data-testid="stHeader"] {
        background: rgba(248, 250, 252, 0.94);
        border-bottom: 1px solid rgba(209, 213, 219, 0.72);
      }
      .block-container { padding-top: 1.55rem; padding-bottom: 2rem; }
      div[data-baseweb="input"] input,
      div[data-baseweb="select"] input {
        background: #ffffff;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
      }
      [data-testid="stWidgetLabel"] p {
        color: #374151;
        font-size: 0.92rem;
        font-weight: 700;
      }
      .app-title {
        color: #0f172a;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.08;
        margin: 0 0 0.35rem 0;
      }
      .app-copy {
        color: #475569;
        font-size: 0.98rem;
        margin: 0 0 0.6rem 0;
        max-width: 62rem;
      }
      div[data-testid="stMetric"] {
        border: 1px solid rgba(209, 213, 219, 0.88);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(248, 250, 252, 0.99));
        border-radius: 8px;
        padding: 0.9rem 0.95rem 0.82rem 0.95rem;
        min-height: 104px;
      }
      div[data-testid="stMetricLabel"] {
        color: #475569;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }
      div[data-testid="stMetricValue"] { color: #0f172a; font-weight: 800; }
      .stTabs [data-baseweb="tab-list"] { gap: 0.35rem; }
      .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        border: 1px solid rgba(209, 213, 219, 0.86);
        background: rgba(255, 255, 255, 0.85);
        padding: 0.42rem 0.8rem;
      }
      .stTabs [aria-selected="true"] {
        background: #ecfeff !important;
        color: #0f766e !important;
        border-color: rgba(45, 212, 191, 0.92) !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


DEFAULT_INPUTS = ScenarioInputs()
ANNUAL_PRODUCTION_MIN_TY = 1_000.0
ANNUAL_PRODUCTION_MAX_TY = 2_000_000.0


def format_annual_production_tonnes(value: float) -> str:
    return f"{value:,.0f}"


def parse_annual_production_tonnes(value: str) -> float:
    normalized = value.replace(",", "").strip()
    if not normalized.isdigit():
        raise ValueError("Annual NH3 production must be a whole number in t/y.")
    return float(int(normalized))


def normalize_annual_production_tonnes_text() -> None:
    try:
        parsed = parse_annual_production_tonnes(
            st.session_state["annual_production_tonnes_text"]
        )
    except ValueError:
        return
    st.session_state["annual_production_tonnes_text"] = format_annual_production_tonnes(
        parsed
    )


WIDGET_DEFAULTS = {field.name: getattr(DEFAULT_INPUTS, field.name) for field in fields(ScenarioInputs)}
WIDGET_DEFAULTS.update(
    {
        "single_pass_conversion_pct": 100.0 * DEFAULT_INPUTS.single_pass_conversion,
        "purge_fraction_pct": 100.0 * DEFAULT_INPUTS.purge_fraction,
        "fresh_argon_mole_fraction_pct": 100.0 * DEFAULT_INPUTS.fresh_argon_mole_fraction,
        "compressor_efficiency_pct": 100.0 * DEFAULT_INPUTS.compressor_efficiency,
        "annual_production_tonnes_text": format_annual_production_tonnes(
            DEFAULT_INPUTS.annual_production_tonnes
        ),
    }
)


def reset_defaults() -> None:
    for key, value in WIDGET_DEFAULTS.items():
        st.session_state[key] = value


for widget_key, default_value in WIDGET_DEFAULTS.items():
    st.session_state.setdefault(widget_key, default_value)


with st.sidebar:
    st.markdown("### Scenario")
    st.button("Reset inputs to defaults", on_click=reset_defaults, width="stretch")

    st.markdown("#### Process")
    st.slider(
        "Single-pass N₂ conversion",
        5.0,
        80.0,
        step=1.0,
        key="single_pass_conversion_pct",
        format="%.0f%%",
        help="Specified fraction of reactor-inlet N₂ that reacts on one pass. It is not calculated from pressure or temperature.",
    )
    st.slider(
        "Purge fraction",
        0.0,
        30.0,
        step=0.5,
        key="purge_fraction_pct",
        format="%.1f%%",
        help="Fraction of separator off-gas removed before the remaining gas is recycled.",
    )
    st.slider(
        "Argon in fresh feed",
        0.0,
        3.0,
        step=0.1,
        key="fresh_argon_mole_fraction_pct",
        format="%.1f%%",
        help="Argon mole fraction of total fresh H₂ + N₂ + Ar feed. Argon is inert and leaves only through the purge.",
    )
    st.text_input(
        "Annual NH₃ production (t/y)",
        key="annual_production_tonnes_text",
        help="Fixed annual separated-ammonia production target.",
        on_change=normalize_annual_production_tonnes_text,
    )
    with st.expander("Advanced process assumptions"):
        st.number_input("Fresh-feed pressure (bar)", min_value=1.0, max_value=149.0, step=1.0, key="fresh_feed_pressure_bar")
        st.number_input("Loop pressure (bar)", min_value=10.0, max_value=350.0, step=5.0, key="loop_pressure_bar")
        st.number_input("Loop pressure drop (bar)", min_value=0.0, max_value=50.0, step=0.5, key="loop_pressure_drop_bar")
        st.slider("Compressor isentropic efficiency", 40.0, 95.0, step=1.0, key="compressor_efficiency_pct", format="%.0f%%")
        st.number_input("Compressor inlet temperature (K)", min_value=250.0, max_value=450.0, step=5.0, key="compressor_inlet_temperature_k")
        st.number_input("Heat-capacity ratio, γ", min_value=1.05, max_value=1.67, step=0.01, key="heat_capacity_ratio")
        st.number_input(
            "Cooling duty (kWh-thermal/kg NH₃)",
            min_value=0.0,
            max_value=5.0,
            step=0.05,
            key="cooling_duty_kwh_th_per_kg_nh3",
            help="Illustrative specific cooling duty, not a rigorous heat balance.",
        )
        st.number_input("Refrigeration COP", min_value=0.5, max_value=10.0, step=0.1, key="refrigeration_cop")

    st.markdown("#### Economics")
    st.number_input("Hydrogen price ($/kg)", min_value=0.0, max_value=15.0, step=0.10, key="hydrogen_price_per_kg")
    st.number_input("Nitrogen price ($/t)", min_value=0.0, max_value=500.0, step=5.0, key="nitrogen_price_per_tonne")
    st.number_input("Electricity price ($/kWh)", min_value=0.0, max_value=0.50, step=0.005, key="electricity_price_per_kwh", format="%.4f")

    st.number_input(
        "Plant lifetime (years)",
        min_value=1,
        max_value=60,
        step=1,
        key="plant_life_years",
        help="Annualized capital equals total installed CapEx divided evenly by plant lifetime. No discount rate is applied.",
    )


try:
    annual_production_tonnes = parse_annual_production_tonnes(
        st.session_state["annual_production_tonnes_text"]
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if not ANNUAL_PRODUCTION_MIN_TY <= annual_production_tonnes <= ANNUAL_PRODUCTION_MAX_TY:
    st.error(
        "Annual NH3 production must be between "
        f"{ANNUAL_PRODUCTION_MIN_TY:,.0f} and {ANNUAL_PRODUCTION_MAX_TY:,.0f} t/y."
    )
    st.stop()

st.session_state["annual_production_tonnes"] = annual_production_tonnes

input_values = {field.name: st.session_state[field.name] for field in fields(ScenarioInputs)}
input_values.update(
    {
        "single_pass_conversion": st.session_state["single_pass_conversion_pct"] / 100.0,
        "purge_fraction": st.session_state["purge_fraction_pct"] / 100.0,
        "fresh_argon_mole_fraction": st.session_state["fresh_argon_mole_fraction_pct"] / 100.0,
        "compressor_efficiency": st.session_state["compressor_efficiency_pct"] / 100.0,
    }
)
inputs = ScenarioInputs(**input_values)

st.markdown(
    "<h1 class='app-title'>Ammonia Loop Lab</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='app-copy'>Explore purge, recycle, inert accumulation, reactant losses, and annualized cost in a transparent fixed-conversion ammonia synthesis loop.</p>",
    unsafe_allow_html=True,
)

try:
    process = solve_process(inputs)
    economics = calculate_economics(inputs, process)
except InfeasibleScenarioError as exc:
    st.error(f"Infeasible steady state — {exc}", icon="🚫")
    st.info("Argon has no modeled exit when purge is zero. The model leaves the singularity visible instead of clipping a denominator.")
    st.stop()
except ValueError as exc:
    st.error(f"Check the advanced assumptions: {exc}")
    st.stop()

for warning in process.warnings:
    st.warning(warning, icon="⚠️")

product_t_h = process.production_kmol_h * MOLECULAR_WEIGHTS["NH3"] / 1_000.0
h2_kg_per_tonne = process.fresh_hydrogen_kg_h / product_t_h
n2_kg_per_tonne = process.fresh_nitrogen_kg_h / product_t_h

overview_tab, sensitivity_tab, assumptions_tab = st.tabs(["Overview", "Sensitivity", "Model Notes"])


def stream_table(results: ProcessResults, basis: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for stream in results.streams.values():
        if basis == "Molar flow (kmol/h)":
            row = {"Stream": stream.name}
            row.update({species: stream.component(species) for species in COMPONENTS})
            row["Total"] = stream.total_kmol_h
            row["Ar (mol%)"] = 100.0 * stream.mole_fraction("Ar")
        else:
            row = {"Stream": stream.name}
            row.update(
                {
                    species: stream.component(species) * MOLECULAR_WEIGHTS[species]
                    for species in COMPONENTS
                }
            )
            row["Total"] = stream.total_kg_h
        rows.append(row)
    return pd.DataFrame(rows)


with overview_tab:
    st.plotly_chart(
        make_process_flow_figure(process),
        width="stretch",
        config={"displaylogo": False, "responsive": True},
        key="process_flow_diagram",
    )
    st.markdown("#### Key results")
    kpi_columns = st.columns(5)
    kpi_columns[0].metric("Annualized cost", f"${economics.total_cost_per_tonne_usd:,.0f}/t NH₃")
    kpi_columns[1].metric("Fresh H2 (kg/t NH3)", f"{h2_kg_per_tonne:,.1f}")
    kpi_columns[2].metric("Fresh N2 (kg/t NH3)", f"{n2_kg_per_tonne:,.1f}")
    kpi_columns[3].metric("Recycle / fresh", f"{process.recycle_to_fresh_ratio:,.2f}")
    kpi_columns[4].metric(
        "Reactor-inlet Ar", f"{100 * process.reactor_inlet_argon_fraction:,.2f} mol%"
    )

    st.plotly_chart(
        make_cost_figure(economics),
        width="stretch",
        config={"displaylogo": False, "responsive": True},
        key="cost_breakdown_chart",
    )

    st.markdown("#### Stream table")
    table_basis = st.radio(
        "Flow basis",
        ["Molar flow (kmol/h)", "Mass flow (kg/h)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    displayed_streams = stream_table(process, table_basis)
    flow_columns = [column for column in [*COMPONENTS, "Total"] if column in displayed_streams]
    stream_formats = {column: "{:,.0f}" for column in flow_columns}
    if "Ar (mol%)" in displayed_streams:
        stream_formats["Ar (mol%)"] = "{:.2f}%"
    st.dataframe(
        displayed_streams.style.format(stream_formats),
        hide_index=True,
        width="stretch",
    )


with sensitivity_tab:
    st.markdown("#### Configurable sensitivity plot")
    st.caption(
        "Choose one main input for the x-axis and one model output for the y-axis. Every other input stays at its current value."
    )

    sensitivity_inputs = {
        "Single-pass N₂ conversion": {
            "field": "single_pass_conversion",
            "minimum": 0.05,
            "maximum": 0.80,
            "multiplier": 100.0,
            "axis_title": "Single-pass N₂ conversion (%)",
            "format": ".0f",
        },
        "Purge fraction": {
            "field": "purge_fraction",
            "minimum": 0.0,
            "maximum": 0.30,
            "multiplier": 100.0,
            "axis_title": "Purge fraction (%)",
            "format": ".1f",
        },
        "Argon in fresh feed": {
            "field": "fresh_argon_mole_fraction",
            "minimum": 0.0,
            "maximum": 0.03,
            "multiplier": 100.0,
            "axis_title": "Argon in fresh feed (mol%)",
            "format": ".2f",
        },
        "Annual NH₃ production": {
            "field": "annual_production_tonnes",
            "minimum": 25_000.0,
            "maximum": 250_000.0,
            "multiplier": 1.0,
            "axis_title": "Annual NH₃ production (t/y)",
            "format": ",.0f",
        },
        "Hydrogen price": {
            "field": "hydrogen_price_per_kg",
            "minimum": 0.5,
            "maximum": 5.0,
            "multiplier": 1.0,
            "axis_title": "Hydrogen price ($/kg)",
            "format": ".2f",
        },
        "Nitrogen price": {
            "field": "nitrogen_price_per_tonne",
            "minimum": 0.0,
            "maximum": 150.0,
            "multiplier": 1.0,
            "axis_title": "Nitrogen price ($/t)",
            "format": ",.0f",
        },
        "Electricity price": {
            "field": "electricity_price_per_kwh",
            "minimum": 0.03,
            "maximum": 0.20,
            "multiplier": 1.0,
            "axis_title": "Electricity price ($/kWh)",
            "format": ".3f",
        },
    }
    sensitivity_outputs = {
        "Annualized production cost": {
            "column": "cost_usd_per_tonne",
            "axis_title": "Annualized production cost ($/t NH₃)",
            "format": ",.0f",
        },
        "Fresh H₂ consumption": {
            "column": "fresh_h2_kg_per_tonne",
            "axis_title": "Fresh H₂ consumption (kg/t NH₃)",
            "format": ",.1f",
        },
        "Fresh N₂ consumption": {
            "column": "fresh_n2_kg_per_tonne",
            "axis_title": "Fresh N₂ consumption (kg/t NH₃)",
            "format": ",.1f",
        },
        "H₂ lost in purge": {
            "column": "h2_loss_kg_h",
            "axis_title": "H₂ lost in purge (kg/h)",
            "format": ",.0f",
        },
        "Recycle flow": {
            "column": "recycle_kmol_h",
            "axis_title": "Recycle flow (kmol/h)",
            "format": ",.0f",
        },
        "Recycle-to-fresh ratio": {
            "column": "recycle_to_fresh_ratio",
            "axis_title": "Recycle-to-fresh molar ratio",
            "format": ".2f",
        },
        "Reactor-inlet argon": {
            "column": "reactor_inlet_argon_mol_pct",
            "axis_title": "Reactor-inlet argon (mol%)",
            "format": ".2f",
        },
        "Total compressor power": {
            "column": "compressor_power_kw",
            "axis_title": "Total compressor power (kW)",
            "format": ",.0f",
        },
        "Installed capital": {
            "column": "installed_capital_musd",
            "axis_title": "Installed capital ($MM)",
            "format": ",.1f",
        },
    }

    input_col, output_col = st.columns(2)
    with input_col:
        selected_input_label = st.selectbox("X-axis input", list(sensitivity_inputs))
    with output_col:
        selected_output_label = st.selectbox("Model output", list(sensitivity_outputs))

    input_config = sensitivity_inputs[selected_input_label]
    output_config = sensitivity_outputs[selected_output_label]
    current_input_value = float(getattr(inputs, input_config["field"]))
    sweep_minimum = min(float(input_config["minimum"]), current_input_value)
    sweep_maximum = max(float(input_config["maximum"]), current_input_value)
    sensitivity = run_sensitivity(
        inputs,
        input_field=input_config["field"],
        input_grid=np.linspace(sweep_minimum, sweep_maximum, 41),
    )
    st.plotly_chart(
        make_sensitivity_figure(
            sensitivity.data,
            output_column=output_config["column"],
            x_title=input_config["axis_title"],
            y_title=output_config["axis_title"],
            current_input_value=current_input_value,
            x_multiplier=input_config["multiplier"],
            x_number_format=input_config["format"],
            y_number_format=output_config["format"],
        ),
        width="stretch",
        config={"displaylogo": False, "responsive": True},
        key="configurable_sensitivity_chart",
    )
    invalid_points = int((~sensitivity.data["valid"]).sum())
    if invalid_points:
        st.caption(
            f"{invalid_points} infeasible sweep point(s) are omitted. For example, positive fresh-feed argon with zero purge has no steady state."
        )


with assumptions_tab:
    st.markdown("#### Model equations and boundary")
    st.warning(
        "Single-pass conversion is an independent teaching input. Temperature and pressure do not calculate conversion, equilibrium, kinetics, catalyst performance, or inert-dilution effects in this model."
    )
    equation_col, boundary_col = st.columns(2)
    with equation_col:
        st.markdown("#### Core balances")
        st.latex(r"\dot n_{NH_3}=\frac{m_{annual}\,1000}{MW_{NH_3}\,(8760\ \mathrm{h/y})}")
        st.latex(r"\dot n_{N_2,in}=\frac{\dot n_{NH_3}}{2X}")
        st.latex(r"\dot n_{N_2,fresh}=\dot n_{N_2,in}[X+p(1-X)]")
        st.latex(r"\dot n_{H_2,fresh}=3\dot n_{N_2,fresh}")
        st.latex(r"\dot n_{Ar,fresh}=\frac{4y_{Ar,fresh}\dot n_{N_2,fresh}}{1-y_{Ar,fresh}}")
        st.latex(r"\dot n_{Ar,in}=\frac{\dot n_{Ar,fresh}}{p}\quad(p>0)")
        st.caption("Here X is the single-pass N2 conversion in the reactor, p is the fraction of separator off-gas purged, and fresh-feed argon mole fraction is based on total fresh H2 + N2 + Ar.")
    with boundary_col:
        st.markdown("#### Cost boundary")
        st.latex(r"C_{\mathrm{prod}}=\frac{C_{H_2}+C_{N_2}+C_{\mathrm{comp}}+C_{\mathrm{refrig}}+C_{\mathrm{cap,annual}}}{m_{NH_3,\mathrm{annual}}}")
        st.latex(r"C_{\mathrm{cap,annual}}=\frac{C_{\mathrm{installed}}}{N_{\mathrm{life}}}")
        st.markdown("#### Compression and cooling")
        st.latex(r"\dot W_{\mathrm{comp}}=\frac{\dot n}{3600}\frac{\gamma}{\gamma-1}\frac{RT}{\eta}\left[\left(\frac{P_2}{P_1}\right)^{(\gamma-1)/\gamma}-1\right]")
        st.latex(r"E_{\mathrm{refrig}}=\frac{q_{\mathrm{cool}}m_{NH_3,\mathrm{annual}}}{COP}")
        st.latex(r"C_{\mathrm{energy}}=\left[(\dot W_{\mathrm{fresh}}+\dot W_{\mathrm{recycle}})(8760)+E_{\mathrm{refrig}}\right]c_{\mathrm{elec}}")

    st.markdown("#### Illustrative capital model")
    st.latex(r"C=C_{ref}\left(\frac{S}{S_{ref}}\right)^n")
    st.latex(r"C_{annual}=\frac{C_{installed}}{\text{plant life}}")
    st.caption("Installed CapEx is spread evenly over the selected plant life. No discount rate is applied.")
    capital_rows = [
        {"Equipment": "Fresh-feed compressor", "Reference size": f"{inputs.fresh_compressor_ref_size_kw:,.0f} kW", "Reference cost ($MM)": inputs.fresh_compressor_ref_cost_musd, "Exponent": inputs.fresh_compressor_exponent, "Current scaled cost ($MM)": economics.installed_capital_usd["Fresh-feed compressor"] / 1e6},
        {"Equipment": "Recycle compressor", "Reference size": f"{inputs.recycle_compressor_ref_size_kw:,.0f} kW", "Reference cost ($MM)": inputs.recycle_compressor_ref_cost_musd, "Exponent": inputs.recycle_compressor_exponent, "Current scaled cost ($MM)": economics.installed_capital_usd["Recycle compressor"] / 1e6},
        {"Equipment": "Reactor loop", "Reference size": f"{inputs.reactor_loop_ref_size_kmol_h:,.0f} kmol/h feed", "Reference cost ($MM)": inputs.reactor_loop_ref_cost_musd, "Exponent": inputs.reactor_loop_exponent, "Current scaled cost ($MM)": economics.installed_capital_usd["Reactor loop"] / 1e6},
        {"Equipment": "Cooler + gas separator", "Reference size": f"{inputs.cooler_separator_ref_size_kmol_h:,.0f} kmol/h effluent", "Reference cost ($MM)": inputs.cooler_separator_ref_cost_musd, "Exponent": inputs.cooler_separator_exponent, "Current scaled cost ($MM)": economics.installed_capital_usd["Cooler and gas separator"] / 1e6},
        {"Equipment": "Ammonia separator", "Reference size": f"{inputs.ammonia_separator_ref_size_kg_h:,.0f} kg/h NH3", "Reference cost ($MM)": inputs.ammonia_separator_ref_cost_musd, "Exponent": inputs.ammonia_separator_exponent, "Current scaled cost ($MM)": economics.installed_capital_usd["Ammonia separator"] / 1e6},
    ]
    st.dataframe(
        pd.DataFrame(capital_rows).style.format(
            {
                "Reference cost ($MM)": "{:,.0f}",
                "Exponent": "{:.2f}",
                "Current scaled cost ($MM)": "{:,.1f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption("All equipment reference costs, reference sizes, exponents, nitrogen price, and cooling duty are illustrative teaching defaults rather than validated plant estimates.")


