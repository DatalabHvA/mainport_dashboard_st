import streamlit as st
import numpy as np
import re
import pandas as pd
import geopandas as gpd

ss = st.session_state

# -----------------------------
# Shared default constants (single source of truth)
# -----------------------------
DEFAULT_SLOTS = 478_000
DEFAULT_FREIGHT_SHARE = 5.0
DEFAULT_PATH = "Hub optimized"
DEFAULT_RUNWAY_COUNTS = {
    "Polderbaan": 763,
    "Zwanenburgbaan": 2058,
    "Buitenveldertbaan": 1944,
    "Oostbaan": 467,
    "Aalsmeerbaan": 1322,
    "Kaagbaan": 3110,
}
DEFAULT_SCENARIO_TITLE = "My Airport Scenario"

# -----------------------------
# Helpers
# -----------------------------

def default_runway_shares():
    """Return normalised default runway shares (single source of truth)."""
    RUNWAYS = list(DEFAULT_RUNWAY_COUNTS.keys())
    return normalize_shares(dict(DEFAULT_RUNWAY_COUNTS), RUNWAYS)


def ensure_defaults():
    if "scenario_title" not in st.session_state:
        st.session_state.scenario_title = DEFAULT_SCENARIO_TITLE

    if "slots" not in st.session_state:
        st.session_state.slots = DEFAULT_SLOTS

    if "ui_sound" not in st.session_state:
        st.session_state.ui_sound = 'Lden'

    if "freight_share" not in st.session_state:
        st.session_state.freight_share = DEFAULT_FREIGHT_SHARE

    if "path" not in st.session_state:
        st.session_state.path = DEFAULT_PATH

    if 'scenarios' not in ss:
        ss.scenarios = pd.read_excel('data/scenarios.xlsx').set_index('scenario')

    if 'cargo_data' not in ss:
        ss.cargo_data = pd.read_csv('data/combined_country_cargo_per_category.csv')
        ss.cargo_data['cargo_in'] = ss.cargo_data['Cargo-in full freight (tons)'] + ss.cargo_data['Cargo-in belly (tons)']
        ss.cargo_data['cargo_out'] = ss.cargo_data['Cargo-out full freight (tons)'] + ss.cargo_data['Cargo-out belly (tons)']

    if 'haul_dist' not in ss:
        ss.haul_dist = pd.read_excel('data/haul_distributions.xlsx').set_index('type')

    if 'econ_fact' not in ss:
        ss.econ_fact = pd.read_excel('data/economische_factoren.xlsx').set_index('type')

    if 'form_version' not in ss:
        ss.form_version = 0

    if "RUNWAYS" not in ss:
        ss.RUNWAYS = list(DEFAULT_RUNWAY_COUNTS.keys())

    if "runway_shares" not in st.session_state:
        st.session_state.runway_shares = default_runway_shares()

    # UI haul keys – always compute from DEFAULTS on first run so baseline is
    # independent of any query-param overrides that haven't been applied yet.
    if "ui_short" not in st.session_state or "ui_medium" not in st.session_state or "ui_long" not in st.session_state:
        d0 = scenario_defaults(st.session_state.get("path", DEFAULT_PATH),
                               int(st.session_state.get("slots", DEFAULT_SLOTS)),
                               float(st.session_state.get("freight_share", DEFAULT_FREIGHT_SHARE)))
        st.session_state.ui_short = d0["short"]
        st.session_state.ui_medium = d0["medium"]
        st.session_state.ui_long = d0["long"]

    if "pinned_kpis" not in ss:
        ss.pinned_kpis = None  # will be set after first calculate_kpis

    if "pinned_label" not in ss:
        ss.pinned_label = "Starting situation"

    if 'noise_gdf' not in ss:
        default_shares = default_runway_shares()
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
                                             weights = [default_shares['Polderbaan'],
                                                        default_shares['Zwanenburgbaan'],
                                                        default_shares['Buitenveldertbaan'],
                                                        default_shares['Oostbaan'],
                                                        default_shares['Aalsmeerbaan'],
                                                        default_shares['Kaagbaan']],
                                             slots=DEFAULT_SLOTS)
        

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
            max(slots - 478_000,0)*scenarios.loc[path]['short haul increase']/1000 +
            max(478_000- slots,0)*scenarios.loc[path]['short haul decrease']/1000)
        medium_slots = (478_000*haul_distributions.loc['medium haul pax']['base_slot_frac'] +
            max(slots - 478_000,0)*scenarios.loc[path]['medium haul increase']/1000 +
            max(478_000- slots,0)*scenarios.loc[path]['medium haul decrease']/1000)
        long_slots = (478_000*haul_distributions.loc['long haul pax']['base_slot_frac'] +
            max(slots - 478_000,0)*scenarios.loc[path]['long haul increase']/1000 +
            max(478_000- slots,0)*scenarios.loc[path]['long haul decrease']/1000)
        short = 100*short_slots/slots
        medium = 100*medium_slots/slots
        long = 100*long_slots/slots

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
    st.markdown("""
    <style>
    .kpi-card{
        position: relative;
        background: white;
        border: 1px solid rgba(49,51,63,0.2);
        border-radius: 10px;
        padding: 14px 14px 10px 14px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        min-height: 108px;
    }

    .kpi-title{
        font-size: 0.78rem;
        color: rgba(49,51,63,0.75);
        margin-bottom: 4px;
        line-height: 1.25;
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

    .kpi-info{
        position: absolute;
        top: 8px;
        right: 8px;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: rgba(49,51,63,0.08);
        color: rgba(49,51,63,0.8);
        font-size: 12px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: help;
        z-index: 2;
    }

    .kpi-info:hover::after{
        content: attr(data-tooltip);
        position: absolute;
        top: 24px;
        right: 0;
        width: 220px;
        background: rgba(49,51,63,0.96);
        color: white;
        padding: 8px 10px;
        border-radius: 8px;
        font-size: 12px;
        line-height: 1.35;
        font-weight: 400;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18);
        white-space: normal;
    }
    /* --- coloured expanders ------------------------------------------------ */
    div[data-testid="stExpander"] {
        border: none;
        border-radius: 10px;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    div[data-testid="stExpander"] details {
        border: none !important;
        border-radius: 10px;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 10px 14px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)


def color_expanders():
    """Inject JS that colours expanders based on their label text."""
    st.markdown("""
    <script>
    const COLORS = {
        'General':            '#e8f0fe',
        'Economy':            '#e6f4ea',
        'Environment':        '#fef7e0',
        'Strategic Autonomy': '#f3e8fd',
        'Connectivity':       '#e0f2f1',
        'Broad Prosperity':   '#fce4ec',
    };
    function paintExpanders() {
        document.querySelectorAll('[data-testid="stExpander"]').forEach(el => {
            const summary = el.querySelector('summary span');
            if (!summary) return;
            const label = summary.textContent.trim();
            if (COLORS[label]) {
                const details = el.querySelector('details');
                if (details) details.style.background = COLORS[label];
            }
        });
    }
    // run after DOM settles
    setTimeout(paintExpanders, 200);
    new MutationObserver(paintExpanders)
        .observe(document.body, {childList: true, subtree: true});
    </script>
    """, unsafe_allow_html=True)


CAT_COLORS = {
    "general":   "#4285F4",   # blue
    "economy":   "#34A853",   # green
    "environment": "#F9AB00", # amber
    "strategic": "#9334E6",   # purple
    "connectivity": "#00897B",# teal
    "prosperity": "#E91E63",  # rose
}

def kpi_card(title: str, value: str, sub: str = "", tooltip = "Dit is extra uitleg over deze KPI.", category: str = ""):
    border_style = ""
    if category and category in CAT_COLORS:
        c = CAT_COLORS[category]
        border_style = f"border-left: 4px solid {c};"
    st.markdown(
        f"""
        <div class="kpi-card" style="{border_style}">
          <div class="kpi-info" data-tooltip="{tooltip}">i</div>
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


def fmt_readable(value, prefix="", suffix=""):
    """Format a large number to a readable string like 1.2M or 345K."""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        s = f"{value / 1_000_000_000:,.1f}B"
    elif abs_val >= 1_000_000:
        s = f"{value / 1_000_000:,.1f}M"
    elif abs_val >= 1_000:
        s = f"{value / 1_000:,.1f}K"
    else:
        s = f"{value:,.0f}"
    return f"{prefix}{s}{suffix}"


def format_delta(current, pinned, invert=False):
    """Return HTML snippet showing % change from pinned reference.
    invert=True means lower is better (e.g. noise population).
    """
    if pinned is None:
        return ""
    diff = current - pinned
    if abs(pinned) > 0:
        pct = (diff / abs(pinned)) * 100
    else:
        pct = 0.0 if diff == 0 else 100.0

    if abs(pct) < 0.05:
        return '<span style="color:#888;font-size:0.78rem;">&#8212; no change</span>'

    is_good = (diff > 0) if not invert else (diff < 0)
    arrow = "&#9650;" if diff > 0 else "&#9660;"
    color = "#2ca02c" if is_good else "#d62728"
    sign = "+" if pct > 0 else ""
    return f'<span style="color:{color};font-weight:600;font-size:0.78rem;">{arrow} {sign}{pct:.1f}%</span>'


def pin_scenario():
    """Pin the current outputs as the reference for delta comparison."""
    if "current_outputs" in ss:
        ss.pinned_kpis = dict(ss.current_outputs)
        ss.pinned_label = ss.scenario_title or "Pinned scenario"
    # Pin current noise scenario as reference for diff
    if "noise_gdf" in ss and "scenario" in ss.noise_gdf.columns:
        ss.pinned_noise = ss.noise_gdf['scenario'].copy()


def unpin_scenario():
    """Reset reference back to starting situation."""
    if "baseline_kpis" in ss:
        ss.pinned_kpis = dict(ss.baseline_kpis)
        ss.pinned_label = "Starting situation"
    # Reset noise reference back to baseline
    if "baseline_noise" in ss:
        ss.pinned_noise = ss.baseline_noise.copy()


def reset_all():
    st.session_state.scenario_title = DEFAULT_SCENARIO_TITLE
    st.session_state.slots = DEFAULT_SLOTS
    st.session_state.freight_share = DEFAULT_FREIGHT_SHARE
    st.session_state.path = DEFAULT_PATH
    d0 = scenario_defaults(DEFAULT_PATH, DEFAULT_SLOTS, DEFAULT_FREIGHT_SHARE)
    st.session_state.ui_short = d0["short"]
    st.session_state.ui_medium = d0["medium"]
    st.session_state.ui_long = d0["long"]
    st.session_state.runway_shares = default_runway_shares()
    st.session_state["form_version"] += 1
    # Reset cargo tab excluded countries
    if "wgi_excluded" in st.session_state:
        st.session_state.wgi_excluded = set()


def combine_lden_df_weighted(df, cols, weights, normalize_weights=True, slots=None):
    if slots is None:
        slots = ss.slots
    w = np.asarray(weights, dtype=float)
    if normalize_weights:
        w = w / w.sum()

    print(w)

    reference = [763, 2058, 1944, 467, 1322, 3110]

    w = [(sum([763, 2058, 1944, 467, 1322, 3110])/478_000)*weight*slots/reference[i] for i, weight in enumerate(w)]

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
