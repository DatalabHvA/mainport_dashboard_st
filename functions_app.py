import streamlit as st
import re
from import_data import data_prep

ss = st.session_state

# -----------------------------
# Helpers
# -----------------------------

def ensure_defaults():
    if "scenario_title" not in st.session_state:
        st.session_state.scenario_title = "My Airport Scenario"

    if "slots" not in st.session_state:
        st.session_state.slots = 478_000

    if "freight_share" not in st.session_state:
        st.session_state.freight_share = 5.0

    if "path" not in st.session_state:
        st.session_state.path = "Hub optimized"
    # UI haul keys
    if "ui_short" not in st.session_state or "ui_medium" not in st.session_state or "ui_long" not in st.session_state:
        d0 = scenario_defaults(st.session_state.path, int(st.session_state.slots), float(st.session_state.freight_share))
        st.session_state.ui_short = d0["short"]
        st.session_state.ui_medium = d0["medium"]
        st.session_state.ui_long = d0["long"]

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
    This is demo logic — replace with your real rules.
    """
    if path in ("Hub optimized", "OD optimized"):
        scenarios = data_prep()[0]
        haul_distributions = data_prep()[1]

        short_slots = (478_000*haul_distributions.loc['short haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['short haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['short haul decrease']/1000) 
        print(short_slots)
        medium_slots = (478_000*haul_distributions.loc['medium haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['medium haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['medium haul decrease']/1000)
        print(medium_slots)
        long_slots = (478_000*haul_distributions.loc['long haul pax']['base_slot_frac'] + 
            max(ss.slots - 478_000,0)*scenarios.loc[path]['long haul increase']/1000 + 
            max(478_000- ss.slots,0)*scenarios.loc[path]['long haul decrease']/1000)
        print(long_slots)
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

