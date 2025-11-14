import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter

import dash
from dash import Dash, dcc, html, Input, Output, State, dash_table
import plotly.express as px

# ---------- Load Data ----------
DATA_DIR = Path(__file__).parent

arthro_path = DATA_DIR / "41_core_arthropods.csv"
sites_path = DATA_DIR / "arthros_temporal.csv"
landuse_path = DATA_DIR / "site_landuse_from_nlcd.csv"
landuse_map = pd.read_csv(landuse_path)

arth = pd.read_csv(arthro_path)
sites = pd.read_csv(sites_path)

# Normalize columns
if "sample_date" in arth.columns:
    arth["sample_date"] = pd.to_datetime(arth["sample_date"], errors="coerce")
if "count" in arth.columns:
    arth["count"] = pd.to_numeric(arth["count"], errors="coerce").fillna(0).astype(int)

# Clean strings
for col in ["site_code","display_name","trap_name","observer","comments","flags","authority"]:
    if col in arth.columns:
        arth[col] = arth[col].astype(str).str.strip()

# Site lat/long lookup
site_lookup = None
lat_col = None
lon_col = None
for cand in ["lat","latitude","Lat","Latitude"]:
    if cand in sites.columns:
        lat_col = cand
        break
for cand in ["long","lon","longitude","Longitude","Long"]:
    if cand in sites.columns:
        lon_col = cand
        break
if lat_col and lon_col and "site_code" in sites.columns:
    site_lookup = sites.dropna(subset=["site_code", lat_col, lon_col]).drop_duplicates("site_code")[["site_code", lat_col, lon_col]]
    site_lookup = site_lookup.rename(columns={lat_col:"lat", lon_col:"lon"})
else:
    site_lookup = pd.DataFrame(columns=["site_code","lat","lon"])

arth = arth.merge(site_lookup, on="site_code", how="left")

# Attach NLCD-derived land use to each record
# (landuse already collapsed to Urban / Desert / Agricultural / Other in R)
arth = arth.merge(
    landuse_map[["site_code", "landuse"]],
    on="site_code",
    how="left"
)

# Use this directly as our 3-region field
arth["region3"] = arth["landuse"].fillna("Unknown")

# Derived fields
if "sample_date" in arth.columns:
    arth["year"] = arth["sample_date"].dt.year
    arth["month"] = arth["sample_date"].dt.to_period("M").astype(str)
    arth["quarter"] = "Q" + arth["sample_date"].dt.quarter.astype("Int64").astype(str)

taxon_col = "display_name" if "display_name" in arth.columns else None

# ---------- Helper functions ----------
def shannon_index(counts: np.ndarray) -> float:
    counts = counts[counts > 0]
    if counts.size == 0:
        return 0.0
    p = counts / counts.sum()
    return -np.sum(p * np.log(p))

def compute_diversity(df: pd.DataFrame) -> pd.DataFrame:
    # diversity per site per year
    if taxon_col is None or "year" not in df.columns:
        return pd.DataFrame(columns=["site_code","year","richness","shannon"])
    grouped = df.groupby(["site_code","year"])
    rows = []
    for (site, yr), g in grouped:
        # species richness: unique taxa
        richness = g[taxon_col].nunique(dropna=True)
        # shannon index by taxa
        counts = g.groupby(taxon_col)["count"].sum().values
        sh = shannon_index(counts.astype(float)) if counts.size else 0.0
        rows.append({"site_code": site, "year": int(yr), "richness": int(richness), "shannon": sh})
    return pd.DataFrame(rows)

def top_taxa(df: pd.DataFrame, n=20):
    if taxon_col is None:
        return []
    tot = df.groupby(taxon_col)["count"].sum().sort_values(ascending=False)
    return tot.head(n).index.tolist()

# ---------- Filter options ----------
site_options = (
    [{"label": s, "value": s} for s in sorted(arth["site_code"].dropna().unique())]
    if "site_code" in arth.columns else []
)
taxa_options = (
    [{"label": t, "value": t} for t in top_taxa(arth, 100)]
    if taxon_col else []
)
trap_options = (
    [{"label": t, "value": t} for t in sorted(arth["trap_name"].dropna().unique())]
    if "trap_name" in arth.columns else []
)

min_date = pd.to_datetime(arth["sample_date"].min()) if "sample_date" in arth.columns else None
max_date = pd.to_datetime(arth["sample_date"].max()) if "sample_date" in arth.columns else None

# ---------- App ----------
app = Dash(__name__)
server = app.server

app.title = "CAP LTER Arthropods Dashboard"

