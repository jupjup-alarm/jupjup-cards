#!/usr/bin/env python3
"""실물 증거 — 옛 신문 지면에서 기사 부분을 찾아 잘라 온다 (미국 의회도서관 Chronicling America, 1963년 이전 미국 신문).
2026-11-04 사용자 결정: "원본 사용하고 출처 남긴다" — 증거 화면(short.json 장면 "proof")에 쓴다.

  python3 ossak/clip.py --search "shower of meat" --dates 1876 [--n 25]          # 기사 찾기: 날짜·신문·문장 미리보기
  python3 ossak/clip.py --page "https://www.loc.gov/resource/sn84022047/1876-03-18/ed-1/?sp=2" \
        --word "meat" --near "shower" --out episodes/<편>/proof/whitepine.jpg   # 그 지면에서 문장 부분만 잘라 저장

- 찾은 문장(OCR) 주변 줄을 잘라 저장하고, 같은 이름 _wide.jpg로 더 넓은 지면도 저장한다.
- 출력의 credit 줄을 short.json proof.credit에 그대로 쓴다. hl(형광펜 상자)은 잘린 그림을 열어 보고 비율로 정한다.
- 국내 신문(네이버 뉴스라이브러리 등)·사진은 이용 조건을 먼저 확인한다. 저작권이 남은 현대 보도사진은 쓰지 않는다.
"""
import argparse, json, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET

UA = {"User-Agent": "ossak-research/1.0 (https://github.com/jupjup-alarm)"}


def get(u, tries=3):
    err = None
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read()
        except Exception as e:      # 의회도서관 서버가 가끔 끊긴다
            err = e
            time.sleep(3 * (k + 1))
    raise err


def page_info(pid):
    j = json.loads(get(pid + ("&" if "?" in pid else "?") + "fo=json"))
    pg = [p for p in j["page"] if isinstance(p, dict)]
    xml = [p["url"] for p in pg if p.get("mimetype") == "text/xml"][0]
    jpg = [p["url"] for p in pg if p.get("mimetype") == "image/jpeg"][0]
    title = j.get("item", {}).get("title") or ""
    return xml, jpg.split("/full/")[0], title


def strings(root):
    ns = root.tag.split("}")[0] + "}"
    return ns, root


def search(q, dates, n):
    u = ("https://www.loc.gov/collections/chronicling-america/?" +
         urllib.parse.urlencode({"q": q, "dates": f"{dates}/{dates}" if "/" not in dates else dates, "fo": "json", "c": n}))
    d = json.loads(get(u))
    print(f"검색 결과 {d.get('pagination', {}).get('of')}건 (앞 {n}건)")
    words = q.strip('"').lower().split()
    for r in d.get("results", [])[:n]:
        pid = r["id"].replace("http://", "https://")
        try:
            xml, _, _ = page_info(pid)
            root = ET.fromstring(get(xml))
        except Exception as e:
            print("  (못 읽음)", r.get("date"), pid, e)
            continue
        ns = root.tag.split("}")[0] + "}"
        toks = [s.get("CONTENT", "") for s in root.iter(ns + "String")]
        low = [t.lower() for t in toks]
        hit = next((i for i in range(len(low)) if low[i].startswith(words[-1]) and
                    all(any(w2.startswith(w) for w2 in low[max(0, i - 5):i + 1]) for w in words)), None)
        ctx = " ".join(toks[max(0, hit - 20):hit + 30]) if hit is not None else "(문장 위치 못 찾음)"
        print(f"\n## {r.get('date')} {r.get('title', '')[:70]}\n   {pid}\n   {ctx}")
        time.sleep(1)


def crop(pid, word, near, out, before=2, after=7, pad=40):
    xml, svc, title = page_info(pid)
    info = json.loads(get(svc + "/info.json"))
    root = ET.fromstring(get(xml))
    ns = root.tag.split("}")[0] + "}"
    page = root.find(f".//{ns}Page")
    sx, sy = info["width"] / float(page.get("WIDTH")), info["height"] / float(page.get("HEIGHT"))
    for blk in root.iter(ns + "TextBlock"):
        lines = list(blk.iter(ns + "TextLine"))
        for li, ln in enumerate(lines):
            txt = " ".join(s.get("CONTENT", "") for s in ln.iter(ns + "String")).lower()
            prev = " ".join(s.get("CONTENT", "") for s in lines[li - 1].iter(ns + "String")).lower() if li else ""
            if word.lower() in txt and (not near or near.lower() in txt or near.lower() in prev):
                sel = lines[max(0, li - before):li + after]
                x0 = min(float(blk.get("HPOS")), min(float(l.get("HPOS")) for l in sel))
                x1 = max(float(blk.get("HPOS")) + float(blk.get("WIDTH")),
                         max(float(l.get("HPOS")) + float(l.get("WIDTH")) for l in sel))
                y0 = min(float(l.get("VPOS")) for l in sel)
                y1 = max(float(l.get("VPOS")) + float(l.get("HEIGHT")) for l in sel)
                X, Y = int(x0 * sx) - pad, int(y0 * sy) - pad
                Wd, Ht = int((x1 - x0) * sx) + 2 * pad, int((y1 - y0) * sy) + 2 * pad
                open(out, "wb").write(get(f"{svc}/{max(0, X)},{max(0, Y)},{Wd},{Ht}/full/0/default.jpg"))
                Y2, H2 = max(0, Y - int(Ht * 1.6)), int(Ht * 4.2)
                open(out.replace(".jpg", "_wide.jpg"), "wb").write(
                    get(f"{svc}/{max(0, X - pad * 3)},{Y2},{Wd + pad * 6},{H2}/pct:60/0/default.jpg"))
                date = pid.split("/")[5] if pid.count("/") > 5 else ""
                print(f"저장: {out} ({Wd}×{Ht}) + _wide")
                print(f"credit: {title.split(',')[0] if title else '신문'} {date.replace('-', '.')} · 미국 의회도서관")
                print("찾은 줄:", txt)
                return
    raise SystemExit(f"'{word}'(+'{near}') 줄을 못 찾음 — 검색 결과의 문장을 보고 다른 단어로")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search")
    ap.add_argument("--dates", default="1800/1963")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--page")
    ap.add_argument("--word")
    ap.add_argument("--near", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.search:
        search(a.search, a.dates, a.n)
    if a.page:
        crop(a.page, a.word, a.near, a.out)


if __name__ == "__main__":
    main()
