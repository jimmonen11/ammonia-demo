from __future__ import annotations

from ammonia_teaching.charts import make_cost_figure
from ammonia_teaching.economics import calculate_economics
from ammonia_teaching.model import ScenarioInputs, solve_process


def test_cost_figure_is_a_waterfall_with_capital_annualization_hover_note():
    inputs = ScenarioInputs()
    economics = calculate_economics(inputs, solve_process(inputs))

    figure = make_cost_figure(economics)
    trace = figure.data[0]

    assert trace.type == "waterfall"
    assert trace.x[-1] == "Total"
    capital_index = list(trace.x).index("Annualized capital")
    assert "divided evenly by plant life" in trace.customdata[capital_index][1]
