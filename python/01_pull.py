#!/usr/bin/env python3
"""
01_pull.py  -- Pull precinct x year x month aggregates from NYC Open Data
via server-side SoQL (no bulk download). Saves tidy CSVs to data/.

Datasets:
  shootings           833y-fsy8   (NYPD Shooting Incident Data, Historic)
  outdoor violent     qgea-i56i   (NYPD Complaint Data Historic; ky_cd 101/105/106)
  arrests (all)       8h9b-rp9u   (NYPD Arrests Data Historic)
"""
import urllib.parse, urllib.request, json, csv, os, time, sys

OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)
BASE = "https://data.cityofnewyork.us/resource/{}.json"

def soql(dataset, query, retries=3):
    url = BASE.format(dataset) + "?" + urllib.parse.urlencode({"$query": query})
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-pipeline"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            sys.stderr.write(f"  retry {a+1}: {e}\n"); time.sleep(3)
    raise RuntimeError(f"failed: {dataset}")

def save(rows, cols, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])
    print(f"  wrote {len(rows):>6} rows -> {os.path.basename(path)}")

LIM = 500000

# 1) Shootings: precinct x year x month, all months
print("shootings (833y-fsy8)...")
q = ("SELECT precinct AS pct, date_extract_y(occur_date) AS yr, "
     "date_extract_m(occur_date) AS mo, count(*) AS n "
     "GROUP BY pct, yr, mo "
     f"ORDER BY yr, mo LIMIT {LIM}")
save(soql("833y-fsy8", q), ["pct","yr","mo","n"], os.path.join(OUT,"shootings_monthly.csv"))

# 2) Outdoor violent complaints (murder/robbery/felony assault, outdoor)
print("outdoor violent complaints (qgea-i56i)...")
q = ("SELECT addr_pct_cd AS pct, date_extract_y(cmplnt_fr_dt) AS yr, "
     "date_extract_m(cmplnt_fr_dt) AS mo, count(*) AS n "
     "WHERE ky_cd in ('101','105','106') "
     "AND loc_of_occur_desc in ('OUTSIDE','FRONT OF','OPPOSITE OF','REAR OF') "
     "AND date_extract_y(cmplnt_fr_dt) >= 2006 "
     "GROUP BY pct, yr, mo "
     f"ORDER BY yr, mo LIMIT {LIM}")
save(soql("qgea-i56i", q), ["pct","yr","mo","n"], os.path.join(OUT,"violent_monthly.csv"))

# 3) Arrests: all, precinct x year x month
print("arrests all (8h9b-rp9u)...")
q = ("SELECT arrest_precinct AS pct, date_extract_y(arrest_date) AS yr, "
     "date_extract_m(arrest_date) AS mo, count(*) AS n "
     "GROUP BY pct, yr, mo "
     f"ORDER BY yr, mo LIMIT {LIM}")
save(soql("8h9b-rp9u", q), ["pct","yr","mo","n"], os.path.join(OUT,"arrests_monthly.csv"))

# 4) Felony arrests only (law_cat_cd = 'F') -- sharper input proxy
print("arrests felony (8h9b-rp9u)...")
q = ("SELECT arrest_precinct AS pct, date_extract_y(arrest_date) AS yr, "
     "date_extract_m(arrest_date) AS mo, count(*) AS n "
     "WHERE law_cat_cd='F' "
     "GROUP BY pct, yr, mo "
     f"ORDER BY yr, mo LIMIT {LIM}")
save(soql("8h9b-rp9u", q), ["pct","yr","mo","n"], os.path.join(OUT,"arrests_felony_monthly.csv"))

print("done.")
