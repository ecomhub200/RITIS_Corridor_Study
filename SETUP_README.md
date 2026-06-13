# RITIS robot setup — 5 steps, ~10 minutes

Your repo should look like this when done:

    your-repo/
    ├── index.html                      <- Signal_Prioritization_Tool_v8.html, renamed
    ├── data/
    │   └── 3_Corridor_Data.csv         <- your 32-corridor / 619-XD file (you commit this)
    ├── scripts/
    │   └── ritis_fetch_action.py       <- from this kit
    └── .github/
        └── workflows/
            └── ritis-fetch.yml         <- from this kit

The robot adds these automatically after each Monday run:

    data/latest.csv.gz        <- the probe data (compressed)
    data/latest_meta.json     <- data window + freshness stamp shown in the tool
    data/XD_Identification.csv  <- segment lengths (if RITIS includes it in the ZIP)

## Steps

1. Copy the two kit files into the repo at the paths shown above.
   Commit data/3_Corridor_Data.csv too — the robot reads the XD list from it,
   so the download always matches your corridors exactly.

2. Add the secret key:
   Repo -> Settings -> Secrets and variables -> Actions -> New repository secret
   Name:  RITIS_KEY     Value: your PDA API key
   (Never put the key in any committed file.)

3. Turn on GitHub Pages:
   Repo -> Settings -> Pages -> Source: Deploy from a branch -> main / root.

4. First run (manual): Actions tab -> "Fetch RITIS probe data" -> Run workflow.
   * Green run -> you're done.
   * "Submit failed" with a schema error -> open pda-api.ritis.org/v2/docs with
     your key, compare the export body field names, fix the BODY dict near the
     top of scripts/ritis_fetch_action.py, run again. One-time fix.

5. Open your Pages site and press "Load data from this repository" in Step 0.
   Files 1/2/3 load in seconds, and the status line shows the data window and
   when the robot last refreshed it.

## Schedule
cron '30 7 * * 1' = every Monday 07:30 UTC = 3:30 AM Eastern in summer,
2:30 AM in winter — always inside RITIS's recommended 2:00-4:00 AM window.

## Size guard
Default window is 91 days (~13 weeks). The script refuses to commit anything
over 95 MB compressed (GitHub hard limit is 100 MB) — it stops with a clear
message instead of saving truncated data. Want 6-12 months? Tell Claude and the
kit can be switched to GitHub Releases or Cloudflare R2 storage.
