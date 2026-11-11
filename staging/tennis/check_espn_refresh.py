#!/usr/bin/env python3
"""Non-destructive gate for publishing an ESPN-only provisional sidecar in ATLAS STAGING.
This never changes the established 655-event multisource snapshot.
No bookmaker data, API secret, or certification is produced.
"""
import argparse
import datetime as dt
import re
import json
from pathlib import Path
from collections import Counter

STATES = {"scheduled", "live", "finished", "status_to_verify"}
UNDECIDED_PLAYER=re.compile(r"^(?:tbd|tba|bye|unknown|to be determined|qualifier|q|lucky loser|ll|winner of(?:\s+.*)?)$", re.I)
FIELDS = {"event_id","date","time","tournament","player1","player2","status","status_fr",
          "score","source","source_trust","consensus","_atlas_gate"}
BLOCKED_WORDS = ("secret","token","password","authorization","api_key","cookie","bearer")

def check(candidate, previous=None, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    problems=[]
    if not isinstance(candidate,dict):
        raise ValueError("Candidate must be an object")
    try:
        stamped=dt.datetime.fromisoformat(candidate["generatedAt"].replace("Z","+00:00"))
        if stamped.tzinfo is None or abs((now-stamped).total_seconds())>7200:
            problems.append("missing_or_stale_timestamp")
    except (ValueError,TypeError,KeyError):
        problems.append("invalid_timestamp")
    for key in ("productionReady","betclicCertified","j15Certified","liveCertified",
                "publicationEligible","coverageVerified"):
        if candidate.get(key) is not False:problems.append(key+"_must_be_false")
    if candidate.get("hold") is not True or candidate.get("publicStaging") is not True:
        problems.append("not_staging_hold")
    if candidate.get("schema")!="atlas-tennis-sandbox-bridge-v1":
        problems.append("unsupported_schema")
    rows=candidate.get("rows")
    if not isinstance(rows,list):rows=[];problems.append("invalid_rows")
    if not(20<=len(rows)<=3000):problems.append("record_count_out_of_bounds")
    if candidate.get("rowsCount")!=len(rows) or candidate.get("uniqueIds")!=len(rows):
        problems.append("count_mismatch")
    seen=set();dates=Counter()
    for n,m in enumerate(rows):
        if not isinstance(m,dict):
            problems.append("non_object_match");continue
        if any(k not in FIELDS for k in m):problems.append("unexpected_fields")
        if any(any(b in str(k).lower() for b in BLOCKED_WORDS) for k in m):problems.append("possible_secret")
        eid=str(m.get("event_id") or "")
        if not eid or eid in seen:problems.append("missing_or_duplicate_id")
        seen.add(eid)
        if not str(m.get("player1") or "").strip() or not str(m.get("player2") or "").strip():
            problems.append("player_name_missing")
        if any(UNDECIDED_PLAYER.fullmatch(str(m.get(k) or "").strip()) for k in ("player1","player2")):
            problems.append("undecided_opponent")
        if m.get("source")!="ESPN":problems.append("unverified_source")
        if m.get("status") not in STATES:problems.append("unsupported_status")
        if m.get("status")=="finished" and m.get("score") is None:
            problems.append("finished_without_score")
        dates[str(m.get("date") or "")]+=1
    valid_dates=[x.get("date") for x in candidate.get("sourceCoverage",[]) if isinstance(x,dict)]
    if len(valid_dates)!=3 or len(set(valid_dates))!=3:
        problems.append("expected_three_day_window")
    if any(x not in valid_dates for x in dates):
        problems.append("event_date_outside_window")
    if any(dates[d]<1 for d in valid_dates):
        problems.append("missing_one_of_three_days")
    if previous:
        old=previous.get("rows",[])
        if not isinstance(old,list):problems.append("bad_previous")
        else:
            old_date=previous.get("generatedAt","")[:10]
            new_date=candidate.get("generatedAt","")[:10]
            if old_date==new_date and len(rows)<max(20,0.65*len(old)):
                problems.append("large_total_drop_same_day")
            # Never allow a final score to regress to "upcoming" within the same daily snapshot.
            previous_final={x.get("event_id") for x in old if isinstance(x,dict) and x.get("status")=="finished"}
            current_by_id={x.get("event_id"):x for x in rows if isinstance(x,dict)}
            for eid in previous_final.intersection(current_by_id):
                if current_by_id[eid].get("status") in ("scheduled","status_to_verify"):
                    problems.append("result_regression")
                    break
    # The candidate is staging-only regardless of acceptance.
    result={"schema":"atlas-staging-refresh-gate-v1","acceptedForStaging":not problems,
            "mode":"STAGING_HOLD_PUBLISH" if not problems else "REJECT_KEEP_PREVIOUS",
            "reasons":sorted(set(problems)),"candidateRows":len(rows),
            "previousRows":len(previous.get("rows",[])) if previous else 0,
            "datedRows":dict(dates),
            "productionModified":False,"canonicalMultisourceModified":False,
            "betclicCertified":False,"liveCertified":False}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True,type=Path)
    p.add_argument("--previous",type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    candidate=json.loads(args.candidate.read_text(encoding="utf-8"))
    previous=json.loads(args.previous.read_text(encoding="utf-8")) if args.previous and args.previous.exists() else None
    report=check(candidate,previous)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ATLAS STAGING GATE",json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
