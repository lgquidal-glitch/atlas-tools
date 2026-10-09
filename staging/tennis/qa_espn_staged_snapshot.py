#!/usr/bin/env python3
"""ATLAS Tennis staged JSON integrity watchdog (read-only).
Checks every write of the independently refreshed ESPN J→J+2 feed.
Does not certify Betclic or touch HTML, live production or the 655-event archive.
"""
import argparse, datetime as dt, json, sys
from zoneinfo import ZoneInfo
from collections import Counter
from pathlib import Path

def check(path, multisource, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    orig=json.loads(Path(multisource).read_text(encoding="utf-8"))
    failures=[]
    if d.get("schema")!="atlas-tennis-sandbox-bridge-v1":failures.append("schema")
    if any(d.get(flag) is not False for flag in ("productionReady","betclicCertified","j15Certified","liveCertified")):
        failures.append("false_certification")
    if d.get("hold") is not True or d.get("publicStaging") is not True:
        failures.append("not_hold")
    if orig.get("rowsCount")!=655 or orig.get("hold") is not True or orig.get("productionReady") is not False:
        failures.append("protected_archive_changed_or_invalid")
    try:
        gen=dt.datetime.fromisoformat(d["generatedAt"].replace("Z","+00:00"))
        if gen.tzinfo is None:raise ValueError("missing tz")
        age=(now-gen).total_seconds()/60
        if not(-2<=age<=130):failures.append("stale_or_future_timestamp")
    except (KeyError,TypeError,ValueError):
        age=None;failures.append("invalid_timestamp")
    rows=d.get("rows",[])
    if not isinstance(rows,list):rows=[];failures.append("rows_not_list")
    ids=[str(m.get("event_id") or "") for m in rows if isinstance(m,dict)]
    if len(ids)!=len(rows) or not all(ids) or len(set(ids))!=len(ids):
        failures.append("duplicate_or_missing_event_id")
    if len(rows)!=d.get("rowsCount") or len(rows)!=d.get("uniqueIds"):
        failures.append("declared_count_mismatch")
    if not(20<=len(rows)<=3000):failures.append("number_of_matches_outside_guard")
    daily=d.get("sourceCoverage",[])
    dates=[v.get("date") for v in daily if isinstance(v,dict)]
    try:
        today=gen.astimezone(ZoneInfo("Europe/Paris")).date()
        expected={(today+dt.timedelta(days=i)).isoformat() for i in range(3)}
        # Use the captured coverage calendar to avoid wrong daily offsets around DST changes.
        if set(dates)!=expected or len(dates)!=3:failures.append("incorrect_window")
    except Exception:
        failures.append("invalid_window")
    counts=Counter()
    for row in rows:
        if not isinstance(row,dict):continue
        counts[row.get("date")]+=1
        if row.get("source")!="ESPN":failures.append("unknown_source")
        if not row.get("player1") or not row.get("player2"):failures.append("player_missing")
        if row.get("status") not in ("scheduled","live","finished","status_to_verify"):
            failures.append("invalid_status")
        if row.get("status")=="finished" and row.get("score") is None:
            failures.append("unverified_finished_score")
        if any(str(k).lower() in ("x-secret","api_key","authorization","token","password") for k in row):
            failures.append("possible_key_exposure")
    if any(counts.get(day,0)<1 for day in dates):failures.append("missing_actual_day")
    if not d.get("dateRequestIndependenceVerified") in (False,True):
        failures.append("unreported_upstream_independence")
    report={
        "schema":"atlas-hourly-refresh-audit-v1","checkedAt":now.isoformat(),
        "generatedAt":d.get("generatedAt"),"ageMinutes":None if age is None else round(age,1),
        "dataRows":len(rows),"distinctIds":len(set(ids)),"days":dict(counts),
        "protectedArchiveRows":orig.get("rowsCount"),
        "pass":not failures,"failures":sorted(set(failures)),
        "fullBookmakerCoverageCertified":False,"liveCertified":False,
        "productionModified":False,"replacedMultisource":False,
    }
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--espn",required=True)
    p.add_argument("--archive",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=check(args.espn,args.archive)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("ATLAS SCHEDULED-FEED GUARD",json.dumps(report,ensure_ascii=False))
    if not report["pass"]:sys.exit(1)
