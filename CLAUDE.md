# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

---

## 1. What this project is

**RITIS Corridor Study — Signal Prioritization Studio.** A browser-based decision
tool that ranks road corridors for traffic-signal retiming, using INRIX XD probe
travel-time data pulled from RITIS. It is published as a **static GitHub Pages site**:

- Live: https://ecomhub200.github.io/RITIS_Corridor_Study/
- Pages source: branch **`main`**, folder **`/` (root)** — whatever is at the repo
  root on `main` is what ships. There is **no build step today** (see §5).

The study area is **Henrico County, VA**: **32 corridors** spanning **619 unique XD
segments** (defined in `data/3_Corridor_Data.csv`).

> **Direction for future work:** this app currently lives in ONE monolithic
> `index.html` (~2,700 lines of inline HTML + CSS + JS). It is being grown into a
> **modular, industry-standard** codebase. New features should NOT be bolted onto the
> single HTML file — add them as ES modules under `src/` per the target architecture
> in §4. When touching the monolith, prefer extracting the relevant piece into a
> module over enlarging the inline script.

---

## 2. Repository layout (file by file)

| Path | Purpose | Notes |
|------|---------|-------|
| `index.html` | **The entire current app** — markup, `<style>`, and one big inline `<script>`. Loads PapaParse, Chart.js, jsPDF, jsPDF-AutoTable, JSZip from cdnjs. | To be decomposed into `src/` modules (§4). |
| `data/3_Corridor_Data.csv` | Corridor definitions: `objectID, index, System Name, bearing, xd_seg_id, NumberofSignals`. `xd_seg_id` is a `;`-separated XD list. **Source of truth** for which 619 segments the tool ranks. | Committed by hand. |
| `data/XD_Identification.csv` | Per-segment metadata incl. **`miles`** (segment length). **Required** — without miles the tool drops every segment. Header: `xd,road-name,road-num,bearing,miles,...` (leading BOM is fine). | From the RITIS export. |
| `data/latest.csv.gz` | The probe readings, **filtered to the 619 corridor segments** and gzipped. Header: `xd_id,measurement_tstamp,speed,historical_average_speed,reference_speed,travel_time_minutes,confidence_score,cvalue`. | Produced by `scripts/make_latest.py`. Keep under 100 MB (GitHub hard limit). |
| `data/latest_meta.json` | `{start, end_inclusive, rows, xd_segments, granularity_min, units, generated}` — drives the freshness line on the page. | Produced by `scripts/make_latest.py`. |
| `scripts/make_latest.py` | **Manual data converter.** Filters a raw (county-wide, ~1.5 GB) RITIS Massive Data Downloader CSV down to the corridor segments, gzips it, writes the meta. Reads segment IDs from `data/3_Corridor_Data.csv` when present, else a built-in fallback list. | This is the supported refresh path today. See `UPDATE_DATA.md`. |
| `scripts/ritis_fetch_action.py` | **Automated PDA robot** (GitHub Action). Submits a Massive Data Downloader export job to `pda-api.ritis.org/v2`, polls, downloads, commits the data files. Auto-detects auth transport (query/header/bearer). | **Currently unusable** — the available RITIS key is a *Filter API* key, not a *PDA/Massive Data Downloader* key (see §8). Kept for when PDA access is obtained. |
| `.github/workflows/ritis-fetch.yml` | Runs `scripts/ritis_fetch_action.py` on a Monday cron + manual dispatch; commits refreshed data. | Will 401 until a valid **PDA** key is set as the `RITIS_KEY` secret. |
| `UPDATE_DATA.md` | Step-by-step recipe for refreshing the data with `make_latest.py`. | Read this before a data refresh. |
| `SETUP_README.md` | Original kit setup notes (file placement, secret, Pages, first run). | Historical; `UPDATE_DATA.md` is the current data guide. |
| `docs/…API Documentation….pdf` | RITIS **Filter API** reference the user uploaded. | ⚠️ Contains a **plaintext API key + email** — see §9. |

---

## 3. The data contract (stable integration boundary)

`index.html`'s `loadRepoData()` fetches these from `data/` (relative, same-origin):

1. `data/3_Corridor_Data.csv`  → corridor list (File 3)
2. `data/XD_Identification.csv` → segment miles (File 2)
3. `data/latest_meta.json`      → freshness/window (optional)
4. `data/latest.csv.gz`         → probe readings (File 1), decompressed in-browser via
   `DecompressionStream`; falls back to `data/latest.csv` if no `.gz`.

**Keep this contract stable** across any refactor — filenames, locations, and the CSV
column names above are what both the tool and `make_latest.py` depend on.

---

## 4. Target architecture (modular — use this for new work)

Decompose the monolith into ES modules. Recommended stack: **Vite + vanilla
ES modules (JS, TS optional), Vitest for unit tests, Playwright for e2e.** npm-manage
the libs currently loaded from cdnjs (papaparse, chart.js, jspdf, jspdf-autotable,
jszip).

```
src/
  main.js              # bootstrap: mount UI, wire events
  state.js             # single shared app-state object (no globals)
  core/
    stats.js           # quantile (type-7), histQuantile, parseTs, inNight, median
    process.js         # streaming ingest -> per-corridor buckets, free-flow refs, delays, speeds
    score.js           # OCRA scoring + ranking (recalcScores)
  io/
    fileLoad.js        # handleFile (File 1/2/3), loadRepoData (fetch + gz decompress)
    exports.js         # ROC / Night / Spreadsheet / Ranked / speed CSV downloads
    pdf.js             # jsPDF report generation
  ui/
    kpis.js  tables.js  charts.js  compare.js  report.js  diagnostics.js
  styles/              # CSS extracted from the inline <style>
index.html             # thin shell: markup + mount points + <script type="module" src="/src/main.js">
tests/                 # vitest unit specs (mirror src/), playwright e2e
```

