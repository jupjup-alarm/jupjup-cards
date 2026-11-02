"""IndexNow — 바뀐 페이지를 네이버·빙 등에 바로 알림 (2026-11-02 SEO 기획안 개선안 3).

GitHub Actions(.github/workflows/indexnow.yml)가 site/public 이 바뀐 푸시마다 돌린다:
Cloudflare Pages 배포가 끝나 키 파일이 실제로 보일 때까지 기다린 뒤, 이번 푸시에서 바뀐 index.html 의 주소를 보낸다.
IndexNow 참여 검색엔진은 받은 주소를 서로 공유한다(indexnow.org 문서). 네이버 엔드포인트에도 따로 보낸다.

  python3 site/tools/indexnow.py <이전 커밋> <이번 커밋>     (주소 목록만 보려면 --dry)
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE = "https://jupjupalarm.com"
HOST = "jupjupalarm.com"
ROOT = Path(__file__).resolve().parents[2]
ENDPOINTS = ["https://api.indexnow.org/indexnow", "https://searchadvisor.naver.com/indexnow"]


def key():
    ks = [p for p in (ROOT / "site/static").glob("*.txt") if len(p.stem) == 32 and p.read_text().strip() == p.stem]
    if not ks:
        sys.exit("site/static/<키>.txt 가 없어요")
    return ks[0].stem


def changed(a, b):
    if not a or set(a) == {"0"}:
        a = f"{b}~1"
    out = subprocess.run(["git", "diff", "--name-only", a, b, "--", "site/public"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    urls = []
    for f in out:
        if not f.endswith("index.html"):
            continue
        rel = f[len("site/public"):-len("index.html")]
        if rel.startswith(("/drafts/", "/data/")):
            continue
        urls.append(BASE + rel)
    return sorted(set(urls))


def main():
    dry = "--dry" in sys.argv
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    a, b = (args + ["", "HEAD"])[:2] if len(args) < 2 else args[:2]
    urls = changed(a, b)
    k = key()
    print(f"바뀐 페이지 {len(urls)}개")
    for u in urls[:20]:
        print("  ", u)
    if dry or not urls:
        return
    # 배포가 끝나 키 파일이 보일 때까지 (최대 10분)
    for i in range(40):
        try:
            r = requests.get(f"{BASE}/{k}.txt", timeout=20)
            if r.status_code == 200 and r.text.strip() == k:
                break
        except requests.RequestException:
            pass
        time.sleep(15)
    else:
        sys.exit("키 파일이 배포되지 않아 보내지 않음")
    time.sleep(30)  # 키 파일과 같은 배포에 실린 페이지가 퍼질 시간
    body = {"host": HOST, "key": k, "keyLocation": f"{BASE}/{k}.txt", "urlList": urls[:10000]}
    ok = False
    for ep in ENDPOINTS:
        try:
            r = requests.post(ep, json=body, timeout=30, headers={"Content-Type": "application/json; charset=utf-8"})
            print(ep, r.status_code, r.text[:200])
            ok = ok or r.status_code in (200, 202)
        except requests.RequestException as e:
            print(ep, "실패:", e)
    if not ok:
        sys.exit("모든 엔드포인트가 거절")


if __name__ == "__main__":
    main()
