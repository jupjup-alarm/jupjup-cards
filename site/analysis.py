"""줍줍 분석 (/analysis/) — 2026-11-22 사용자 요청: 청약홈 자료를 직접 집계한 분석 글(블로그형), 모바일 하단 탭 '일정' 자리에 '분석'.

글 원고: site/data/analysis/posts/<slug>.json  (숫자는 site/data/analysis/raw.json 에서 계산 — site/tools/analysis_calc.py)
  {slug, title, card, dek, published, basis, tag, stat:{big,label}, answer:[...],
   sections:[{h, paras:[...], table?:{cap, head:[...], rows:[[...]]}, bars?:[{label, value, text}]}],
   method:[...], caveat, related:[{t,u}]}
'뉴스·기자' 표기는 쓰지 않는다(인터넷신문 미등록) — '줍줍 분석'·'줍줍알람 편집팀'.
"""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / "data" / "analysis" / "posts"


def load():
    out = []
    for p in sorted(DIR.glob("*.json")) if DIR.exists() else []:
        g = json.loads(p.read_text())
        if g.get("draft"):
            continue
        g["url"] = f"/analysis/{g['slug']}/"
        for s in g.get("sections", []):
            if s.get("bars"):
                mx = max(b["value"] for b in s["bars"]) or 1
                for b in s["bars"]:
                    b["pct"] = round(b["value"] / mx * 100)
        out.append(g)
    out.sort(key=lambda g: (g["published"], g.get("order", 0)), reverse=True)
    return out


def build(E, write, common, today):
    posts = load()
    if not posts:
        return []
    tpl = E.get_template("analysis.html")
    for i, g in enumerate(posts):
        more = [x for x in posts if x is not g][:4]
        title = f"{g['title']} | 줍줍 분석 · 줍줍알람"
        h = tpl.render(g=g, more=more, **common, page_url=g["url"], title=title, desc=g["dek"], og="/og-default.jpg",
                       crumb=[("홈", "/"), ("줍줍 분석", "/analysis/"), (g["card"], "")], nav="analysis")
        write(g["url"], h, title, g["dek"], "page", g.get("updated") or g["published"])
    title = "줍줍 분석 | 청약홈 자료로 직접 집계한 청약 분석 · 줍줍알람"
    desc = "미달 단지 비율, 1순위 마감 뒤 줍줍, 당첨 가점 커트라인, 경쟁률 상위·하위 단지까지. 청약홈 공식 자료를 줍줍알람이 직접 집계해 정리해요."
    blog_ld = [{"@type": "BlogPosting", "headline": g["title"], "url": common.get("BASE", "https://jupjupalarm.com") + g["url"], "datePublished": g["published"]} for g in posts]
    h = E.get_template("analysis_index.html").render(posts=posts, blog_ld=blog_ld, **common, page_url="/analysis/", title=title, desc=desc, og="/og-default.jpg",
                                                     crumb=[("홈", "/"), ("줍줍 분석", "")], nav="analysis")
    write("/analysis/", h, title, desc, "list", posts[0]["published"])
    return posts
