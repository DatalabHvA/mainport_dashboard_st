# app.py
import streamlit as st
import re
import numpy as np
import pandas as pd
import plotly.express as px
from functions_app import * 
from import_data import calculate_kpis
from charts import *

st.set_page_config(page_title="Airport Scenario Explorer", layout="wide")
ss = st.session_state

# -----------------------------
# App
# -----------------------------

ensure_defaults()
css()

# Sidebar
with st.sidebar:
    st.markdown("### Scenario inputs")

    st.number_input(
        "Number of slots",
        min_value=200000,
        step=10_000,
        key="slots",
        on_change=apply_path_defaults_to_ui,  # top input influences defaults lower down
        bind="query-params",
    )
    
    st.slider(
        "Freight share (%)",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key="freight_share",
        on_change=apply_path_defaults_to_ui,  # top input influences defaults
    )

    st.selectbox(
        "Scenario",
        ["Hub optimized", "OD optimized", "Custom"],
        key="path",
        on_change=apply_path_defaults_to_ui,
    )

    st.markdown("**Haul distribution**")

    locked = st.session_state.path != "Custom"

    # Sliders are bound to ui_* keys only
    st.slider("Short-haul (%)", 0, 99, key="ui_short", disabled=locked)
    st.slider("Medium-haul (%)", 0, 100 - int(st.session_state.ui_short), key="ui_medium", disabled=locked)

    if locked:
        st.slider("Long-haul (%)", 0, 100, key="ui_long", disabled=True)
    else:
        # enforce sum=100 in custom
        enforce_sum_100_custom()
        st.slider("Long-haul (%)", 0, 100, key="ui_long", disabled=True)

    st.markdown("### Runway usage")

    with st.form(key=f"slots_form_v{st.session_state['form_version']}"):
        st.caption("Set fractions per runway (will be normalised to sum to 1 on submit).")

        # tijdelijke inputs (geen directe impact op model totdat je submit)
        tmp = {}
        fv = st.session_state['form_version']
        for r in ss.RUNWAYS:
            tmp[r] = st.number_input(
                r,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                value=round(float(st.session_state.runway_shares.get(r, 0.0)), 2),
                key=f"tmp_runway_{r}_v{fv}",
            )

        submitted = st.form_submit_button("Apply runway shares")

        if submitted:
            new = normalize_shares(tmp, ss.RUNWAYS)
            # schrijf genormaliseerde waarden terug
            st.session_state.runway_shares = new
            st.session_state["form_version"] += 1

            # 🔁 force rerun zodat de form opnieuw tekent met nieuwe defaults
            st.rerun()

    st.button("Reset", on_click=reset_all)

    st.markdown("### Reference scenario")
    if ss.get("pinned_label") and ss.pinned_label != "Starting situation":
        st.caption(f"Pinned: **{ss.pinned_label}**")
        col_pin, col_unpin = st.columns(2)
        with col_pin:
            st.button("Pin current", on_click=pin_scenario)
        with col_unpin:
            st.button("Unpin", on_click=unpin_scenario)
    else:
        st.caption("Reference: **Starting situation**")
        st.button("Pin current scenario", on_click=pin_scenario)

# Main layout: left content + right meta panel
left, right = st.columns([4.5, 1], gap="small")

