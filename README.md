# arthropods_visualization
Repository for code and resources for an interactive visualization of CAP LTER ground-dwelling arthropod data

The app is built with **Streamlit** and **Plotly**, and uses NLCD-derived land cover
to classify sites into **Urban, Desert, Agricultural** (plus Other/Unknown).

---

## Repository Structure

Key files:

- `streamlit_app.py` — main Streamlit dashboard
- `41_core_arthropods.csv` — core arthropod data  
- `arthros_temporal.csv` — site metadata (including coordinates)
- `site_landuse_from_nlcd.csv` — site → landuse mapping derived from NLCD
- `requirements.txt` — Python dependencies

---

## Data Overview

### 1. 41_core_arthropods.csv

- `site_code` — CAP LTER site identifier  
- `sample_date` — date of sampling  
- `display_name` — taxon name (used as `Taxa`)  
- `trap_name` — trap type / ID  
- `count` — abundance / count per record  
- (plus observer, comments, flags, etc.)

### 2. arthros_temporal.csv

Contains temporal and spatial metadata for sites, including:

- `site_code`  
- `lat`, `long` (or similar latitude / longitude columns)  

These are used to map points on the site map.

### 3. site_landuse_from_nlcd.csv

Generated in R using `FedData::get_nlcd()` + `terra::extract()`.  

- `site_code`  
- `landuse` — collapsed NLCD class: **Urban, Desert, Agricultural, Other**  

The dashboard uses `landuse` as `region3`.

---

## Dashboard Features

The Streamlit app provides:

### Filters (sidebar)

- **Sites** — multi-select `site_code`
- **Taxa** — multi-select (top 100 taxa by total count)
- **Year** — multi-select years present in the data

All visualizations respond to these filters.

### Visualizations

1. **Community composition (top 10 taxa × site)**  
   - Stacked bar chart  
   - X: Site  
   - Y: Total count  
   - Colors: Taxa (top 10 per current filter, others grouped as "Other")

2. **Quarterly abundance by region**  
   - Grouped bar chart  
   - X: Region (`Urban`, `Desert`, `Agricultural`, `Other`)  
   - Bars: Quarters `Q1–Q4`  
   - Y: Total arthropod counts

3. **Site map (bubble size = total counts)**  
   - Mapbox scatter plot  
   - Points: Site lat/long  
   - Size: Total counts  
   - Hover: Site ID, total counts

---

## Running Locally

### 1. Clone or Download the repository

      https://github.com/CAPLTER/arthropods_visualization.git

### 2. Create and activate a virtual environment

    python -m venv .venv
    .venv\Scripts\activate      # on Windows
    source .venv/bin/activate     # on macOS / Linux

### 3. Install dependencies

    pip install -r requirements.txt

### 4. Run the Streamlit app

    streamlit run streamlit_app.py

Streamlit will open a browser tab at : http://localhost:8501

## Deploying on Streamlit

1. Push this repo to GitHub
2. Go to Streamlit Community Cloud
3. Click "New app" and select:
   - Repo: your GitHub repo
   - Branch: main (or whichever)
   - File: streamlit_app.py
4. Deploy

You’ll get a URL that can be embedded in WordPress using iframe.
