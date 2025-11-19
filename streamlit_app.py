import pandas as pd
import numpy as np
from pathlib import Path

import streamlit as st
import plotly.express as px

# -----------------------------------------------------------
# Load data
# -----------------------------------------------------------
DATA_DIR = Path(__file__).parent

arthro_path = DATA_DIR / "41_core_arthropods.csv"
sites_path  = DATA_DIR / "arthros_temporal.csv"
landuse_path = DATA_DIR / "site_landuse_from_nlcd.csv"

arth = pd.read_csv(arthro_path)
sites = pd.read_csv(sites_path)
landuse_map = pd.read_csv(landuse_path)

# -----------------------------------------------------------
# Preprocess data
# -----------------------------------------------------------
if "sample_date" in arth.columns:
    arth["sample_date"] = pd.to_datetime(arth["sample_date"], errors="coerce")

if "count" in arth.columns:
    arth["count"] = pd.to_numeric(arth["count"], errors="coerce").fillna(0).astype(int)

for col in ["site_code", "display_name", "trap_name", "observer",
            "comments", "flags", "authority"]:
    if col in arth.columns:
        arth[col] = arth[col].astype(str).str.strip()

# Site lat/long lookup
lat_col = next((c for c in ["lat", "latitude", "Lat", "Latitude"]
                if c in sites.columns), None)
lon_col = next((c for c in ["long", "lon", "longitude", "Longitude", "Long"]
                if c in sites.columns), None)

if lat_col and lon_col and "site_code" in sites.columns:
    site_lookup = (
        sites.dropna(subset=["site_code", lat_col, lon_col])
             .drop_duplicates("site_code")[["site_code", lat_col, lon_col]]
             .rename(columns={lat_col: "lat", lon_col: "lon"})
    )
else:
    site_lookup = pd.DataFrame(columns=["site_code", "lat", "lon"])

arth = arth.merge(site_lookup, on="site_code", how="left")

# Attach NLCD-derived land use
arth = arth.merge(
    landuse_map[["site_code", "landuse"]],
    on="site_code",
    how="left"
)

arth["region3"] = arth["landuse"].fillna("Unknown")

# Derived fields
if "sample_date" in arth.columns:
    arth["year"] = arth["sample_date"].dt.year
    arth["month"] = arth["sample_date"].dt.to_period("M").astype(str)
    arth["quarter"] = "Q" + arth["sample_date"].dt.quarter.astype("Int64").astype(str)

taxon_col = "display_name" if "display_name" in arth.columns else None

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------
def top_taxa(df: pd.DataFrame, n=20):
    if taxon_col is None or df.empty:
        return []
    tot = df.groupby(taxon_col)["count"].sum().sort_values(ascending=False)
    return tot.head(n).index.tolist()

def apply_filters(df, sites, taxa, years):
    g = df.copy()
    if sites:
        g = g[g["site_code"].isin(sites)]
    if taxa and taxon_col:
        g = g[g[taxon_col].isin(taxa)]
    if years and "year" in g.columns:
        g = g[g["year"].isin(years)]
    return g

# -----------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------
st.set_page_config(page_title="CAPLTER Arthropods Dashboard", layout="wide")

st.title("CAPLTER Arthropods Dashboard")
st.markdown(
    "Explore long-term ecological trends in arthropod communities "
    "across CAPLTER sites."
)

# ---- sidebar filters ----
st.sidebar.header("Filters")

site_values = sorted(arth["site_code"].dropna().unique()) if "site_code" in arth.columns else []
taxa_values = top_taxa(arth, 100) if taxon_col else []
year_values = sorted(arth["year"].dropna().unique()) if "year" in arth.columns else []

selected_sites = st.sidebar.multiselect("Sites", options=site_values, default=[])
selected_taxa  = st.sidebar.multiselect("Taxa (top 100 by total count)",
                                        options=taxa_values, default=[])
selected_years = st.sidebar.multiselect(
    "Year",
    options=[int(y) for y in year_values],
    default=[]
)

# Filtered data
g = apply_filters(arth, selected_sites, selected_taxa, selected_years)

st.caption(
    f"Records: {len(g):,} | "
    f"Sites: {g['site_code'].nunique() if 'site_code' in g.columns else 0} | "
    f"Taxa: {g[taxon_col].nunique() if taxon_col and not g.empty else 0}"
)

# -----------------------------------------------------------
# 1) Community composition (top 10 taxa stacked bar)
# -----------------------------------------------------------
st.subheader("Community composition (top 10 taxa)")

comp = g.copy()
if taxon_col and not comp.empty:
    top_local = top_taxa(comp, n=10)
    comp[taxon_col] = np.where(comp[taxon_col].isin(top_local),
                               comp[taxon_col],
                               "Other")
    comp_agg = comp.groupby(["site_code", taxon_col])["count"].sum().reset_index()
    comp_fig = px.bar(
        comp_agg,
        x="site_code",
        y="count",
        color=taxon_col,
        barmode="stack",
        labels={"site_code": "Site", "count": "Total count", taxon_col: "Taxon"},
    )
    st.plotly_chart(comp_fig, use_container_width=True)
else:
    st.info("No taxa available for the selected filters.")

# -----------------------------------------------------------
# 2) Quarterly abundance by land use
# -----------------------------------------------------------
st.subheader("Quarterly abundance by Land use")

if {"region3", "quarter", "count"}.issubset(g.columns) and not g.empty:
    lu_agg = (
        g.groupby(["region3", "quarter"], dropna=False)["count"]
         .sum()
         .reset_index()
    )
    q_order = ["Q1", "Q2", "Q3", "Q4"]
    lu_agg["quarter"] = pd.Categorical(lu_agg["quarter"],
                                       categories=q_order,
                                       ordered=True)
    lu_agg = lu_agg.sort_values(["region3", "quarter"])
    landuse_fig = px.bar(
        lu_agg,
        x="region3",
        y="count",
        color="quarter",
        barmode="group",
        labels={"region3": "Region", "count": "Total count", "quarter": "Quarter"},
    )
    st.plotly_chart(landuse_fig, use_container_width=True)
else:
    st.info("No land use / quarter data available for the selected filters.")

# -----------------------------------------------------------
# 3) Site map (bubble size = total counts)
# -----------------------------------------------------------
st.subheader("Sites (bubble size = total counts)")

if {"lat","lon"}.issubset(g.columns) and not g[["lat","lon"]].dropna().empty:
    m = g.groupby(["site_code","lat","lon"], dropna=True)["count"].sum().reset_index()
    map_fig = px.scatter_mapbox(
        m,
        lat="lat",
        lon="lon",
        size="count",
        hover_name="site_code",
        zoom=9,
        height=800,
    )
    map_fig.update_traces(marker=dict(color="purple"))
    map_fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(map_fig, use_container_width=True)
else:
    st.info("No geospatial data available for the selected filters.")