app.layout = html.Div([
    html.H1("CAP LTER Arthropods Dashboard"),
    html.P("Explore long-term ecological trends in arthropod communities across CAP LTER sites."),
    html.Div([
        html.Div([
            html.Label("Sites"),
            dcc.Dropdown(id="site-select", options=site_options, multi=True, placeholder="All sites"),
            html.Label("Taxa (top 100 by total count)"),
            dcc.Dropdown(id="taxa-select", options=taxa_options, multi=True, placeholder="All taxa"),
            html.Label("Trap"),
            dcc.Dropdown(id="trap-select", options=trap_options, multi=True, placeholder="All traps"),
            html.Label("Date range"),
            dcc.DatePickerRange(
                id="date-range",
                min_date_allowed=min_date,
                max_date_allowed=max_date,
                start_date=min_date,
                end_date=max_date
            ),
            html.Br(),
            html.Button("Apply filters", id="apply", n_clicks=0),
        ], style={"flex": "1", "minWidth":"280px", "padding":"12px"}),
        html.Div([
            html.Div([
                dcc.Graph(id="ts-abundance"),
            ], style={"marginBottom":"20px"}),
            html.Div([
                dcc.Graph(id="diversity"),
            ], style={"marginBottom":"20px"}),
            html.Div([
                dcc.Graph(id="composition"),
            ], style={"marginBottom":"20px"}),
            html.Div([
                dcc.Graph(id="landuse-quarter"),
            ], style={"marginBottom":"20px"}),
            html.Div([
                dcc.Graph(id="site-map"),
            ]),
        ], style={"flex": "3", "padding":"12px"}),
    ], style={"display":"flex", "gap":"12px", "alignItems":"stretch"}),
    html.Hr(),
    html.H2("Data explorer"),
    dash_table.DataTable(
        id="table",
        columns=[{"name": c, "id": c} for c in arth.columns],
        page_current=0,
        page_size=15,
        page_action="native",
        filter_action="native",
        sort_action="native",
        style_table={"overflowX":"auto"},
        style_cell={"fontFamily":"Inter, system-ui, sans-serif", "fontSize":"12px", "padding":"6px"},
        style_header={"fontWeight":"bold"}
    ),
    html.Div(id="record-count", style={"marginTop":"8px"})
], style={"maxWidth":"1400px","margin":"0 auto","fontFamily":"Inter, system-ui, sans-serif"})

def apply_filters(df, sites, taxa, traps, start_date, end_date):
    g = df.copy()
    if sites:
        g = g[g["site_code"].isin(sites)]
    if taxa and taxon_col:
        g = g[g[taxon_col].isin(taxa)]
    if traps and "trap_name" in g.columns:
        g = g[g["trap_name"].isin(traps)]
    if "sample_date" in g.columns and start_date and end_date:
        s = pd.to_datetime(start_date)
        e = pd.to_datetime(end_date)
        g = g[(g["sample_date"] >= s) & (g["sample_date"] <= e)]
    return g

@app.callback(
    Output("ts-abundance", "figure"),
    Output("diversity", "figure"),
    Output("composition", "figure"),
    Output("site-map", "figure"),
    Output("landuse-quarter", "figure"),
    Output("table", "data"),
    Output("record-count", "children"),
    Input("apply", "n_clicks"),
    State("site-select", "value"),
    State("taxa-select", "value"),
    State("trap-select", "value"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
)
def update_visuals(n, sites, taxa, traps, start_date, end_date):
    g = apply_filters(arth, sites, taxa, traps, start_date, end_date)

    # Time series of abundance (total counts per month)
    if "month" in g.columns:
        ts = g.groupby(["month","site_code"], dropna=False)["count"].sum().reset_index()
        ts = ts.sort_values("month")
        ts_fig = px.line(ts, x="month", y="count", color="site_code", markers=True,
                         title="Abundance over time (monthly total counts)")
    else:
        ts_fig = px.scatter(title="No date information available.")

    # Diversity metrics by year & site
    div = compute_diversity(g)
    if not div.empty:
        div_fig = px.line(div, x="year", y=["richness","shannon"], color="site_code",
                          title="Diversity metrics by year")
    else:
        div_fig = px.scatter(title="Diversity metrics not available.")

    # Community composition (stacked bar by top taxa)
    comp = g.copy()
    if taxon_col and not comp.empty:
        # limit to top taxa within filtered set for readability
        top_local = top_taxa(comp, n=10)
        comp[taxon_col] = np.where(comp[taxon_col].isin(top_local), comp[taxon_col], "Other")
        comp_agg = comp.groupby(["site_code", taxon_col])["count"].sum().reset_index()
        comp_fig = px.bar(comp_agg, x="site_code", y="count", color=taxon_col, barmode="stack",
                          title="Community composition (top 10 taxa)")
    else:
        comp_fig = px.bar(title="No taxa available.")

    # Land use (region) × Quarter grouped bar:
    # x-axis = region (Urban/Desert/Agricultural/Other)
    # 4 bars per region = Q1–Q4
    if {"region3", "quarter", "count"}.issubset(g.columns) and not g.empty:
        lu_agg = (
            g.groupby(["region3", "quarter"], dropna=False)["count"]
             .sum()
             .reset_index()
        )
        # order quarters nicely
        q_order = ["Q1", "Q2", "Q3", "Q4"]
        lu_agg["quarter"] = pd.Categorical(
            lu_agg["quarter"],
            categories=q_order,
            ordered=True
        )
        lu_agg = lu_agg.sort_values(["region3", "quarter"])
        landuse_fig = px.bar(
            lu_agg,
            x="region3",
            y="count",
            color="quarter",
            barmode="group",
            title="Quarterly abundance by region",
            labels={"region3": "Region", "count": "Total count", "quarter": "Quarter"},
        )
    else:
        landuse_fig = px.bar(
            title="No land use / quarter data available. Check 'landuse' mapping."
        )


    # Site map (bubble size by total count)
    if {"lat","lon"}.issubset(g.columns) and not g[["lat","lon"]].dropna().empty:
        m = g.groupby(["site_code","lat","lon"], dropna=True)["count"].sum().reset_index()
        map_fig = px.scatter_mapbox(
            m, lat="lat", lon="lon", size="count", hover_name="site_code",
            zoom=8, height=450, title="Sites (bubble size = total counts)")
        map_fig.update_layout(mapbox_style="open-street-map")
    else:
        map_fig = px.scatter(title="No geospatial data available.")

    # Data table & record count
    data_records = g.to_dict("records")
    rec_text = f"Records: {len(g):,}  |  Sites: {g['site_code'].nunique() if 'site_code' in g.columns else 0}  |  Taxa: {g[taxon_col].nunique() if taxon_col and not g.empty else 0}"

    return ts_fig, div_fig, comp_fig, map_fig, landuse_fig, data_records, rec_text

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
