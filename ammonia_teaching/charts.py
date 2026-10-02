"""Plotly figures used by the Streamlit teaching interface."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .economics import EconomicResults
from .model import ProcessResults, Stream


NAVY = "#111827"
BLUE = "#1d4ed8"
TEAL = "#0f766e"
AMBER = "#b45309"
CORAL = "#dc2626"
PURPLE = "#6b7280"
LIGHT = "#f8fafc"
GRID = "#e5e7eb"
BORDER = "#d1d5db"


def _stream_label(stream: Stream) -> str:
    return (
        f"<b>{stream.name}</b><br>"
        f"Total mol flow: {stream.total_kmol_h:,.0f} kmol/h<br>"
        f"H2: {100.0 * stream.mole_fraction('H2'):,.2f} mol%<br>"
        f"N2: {100.0 * stream.mole_fraction('N2'):,.2f} mol%<br>"
        f"NH3: {100.0 * stream.mole_fraction('NH3'):,.2f} mol%<br>"
        f"Ar: {100.0 * stream.mole_fraction('Ar'):,.2f} mol%"
    )


def make_process_flow_figure(process: ProcessResults) -> go.Figure:
    """Build an interactive process-flow diagram with live stream values."""

    fig = go.Figure()

    units = [
        (0.18, 0.63, "Fresh<br>compressor"),
        (0.34, 0.63, "Mixer"),
        (0.52, 0.63, "Reactor"),
        (0.70, 0.63, "Cooler +<br>separator"),
        (0.87, 0.63, "Purge /<br>recycle split"),
    ]
    for x, y, label in units:
        fig.add_shape(
            type="rect",
            x0=x - 0.055,
            x1=x + 0.055,
            y0=y - 0.105,
            y1=y + 0.105,
            line=dict(color=NAVY, width=2),
            fillcolor=LIGHT,
            layer="below",
        )
        fig.add_annotation(
            x=x, y=y, text=f"<b>{label}</b>", showarrow=False, font=dict(size=12, color=NAVY)
        )

    def arrow(x0: float, y0: float, x1: float, y1: float, color: str = BLUE) -> None:
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.2,
            arrowwidth=2.5,
            arrowcolor=color,
        )

    arrow(0.02, 0.63, 0.125, 0.63)
    arrow(0.235, 0.63, 0.285, 0.63)
    arrow(0.395, 0.63, 0.465, 0.63)
    arrow(0.575, 0.63, 0.645, 0.63)
    arrow(0.755, 0.63, 0.815, 0.63)
    arrow(0.925, 0.63, 0.99, 0.63, CORAL)
    arrow(0.70, 0.735, 0.70, 0.88, TEAL)

    # Recycle line is drawn in segments to make the loop direction clear.
    fig.add_trace(
        go.Scatter(
            x=[0.87, 0.87, 0.34, 0.34],
            y=[0.525, 0.34, 0.34, 0.525],
            mode="lines",
            line=dict(color=PURPLE, width=3),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    arrow(0.34, 0.40, 0.34, 0.525, PURPLE)

    stream_points = [
        (0.065, 0.63, process.streams["fresh_feed"], "Fresh feed"),
        (0.43, 0.63, process.streams["reactor_feed"], "Reactor feed"),
        (0.61, 0.63, process.streams["reactor_effluent"], "Reactor effluent"),
        (0.785, 0.63, process.streams["separator_offgas"], "Separator off-gas"),
        (0.965, 0.63, process.streams["purge_gas"], "Purge"),
        (0.61, 0.34, process.streams["recycle_gas"], "Recycle"),
        (0.70, 0.88, process.streams["ammonia_product"], "NH₃ product"),
    ]
    fig.add_trace(
        go.Scatter(
            x=[point[0] for point in stream_points],
            y=[point[1] for point in stream_points],
            mode="markers",
            marker=dict(
                size=12,
                color=[BLUE, BLUE, BLUE, BLUE, CORAL, PURPLE, TEAL],
                line=dict(color="white", width=2),
            ),
            text=[_stream_label(point[2]) for point in stream_points],
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )
    for x, y, _, label in stream_points:
        if label == "NH₃ product":
            y_shift = 0.055
        elif label == "Recycle":
            y_shift = -0.055
        else:
            y_shift = -0.075
        fig.add_annotation(
            x=x, y=y + y_shift, text=label, showarrow=False, font=dict(size=10, color=NAVY)
        )

    fig.update_layout(
        title=dict(
            text="Simple ammonia process-flow diagram — hover over stream markers for total flow and mol%",
            x=0.01,
        ),
        height=430,
        margin=dict(l=20, r=20, t=65, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=NAVY),
        xaxis=dict(range=[0, 1.02], visible=False, fixedrange=True),
        yaxis=dict(range=[0.08, 1.02], visible=False, fixedrange=True),
        hoverlabel=dict(bgcolor="white", font_size=12, font_color=NAVY),
    )
    return fig


def make_cost_figure(economics: EconomicResults) -> go.Figure:
    names = list(economics.costs_per_tonne_usd)
    values = list(economics.costs_per_tonne_usd.values())
    total = sum(values)
    notes = [
        "Annual purchased hydrogen cost",
        "Annual purchased nitrogen cost",
        "Fresh-feed and recycle compressor electricity",
        "Illustrative refrigeration electricity",
        "Installed CapEx divided evenly by plant life; no discount rate is applied",
    ]
    hover_data = [[f"${value:,.2f}/t NH₃", note] for value, note in zip(values, notes, strict=True)]
    hover_data.append([f"${total:,.2f}/t NH₃", "Sum of the annualized cost contributions"])
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["relative"] * len(values) + ["total"],
            x=names + ["Total"],
            y=values + [0.0],
            text=[f"${value:,.0f}" for value in values] + [f"${total:,.0f}"],
            textposition="outside",
            customdata=hover_data,
            hovertemplate="<b>%{x}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
            connector=dict(line=dict(color=BORDER, width=1.5)),
            increasing=dict(marker=dict(color=TEAL)),
            totals=dict(marker=dict(color=BLUE)),
        )
    )
    fig.update_layout(
        title="Annualized production cost waterfall",
        xaxis_title="",
        yaxis_title="Cost (USD per tonne NH₃)",
        height=430,
        margin=dict(l=10, r=10, t=55, b=85),
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=NAVY),
    )
    fig.update_xaxes(linecolor=BORDER, tickangle=-20)
    fig.update_yaxes(gridcolor=GRID, linecolor=BORDER, zerolinecolor=BORDER)
    return fig


def make_sensitivity_figure(
    frame: pd.DataFrame,
    output_column: str,
    x_title: str,
    y_title: str,
    current_input_value: float,
    x_multiplier: float = 1.0,
    x_number_format: str = ",.2f",
    y_number_format: str = ",.0f",
) -> go.Figure:
    """Create one selectable input-output sensitivity chart."""

    valid = frame[frame["valid"]].copy()
    x = valid["input_value"] * x_multiplier
    current_x = current_input_value * x_multiplier
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=valid[output_column],
            mode="lines+markers",
            line=dict(color=TEAL, width=3),
            marker=dict(size=7, color=TEAL),
            hovertemplate=(
                f"{x_title}: %{{x:{x_number_format}}}<br>"
                f"{y_title}: %{{y:{y_number_format}}}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    fig.add_vline(
        x=current_x,
        line_dash="dot",
        line_color=NAVY,
        opacity=0.7,
        annotation_text="Current input",
        annotation_position="top",
    )
    fig.update_layout(
        title=dict(text=f"{y_title} vs. {x_title}", x=0.02),
        xaxis_title=x_title,
        yaxis_title=y_title,
        height=520,
        margin=dict(l=55, r=25, t=75, b=55),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=NAVY),
        hovermode="closest",
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=GRID, linecolor=BORDER, zerolinecolor=BORDER)
    return fig
