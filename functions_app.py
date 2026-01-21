import streamlit as st
import numpy as np
import re
import pandas as pd
import geopandas as gpd

ss = st.session_state

# -----------------------------
# Helpers
# -----------------------------

def ensure_defaults():
    if "scenario_title" not in st.session_state:
        st.session_state.scenario_title = "My Airport Scenario"

    if "slots" not in st.session_state:
        st.session_state.slots = 478_000

    if "ui_sound" not in st.session_state:
        st.session_state.ui_sound = 'diff'

    if "freight_share" not in st.session_state:
        st.session_state.freight_share = 5.0

    if "path" not in st.session_state:
        st.session_state.path = "Hub optimized"

    if 'scenarios' not in ss: 
        ss.scenarios = pd.read_excel('data/scenarios.xlsx').set_index('scenario')
    
    if 'wgi_data' not in ss:
        ss.wgi_data = pd.read_excel('data/wgi_governance_scores_2023_with_iso3.xlsx')

    if 'haul_dist' not in ss:
        ss.haul_dist = pd.read_excel('data/haul_distributions.xlsx').set_index('type')
    
    if 'econ_fact' not in ss: 
        ss.econ_fact = pd.read_excel('data/economische_factoren.xlsx').set_index('type')

    # UI haul keys
    if "ui_short" not in st.session_state or "ui_medium" not in st.session_state or "ui_long" not in st.session_state:
        d0 = scenario_defaults(st.session_state.path, int(st.session_state.slots), float(st.session_state.freight_share))
        st.session_state.ui_short = d0["short"]
        st.session_state.ui_medium = d0["medium"]
        st.session_state.ui_long = d0["long"]
    
    if "RUNWAYS" not in ss:
        ss.RUNWAYS  = [
            "Polderbaan",
            "Zwanenburgbaan",
            "Buitenveldertbaan",
            "Oostbaan",
            "Aalsmeerbaan",
            "Kaagbaan",
        ]

    if "runway_shares" not in st.session_state:
        # gelijke startverdeling
        st.session_state.runway_shares = normalize_shares({
            "Polderbaan" : 763,
            "Zwanenburgbaan" : 2058,
            "Buitenveldertbaan" : 1944,
            "Oostbaan" : 467,
            "Aalsmeerbaan" : 1322,
            "Kaagbaan" : 3110
        }, ss.RUNWAYS)

    if 'noise_gdf' not in ss:
        ss.noise_gdf = gpd.read_feather('data/geluid_banen.ftr')
        ss.noise_gdf['aantalInwoners'] = np.where(ss.noise_gdf['aantalInwoners'] < 0, 0, ss.noise_gdf['aantalInwoners'])
        ss.noise_gdf['normal'] = combine_lden_df_weighted(df = ss.noise_gdf, 
                                             cols = [
                                                        "Lden_Polderbaan",
                                                        "Lden_Zwanenburgbaan",
                                                        "Lden_Buitenveldertbaan",
                                                        "Lden_Oostbaan",
                                                        "Lden_Aalsmeerbaan",
                                                        "Lden_Kaagbaan",
                                                    ], 
                                             weights = [ss.runway_shares['Polderbaan'], 
                                                        ss.runway_shares['Zwanenburgbaan'],
                                                        ss.runway_shares['Buitenveldertbaan'],
                                                        ss.runway_shares['Oostbaan'],
                                                        ss.runway_shares['Aalsmeerbaan'],
                                                        ss.runway_shares['Kaagbaan']])
        

