#!/usr/bin/env python3
"""GitHub Action: fetch a rolling window of XD probe data from the RITIS PDA API v2.

What it does, in order:
  1. Reads the XD segment list from data/3_Corridor_Data.csv (your corridor file),
     so the download ALWAYS covers exactly the corridors the tool ranks.
  2. Submits an export job, polls politely (the API allows 100 requests/hour),
     and downloads the result ZIP.
  3. Saves data/latest.csv.gz, data/latest_meta.json, and (if the ZIP includes one)
     data/XD_Identification.csv — exactly the files the GitHub Pages tool's
     "Load data from this repository" button expects.

The API key comes from the environment (GitHub repo Secret RITIS_KEY).
It is never written to the repository or printed in logs.

ACCURACY NOTE: the export request body below follows the Massive Data Downloader
format. RITIS's public reference documents the workflow but NOT the body schema.
On the first run, if the log shows "Submit failed" with a schema error, open
https://pda-api.ritis.org/v2/docs with your key, compare field names, and fix
the BODY dict below — one time, then it works forever. This script fails loudly
and never commits partial or wrong data.
"""
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import shutil
import sys
import time
import uuid
import zipfile
import urllib.error
import urllib.request

BASE = 'https://pda-api.ritis.org/v2'
KEY = os.environ['RITIS_KEY']
DAYS = int(os.environ.get('WINDOW_DAYS', '91'))
GRAN = int(os.environ.get('GRANULARITY_MIN', '15'))
UNITS = os.environ.get('TT_UNITS', 'seconds')

# ---- 1. XD list straight from the corridor definitions ----------------------
xds = set()
with open('data/3_Corridor_Data.csv', newline='', encoding='utf-8-sig') as f:
    rd = csv.DictReader(f)
    segcol = next((c for c in rd.fieldnames if 'xd' in c.lower()), None)
    if not segcol:
        sys.exit('ERROR: no xd_seg_id column found in data/3_Corridor_Data.csv')
    for row in rd:
        for tok in re.split(r'[;,\s]+', row.get(segcol) or ''):
            if tok.strip():
                xds.add(tok.strip())
xds = sorted(xds)
if not xds:
    sys.exit('ERROR: corridor file contained no XD segment ids')
print(f'{len(xds)} XD segments read from data/3_Corridor_Data.csv')

# ---- 2. Build the export request --------------------------------------------
# API end date is EXCLUSIVE: end = today  ->  data through yesterday (inclusive),
# matching probe-data availability which lags about one day.
end_excl = dt.date.today()
start = end_excl - dt.timedelta(days=DAYS)
BODY = {
    'UUID': str(uuid.uuid4()),
    'DATASOURCES': [{
        'id': 'inrix_xd',
        'columns': ['SPEED', 'HISTORICAL_AVERAGE_SPEED', 'REFERENCE_SPEED',
                    'TRAVEL_TIME', 'CONFIDENCE_SCORE', 'CVALUE'],
    }],
    'DATES': [{'start': start.isoformat(), 'end': end_excl.isoformat()}],
    'GRANULARITY': {'type': 'minutes', 'value': GRAN},
    'TRAVELTIMEUNITS': UNITS,
    'SEGMENTS': {'type': 'xd', 'ids': xds},
}


def call(url, data=None):
    req = urllib.request.Request(url, data=data, method='POST' if data else 'GET')
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


print(f'Submitting export: {start} -> {end_excl} (exclusive), {GRAN}-min, {UNITS}')
code, raw = call(f'{BASE}/submit/export?key={KEY}', json.dumps(BODY).encode())
resp = json.loads(raw or b'{}')
if code != 200 or 'id' not in resp:
    sys.exit(f'Submit failed (HTTP {code}): {raw[:600]}\n'
             'If this is a schema error, compare BODY against '
             'https://pda-api.ritis.org/v2/docs and fix the field names above.')
job = resp['id']
print('Job id:', job)

# ---- 3. Poll politely (workflow: status by jobId, results by ORIGINAL UUID) --
waits = [10, 20, 30] + [45] * 70          # ~55 min ceiling, gentle on 100 req/hr
for i, w in enumerate(waits):
    time.sleep(w)
    code, raw = call(f'{BASE}/jobs/status?jobId={job}&key={KEY}')
    st = json.loads(raw or b'{}')
    print(f'poll {i + 1}: {st.get("state")} {st.get("progress")}%')
    if st.get('state') == 'SUCCEEDED' and st.get('progress') == 100:
        break
    if st.get('state') in ('FAILED', 'KILLED'):
        sys.exit('Job ' + st['state'])
else:
    sys.exit('Timed out waiting for the job. Results remain retrievable for '
             '30 days; rerun the workflow.')

print('Downloading result ZIP (uses the original UUID, not the job id)...')
code, raw = call(f'{BASE}/results/export?uuid={BODY["UUID"]}&key={KEY}')
if code != 200:
    sys.exit(f'Result download failed (HTTP {code})')

# ---- 4. Unpack and save the files the Pages tool reads -----------------------
zf = zipfile.ZipFile(io.BytesIO(raw))
data_name, ident_name, best = None, None, -1
for info in zf.infolist():
    if not info.filename.lower().endswith('.csv'):
        continue
    if 'identification' in info.filename.lower():
        ident_name = info.filename
        continue
    if info.file_size > best:
        best, data_name = info.file_size, info.filename
if not data_name:
    sys.exit('No data CSV found inside the result ZIP')

os.makedirs('data', exist_ok=True)
rows = 0
with zf.open(data_name) as src, gzip.open('data/latest.csv.gz', 'wb', compresslevel=6) as dst:
    while True:
        chunk = src.read(1 << 20)
        if not chunk:
            break
        rows += chunk.count(b'\n')
        dst.write(chunk)
if ident_name:
    with zf.open(ident_name) as src, open('data/XD_Identification.csv', 'wb') as dst:
        shutil.copyfileobj(src, dst)
    print('saved data/XD_Identification.csv')

meta = {
    'start': start.isoformat(),
    'end_inclusive': (end_excl - dt.timedelta(days=1)).isoformat(),
    'rows': rows - 1,
    'xd_segments': len(xds),
    'granularity_min': GRAN,
    'units': UNITS,
    'generated': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
}
with open('data/latest_meta.json', 'w') as f:
    json.dump(meta, f, indent=1)

sz = os.path.getsize('data/latest.csv.gz') / 1048576
print(f'saved data/latest.csv.gz ({sz:.1f} MB, {rows - 1:,} data rows)')
if sz > 95:
    sys.exit('ERROR: gzip exceeds the GitHub 100 MB file limit. Reduce '
             'WINDOW_DAYS in the workflow, or move storage to a GitHub '
             'Release / Cloudflare R2 with CORS.')
print('Done — the GitHub Pages tool will load this on its next visit.')
