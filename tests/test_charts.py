from __future__ import annotations

from ammonia_teaching.charts import make_cost_figure, make_process_flow_figure
from ammonia_teaching.economics import calculate_economics
from ammonia_teaching.model import ScenarioInputs, solve_process


def test_cost_figure_is_a_waterfall_with_capital_annualization_hover_note():
    inputs = ScenarioInputs()
    economics = calculate_economics(inputs, solve_process(inputs))

    figure = make_cost_figure(economics)
    trace = figure.data[0]

    assert trace.type == "waterfall"
    assert trace.x[0] == "Fresh H2"
    assert trace.x[1] == "Fresh N2"
    assert "Purchased H2" not in trace.x
    assert "Purchased N2" not in trace.x
    assert trace.x[-1] == "Total"
    capital_index = list(trace.x).index("Annualized capital")
    assert "divided evenly by plant life" in trace.customdata[capital_index][1]


def test_process_flow_hover_reports_total_flow_and_mol_percent():
    process = solve_process(ScenarioInputs())

    figure = make_process_flow_figure(process)
    hover_trace = next(trace for trace in figure.data if trace.hovertemplate == "%{text}<extra></extra>")
    label = hover_trace.text[0]

    assert "Total mol flow:" in label
    assert "kmol/h" in label
    assert "H2:" in label
    assert "N2:" in label
    assert "NH3:" in label
    assert "Ar:" in label
    assert label.count("mol%") == 4
    assert "H2: 3,714" not in label
