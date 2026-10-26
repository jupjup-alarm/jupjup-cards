#!/usr/bin/env python3
"""episode.json(또는 story.json)에서 장별 자막만 뽑는다 — '처음 보는 사람 검수'용.

  python3 ossak/captions.py episodes/<편>
"""
import json, pathlib, sys


def text_of(cap):
    return cap if isinstance(cap, str) else (cap or {}).get("text", "")


def card_text(cd):
    t = cd.get("type")
    if t == "evidence":
        return "[저장 카드] " + " / ".join(f'{x["head"]}: {x["body"]}' for x in cd["items"])
    if t == "list":
        return "[목록 카드] " + cd.get("title", "") + ": " + " / ".join(x["head"] + " " + " ".join(x.get("lines", [])) for x in cd["items"])
    if t == "timeline":
        return "[연표 카드] " + " / ".join(f'{x.get("head","")} {x.get("body","")}' for x in cd.get("items", []))
    lines = [l["text"] for l in cd.get("lines", []) if l.get("text") not in ("출처", "다음 편")]
    return "[카드] " + " / ".join(lines)


def from_episode(e):
    out = []
    for i, sl in enumerate(e["slides"], 1):
        t = []
        for c in sl["cells"]:
            if "cover" in c:
                cv = c["cover"]; t.append("[표지] " + " ".join(cv["title"]) + (" / " + cv["sub"] if cv.get("sub") else ""))
            if "caption" in c: t.append(text_of(c["caption"]))
            if "bubble" in c: t.append("[부엉이 말풍선] " + c["bubble"]["text"])
            if "card" in c and not any(l.get("text") in ("출처", "다음 편") for l in c["card"].get("lines", [])):
                t.append(card_text(c["card"]))
        out.append(f"{i}장: " + "  ▸ ".join(x.replace("\n", " ") for x in t if x))
    return out


def from_story(s):
    out = []
    for i, sl in enumerate(s["slides"], 1):
        t = []
        if "cover" in sl:
            cv = sl["cover"]; t.append("[표지] " + " ".join(cv["title"]) + (" / " + cv["sub"] if cv.get("sub") else ""))
        for c in sl.get("rows", []):
            if "cap" in c: t.append(text_of(c["cap"]))
            if "card" in c: t.append(card_text(c["card"]))
        if "card" in sl: t.append(card_text(sl["card"]))
        if "end" in sl: t.append("[부엉이 말풍선] " + sl["end"]["bubble"])
        out.append(f"{i}장: " + "  ▸ ".join(x.replace("\n", " ") for x in t if x))
    return out


if __name__ == "__main__":
    ep = pathlib.Path(sys.argv[1])
    if (ep / "story.json").exists():
        lines = from_story(json.loads((ep / "story.json").read_text()))
    else:
        lines = from_episode(json.loads((ep / "episode.json").read_text()))
    print("\n".join(lines))