Map from the current monolith (for extraction): `quantile/histQuantile/parseTs` →
`core/stats.js`; `processData/finalize` → `core/process.js`; `recalcScores` →
`core/score.js`; `handleFile/loadRepoData` → `io/fileLoad.js`; the `download*`
functions → `io/exports.js` + `io/pdf.js`; `render*/draw*` → `ui/*`.

**Conventions for new code**
- Pure, testable functions in `core/` (no DOM); keep DOM access in `ui/`.
- One concern per module; explicit `import`/`export`, no global mutable state except
  the single `state` object passed in.
- Add a Vitest spec next to every `core/` function (the math is the product — test it).
- Match the existing code's terse style only inside the monolith; new modules should
  be clean and documented.

**Deployment implication:** once a build exists, GitHub Pages must serve the **built
output**. Switch Pages to the **GitHub Actions** source and add a build-and-deploy
workflow (`actions/deploy-pages`) that runs `vite build` → `dist/`. Until then, Pages
serves the root `index.html` as-is, so don't introduce a build dependency without also
updating the deploy path.

---

## 5. Build / run / test / deploy (current)

- **Run locally:** `python3 -m http.server 8000` from the repo root, open
  `http://localhost:8000/`. (A web server is required — the data loads via `fetch`,
  which won't work from `file://`.)
- **No build, no package.json yet.** Adding Vite (§4) is the first modularization step.
- **Test (how Claude verifies today):** there is no committed test runner yet. Logic
  has been verified by (a) extracting functions from `index.html` and unit-testing in
  Node, and (b) headless Chromium (Playwright at `/opt/.../playwright`, browser at
  `/opt/pw-browsers`) driving the page with PapaParse/Chart stubs (cdnjs is often
  egress-blocked in CI sandboxes). Standardize on **Vitest + Playwright** going forward.
- **Deploy:** push to `main`; GitHub Pages redeploys root automatically (~1 min).

---

## 6. Domain knowledge (the calculations)

- **Free-flow reference:** per segment = 25th percentile of its **night-time** travel
  times (all nights in range); summed over the corridor. Fallbacks: INRIX
  `reference_speed`-derived TT → mileage-proportional share.
- **Delay:** `measured TT − reference`, computed only over the segments that reported
  in each 15-min interval (like-for-like); missing segments assumed at free-flow.
- **Space-mean speed:** `Σmiles × 60 / Σtravel-time` per interval.
- **Normalization:** pool both directions → median delay (`normDelay`, sec/intersection)
  and delay IQR (`normIQR`, min/intersection), divided by signal count.
- **OCRA score:** `NormDelay × NormIQR × √(AADT/1000) × √T`. **AADT** and **T**
  (years-since-retimed) are user inputs; they default to placeholders (20000, 24.4) and
  the OCRA table shows a yellow warning until real values are entered + recalculated.
- **Percentiles:** type-7 (interpolated), matching Excel `PERCENTILE.INC`. Used for both
  the array-based corridor speeds and the integer-binned segment-speed histogram.
- **Granularity/units:** 15-minute intervals; travel time in **minutes**
  (`travel_time_minutes`).

---

## 7. Data refresh workflow

See **`UPDATE_DATA.md`**. In short: download the RITIS Massive Data Downloader export
(INRIX XD, 15-min, with travel time + cvalue + the XD identification file) → run
`python scripts/make_latest.py READINGS.csv XD_Identification.csv` → upload the produced
`latest.csv.gz`, `latest_meta.json`, `XD_Identification.csv` to `data/` → commit to `main`.

---

## 8. RITIS APIs — important distinction

- **Massive Data Downloader / PDA** (`pda-api.ritis.org`): provides the **INRIX XD probe
  travel-time** data this tool needs. The automated robot
  (`scripts/ritis_fetch_action.py`) targets this. Requires a **PDA** entitlement.
- **Filter API** (`filter.ritis.org`): event/incident/DMS/weather/detector data — **not**
  probe travel times. The key currently on file is a Filter API key, which is why the
  robot returns **HTTP 401** against the PDA API. Until a PDA key is obtained, refresh
  data **manually** via `make_latest.py`.

---

## 9. Conventions & gotchas

- **Never commit secrets.** API keys belong only in GitHub **Actions secrets**
  (`RITIS_KEY`), never in code, comments, or committed files. ⚠️ A live key is currently
  exposed in `docs/…API Documentation….pdf`; it should be **rotated** and the PDF
  removed/ purged from history.
- **GitHub file-size limits:** web upload caps at **25 MB**; the hard repo limit is
  **100 MB/file**. `make_latest.py` warns at both. If `latest.csv.gz` is too big,
  shorten the RITIS date range (or move bulk storage to a Release / R2).
- **Pages = public.** Treat everything committed as public (the site is live).
- **Browser/CORS:** RITIS APIs send no CORS headers, so the browser cannot call them
  directly — data must be pre-fetched into `data/` (robot or `make_latest.py`).
- **Two branches:** development happens on `main` and is mirrored to
  `claude/keen-meitner-m86hyl`. Pages and the scheduled robot use `main`.
- **Timestamps:** `measurement_tstamp` is ISO `YYYY-MM-DD HH:MM:SS` (string-sortable).

---

## 10. Roadmap notes (intended growth)

The owner plans to add many features. Land them as modules per §4. Likely areas:
before/after retiming comparison, additional corridor metrics, richer PDF/report output,
saved scenarios, and (if PDA access is granted) re-enabling the automated weekly robot.
First infra step: introduce Vite + package.json, extract `core/` math + tests, then peel
the UI off `index.html` incrementally while keeping the §3 data contract intact.
