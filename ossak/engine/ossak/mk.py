#!/usr/bin/env python3
"""짧은 스토리 스펙(story.json) → episode.json 변환기.

사용: python3 ossak/mk.py episodes/W-0002-maryceleste
  story.json 을 읽어 같은 폴더에 episode.json 을 쓴다. 이후 batch.py / render.py / compose.py 가 episode.json 을 읽는다.

story.json 형식
{
  "id": "W-0002", "series": "세계기담", "title": "메리 셀레스트호",
  "sources": ["표시용 출처 1", ...], "source_urls": [...],
  "next": "[세계기담] 다음 편 제목",
  "caption": "...", "threads": ["...", ...], "reels_script": ["...", ...],
  "slides": [
    {"cover": {"title": [...], "accent_word": "...", "sub": "...", "size": 100}, "scene": "...", "nop": true},
    {"rows": [{"scene": "...", "cap": "...", "h": 700, "nop": true}, {"panel": "s02a", "cap": {...}}]},
    {"rows": [{"scene": "..."}, {"card": {...}}]},
    {"card": {...}},
    {"end": {"scene": "...", "bubble": "..."}}
  ]
}
- scene: 그림 프롬프트(영문). 컷 ID는 s{장번호}{a,b,c} 로 자동 부여, 크기는 레이아웃에서 계산.
- panel: 앞에서 만든 컷 재사용(복선 회수용).
- nop: 사람 실루엣 금지 문구 추가. ref: 같은 편 컷 참조 목록.
- cap: 문자열 또는 compose.caption 옵션(dict: text, pos, maxw, size, style).
"""
import json, pathlib, sys

AW, AH, GAP = 992, 1202, 20
SERIES = {
    "세계기담": ("#F2B544", "amber"),
    "새벽괴담": ("#3FB8A8", "teal"),
    "미제파일": ("#E8693A", "orange"),
    "그날의 기록": ("#E8693A", "orange"),
    "그 후": ("#9AA3B8", "silver"),
}
CHARACTER = ("Boogi, a small round owl archivist mascot: dark slate-navy feathers, two pointed ear tufts, large glowing "
             "amber eyes behind thin round silver glasses, a small amber diamond-shaped beak, a lighter navy chevron-patterned "
             "belly, short wings, carrying a small cream notebook and a little amber lantern. Cute, simple, flat webtoon character design.")
NOP = " Absolutely no human figures, silhouettes or shadows of people anywhere in the image."
OWL = " The owl is the only figure in the image: no humans, no human silhouettes, no shadows of people."
DEFAULT_H = {2: [700, 482], 3: [520, 321, 321]}


def heights(cells):
    n = len(cells)
    given = [c.get("h") for c in cells]
    total = AH - GAP * (n - 1)
    if all(given):
        hs = given
    elif any(given):
        rest = total - sum(h for h in given if h)
        k = sum(1 for h in given if not h)
        hs = [h if h else rest // k for h in given]
    else:
        hs = list(DEFAULT_H.get(n, [total // n] * n))
    hs[-1] += total - sum(hs)
    return hs


def cap(c):
    v = c.get("cap")
    if v is None:
        return None
    return {"text": v} if isinstance(v, str) else v


def main(ep_dir):
    ep = pathlib.Path(ep_dir)
    s = json.loads((ep / "story.json").read_text())
    accent, accent_name = SERIES[s["series"]]
    panels, slides = [], []

    def add_panel(pid, size, scene, nop=False, owl=False, ref=None):
        p = {"id": pid, "size": list(size), "prompt": scene + (OWL if owl else NOP if nop else "")}
        if owl:
            p["with_character"] = True
        if ref:
            p["ref_panels"] = ref
        panels.append(p)

    for i, sl in enumerate(s["slides"], 1):
        n = f"s{i:02d}"
        if "cover" in sl:
            add_panel(n + "a", (AW, AH), sl["scene"], sl.get("nop", True), ref=sl.get("ref"))
            cv = dict(sl["cover"]); cv.setdefault("badge", s["series"])
            slides.append({"layout": "one", "footer_left": "@ossak_alarm",
                           "cells": [{"panel": n + "a", "cover": cv}]})
        elif "card" in sl:
            slides.append({"layout": "one", "cells": [{"card": sl["card"]}]})
        elif "rows" in sl:
            cells_in = sl["rows"]
            hs = heights(cells_in)
            cells = []
            for j, (c, h) in enumerate(zip(cells_in, hs)):
                cell = {}
                if "card" in c:
                    cell["card"] = c["card"]
                else:
                    pid = c.get("panel")
                    if not pid:
                        pid = n + "abc"[j]
                        add_panel(pid, (AW, h), c["scene"], c.get("nop", False), c.get("owl", False), c.get("ref"))
                    cell["panel"] = pid
                    if cap(c):
                        cell["caption"] = cap(c)
                    if c.get("bubble"):
                        cell["bubble"] = c["bubble"]
                cells.append(cell)
            slides.append({"layout": "rows", "heights": hs, "cells": cells})
        elif "end" in sl:
            e = sl["end"]
            add_panel(n + "a", (AW, 760), e["scene"], owl=True)
            src_lines = [{"text": "출처", "size": 24, "weight": 700, "color": "#9AA3B8"}]
            src_lines += [{"text": t} for t in s["sources"]]
            src_lines.append({"text": "그림은 사건을 재구성한 AI 일러스트입니다", "size": 18, "color": "#7C86A2"})
            nxt = s.get("next", "")
            slides.append({"layout": "cols2_bottom", "heights": [760], "footer_left": "@ossak_alarm", "cells": [
                {"panel": n + "a", "bubble": {"text": e["bubble"], "x": e.get("x", 0.4), "y": e.get("y", 0.08),
                                                "maxw": e.get("maxw", 0.56), "size": e.get("size", 42)}},
                {"card": {"type": "text", "pad": 32, "lines": src_lines}},
                {"card": {"type": "text", "pad": 32, "border": "#3FB8A8", "lines": [
                    {"text": "다음 편", "size": 24, "weight": 700, "color": "#9AA3B8"},
                    {"text": nxt, "size": 32, "weight": 700, "color": "#EDE6D6", "lh": 1.35},
                    {"text": "내일 밤 9시 30분 · 팔로우하고 알림 받기", "size": 22}]}}]})
        else:
            raise ValueError(f"slide {i}: unknown type")

    out = {"id": s["id"], "series": s["series"], "title": s["title"], "accent": accent, "accent_name": accent_name,
           "footer": f'{s["series"]} · {s["title"]}', "character": CHARACTER,
           "sources": s.get("source_urls", s["sources"]), "panels": panels, "slides": slides}
    for k in ("caption", "threads", "reels_script", "risk"):
        if k in s:
            out[k] = s[k]
    (ep / "episode.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'{ep.name}: {len(slides)}장, 그림 {len(panels)}컷 → episode.json')


if __name__ == "__main__":
    for d in sys.argv[1:]:
        main(d)
