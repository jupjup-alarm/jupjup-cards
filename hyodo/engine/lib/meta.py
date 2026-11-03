"""업로드 정보: 설명란(챕터·출처·고지), 태그, 고정 댓글, ego lite job.json. python3 lib/meta.py episodes/<편>"""
import json, pathlib, sys

NOTICE = ("※ 정부기관과 관계없는 개인 채널입니다. 기준은 바뀔 수 있으니 신청 전 해당 기관에서 꼭 확인하세요.\n"
          "※ 화면 일부와 내레이션은 AI 도구로 제작했습니다.")


def mmss(t):
    t = int(t); return f"{t // 60}:{t % 60:02d}"


def make(ep):
    spec = json.loads((ep / "video.json").read_text())
    tl = json.loads((ep / "out" / "timeline.json").read_text())
    t, chapters = 0.0, []
    for s in spec["scenes"]:
        chapters.append(f"{mmss(t)} {s['chapter']}"); t += tl[s["id"]]["dur"]
    S = {s["id"]: s for s in spec["scenes"]}
    # 태그·해시태그는 편마다 video.json에 적는다: "tags": [...], "hashtags": ["#기초연금", ...]
    tags = spec.get("tags") or ["정부지원금", "효도알람"]
    if "효도알람" not in tags:
        tags = tags + ["효도알람"]
    hs = spec.get("hashtags") or ["#" + tags[0].replace(" ", ""), "#정부지원금"]
    hashtags = " ".join(hs + ["#효도알람"])
    playlist = spec.get("playlist") or {"본인": "본인 받을 돈", "자녀": "자녀 받을 돈"}.get(spec.get("category", ""), "달라지는 정책")
    rows = S["summary"]["data"]["rows"]
    src = "\n".join(f"· {x['name']} {x['url']}" for x in spec["sources"])
    desc = (f"{spec['title']}\n\n"
            + "\n".join(f"✔ {a}: {b}" for a, b in rows)
            + f"\n\n{S['apply']['data']['tel']}\n\n[챕터]\n" + "\n".join(chapters)
            + f"\n\n[출처] 확인일 {spec['checked']}\n{src}\n\n{NOTICE}\n\n{hashtags}")

    pinned = ("3줄 요약\n" + "\n".join(f"· {a}: {b}" for a, b in rows) + f"\n문의: {S['apply']['data']['tel']}")
    long = {"id": spec["id"], "format": "롱폼", "title": spec["title"], "description": desc, "tags": tags,
            "pinned": pinned, "chapters": chapters, "video": f"{spec['id']}.mp4", "thumb": f"{spec['id']}_thumb.jpg",
            "length": round(t, 1), "playlist": playlist}
    shorts = []
    for sh in spec.get("shorts", []):
        shorts.append({"id": sh["id"], "format": "숏츠", "title": sh["title"],
                       "description": f"{sh['title']}\n\n자세한 신청 방법은 효도알람 전체 영상에서 확인하세요.\n\n[출처] 확인일 {spec['checked']}\n{src}\n\n{NOTICE}\n\n" + " ".join(hs[:2] + ["#shorts"]),
                       "tags": tags, "video": f"{sh['id']}.mp4", "playlist": playlist, "parent": spec["id"]})
    out = {"long": long, "shorts": shorts}
    (ep / "out" / "upload.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    o = make(pathlib.Path(sys.argv[1]).resolve())
    print(o["long"]["description"]); print("---"); print(o["long"]["pinned"])
