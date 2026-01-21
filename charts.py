import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import json

ss = st.session_state

def value_fig(seg: pd.DataFrame):
    if seg is None or seg.empty or "AddedValue" not in seg:
        return px.bar()
    return px.bar(seg, x="Segment", y="AddedValue", title="Added value by segment (€m/yr)")

def pax_hist_fig(seg: pd.DataFrame):
    if seg is None or len(seg) == 0:
        return px.bar()
    fig = px.bar(seg, x="Segment", y="Pax", title="Number of passengers by segment (million)")
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=50),
        height=300,
        title_font=dict(
            size=12,
            family="Arial",
            color="black"
        ),
        title = dict(
            x = 0.5,
            xanchor="center",

        )
    )
    return fig 

def employment_fig(seg: pd.DataFrame):
    if seg is None or seg.empty or "Jobs" not in seg:
        return px.bar()
    return px.bar(seg, x="Segment", y="Jobs", title="Employment by segment (direct jobs)")

def cargo_hist_fig(seg: pd.DataFrame):
    if seg is None or len(seg) == 0:
        return px.bar()
    fig = px.bar(seg, x="Segment", y="Cargo", title="Cargo volume by segment (million tons)")
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=50),
        height=300,
        title_font=dict(
            size=12,
            family="Arial",
            color="black"
        ),
        title = dict(
            x = 0.5,
            xanchor="center",

        )
    )
    return fig

def noise_choropleth_fig(gdf: pd.DataFrame, color_col: str = "diff"):
    """Create a choropleth from a GeoDataFrame with polygon geometry.
    Expects columns: geometry; and a numeric column to color by (default 'Lden_sim').
    If gdf is None or empty, return an empty placeholder figure.
    """
    
    if color_col not in gdf.columns:
        # fall back to 'Lden' if available
        color_col = "diff" if "diff" in gdf.columns else None
    if color_col is None:
        return px.choropleth_mapbox(pd.DataFrame(dict(dummy=[])), geojson={}, locations="dummy", mapbox_style="open-street-map", zoom=9, center=dict(lat=52.308, lon=4.764), opacity=0.6, color_continuous_scale=["red", "orange", "yellow", "green"])

    # Plotly needs a feature id; we'll use the index
    gdf = gdf.reset_index(drop=True)
    gdf["fid"] = gdf.index.astype(str)
    geojson = json.loads(gdf.to_json())

    center, zoom = _bounds_center_zoom(gdf)

    fig = px.choropleth_mapbox(
        gdf,
        geojson=geojson,
        locations="fid",
        color=color_col,
        mapbox_style="open-street-map",  # no token required
        center=center,
        zoom=zoom,
        opacity=0.6,
        color_continuous_scale=["green", "yellow",  "red"],
        color_continuous_midpoint=0,
        hover_data=['aantalInwoners'],
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig

def _bounds_center_zoom(gdf):
    minx, miny, maxx, maxy = gdf.total_bounds
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    # crude zoom heuristic: fit box
    area = (maxx - minx) * (maxy - miny)
    if area <= 0:
        return dict(lat=cy, lon=cx), 10
    if area < 0.01:
        z = 11
    elif area < 0.1:
        z = 10
    elif area < 1:
        z = 9
    else:
        z = 8
    return dict(lat=cy, lon=cx), z


def noise_hist_fig(ndf: pd.DataFrame):
    if ndf is None or len(ndf) == 0 or ("diff" not in ndf.columns and "Lden" not in ndf.columns):
        return px.histogram(pd.DataFrame(dict(Lden=[])), x="Lden", nbins=40, title="Distribution of Lden")
    col = "diff" if "diff" in ndf.columns else "Lden"
    fig = px.histogram(ndf, x=col, nbins=40, title="Distribution of Lden")
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=50),
        height=300,
        title_font=dict(
            size=12,
            family="Arial",
            color="black"
        ),
        title = dict(
            x = 0.5,
            xanchor="center",

        )
    )
    return fig
