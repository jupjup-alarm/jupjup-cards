"""유튜브 탭에 넣을 행(A~P) 만들기: 롱폼 1 + 숏츠 2. publish.py 다음에 쓴다.

  python3 lib/rows.py episodes/<편> <롱폼 업로드일 YYYY-MM-DD> "<검수 결과>"

- 롱폼: 설정의 롱폼 기본 시각 07:00, 숏츠: 다음 날·다다음 날 12:30
- 상태(O)는 '업로드대기'(자동 발행 원칙, 2026-11-03 운영자 결정). 자동 검수에 걸린 편은 행을 넣지 않는다.
- 수정본(정정)은 publish.py --rev N 뒤에 rows.py를 돌려 L·M열 주소만 새 파일로 바꾸는 데 쓴다(README 8절).
- 출력: out/sheet_rows.json (구글 시트 update_values/append_values에 그대로 넣는 2차원 배열)
"""
import datetime as dt, json, pathlib, sys

LONG_T, SHORT_T = "07:00", "12:30"


def main(ep, day, review):
    spec = json.loads((ep / "video.json").read_text())
    up = json.loads((ep / "out" / "upload.json").read_text())
    L = up["long"]
    if "video_url" not in L:
        raise SystemExit("upload.json에 video_url이 없어요 — 먼저 lib/publish.py를 돌리세요")
    d0 = dt.date.fromisoformat(day)
    cat = spec.get("category", "")
    rows = [[d0.isoformat(), LONG_T, L["id"], "롱폼", cat, "", L["title"], L["description"], ", ".join(L["tags"]),
             L["pinned"], "\n".join(L["chapters"]), L["video_url"], L.get("thumb_url", ""), L["playlist"], "업로드대기", review]]
    for i, s in enumerate(up["shorts"], 1):
        rows.append([(d0 + dt.timedelta(days=i)).isoformat(), SHORT_T, s["id"], "숏츠", cat, L["id"], s["title"],
                     s["description"], ", ".join(s["tags"]), "", "", s["video_url"], "", s["playlist"], "업로드대기", review])
    for r in rows:
        if len(r[6]) > 100:
            raise SystemExit(f"{r[2]}: 제목 {len(r[6])}자 — 유튜브 최대 100자")
    (ep / "out" / "sheet_rows.json").write_text(json.dumps(rows, ensure_ascii=False))
    for r in rows:
        print(r[0], r[1], r[2], r[3], r[6])


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3])