def normalize_shares(shares, keys):
    vals = np.array([max(0.0, shares[k]) for k in keys], dtype=float)
    s = vals.sum()

    if s <= 0:
        vals[:] = 1.0 / len(vals)
    else:
        vals /= s

    return dict(zip(keys, vals))

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text or "my-airport-scenario"

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def scenario_defaults(path: str, slots: int, freight_share: float) -> dict:
    """
    Return default haul shares based on path + top inputs.
    This is demo logic — replace with real rules.
    """
    if path in ("Hub optimized", "OD optimized"):
        scenarios = ss.scenarios
        haul_distributions = ss.haul_dist

        short_slots = (478_000*haul_distributions.loc['short haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['short haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['short haul decrease']/1000) 
        print('short slots', short_slots)
        medium_slots = (478_000*haul_distributions.loc['medium haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['medium haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['medium haul decrease']/1000)
        print('medium slots', medium_slots)
        long_slots = (478_000*haul_distributions.loc['long haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['long haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['long haul decrease']/1000)
        print('long slots', long_slots)
        short = 100*short_slots/ss.slots
        medium = 100*medium_slots/ss.slots
        long = 100*long_slots/ss.slots

    else:  # Custom (won't be used for locking; we keep current UI)
        short = st.session_state.get("ui_short", 40)
        medium = st.session_state.get("ui_medium", 30)
        long = 100 - short - medium

    return {"short": int(short), "medium": int(medium), "long": int(long)}

def apply_path_defaults_to_ui():
    ensure_defaults()
    d = scenario_defaults(st.session_state.path, int(st.session_state.slots), float(st.session_state.freight_share))
    st.session_state.ui_short = d["short"]
    st.session_state.ui_medium = d["medium"]
    st.session_state.ui_long = d["long"]

def enforce_sum_100_custom():
    """
    In Custom mode, long is derived as 100 - short - medium.
    Also prevents short+medium > 100 by clamping medium.
    """
    s = int(st.session_state.ui_short)
    m = int(st.session_state.ui_medium)

    if s + m > 100:
        st.session_state.ui_medium = max(0, 100 - s)
        m = int(st.session_state.ui_medium)

    st.session_state.ui_long = int(clamp(100 - s - m, 0, 100))

def css():
    st.markdown(
        """
        <style>
        .kpi-card{
            background: white;
            border: 1px solid rgba(49,51,63,0.2);
            border-radius: 10px;
            padding: 14px 14px 10px 14px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06);
            height: 92px;
        }
        .kpi-title{
            font-size: 0.85rem;
            color: rgba(49,51,63,0.75);
            margin-bottom: 4px;
        }
        .kpi-value{
            font-size: 1.65rem;
            font-weight: 650;
            line-height: 1.05;
            color: rgba(49,51,63,0.95);
        }
        .kpi-sub{
            margin-top: 6px;
            font-size: 0.8rem;
            color: rgba(49,51,63,0.65);
        }
        .meta-card{
            background: white;
            border: 1px solid rgba(49,51,63,0.2);
            border-radius: 10px;
            padding: 14px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        }
        .small-mono{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            color: #C2185B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(title: str, value: str, sub: str = ""):
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-title">{title}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Safe state pattern:
# - widgets use ui_* keys
# - we never set widget-bound keys after instantiation in the same run
# -----------------------------


def reset_all():
    st.session_state.scenario_title = "My Airport Scenario"
    st.session_state.slots = 478_000
    st.session_state.freight_share = 5.0
    st.session_state.path = "Hub optimized"
    d0 = scenario_defaults("Hub optimized", 478_000, 5.0)
    st.session_state.ui_short = d0["short"]
    st.session_state.ui_medium = d0["medium"]
    st.session_state.ui_long = d0["long"]
    n = len(ss.RUNWAYS)
    st.session_state.runway_shares = normalize_shares({
            "Polderbaan" : 763,
            "Zwanenburgbaan" : 2058,
            "Buitenveldertbaan" : 1944,
            "Oostbaan" : 467,
            "Aalsmeerbaan" : 1322,
            "Kaagbaan" : 3110
        }, ss.RUNWAYS)


def combine_lden_df_weighted(df, cols, weights, normalize_weights=True):
    w = np.asarray(weights, dtype=float)
    if normalize_weights:
        w = w / w.sum()
    
    print(w)

    reference = [763, 2058, 1944, 467, 1322, 3110]

    w = [(sum([763, 2058, 1944, 467, 1322, 3110])/478_000)*weight*ss.slots/reference[i] for i, weight in enumerate(w)]

    print(w)

    L = df[cols].to_numpy(dtype=np.float64, copy=False)   # shape (n_rows, n_cols)
    # energy per cell:
    E = 10.0 ** (L / 10.0)
    # weighted sum per row:
    Ew = E @ w
    return 10.0 * np.log10(Ew)

def delta_lden_from_haul_mix(
    N_short: float, N_med: float, N_long: float,
    N_short_new: float, N_med_new: float, N_long_new: float,
    dL_med_minus_short: float = 0.2838603921484293,
    dL_long_minus_short: float = 1.3974990345316523,
) -> float:
    """
    Same as above but returns only the change in Lden (dB).
    Useful if you want to apply it to many baseline levels.
    """
    rM = 10 ** (dL_med_minus_short / 10.0)
    rL = 10 ** (dL_long_minus_short / 10.0)

    E_base = N_short + rM * N_med + rL * N_long
    E_new  = N_short_new + rM * N_med_new + rL * N_long_new

    if E_base <= 0 or E_new <= 0:
        raise ValueError("Energy totals must be positive. Check slot counts and inputs.")

    return float(10.0 * np.log10(E_new / E_base))
