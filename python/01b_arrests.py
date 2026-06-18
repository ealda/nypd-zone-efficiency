import urllib.parse, urllib.request, json, csv, os, time, sys
OUT="data"; BASE="https://data.cityofnewyork.us/resource/8h9b-rp9u.json"
def soql(q):
    url=BASE+"?"+urllib.parse.urlencode({"$query":q})
    for a in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"rp"})
            with urllib.request.urlopen(req,timeout=280) as r: return json.load(r)
        except Exception as e: sys.stderr.write(f"retry {a}: {e}\n"); time.sleep(5)
    raise SystemExit("fail")
def save(rows,path):
    with open(path,"w",newline="") as f:
        w=csv.writer(f); w.writerow(["pct","yr","mo","n"])
        for r in rows: w.writerow([r.get("pct",""),r.get("yr",""),r.get("mo",""),r.get("n","")])
    print(len(rows),"->",path,flush=True)
save(soql("SELECT arrest_precinct AS pct, date_extract_y(arrest_date) AS yr, date_extract_m(arrest_date) AS mo, count(*) AS n GROUP BY pct,yr,mo ORDER BY yr,mo LIMIT 500000"), OUT+"/arrests_monthly.csv")
save(soql("SELECT arrest_precinct AS pct, date_extract_y(arrest_date) AS yr, date_extract_m(arrest_date) AS mo, count(*) AS n WHERE law_cat_cd='F' GROUP BY pct,yr,mo ORDER BY yr,mo LIMIT 500000"), OUT+"/arrests_felony_monthly.csv")
print("ARRESTS_DONE",flush=True)
