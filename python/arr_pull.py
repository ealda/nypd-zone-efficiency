#!/usr/bin/env python3
# Resumable summer-arrests puller. Appends one year at a time to data/arrests_summer.csv.
# Usage: python3 arr_pull.py NMAX   (pulls up to NMAX not-yet-done years)
import urllib.parse, urllib.request, json, csv, os, sys
BASE = "https://data.cityofnewyork.us/resource/8h9b-rp9u.json"
PATH = "data/arrests_summer.csv"
YEARS = list(range(2009, 2026))
NMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 3

def soql(q, t=12):
    url = BASE + "?" + urllib.parse.urlencode({"$query": q})
    req = urllib.request.Request(url, headers={"User-Agent": "rp"})
    with urllib.request.urlopen(req, timeout=t) as r:
        return json.load(r)

def summer(y, felony=False):
    w = f"arrest_date between '{y}-06-01T00:00:00' and '{y}-09-30T23:59:59'"
    if felony: w += " AND law_cat_cd='F'"
    return soql(f"SELECT arrest_precinct AS pct, count(*) AS n WHERE {w} GROUP BY pct LIMIT 5000")

done = set()
if os.path.exists(PATH):
    with open(PATH) as f:
        for row in csv.DictReader(f):
            done.add(int(row["yr"]))
else:
    with open(PATH, "w", newline="") as f:
        csv.writer(f).writerow(["pct", "yr", "arr", "arr_fel"])

todo = [y for y in YEARS if y not in done][:NMAX]
for y in todo:
    a = summer(y, False); fl = summer(y, True)
    fd = {r["pct"]: r["n"] for r in fl}
    with open(PATH, "a", newline="") as f:
        w = csv.writer(f)
        for r in a:
            w.writerow([r.get("pct",""), y, r.get("n",""), fd.get(r.get("pct",""), "0")])
    print(f"year {y}: {len(a)} precincts", flush=True)
print("remaining:", [y for y in YEARS if y not in done and y not in todo])
