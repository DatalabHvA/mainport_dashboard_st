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
        min_value=0,
        step=10_000,
        key="slots",
        on_change=apply_path_defaults_to_ui,  # top input influences defaults lower down
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
    st.slider("Short-haul (%)", 0, 100, key="ui_short", disabled=locked)
    st.slider("Medium-haul (%)", 0, 100 - int(st.session_state.ui_short), key="ui_medium", disabled=locked)

    if locked:
        st.slider("Long-haul (%)", 0, 100, key="ui_long", disabled=True)
    else:
        # enforce sum=100 in custom
        enforce_sum_100_custom()
        st.slider("Long-haul (%)", 0, 100, key="ui_long", disabled=True)

    st.markdown("### Runway usage")

    with st.form("runway_form", clear_on_submit=False):
        st.caption("Set fractions per runway (will be normalised to sum to 1 on submit).")

        # tijdelijke inputs (geen directe impact op model totdat je submit)
        tmp = {}
        for r in ss.RUNWAYS:
            tmp[r] = st.number_input(
                r,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                format="%.2f",
                value=float(st.session_state.runway_shares.get(r, 0.0)),
                key=f"tmp_runway_{r}",
            )

        submitted = st.form_submit_button("Apply runway shares")

        if submitted:
            new = normalize_shares(tmp, ss.RUNWAYS)

            # schrijf genormaliseerde waarden terug
            st.session_state.runway_shares = new

            # 🔁 force rerun zodat de form opnieuw tekent met nieuwe defaults
            st.rerun()

    st.button("Reset", on_click=reset_all)

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
    noise = data_prep()[3]
    noise['diff'] = noise['diff'] + (10 * np.log10(int(st.session_state.slots) / 478_000))
    #fig_em_over = emissions_overview_fig(seg)
    fig_pax = pax_hist_fig(outputs['seg']) 
    cargo_pax = cargo_hist_fig(outputs['seg']) 

    fig_noise = noise_choropleth_fig(noise, color_col="Lden_sim") 
    fig_hist = noise_hist_fig(noise)
    fig_val = value_fig(outputs['seg'])
    fig_emp = employment_fig(outputs['seg'])

    # 8 KPI cards (2 rows x 4)
    r1 = st.columns(4, gap="small")
    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
    r2 = st.columns(4, gap="small")

    with r1[0]:
        kpi_card("Lden lowered > 1dB (# people)", f"{outputs['homes']:,}")
    with r1[1]:
        kpi_card("Added value – direct (€m)", f"{outputs['va_direct']:,.1f}")
    with r1[2]:
        kpi_card("Added value – indirect (€m)", f"{outputs['va_indirect']:,.1f}")
    with r1[3]:
        kpi_card("Total passengers (millions)", f"{outputs['total_pax']:.3f}")

    with r2[0]:
        kpi_card("Employment – direct (jobs)", f"{outputs['jobs_direct']:,}")
    with r2[1]:
        kpi_card("Employment – indirect (jobs)", f"{outputs['jobs_indirect']:,}")
    with r2[2]:
        kpi_card("Freight Cargo volume (M tons)", f"{outputs['total_cargo_freight']:.4f}")
    with r2[3]:
        kpi_card("Belly Cargo volume (M tons)", f"{outputs['total_cargo_belly']:.3f}")

    st.markdown("")

    # Two charts
    c1, c2, c3 = st.columns([1.2, 1.2, 1.2], gap="small")

    with c1:
        st.plotly_chart(fig_pax, use_container_width=True)

    with c2:
        st.plotly_chart(cargo_pax, use_container_width=True)

    with c3:
        st.plotly_chart(fig_hist, use_container_width=True)

    # Tabs with extra graphs
    tab1, tab2, tab3, tab4 = st.tabs(["Noise map (Lden)", "Added value", "Employment", "WGI"])

    with tab1:
        st.plotly_chart(fig_noise, use_container_width=True)

    with tab2:
        st.plotly_chart(fig_val, use_container_width=True)

    with tab3:
        st.plotly_chart(fig_emp, use_container_width=True)
    
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
        st.plotly_chart(fig, use_container_width=True)

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