with left:

    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.5rem; }
        h1, h2, h3 { margin-top: 0.0rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Airport Scenario Explorer")
    st.text_input(
        "Scenario title",
        key="scenario_title",
        label_visibility="collapsed",
        placeholder="Scenario title",
    )

    outputs = calculate_kpis(
        slots=int(st.session_state.slots),
        freight_pct=float(st.session_state.freight_share),
        short_pct=int(st.session_state.ui_short),
        medium_pct=int(st.session_state.ui_medium),
        long_pct=int(st.session_state.ui_long),
    )

    # Store current outputs for pinning; initialise baseline on first run
    ss.current_outputs = {k: v for k, v in outputs.items() if k != 'seg'}
    if ss.pinned_kpis is None:
        ss.pinned_kpis = dict(ss.current_outputs)
        ss.baseline_kpis = dict(ss.current_outputs)
        ss.pinned_label = "Starting situation"
    if "baseline_kpis" not in ss:
        ss.baseline_kpis = dict(ss.current_outputs)

    ref = ss.pinned_kpis  # reference for delta computation

    #fig_em_over = emissions_overview_fig(seg)
    fig_pax = pax_hist_fig(outputs['seg'])
    cargo_pax = cargo_hist_fig(outputs['seg']) 

    #fig_noise = noise_choropleth_fig(ss.noise_gdf, color_col="diff") 
    fig_hist = noise_hist_fig(ss.noise_gdf)
    fig_val = value_fig(outputs['seg'])
    fig_emp = employment_fig(outputs['seg'])

    # 8 KPI cards (2 rows x 4)
    r1 = st.columns(4, gap="small")
    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
    r2 = st.columns(4, gap="small")
    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
    r3 = st.columns(4, gap="small")

    with r1[0]:
        kpi_card("Lden lowered > 1dB (# people)", f"{outputs['homes']:,}",
                 sub=format_delta(outputs['homes'], ref.get('homes'), invert=False),
                 tooltip="This KPI shows the number of people whose aircraft noise exposure (Lden) decreases by more than 1 decibel compared to the baseline scenario")
    with r1[1]:
        kpi_card("Added value – direct (€m)", f"{outputs['va_direct']:,.1f}",
                 sub=format_delta(outputs['va_direct'], ref.get('va_direct')),
                 tooltip="This KPI represents the direct economic value added generated by the sector or activity, expressed in millions of euros.")
    with r1[2]:
        kpi_card("Added value – indirect (€m)", f"{outputs['va_indirect']:,.1f}",
                 sub=format_delta(outputs['va_indirect'], ref.get('va_indirect')),
                 tooltip="This KPI represents the indirect economic value added generated in the supply chain, expressed in millions of euros.")
    with r1[3]:
        kpi_card("Total passengers (millions)", f"{outputs['total_pax']:.3f}",
                 sub=format_delta(outputs['total_pax'], ref.get('total_pax')),
                 tooltip="This KPI represents the total number of passengers handled on Schiphol, expressed in millions of passengers per year.")

    with r2[0]:
        kpi_card("Employment – direct (jobs)", f"{outputs['jobs_direct']:,}",
                 sub=format_delta(outputs['jobs_direct'], ref.get('jobs_direct')),
                 tooltip="This KPI represents the number of jobs directly generated by the activities in the Schiphol cluster, measured as the total number of positions (jobs).")
    with r2[1]:
        kpi_card("Employment – indirect (jobs)", f"{outputs['jobs_indirect']:,}",
                 sub=format_delta(outputs['jobs_indirect'], ref.get('jobs_indirect')),
                 tooltip="This KPI represents the number of jobs indirectly generated by the activities in the Schiphol cluster, measured as the total number of positions (jobs).")
    with r2[2]:
        kpi_card("Freight Cargo volume (M tons)", f"{outputs['total_cargo_freight']:.4f}",
                 sub=format_delta(outputs['total_cargo_freight'], ref.get('total_cargo_freight')),
                 tooltip="This KPI represents the total volume of air freight transported by full freight flights, expressed in millions of metric tons per year.")
    with r2[3]:
        kpi_card("Belly Cargo volume (M tons)", f"{outputs['total_cargo_belly']:.3f}",
                 sub=format_delta(outputs['total_cargo_belly'], ref.get('total_cargo_belly')),
                 tooltip="This KPI represents the total volume of air freight transported as belly cargo, expressed in millions of metric tons per year.")

    with r3[0]:
        kpi_card("Netwerk quality cargo", f"{outputs['netwerk']:,}",
                 sub=format_delta(outputs['netwerk'], ref.get('netwerk')),
                 tooltip="Network quailty is the product of network breadth (number of destinations weighed with GaWC score) and network depth (volume/frequency of the connections).")
    with r3[1]:
        kpi_card("Population > 50db", f"{outputs['pop_above50']:,}",
                 sub=format_delta(outputs['pop_above50'], ref.get('pop_above50'), invert=True),
                 tooltip="This KPI shows the number of people who are highly annoyed by aircraft noise exposure (Lden) - 50dB.")
    with r3[2]:
        kpi_card("Population > 45db", f"{outputs['pop_above45']:,}",
                 sub=format_delta(outputs['pop_above45'], ref.get('pop_above45'), invert=True),
                 tooltip="This KPI shows the number of people whose aircraft noise exposure (Lden) is higher than the WHO guideline of 45dB.")


    st.markdown("")

    # Two charts
    c1, c2, c3 = st.columns([1.2, 1.2, 1.2], gap="small")

    with c1:
        st.plotly_chart(fig_pax, width='stretch')

    with c2:
        st.plotly_chart(cargo_pax, width='stretch')

    with c3:
        st.plotly_chart(fig_hist, width='stretch')

    # Tabs with extra graphs
    tab1, tab2, tab3, tab4 = st.tabs(["Noise map (Lden)", "Added value", "Employment", "WGI"])

    with tab1:
        st.radio(
            "Color by",
            options=["diff", "Lden"],
            key='ui_sound'
        )
        st.plotly_chart(noise_choropleth_fig(ss.noise_gdf, color_col=ss.ui_sound), width='stretch')

    with tab2:
        st.plotly_chart(fig_val, width='stretch')

    with tab3:
        st.plotly_chart(fig_emp, width='stretch')
    
    with tab4:
        fig = px.choropleth(
        ss.wgi_data, locations="iso3", color="governance_score",
        color_continuous_scale=["#d62728", "#ffbf00", "#2ca02c"],  # red→yellow→green
        range_color=(0, 1), projection="natural earth",
        hover_name="country", hover_data={'iso3':False, "governance_score" : ':.2f'}
        )
        fig.update_layout(
            height=600, margin=dict(l=10, r=10, t=30, b=10),
            coloraxis_colorbar=dict(title="Stabiliteit")
        )
        st.plotly_chart(fig, width='stretch')

with right:

    st.markdown("<div style='height: 7.2rem;'></div>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="meta-card" style="margin-top:-10px;">
          <div style="font-size:1.05rem; font-weight:650; margin-bottom:10px;">
            {st.session_state.scenario_title or "My Airport Scenario"}
          </div>
          <div style="font-size:0.9rem; color:rgba(49,51,63,0.75); margin-bottom:6px;">
            Shareable link
          </div>
          <div class="small-mono">/share/{slugify(st.session_state.scenario_title)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")
    st.button("Share", disabled=True)
