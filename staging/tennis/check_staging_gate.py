#!/usr/bin/env python3
"""ATLAS Tennis staging publication gate. Never modifies the incumbent feed.
Provider observations are NOT equivalent to Betclic completeness or LIVE certification.
"""
import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

def inspect(candidate, incumbent, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    problems = []
    try:
        age = dt.datetime.fromisoformat(candidate["generatedAt"].replace("Z", "+00:00"))
        if age.tzinfo is None:
            problems.append("timestamp_no_timezone")
        elif abs((now-age).total_seconds())>2*3600:
            problems.append("timestamp_outside_2h")
    except Exception:
        problems.append("invalid_timestamp")
    required = ("schema","source","generatedAt","rowsCount","uniqueIds","rows",
                "hold","productionReady","betclicCertified","j15Certified","liveCertified")
    for key in required:
        if key not in candidate: problems.append("missing_"+key)
    if candidate.get("schema") != "atlas-tennis-sandbox-bridge-v1":
        problems.append("schema_unrecognized")
    for key in ("productionReady","betclicCertified","j15Certified","liveCertified"):
        if candidate.get(key) is not False: problems.append(key+"_must_be_false")
    if candidate.get("hold") is not True or candidate.get("publicStaging") is not True:
        problems.append("must_remain_staging_hold")
    rows=candidate.get("rows") if isinstance(candidate.get("rows"),list) else []
    incumbent_rows=incumbent.get("rows") if isinstance(incumbent.get("rows"),list) else []
    if len(rows) != candidate.get("rowsCount") or len(rows)!=candidate.get("uniqueIds"):
        problems.append("count_mismatch")
    ids = [str(x.get("event_id","")) for x in rows if isinstance(x,dict)]
    if len(set(ids)) != len(rows) or not all(ids):
        problems.append("duplicate_or_missing_event_id")
    prohibited=("secret","token","authorization","api_key","password","cookie")
    if any(any(word in str(k).lower() for word in prohibited) for x in rows if isinstance(x,dict) for k in x):
        problems.append("potential_secret_field")
    counts = Counter(x.get("date") for x in rows if isinstance(x,dict))
    first_day = candidate.get("generatedAt","")[:10]
    parsed = None
    try:parsed=dt.date.fromisoformat(first_day)
    except ValueError:problems.append("unparseable_generation_day")
    required_dates=[(parsed+dt.timedelta(days=i)).isoformat() for i in range(3)] if parsed else []
    # A single provider can have no far-future matches. That's NOT proof no matches exist.
    if any(counts.get(day,0)==0 for day in required_dates):
        problems.append("J2_future_coverage_not_demonstrated")
    prior_day = incumbent.get("generatedAt","")[:10]
    old_same_day = sum(1 for x in incumbent_rows if isinstance(x,dict) and x.get("date")==first_day) if prior_day==first_day else 0
    new_same_day = counts.get(first_day,0)
    if old_same_day>=30 and new_same_day < 0.8*old_same_day:
        problems.append("regressive_match_count")
    if len(rows)<20:
        problems.append("insufficient_evidence")
    if candidate.get("source") == "ESPN / TennisExplorer" and len(rows)<50:
        problems.append("partial_provider_failure")
    result={
        "schema":"atlas-tennis-staging-publish-gate-v1",
        "candidateGeneratedAt":candidate.get("generatedAt"),
        "previousGeneratedAt":incumbent.get("generatedAt"),
        "candidateRows":len(rows),"incumbentRows":len(incumbent_rows),
        "coverageByDay":dict(counts),
        "accepted":not problems,
        "problems":problems,"couldCertifyBetclic":False,
        "doesNotMutateProduction":True,
        "mode":"HOLD" if problems else "STAGING_ONLY_ELIGIBLE",
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--incumbent",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    x=p.parse_args()
    c=json.loads(x.candidate.read_text(encoding="utf-8"))
    old=json.loads(x.incumbent.read_text(encoding="utf-8"))
    report=inspect(c,old)
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ATLAS STAGING GATE",json.dumps(report,ensure_ascii=False))
    # HOLD is a valid safety result; never writes to branch, never certifies.
if __name__=="__main__": main()
