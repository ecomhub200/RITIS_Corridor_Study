# Refreshing the corridor data — do this whenever you want newer numbers

The Signal Prioritization site (https://ecomhub200.github.io/RITIS_Corridor_Study/)
reads three files from the repo's **`data/`** folder:

| File | What it is |
|------|------------|
| `latest.csv.gz` | the probe travel-time readings, filtered to your corridors, gzipped |
| `latest_meta.json` | the date window + row count shown on the page |
| `XD_Identification.csv` | the segment lengths (miles) — required |

A raw RITIS download is **county-wide and ~1.5 GB** — far too big for GitHub. The
helper script `scripts/make_latest.py` filters it down to just your 619 corridor
segments (~20 MB gzipped) and builds the metadata. Follow these steps — no guessing.

## 1. Download from the RITIS Massive Data Downloader
- Site: https://pda.ritis.org  →  **Massive Data Downloader**
- **Segments:** your corridor XD segments (county-wide Henrico is fine too — the
  script filters it). The 619 IDs are also in `data/3_Corridor_Data.csv`.
- **Dataset:** INRIX XD
- **Date range:** whatever window you want (e.g. last ~90 days). Shorter = smaller file.
- **Granularity:** 15 minutes
- **Columns:** speed, historical average speed, reference speed, **travel time**,
  confidence score, **cvalue**
- **Include the XD / segment identification file** (gives the `miles`).
- Download and **unzip**. You'll get a big readings CSV, an `XD_Identification.csv`,
  and a `Contents.txt`.

## 2. Convert it (one command)
Put `scripts/make_latest.py` from this repo in the unzipped folder (or run it from a
checkout of this repo). Then run, replacing the readings filename with yours:

```bash
python make_latest.py "YOUR_READINGS_FILE.csv" "XD_Identification.csv"
```

It prints a summary and writes **`latest.csv.gz`**, **`latest_meta.json`**, and
passes **`XD_Identification.csv`** through. It also tells you the gzipped size and
whether it's small enough for a web upload.

> If it warns the file is **over 25 MB**, GitHub's web uploader won't take it —
> either re-download a **shorter date range**, or commit with `git` instead.
> Over 100 MB is impossible on GitHub; shorten the window.

## 3. Upload to the repo
In GitHub: open the **`data/`** folder → **Add file ▸ Upload files** → drop in the
three files (replace the existing ones) → **Commit changes** to `main`.

## 4. Done
Wait ~1 minute for GitHub Pages to redeploy, then open the site and click
**"Load data from this repository"** in Step 0. The rankings refresh automatically.

---
*Note: enter the real **AADT** and **years-since-retimed** for each corridor in the
OCRA table and press Recalculate — until then the page shows a yellow reminder and the
ranking reflects only measured delay and reliability.*
