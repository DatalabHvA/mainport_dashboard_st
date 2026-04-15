# app.py
import streamlit as st
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from functions_app import *
from import_data import calculate_kpis
from charts import *

# Cargo category dropdown mapping: label → column prefix
CARGO_CATEGORIES = {
    "Totaal": None,
    "Perishables": "Perishables",
    "Fashion & textiel": "Fashion_en_textiel",
    "Machines & elektronica": "Machines_en_elektronica",
    "Transport": "Transport",
    "Pharma": "Pharma",
    "Industrie & materialen": "Industrie_en_materialen",
    "Low value bulk": "Low_value_bulk",
    "Overig": "Overig",
}

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
        # Compute baseline with DEFAULT values so that shared URLs with
        # e.g. ?slots=500000 still show delta vs the starting situation.
        # Uses the same constants as reset_all() and ensure_defaults().
        default_haul = scenario_defaults(DEFAULT_PATH, DEFAULT_SLOTS, DEFAULT_FREIGHT_SHARE)
        # Temporarily swap in default runway shares for baseline noise computation
        saved_runway = ss.runway_shares
        ss.runway_shares = default_runway_shares()
        baseline_outputs = calculate_kpis(
            slots=DEFAULT_SLOTS,
            freight_pct=DEFAULT_FREIGHT_SHARE,
            short_pct=default_haul["short"],
            medium_pct=default_haul["medium"],
            long_pct=default_haul["long"],
        )
        ss.runway_shares = saved_runway  # restore user's runway shares
        baseline_out = {k: v for k, v in baseline_outputs.items() if k != 'seg'}
        ss.pinned_kpis = dict(baseline_out)
        ss.baseline_kpis = dict(baseline_out)
        ss.pinned_label = "Starting situation"
        # Store baseline noise scenario for unpin
        ss.pinned_noise = ss.noise_gdf['scenario'].copy()
        ss.baseline_noise = ss.noise_gdf['scenario'].copy()
        # Re-run calculate_kpis with actual inputs to restore current scenario state
        outputs = calculate_kpis(
            slots=int(st.session_state.slots),
            freight_pct=float(st.session_state.freight_share),
            short_pct=int(st.session_state.ui_short),
            medium_pct=int(st.session_state.ui_medium),
            long_pct=int(st.session_state.ui_long),
        )
        ss.current_outputs = {k: v for k, v in outputs.items() if k != 'seg'}
    if "baseline_kpis" not in ss:
        ss.baseline_kpis = dict(ss.current_outputs)
    if "pinned_noise" not in ss:
        ss.pinned_noise = ss.noise_gdf['normal'].copy()
        ss.baseline_noise = ss.noise_gdf['normal'].copy()

    ref = ss.pinned_kpis  # reference for delta computation

    #fig_em_over = emissions_overview_fig(seg)
    fig_pax = pax_hist_fig(outputs['seg'])
    cargo_pax = cargo_hist_fig(outputs['seg']) 

    #fig_noise = noise_choropleth_fig(ss.noise_gdf, color_col="diff") 
    fig_hist = noise_hist_fig(ss.noise_gdf)
    fig_val = value_fig(outputs['seg'])
    fig_emp = employment_fig(outputs['seg'])

    # KPI cards in compact grid with coloured left borders per category
    # Order: General → Strategic Autonomy → Economy → Environment
    r1 = st.columns(4, gap="small")
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    r2 = st.columns(4, gap="small")
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    r3 = st.columns(4, gap="small")

    # Row 1: General (blue) × 3 + Strategic Autonomy (purple) × 1
    with r1[0]:
        kpi_card("Total passengers (millions)", f"{outputs['total_pax']:.3f}",
                 sub=format_delta(outputs['total_pax'], ref.get('total_pax')),
                 tooltip="This KPI represents the total number of passengers handled on Schiphol, expressed in millions of passengers per year.",
                 category="general")
    with r1[1]:
        kpi_card("Freight Cargo volume (M tons)", f"{outputs['total_cargo_freight']:.4f}",
                 sub=format_delta(outputs['total_cargo_freight'], ref.get('total_cargo_freight')),
                 tooltip="This KPI represents the total volume of air freight transported by full freight flights, expressed in millions of metric tons per year.",
                 category="general")
    with r1[2]:
        kpi_card("Belly Cargo volume (M tons)", f"{outputs['total_cargo_belly']:.3f}",
                 sub=format_delta(outputs['total_cargo_belly'], ref.get('total_cargo_belly')),
                 tooltip="This KPI represents the total volume of air freight transported as belly cargo, expressed in millions of metric tons per year.",
                 category="general")
    with r1[3]:
        netwerk = int(outputs['netwerkbreedte'] * outputs['netwerkdiepte'])
        ref_netwerk = int(ref.get('netwerkbreedte', 0) * ref.get('netwerkdiepte', 0)) if ref.get('netwerkbreedte') else None
        kpi_card("Netwerk quality cargo", f"{netwerk:,}",
                 sub=format_delta(netwerk, ref_netwerk),
                 tooltip="Network quality is the product of network breadth (number of destinations weighed with GaWC score) and network depth (volume/frequency of the connections). Reference numbers are DXB: 500k, LHR: 280k, FRA: 185k, IST: 170k, CDG: 160k, ZRH: 70k, BRU: 40k and DUS: 3k.",
                 category="strategic")

    # Row 2: Economy (green) × 4
    with r2[0]:
        kpi_card("Added value – direct (€m)", f"{outputs['va_direct']:,.1f}",
                 sub=format_delta(outputs['va_direct'], ref.get('va_direct')),
                 tooltip="This KPI represents the direct economic value added generated by the sector or activity, expressed in millions of euros.",
                 category="economy")
    with r2[1]:
        kpi_card("Added value – indirect (€m)", f"{outputs['va_indirect']:,.1f}",
                 sub=format_delta(outputs['va_indirect'], ref.get('va_indirect')),
                 tooltip="This KPI represents the indirect economic value added generated in the supply chain, expressed in millions of euros.",
                 category="economy")
    with r2[2]:
        kpi_card("Employment – direct (jobs)", f"{outputs['jobs_direct']:,}",
                 sub=format_delta(outputs['jobs_direct'], ref.get('jobs_direct')),
                 tooltip="This KPI represents the number of jobs directly generated by the activities in the Schiphol cluster, measured as the total number of positions (jobs).",
                 category="economy")
    with r2[3]:
        kpi_card("Employment – indirect (jobs)", f"{outputs['jobs_indirect']:,}",
                 sub=format_delta(outputs['jobs_indirect'], ref.get('jobs_indirect')),
                 tooltip="This KPI represents the number of jobs indirectly generated by the activities in the Schiphol cluster, measured as the total number of positions (jobs).",
                 category="economy")

    # Row 3: Environment (amber) × 2
    with r3[0]:
        kpi_card("Population > 50db", f"{outputs['pop_above50']:,}",
                 sub=format_delta(outputs['pop_above50'], ref.get('pop_above50'), invert=True),
                 tooltip="This KPI shows the number of people who are highly annoyed by aircraft noise exposure (Lden) - 50dB.",
                 category="environment")
    with r3[1]:
        kpi_card("Population > 45db", f"{outputs['pop_above45']:,}",
                 sub=format_delta(outputs['pop_above45'], ref.get('pop_above45'), invert=True),
                 tooltip="This KPI shows the number of people whose aircraft noise exposure (Lden) is higher than the WHO guideline of 45dB.",
                 category="environment")

    # Placeholder expanders for future categories (closed by default)
    col_left2, col_right2 = st.columns(2, gap="small")
    with col_left2:
        with st.expander("Connectivity", expanded=False):
            st.caption("KPIs coming soon.")
    with col_right2:
        with st.expander("Broad Prosperity", expanded=False):
            st.caption("KPIs coming soon.")

    color_expanders()

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
    tab1, tab2, tab3, tab4 = st.tabs(["Noise map (Lden)", "Added value", "Employment", "Cargo flows"])

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
        # Initialise excluded-country set in session state
        if 'wgi_excluded' not in ss:
            ss.wgi_excluded = set()

        # Category descriptions for tooltips
        CARGO_CAT_DESCRIPTIONS = {
            "Totaal": "Alle cargocategorieën samen.",
            "Perishables": "Landbouw, bosbouw, visserijproducten; Voedings- en genotmiddelen.",
            "Fashion & textiel": "Textiel, leer en producten daarvan.",
            "Machines & elektronica": "Machines en elektronica.",
            "Transport": "Transportmiddelen.",
            "Pharma": "Farmaceutica, chemische specialiteit.",
            "Industrie & materialen": "Kunststoffen en rubber; Basismetalen en metaalproducten.",
            "Low value bulk": "Aardolieproducten; Ertsen; Zout, zand, grind en klei; Overige minerale producten; Afval en secundaire grondstoffen.",
            "Overig": "Overige goederen.",
        }

        @st.fragment
        def cargo_fragment():
            df = ss.cargo_data

            col_dd, col_reset = st.columns([3, 1])
            with col_dd:
                selected_cat = st.selectbox(
                    "Cargo category",
                    list(CARGO_CATEGORIES.keys()),
                    key="cargo_category",
                    help="Select a cargo category to filter the map and KPIs.",
                )
            with col_reset:
                st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
                if st.button("Reset country selection", key="wgi_reset"):
                    ss.wgi_excluded = set()
                    st.rerun(scope="fragment")

            cat_prefix = CARGO_CATEGORIES[selected_cat]

            # Scale freight and belly independently based on slots and freight share
            # Base data assumes DEFAULT_FREIGHT_SHARE (5%) at 478k slots
            freight_pct = float(ss.freight_share)
            base_freight_slots = 478_000 * DEFAULT_FREIGHT_SHARE / 100
            base_belly_slots = 478_000 * (100 - DEFAULT_FREIGHT_SHARE) / 100
            new_freight_slots = int(ss.slots) * freight_pct / 100
            new_belly_slots = int(ss.slots) * (100 - freight_pct) / 100
            freight_scale = new_freight_slots / base_freight_slots if base_freight_slots > 0 else 1
            belly_scale = new_belly_slots / base_belly_slots if base_belly_slots > 0 else 1

            scaled = df.copy()
            # Scale freight flights and cargo
            for c in ['Arrivals full-freight', 'Departures full-freight',
                       'Cargo-in full freight (tons)', 'Cargo-out full freight (tons)']:
                scaled[c] = scaled[c] * freight_scale
            # Scale belly/passenger flights and cargo
            for c in ['Arrivals belly', 'Departures belly',
                       'Cargo-in belly (tons)', 'Cargo-out belly (tons)']:
                scaled[c] = scaled[c] * belly_scale
            # Total flights = freight + belly
            scaled['Arrivals total'] = scaled['Arrivals full-freight'] + scaled['Arrivals belly']
            scaled['Departures total'] = scaled['Departures full-freight'] + scaled['Departures belly']

            # Apply category fraction if a specific category is selected
            if cat_prefix is not None:
                frac_in = scaled[f'{cat_prefix}_fraction_in']
                frac_out = scaled[f'{cat_prefix}_fraction_out']
                scaled['Cargo-in full freight (tons)'] = scaled['Cargo-in full freight (tons)'] * frac_in
                scaled['Cargo-out full freight (tons)'] = scaled['Cargo-out full freight (tons)'] * frac_out
                scaled['Cargo-in belly (tons)'] = scaled['Cargo-in belly (tons)'] * frac_in
                scaled['Cargo-out belly (tons)'] = scaled['Cargo-out belly (tons)'] * frac_out

            scaled['cargo_in'] = scaled['Cargo-in full freight (tons)'] + scaled['Cargo-in belly (tons)']
            scaled['cargo_out'] = scaled['Cargo-out full freight (tons)'] + scaled['Cargo-out belly (tons)']

            # Compute euro value columns (tons × eur_per_ton per country)
            if cat_prefix is not None:
                eur_per_ton_in = df[f'{cat_prefix}_eur_per_ton_in']
                eur_per_ton_out = df[f'{cat_prefix}_eur_per_ton_out']
            else:
                # Totaal: weighted eur/ton = sum(fraction_i * eur_per_ton_i)
                all_prefixes = [v for v in CARGO_CATEGORIES.values() if v is not None]
                eur_per_ton_in = sum(
                    df[f'{p}_fraction_in'] * df[f'{p}_eur_per_ton_in'] for p in all_prefixes
                )
                eur_per_ton_out = sum(
                    df[f'{p}_fraction_out'] * df[f'{p}_eur_per_ton_out'] for p in all_prefixes
                )
            scaled['eur_freight_in'] = scaled['Cargo-in full freight (tons)'] * eur_per_ton_in
            scaled['eur_freight_out'] = scaled['Cargo-out full freight (tons)'] * eur_per_ton_out
            scaled['eur_belly_in'] = scaled['Cargo-in belly (tons)'] * eur_per_ton_in
            scaled['eur_belly_out'] = scaled['Cargo-out belly (tons)'] * eur_per_ton_out

            # Split into active and excluded dataframes
            active = scaled[~scaled['country'].isin(ss.wgi_excluded)].reset_index(drop=True)
            excluded_df = scaled[scaled['country'].isin(ss.wgi_excluded)].reset_index(drop=True)

            # Excluded flights are removed (not redistributed)
            # Compute available slots freed by excluded countries
            total_movements = scaled['Arrivals total'].sum() + scaled['Departures total'].sum()
            excluded_movements = excluded_df['Arrivals total'].sum() + excluded_df['Departures total'].sum() if len(excluded_df) > 0 else 0
            available_slots = int(round(excluded_movements / 2))

            if len(active) > 0:
                adj_freight_in = active['Cargo-in full freight (tons)'].sum()
                adj_freight_out = active['Cargo-out full freight (tons)'].sum()
                adj_belly_in = active['Cargo-in belly (tons)'].sum()
                adj_belly_out = active['Cargo-out belly (tons)'].sum()
                adj_eur_freight_in = active['eur_freight_in'].sum()
                adj_eur_freight_out = active['eur_freight_out'].sum()
                adj_eur_belly_in = active['eur_belly_in'].sum()
                adj_eur_belly_out = active['eur_belly_out'].sum()
            else:
                adj_freight_in = adj_freight_out = adj_belly_in = adj_belly_out = 0
                adj_eur_freight_in = adj_eur_freight_out = adj_eur_belly_in = adj_eur_belly_out = 0

            # Store cargo KPIs in current_outputs so pin/unpin works
            ss.current_outputs['cargo_freight_in'] = adj_freight_in
            ss.current_outputs['cargo_freight_out'] = adj_freight_out
            ss.current_outputs['cargo_belly_in'] = adj_belly_in
            ss.current_outputs['cargo_belly_out'] = adj_belly_out

            # Compute reference dynamically using pinned slots/freight_share
            ref_slots = int(ss.get('pinned_slots', DEFAULT_SLOTS))
            ref_freight_pct = float(ss.get('pinned_freight_share', DEFAULT_FREIGHT_SHARE))
            ref_freight_scale = (ref_slots * ref_freight_pct / 100) / (478_000 * DEFAULT_FREIGHT_SHARE / 100)
            ref_belly_scale = (ref_slots * (100 - ref_freight_pct) / 100) / (478_000 * (100 - DEFAULT_FREIGHT_SHARE) / 100)

            if cat_prefix is not None:
                frac_in_ref = df[f'{cat_prefix}_fraction_in']
                frac_out_ref = df[f'{cat_prefix}_fraction_out']
                eur_in_ref = df[f'{cat_prefix}_eur_per_ton_in']
                eur_out_ref = df[f'{cat_prefix}_eur_per_ton_out']
                ref_fi = df['Cargo-in full freight (tons)'] * frac_in_ref * ref_freight_scale
                ref_fo = df['Cargo-out full freight (tons)'] * frac_out_ref * ref_freight_scale
                ref_bi = df['Cargo-in belly (tons)'] * frac_in_ref * ref_belly_scale
                ref_bo = df['Cargo-out belly (tons)'] * frac_out_ref * ref_belly_scale
            else:
                all_prefixes = [v for v in CARGO_CATEGORIES.values() if v is not None]
                eur_in_ref = sum(df[f'{p}_fraction_in'] * df[f'{p}_eur_per_ton_in'] for p in all_prefixes)
                eur_out_ref = sum(df[f'{p}_fraction_out'] * df[f'{p}_eur_per_ton_out'] for p in all_prefixes)
                ref_fi = df['Cargo-in full freight (tons)'] * ref_freight_scale
                ref_fo = df['Cargo-out full freight (tons)'] * ref_freight_scale
                ref_bi = df['Cargo-in belly (tons)'] * ref_belly_scale
                ref_bo = df['Cargo-out belly (tons)'] * ref_belly_scale

            cat_ref = {
                'cargo_freight_in': ref_fi.sum(),
                'cargo_freight_out': ref_fo.sum(),
                'cargo_belly_in': ref_bi.sum(),
                'cargo_belly_out': ref_bo.sum(),
                'eur_freight_in': (ref_fi * eur_in_ref).sum(),
                'eur_freight_out': (ref_fo * eur_out_ref).sum(),
                'eur_belly_in': (ref_bi * eur_in_ref).sum(),
                'eur_belly_out': (ref_bo * eur_out_ref).sum(),
            }
            cat_label = selected_cat

            # Network quality KPI based on active countries
            # Use fraction of OAG cargo retained (active/total) applied to model cargo
            # This guarantees exact match with main page when no countries are excluded
            total_oag_freight = scaled['Cargo-in full freight (tons)'].sum() + scaled['Cargo-out full freight (tons)'].sum()
            total_oag_belly = scaled['Cargo-in belly (tons)'].sum() + scaled['Cargo-out belly (tons)'].sum()
            frac_freight = (adj_freight_in + adj_freight_out) / total_oag_freight if total_oag_freight > 0 else 1.0
            frac_belly = (adj_belly_in + adj_belly_out) / total_oag_belly if total_oag_belly > 0 else 1.0
            # Model cargo from calculate_kpis (M tons)
            model_freight_M = ss.current_outputs.get('total_cargo_freight', 0)
            model_belly_M = ss.current_outputs.get('total_cargo_belly', 0)
            adj_cargo_M = max(0, model_freight_M * frac_freight + model_belly_M * frac_belly)
            cargo_nb = ss.current_outputs.get('netwerkbreedte', 0.378)
            cargo_nd = 274442 * np.sqrt(adj_cargo_M) + 31513
            cargo_nwk = int(cargo_nb * cargo_nd)
            # Reference: main page pinned NWK (all countries, pinned scenario)
            ref_nwk = int(ss.pinned_kpis.get('netwerkbreedte', 0) * ss.pinned_kpis.get('netwerkdiepte', 0)) if ss.pinned_kpis and ss.pinned_kpis.get('netwerkbreedte') else None

            # Top row: network quality + available slots (if countries excluded)
            if available_slots > 0:
                top_cols = st.columns([1, 1, 2], gap="small")
            else:
                top_cols = st.columns([1, 3], gap="small")
            with top_cols[0]:
                kpi_card(
                    "Network quality cargo",
                    f"{cargo_nwk:,}",
                    sub=format_delta(cargo_nwk, ref_nwk),
                    tooltip="Network quality is the product of network breadth and network depth (Σ√cargo×GaWC). Adjusted for excluded countries. Reference: DXB 500k, LHR 280k, FRA 185k, IST 170k, CDG 160k.",
                    category="strategic"
                )
            if available_slots > 0:
                with top_cols[1]:
                    kpi_card(
                        "Available slots",
                        f"{available_slots:,}",
                        sub=f"from {len(ss.wgi_excluded)} excluded countries",
                        tooltip="Flight movements freed up by excluding countries. These slots are available for reallocation.",
                        category="strategic"
                    )
            st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

            # KPIs: freight and belly, in and out (delta vs category baseline)
            kpi_cols = st.columns(4, gap="small")
            with kpi_cols[0]:
                kpi_card(
                    f"Freight capacity in – {cat_label}",
                    fmt_readable(adj_freight_in, suffix=" t"),
                    sub=format_delta(adj_freight_in, cat_ref['cargo_freight_in']),
                    tooltip=f"Incoming full-freight cargo capacity in tons. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with kpi_cols[1]:
                kpi_card(
                    f"Freight capacity out – {cat_label}",
                    fmt_readable(adj_freight_out, suffix=" t"),
                    sub=format_delta(adj_freight_out, cat_ref['cargo_freight_out']),
                    tooltip=f"Outgoing full-freight cargo capacity in tons. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with kpi_cols[2]:
                kpi_card(
                    f"Belly capacity in – {cat_label}",
                    fmt_readable(adj_belly_in, suffix=" t"),
                    sub=format_delta(adj_belly_in, cat_ref['cargo_belly_in']),
                    tooltip=f"Incoming belly cargo capacity in tons. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with kpi_cols[3]:
                kpi_card(
                    f"Belly capacity out – {cat_label}",
                    fmt_readable(adj_belly_out, suffix=" t"),
                    sub=format_delta(adj_belly_out, cat_ref['cargo_belly_out']),
                    tooltip=f"Outgoing belly cargo capacity in tons. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )

            # Euro value KPIs
            st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
            eur_cols = st.columns(4, gap="small")
            with eur_cols[0]:
                kpi_card(
                    f"Freight value in – {cat_label}",
                    fmt_readable(adj_eur_freight_in, prefix="€"),
                    sub=format_delta(adj_eur_freight_in, cat_ref.get('eur_freight_in')),
                    tooltip=f"Value of incoming full-freight cargo. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with eur_cols[1]:
                kpi_card(
                    f"Freight value out – {cat_label}",
                    fmt_readable(adj_eur_freight_out, prefix="€"),
                    sub=format_delta(adj_eur_freight_out, cat_ref.get('eur_freight_out')),
                    tooltip=f"Value of outgoing full-freight cargo. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with eur_cols[2]:
                kpi_card(
                    f"Belly value in – {cat_label}",
                    fmt_readable(adj_eur_belly_in, prefix="€"),
                    sub=format_delta(adj_eur_belly_in, cat_ref.get('eur_belly_in')),
                    tooltip=f"Value of incoming belly cargo. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )
            with eur_cols[3]:
                kpi_card(
                    f"Belly value out – {cat_label}",
                    fmt_readable(adj_eur_belly_out, prefix="€"),
                    sub=format_delta(adj_eur_belly_out, cat_ref.get('eur_belly_out')),
                    tooltip=f"Value of outgoing belly cargo. {CARGO_CAT_DESCRIPTIONS.get(selected_cat, '')}",
                    category="strategic"
                )

            # Build figure: colour by total cargo (in + out)
            fig = go.Figure()

            # Helper: build customdata and hovertemplate for a dataframe
            def _cargo_customdata(d):
                nan = float('nan')
                avg_freight_in = (d['Cargo-in full freight (tons)'] / d['Arrivals full-freight'].replace(0, nan)).fillna(0)
                avg_freight_out = (d['Cargo-out full freight (tons)'] / d['Departures full-freight'].replace(0, nan)).fillna(0)
                avg_belly_in = (d['Cargo-in belly (tons)'] / d['Arrivals belly'].replace(0, nan)).fillna(0)
                avg_belly_out = (d['Cargo-out belly (tons)'] / d['Departures belly'].replace(0, nan)).fillna(0)
                return np.column_stack([
                    d['Arrivals full-freight'], d['Departures full-freight'],
                    d['Cargo-in full freight (tons)'], d['Cargo-out full freight (tons)'],
                    avg_freight_in, avg_freight_out,
                    d['Arrivals belly'], d['Departures belly'],
                    d['Cargo-in belly (tons)'], d['Cargo-out belly (tons)'],
                    avg_belly_in, avg_belly_out,
                ])

            _hover = (
                '%{text}<br>'
                '<b>Freight</b>  Arr: %{customdata[0]:,.0f} · Dep: %{customdata[1]:,.0f}<br>'
                '  Capacity in: %{customdata[2]:,.0f} t · out: %{customdata[3]:,.0f} t<br>'
                '  Avg/flight in: %{customdata[4]:,.1f} t · out: %{customdata[5]:,.1f} t<br>'
                '<b>Belly</b>  Arr: %{customdata[6]:,.0f} · Dep: %{customdata[7]:,.0f}<br>'
                '  Capacity in: %{customdata[8]:,.0f} t · out: %{customdata[9]:,.0f} t<br>'
                '  Avg/flight in: %{customdata[10]:,.1f} t · out: %{customdata[11]:,.1f} t'
                '<extra></extra>'
            )

            # Trace 0: active countries
            active_total_cargo = active['cargo_in'] + active['cargo_out']
            fig.add_trace(go.Choropleth(
                locations=active['iso3'],
                z=active_total_cargo,
                text=active['country'],
                customdata=_cargo_customdata(active),
                colorscale="YlOrRd",
                hovertemplate=_hover,
                colorbar=dict(title="Cargo capacity (tons)"),
                marker_line_width=0.5,
            ))

            # Trace 1: excluded countries (grey)
            if len(excluded_df) > 0:
                excluded_total_cargo = excluded_df['cargo_in'] + excluded_df['cargo_out']
                fig.add_trace(go.Choropleth(
                    locations=excluded_df['iso3'],
                    z=excluded_total_cargo,
                    text=excluded_df['country'],
                    customdata=_cargo_customdata(excluded_df),
                    colorscale=[[0, '#d3d3d3'], [1, '#d3d3d3']],
                    hovertemplate=_hover.replace('%{text}', '%{text} (excluded)'),
                    showscale=False,
                    marker_line_width=0.5,
                ))

            fig.update_layout(
                height=600, margin=dict(l=10, r=10, t=30, b=10),
                geo=dict(projection_type="natural earth"),
            )

            event = st.plotly_chart(fig, on_select="rerun", key="wgi_chart", selection_mode=["points"])

            # Process map clicks: toggle countries between active ↔ excluded
            if event and event.selection and len(event.selection.points) > 0:
                changed = False
                for point in event.selection.points:
                    curve = point.get("curve_number", point.get("curveNumber", 0))
                    idx = point.get("point_number", point.get("pointNumber", point.get("pointIndex", 0)))
                    if curve == 0 and idx < len(active):
                        ss.wgi_excluded.add(active.iloc[idx]['country'])
                        changed = True
                    elif curve == 1 and idx < len(excluded_df):
                        ss.wgi_excluded.discard(excluded_df.iloc[idx]['country'])
                        changed = True
                if changed:
                    st.rerun(scope="fragment")

        cargo_fragment()

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
