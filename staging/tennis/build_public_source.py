#!/usr/bin/env python3
"""ATLAS public staging: ESPN-only J→J+2 provisional snapshot generator.
No secrets, no bookmaker claim. Does not write production UI or the default branch.
"""
import argparse,datetime as dt,hashlib,json,pathlib,re,urllib.request
from zoneinfo import ZoneInfo
PARIS=ZoneInfo("Europe/Paris")
API="https://site.api.espn.com/apis/site/v2/sports/tennis/all/scoreboard"
MAX_BYTES=4_000_000
SAFE_STATES={"scheduled","live","finished","status_to_verify"}
UNDECIDED_PLAYER=re.compile(r"^(?:tbd|tba|bye|unknown|to be determined|qualifier|q|lucky loser|ll|winner of(?:\s+.*)?)$",re.I)

def all_competitions(root,out):
    if isinstance(root,list):
        for x in root:all_competitions(x,out)
    elif isinstance(root,dict):
        if isinstance(root.get("competitors"),list) and len(root["competitors"])>=2 and isinstance(root.get("status"),dict):
            out.append(root)
        for v in root.values():
            if isinstance(v,(dict,list)):all_competitions(v,out)

def fetch(day):
    url=API+"?dates="+day.strftime("%Y%m%d")
    req=urllib.request.Request(url,headers={"User-Agent":"ATLAS-Tennis-Staging-QA/1.0",
                                            "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        if r.status!=200:raise ValueError("upstream HTTP "+str(r.status))
        raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("upstream too large")
        return json.loads(raw)

def name(c):
    x=c.get("athlete") or {}
    return str(x.get("displayName") or x.get("fullName") or c.get("displayName") or "").strip()
def sets(a,b):
    result=[]
    for x,y in zip(a or [],b or []):
        p=x.get("displayValue",x.get("value")) if isinstance(x,dict) else x
        q=y.get("displayValue",y.get("value")) if isinstance(y,dict) else y
        if p is not None or q is not None: result.append([p,q])
    return result

def run(outfile):
    now=dt.datetime.now(PARIS);days=[now.date()+dt.timedelta(days=i) for i in range(3)]
    out=[];seen=set();daily=[];fingerprints=[]
    for day in days:
        raw=fetch(day);comps=[];all_competitions(raw,comps)
        fingerprint=hashlib.sha256('|'.join(sorted(str(x.get('id') or '') for x in comps)).encode()).hexdigest()[:16]
        fingerprints.append(fingerprint)
        counted=0
        for c in comps:
            cs=c.get("competitors") or [];a,b=name(cs[0]),name(cs[1])
            if not a or not b or a.casefold()==b.casefold() or UNDECIDED_PLAYER.fullmatch(a) or UNDECIDED_PLAYER.fullmatch(b):continue
            event_stamp=c.get("date")
            # Unknown event dates are excluded rather than guessed from the URL.
            if not event_stamp:continue
            try:
                starts=dt.datetime.fromisoformat(str(event_stamp).replace("Z","+00:00"))
                if starts.tzinfo is None:continue
                event_day=starts.astimezone(PARIS).date()
                if event_day not in days:continue
            except Exception:continue
            eid=str(c.get("id") or "")
            if not eid:continue
            ident="espn:"+event_day.isoformat()+":"+eid
            if ident in seen:continue
            seen.add(ident);counted+=1
            state=(((c.get("status") or {}).get("type") or {}).get("state")) or ""
            status={"pre":"scheduled","in":"live","post":"finished"}.get(state,"status_to_verify")
            score=None
            raw_sets=sets(cs[0].get("linescores"),cs[1].get("linescores"))
            a_score=cs[0].get("score");b_score=cs[1].get("score")
            if status in ("live","finished") and (raw_sets or a_score is not None or b_score is not None):
                score={"sets":raw_sets,"player1":a_score,"player2":b_score}
            elif status=="finished":
                status="status_to_verify"
            tour=None
            notes=c.get("notes") or []
            if isinstance(notes,list) and notes and isinstance(notes[0],dict):
                tour=notes[0].get("headline")
            out.append({
                "event_id":ident,"date":event_day.isoformat(),
                "time":starts.astimezone(PARIS).strftime("%H:%M"),
                "tournament":str(tour or "Tennis — compétition à vérifier")[:150],
                "player1":a[:120],"player2":b[:120],
                "status":status,"status_fr":{"scheduled":"À venir","live":"En cours","finished":"Terminé"}.get(status,"À vérifier"),
                "score":score,"source":"ESPN","source_trust":"Source simple provisoire",
                "consensus":"SINGLE_SOURCE","_atlas_gate":"REVIEW" if status in ("live","status_to_verify") else "ALLOW"
            })
        daily.append({"date":day.isoformat(),"recordsFound":0,"acceptedDuringRequest":counted,"upstreamParsed":len(comps),"sourceFingerprint":fingerprint})
    # Count actual event dates, never the date of the API request that returned them.
    for item in daily:
        item["recordsFound"]=sum(m["date"]==item["date"] for m in out)
    request_dates_distinct=(len(set(fingerprints))==len(fingerprints))
    if len(out)<20:raise ValueError("Too few valid matches: refuse update")
    if len(out)>3000:raise ValueError("Too many matches: refuse update")
    obj={"schema":"atlas-tennis-sandbox-bridge-v1","source":"ESPN public scoreboard",
         "generatedAt":now.isoformat(timespec="seconds"),"rowsCount":len(out),"uniqueIds":len(seen),
         "rows":sorted(out,key=lambda x:(x["date"],x["time"],x["player1"])),
         "sourceCoverage":daily,"windowMode":"J→J+2 priority (unverified)",
         "dateRequestIndependenceVerified":request_dates_distinct,
         "coverageVerified":False,"publicationEligible":False,
         "publicStaging":True,"hold":True,"productionReady":False,
         "betclicCertified":False,"j15Certified":False,"liveCertified":False}
    assert len(out)==len(seen)
    assert all(x["status"] in SAFE_STATES for x in out)
    path=pathlib.Path(outfile);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("ATLAS ESPN PROVISIONAL QA",json.dumps({
        "rows":len(out),"dates":daily,"certified":False,
        "dateRequestIndependenceVerified":request_dates_distinct,
        "publicationEligible":False},ensure_ascii=False))
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",required=True)
    run(parser.parse_args().output)
