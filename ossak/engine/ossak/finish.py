#!/usr/bin/env python3
"""조판이 끝난 편을 발행용으로 마무리한다.

  python3 ossak/finish.py episodes/<편> --date 2026-11-03 [--caro-time 21:30] [--threads-time 12:30]

1. slides/NN.png → 저장소 ossak/<편>/NN.jpg (품질 92, 인스타 API는 JPG만 받음)
2. 미리보기 시트 episodes/<편>/preview.jpg (6열 축소본, 검수용)
3. 발행계획에 붙일 두 행(인스타 캐러셀·스레드)을 rows.json 으로 출력
   - 캐러셀: --date 의 캐러셀 시각, 스레드: 다음 날 스레드 시각 (스레드 끝 '풀버전은 인스타에'라서 인스타가 먼저)
   - 날짜·시각은 앞에 작은따옴표를 붙여 텍스트로 넣는다. 장수(M열)는 시트 수식이 채운다 → A:L 12칸만.
"""
import argparse, datetime, json, pathlib
from PIL import Image

ENGINE = pathlib.Path(__file__).resolve().parent.parent
REPO_OSSAK = ENGINE.parent  # jupjup-cards/ossak
BASE = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/ossak/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--date", required=True)
    ap.add_argument("--caro-time", default="21:30")
    ap.add_argument("--threads-time", default="12:30")
    a = ap.parse_args()
    ep = pathlib.Path(a.episode).resolve()
    spec = json.loads((ep / "episode.json").read_text())
    slides = sorted((ep / "slides").glob("*.png"))
    if not slides:
        raise SystemExit("slides/*.png 없음 — compose.py 먼저")
    if len(slides) > 20:
        raise SystemExit(f"{len(slides)}장: 인스타 캐러셀은 최대 20장 — 1부/2부로 나누세요")
    out = REPO_OSSAK / ep.name
    out.mkdir(parents=True, exist_ok=True)
    for f in slides:
        Image.open(f).convert("RGB").save(out / (f.stem + ".jpg"), quality=92, optimize=True)
    # 미리보기
    w, h, cols = 360, 450, 6
    rows_n = (len(slides) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows_n * h))
    for i, f in enumerate(slides):
        sheet.paste(Image.open(f).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(ep / "preview.jpg", quality=82)
    # 발행계획 행
    cover = spec["slides"][0]["cells"][0]["cover"]
    hook = " ".join(cover["title"])
    urls = "\n".join(f"{BASE}{ep.name}/{f.stem}.jpg" for f in slides)
    d1 = datetime.date.fromisoformat(a.date)
    d2 = d1 + datetime.timedelta(days=1)
    risk = spec.get("risk", "저")
    base = [spec["id"], spec["series"], spec["title"], hook, risk, "예약"]
    rows = [
        ["'" + d1.isoformat(), "'" + a.caro_time, "인스타 캐러셀", *base, spec.get("caption", ""), "", urls],
        ["'" + d2.isoformat(), "'" + a.threads_time, "스레드", *base, "", "\n---\n".join(spec.get("threads", [])), ""],
    ]
    (ep / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"{ep.name}: JPG {len(slides)}장 → {out}")
    print(f"미리보기 {ep / 'preview.jpg'}")
    print(f"발행계획 행 → {ep / 'rows.json'}")


if __name__ == "__main__":
    main()
