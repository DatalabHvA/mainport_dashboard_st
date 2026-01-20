import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np

ss = st.session_state

@st.cache_data
def data_prep():
    scenarios = pd.read_excel('data/scenarios.xlsx').set_index('scenario')
    haul_dist = pd.read_excel('data/haul_distributions.xlsx').set_index('type')
    econ_fact = pd.read_excel('data/economische_factoren.xlsx').set_index('type')

    noise_gdf = gpd.read_feather('data/geluid_banen.ftr')
    noise_gdf['diff'] = noise_gdf['Lden_one'] - noise_gdf['Lden_two']

    return(scenarios, haul_dist, econ_fact, noise_gdf)


def calculate_kpis(slots, freight_pct, short_pct, medium_pct, long_pct):

    scenarios, haul_dist, econ_fact, noise_gdf = data_prep()
    noise_gdf['diff'] = noise_gdf['diff'] + (10 * np.log10(int(st.session_state.slots) / 478_000))
    SEGMENTS = [
        ("Passengers", "Short"), ("Passengers", "Medium"), ("Passengers", "Long"),
        ("Freight", "Short"), ("Freight", "Medium"), ("Freight", "Long"),
    ]

    HAUL_PAX = {"Short": haul_dist.loc['short haul pax']['num_passengers'], 
                "Medium": haul_dist.loc['medium haul pax']['num_passengers'], 
                "Long": haul_dist.loc['long haul pax']['num_passengers']}

    ADDED_VALUE_PER_SLOT = {
        ("Passengers", "Short"): haul_dist.loc['short haul pax']['num_passengers']*econ_fact.loc['pax']['added_value_schiphol'] + 
        haul_dist.loc['short haul pax']['num_passengers']*haul_dist.loc['short haul pax']['frac_tourist']*econ_fact.loc['pax']['added_value_tourist'] + 
        haul_dist.loc['short haul pax']['num_passengers']*haul_dist.loc['short haul pax']['frac_business']*econ_fact.loc['pax']['added_value_business'] + 
        haul_dist.loc['short haul pax']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'], 
        ("Passengers", "Medium"): haul_dist.loc['medium haul pax']['num_passengers']*econ_fact.loc['pax']['added_value_schiphol'] + 
        haul_dist.loc['medium haul pax']['num_passengers']*haul_dist.loc['medium haul pax']['frac_tourist']*econ_fact.loc['pax']['added_value_tourist'] + 
        haul_dist.loc['medium haul pax']['num_passengers']*haul_dist.loc['medium haul pax']['frac_business']*econ_fact.loc['pax']['added_value_business'] + 
        haul_dist.loc['medium haul pax']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'], 
        ("Passengers", "Long"): haul_dist.loc['long haul pax']['num_passengers']*econ_fact.loc['pax']['added_value_schiphol'] + 
        haul_dist.loc['long haul pax']['num_passengers']*haul_dist.loc['long haul pax']['frac_tourist']*econ_fact.loc['pax']['added_value_tourist'] + 
        haul_dist.loc['long haul pax']['num_passengers']*haul_dist.loc['long haul pax']['frac_business']*econ_fact.loc['pax']['added_value_business'] + 
        haul_dist.loc['long haul pax']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'],
        ("Freight", "Short"): haul_dist.loc['short haul cargo']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'], 
        ("Freight", "Medium"):  haul_dist.loc['medium haul cargo']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'], 
        ("Freight", "Long"):  haul_dist.loc['long haul cargo']['cargo_volume']*econ_fact.loc['cargo']['added_value_schiphol'],
    }
    EMPLOYMENT_PER_SLOT = {
        ("Passengers", "Short"): haul_dist.loc['short haul pax']['num_passengers']*econ_fact.loc['pax']['employment_schiphol'] + 
        haul_dist.loc['short haul pax']['num_passengers']*haul_dist.loc['short haul pax']['frac_tourist']*econ_fact.loc['pax']['employment_tourist'] + 
        haul_dist.loc['short haul pax']['num_passengers']*haul_dist.loc['short haul pax']['frac_business']*econ_fact.loc['pax']['employment_business'] + 
        haul_dist.loc['short haul pax']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'], 
        ("Passengers", "Medium"): haul_dist.loc['medium haul pax']['num_passengers']*econ_fact.loc['pax']['employment_schiphol'] + 
        haul_dist.loc['medium haul pax']['num_passengers']*haul_dist.loc['medium haul pax']['frac_tourist']*econ_fact.loc['pax']['employment_tourist'] + 
        haul_dist.loc['medium haul pax']['num_passengers']*haul_dist.loc['medium haul pax']['frac_business']*econ_fact.loc['pax']['employment_business'] + 
        haul_dist.loc['medium haul pax']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'], 
        ("Passengers", "Long"): haul_dist.loc['long haul pax']['num_passengers']*econ_fact.loc['pax']['employment_schiphol'] + 
        haul_dist.loc['long haul pax']['num_passengers']*haul_dist.loc['long haul pax']['frac_tourist']*econ_fact.loc['pax']['employment_tourist'] + 
        haul_dist.loc['long haul pax']['num_passengers']*haul_dist.loc['long haul pax']['frac_business']*econ_fact.loc['pax']['employment_business'] + 
        haul_dist.loc['long haul pax']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'],
        ("Freight", "Short"): haul_dist.loc['short haul cargo']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'], 
        ("Freight", "Medium"): haul_dist.loc['medium haul cargo']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'], 
        ("Freight", "Long"): haul_dist.loc['long haul cargo']['cargo_volume']*econ_fact.loc['cargo']['employment_schiphol'],
    }
    PAX_PER_SLOT = {
        ("Passengers", "Short"): haul_dist.loc['short haul pax']['num_passengers'], 
        ("Passengers", "Medium"): haul_dist.loc['medium haul pax']['num_passengers'], 
        ("Passengers", "Long"): haul_dist.loc['long haul pax']['num_passengers'],
        ("Freight", "Short"): 0, 
        ("Freight", "Medium"): 0, 
        ("Freight", "Long"): 0,
    }
    CARGO_PER_SLOT = {
        ("Passengers", "Short"): haul_dist.loc['short haul pax']['cargo_volume'], 
        ("Passengers", "Medium"): haul_dist.loc['medium haul pax']['cargo_volume'], 
        ("Passengers", "Long"): haul_dist.loc['long haul pax']['cargo_volume'],
        ("Freight", "Short"): haul_dist.loc['short haul cargo']['cargo_volume'], 
        ("Freight", "Medium"): haul_dist.loc['medium haul cargo']['cargo_volume'], 
        ("Freight", "Long"): haul_dist.loc['long haul cargo']['cargo_volume'],
    }

    INDIRECT_MULT = 1.9 
    slots = int(round(slots or 0)); freight_pct = int(round(freight_pct or 0)); short_pct = int(round(short_pct or 0)); medium_pct = int(round(medium_pct or 0))
    passengers_pct = max(0, 100 - freight_pct)
    long_pct = max(0, 100 - short_pct - medium_pct)

    path = ss.path

    seg_shares = {}
    for ptype, h in SEGMENTS:
        top = passengers_pct if ptype == "Passengers" else freight_pct
        haul_share = {"Short": short_pct, "Medium": medium_pct, "Long": long_pct}[h]
        seg_shares[(ptype, h)] = max(0, top)/100 * max(0, haul_share)/100

    results = []; total_va_direct = 0.0; total_jobs_direct = 0.0

    # Aggregate a simple noise intensity proxy based on fleet mix (nf)
    noise_intensity = 0.0

    for (ptype, h) in SEGMENTS:
        share = seg_shares[(ptype, h)]
        seg_slots = max(0.0, slots * share)
        row_label = f"{ptype} - {h}"

        va = seg_slots * ADDED_VALUE_PER_SLOT[(ptype, h)]
        jobs = seg_slots * EMPLOYMENT_PER_SLOT[(ptype, h)]
        total_va_direct += va; total_jobs_direct += jobs
        pax = seg_slots * PAX_PER_SLOT[(ptype, h)]/1000000
        cargo = seg_slots * CARGO_PER_SLOT[(ptype, h)]/1000000

        results.append(dict(Segment=row_label, Slots=seg_slots, AddedValue=va, Jobs=jobs, Pax = pax, Cargo = cargo))

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("AddedValue", ascending=False, inplace=True)

    # Choropleth path: if NOISE_GDF is provided, create a simulated Lden column responsive to scenario
    if noise_gdf is not None:
        noise_gdf = noise_gdf.copy()
        base_col = "diff"
        # scale around baseline: make a gentle 0-centered adjustment factor
        # normalizer based on default slots
        #default_slots = DEFAULTS["slots"]
        #scale = (noise_intensity / max(1.0, default_slots))
        # create simulated column used by the choropleth
        # KPI computation (households above threshold)
        homes_affected = int(noise_gdf.loc[noise_gdf["diff"] < -1]['aantalInwoners'].sum())
    else:
        # Fallback: no polygons; KPI 0 so user knows to load polygons
        homes_affected = 0

    va_indirect = total_va_direct * (INDIRECT_MULT-1)
    jobs_indirect = int(total_jobs_direct * (INDIRECT_MULT-1))

    total_cargo_freight = (slots*(freight_pct*short_pct/10000)*haul_dist.loc['short haul cargo']['cargo_volume'] + 
                   slots*(freight_pct*medium_pct/10000)*haul_dist.loc['medium haul cargo']['cargo_volume'] + 
                   slots*(freight_pct*(100-(short_pct+medium_pct))/10000)*haul_dist.loc['long haul cargo']['cargo_volume'])
    total_cargo_belly = ( +
                   slots*((100-freight_pct)*short_pct/10000)*haul_dist.loc['short haul pax']['cargo_volume'] + 
                   slots*((100-freight_pct)*medium_pct/10000)*haul_dist.loc['medium haul pax']['cargo_volume'] + 
                   slots*((100-freight_pct)*(100-(short_pct+medium_pct))/10000)*haul_dist.loc['long haul pax']['cargo_volume'])
    
    total_pax = (slots*((100-freight_pct)*short_pct/10000)*haul_dist.loc['short haul pax']['num_passengers'] + 
                   slots*((100-freight_pct)*medium_pct/10000)*haul_dist.loc['medium haul pax']['num_passengers'] + 
                   slots*((100-freight_pct)*(100-(short_pct+medium_pct))/10000)*haul_dist.loc['long haul pax']['num_passengers'] 
    )
    return dict(
        long_pct=long_pct,
        seg=df,
        homes=homes_affected,
        va_direct=total_va_direct/1000000,
        va_indirect=va_indirect/1000000,
        jobs_direct=int(total_jobs_direct),
        jobs_indirect=jobs_indirect,
        noise_gdf=noise_gdf,
        total_cargo_freight  = total_cargo_freight/1000000,
        total_cargo_belly =  total_cargo_belly/1000000,
        total_pax = total_pax/1000000
    )