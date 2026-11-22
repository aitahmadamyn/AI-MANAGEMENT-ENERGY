"""
Interactive Plotly time-series, comparison charts, and energy flow diagrams.
Strictly preserves separation between electrical (kW_e/kWh_e) and thermal (kW_th/kWh_th).
"""

from __future__ import annotations

from typing import Any, Dict, List

import plotly.graph_objects as go
import streamlit as st


def render_energy_flow_sankey(
    pv_elec_kw: float,
    pv_base_load_kw: float,
    pv_heater_elec_kw: float,
    solar_thermal_kw: float,
    ncg_recovered_kw: float,
    sand_charge_kw: float,
    sand_discharge_kw: float,
    aux_heating_kw: float,
    dryer_demand_kw: float,
) -> None:
    """Render clear dual-domain Energy Flow Sankey keeping kW_e and kW_th distinct."""
    labels = [
        f"PV Array ({pv_elec_kw:.1f} kW_e)",
        f"Plant Base Load ({min(pv_elec_kw, pv_base_load_kw):.1f} kW_e)",
        f"PV Resistance Heater ({pv_heater_elec_kw:.1f} kW_e)",
        f"Solar Thermal Collector ({solar_thermal_kw:.1f} kW_th)",
        f"Pyrolysis NCG Burner ({ncg_recovered_kw:.1f} kW_th)",
        "Sand Thermal Storage (kW_th)",
        f"Auxiliary Thermal Backup ({aux_heating_kw:.1f} kW_th)",
        f"Indirect Biomass Dryer ({dryer_demand_kw:.1f} kW_th)",
    ]

    direct_ncg = min(dryer_demand_kw, ncg_recovered_kw)
    direct_sol = min(max(0.0, dryer_demand_kw - direct_ncg), solar_thermal_kw)

    sources = [0, 0, 2, 3, 3, 4, 4, 5, 6]
    targets = [1, 2, 5, 7, 5, 7, 5, 7, 7]
    values = [
        max(0.01, min(pv_elec_kw, pv_base_load_kw)),
        max(0.01, pv_heater_elec_kw),
        max(0.01, pv_heater_elec_kw * 0.98),
        max(0.01, direct_sol),
        max(0.01, max(0.0, solar_thermal_kw - direct_sol)),
        max(0.01, direct_ncg),
        max(0.01, max(0.0, ncg_recovered_kw - direct_ncg)),
        max(0.01, sand_discharge_kw),
        max(0.01, aux_heating_kw),
    ]

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=16,
                    thickness=18,
                    line=dict(color="#334155", width=0.5),
                    label=labels,
                    color=["#0284c7", "#64748b", "#0ea5e9", "#f59e0b", "#10b981", "#d97706", "#e11d48", "#0f172a"],
                ),
                link=dict(source=sources, target=targets, value=values),
            )
        ]
    )
    fig.update_layout(
        title_text="Plant Energy Flow Topology (Electrical kW_e vs. Thermal kW_th Kept Separate)",
        font_size=11,
        height=380,
        margin=dict(l=16, r=16, t=44, b=16),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_timeseries_dual_line(
    timestamps: List[str],
    series_a: List[float],
    name_a: str,
    series_b: List[float],
    name_b: str,
    title: str,
    yaxis_title: str,
) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=timestamps, y=series_a, mode="lines", name=name_a, line=dict(color="#0284c7", width=2)))
    fig.add_trace(go.Scatter(x=timestamps, y=series_b, mode="lines", name=name_b, line=dict(color="#0f766e", width=2, dash="dash")))
    fig.update_layout(
        title=title,
        xaxis_title="UTC Timestamp",
        yaxis_title=yaxis_title,
        height=340,
        margin=dict(l=45, r=20, t=42, b=36),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_strategy_bar_comparison(scenarios: List[Dict[str, Any]]) -> None:
    names = [s["title"] for s in scenarios]
    aux_a = [s["strategy_a"]["auxiliary_heating_kwh_th"] for s in scenarios]
    aux_b = [s["strategy_b"]["auxiliary_heating_kwh_th"] for s in scenarios]

    fig = go.Figure(
        data=[
            go.Bar(name="Strategy A: Rule-Based (kWh_th)", x=names, y=aux_a, marker_color="#64748b"),
            go.Bar(name="Strategy B: Forecast AI (kWh_th)", x=names, y=aux_b, marker_color="#0284c7"),
        ]
    )
    fig.update_layout(
        barmode="group",
        title="Auxiliary Heating Required across Identical 168h 2023 Scenarios (Lower is Better)",
        yaxis_title="Auxiliary Heat (kWh_th)",
        height=360,
        margin=dict(l=45, r=20, t=48, b=60),
    )
    st.plotly_chart(fig, use_container_width=True)
