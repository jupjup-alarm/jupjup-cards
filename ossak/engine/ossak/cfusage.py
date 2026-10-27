#!/usr/bin/env python3
"""Cloudflare Workers AI 직전 24시간 뉴런 사용량 (무료 1만이 이 기준으로 차는 것으로 보임).
  python3 ossak/cfusage.py      → 시간별·합계 출력, 마지막 줄 'TOTAL_24H <숫자>'"""
import datetime, json, sys, urllib.request, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cf import load_env

acc, tok = load_env()
now = datetime.datetime.now(datetime.timezone.utc)
q = """query($a:String!,$s:Time!,$e:Time!){viewer{accounts(filter:{accountTag:$a}){aiInferenceAdaptiveGroups(limit:200,
filter:{datetime_geq:$s,datetime_leq:$e},orderBy:[datetimeHour_ASC]){sum{totalNeurons} count dimensions{modelId datetimeHour}}}}}"""
v = {"a": acc, "s": (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"), "e": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
req = urllib.request.Request("https://api.cloudflare.com/client/v4/graphql", data=json.dumps({"query": q, "variables": v}).encode(),
                             headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=60))
if r.get("errors"):
    sys.exit(f"조회 실패: {r['errors'][0]['message']}")
tot = 0
for g in r["data"]["viewer"]["accounts"][0]["aiInferenceAdaptiveGroups"]:
    n = g["sum"]["totalNeurons"]; tot += n
    print(g["dimensions"]["datetimeHour"][5:16], g["dimensions"]["modelId"].split("/")[-1], g["count"], round(n))
print("TOTAL_24H", round(tot))
