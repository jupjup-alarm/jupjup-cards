"""완성 영상·썸네일을 저장소 hyodo/<편ID>/ 로 옮기고 공개 주소를 upload.json에 적는다.

  python3 lib/publish.py episodes/<편>

- 공개 주소: https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/hyodo/<편ID>/<파일>
- GitHub 한 파일 상한 100MB. 90MB가 넘는 영상은 CRF를 올려 다시 인코딩한다(화면이 거의 정지라 화질 차이가 작다).
- 커밋·푸시는 하지 않는다(호출한 쪽이 git add hyodo/ 로 함께 올린다).
"""
import json, pathlib, shutil, subprocess, sys

ENGINE = pathlib.Path(__file__).resolve().parent.parent
REPO = ENGINE.parent.parent  # jupjup-cards
BASE = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/hyodo"
LIMIT = 90 * 1024 * 1024


def shrink(src, dst):
    for crf in (26, 30, 34):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)
        if dst.stat().st_size <= LIMIT:
            return crf
    raise SystemExit(f"{src.name}: CRF 34로도 90MB를 넘어요 — 길이를 줄이거나 R2가 필요해요")


def main(ep):
    out = ep / "out"
    up = json.loads((out / "upload.json").read_text())
    vid = up["long"]["id"]
    dest = REPO / "hyodo" / vid
    dest.mkdir(parents=True, exist_ok=True)
    items = [up["long"]] + up["shorts"]
    report = []
    for it in items:
        src = out / it["video"]
        tgt = dest / src.name
        if src.stat().st_size > LIMIT:
            crf = shrink(src, tgt); report.append(f"{src.name}: CRF {crf}로 다시 인코딩")
        else:
            shutil.copy(src, tgt)
        it["video_url"] = f"{BASE}/{vid}/{tgt.name}"
        it["size_mb"] = round(tgt.stat().st_size / 1048576, 1)
    th = out / up["long"]["thumb"]
    shutil.copy(th, dest / th.name)
    up["long"]["thumb_url"] = f"{BASE}/{vid}/{th.name}"
    (out / "upload.json").write_text(json.dumps(up, ensure_ascii=False, indent=1))
    shutil.copy(out / "upload.json", dest / "upload.json")
    for it in items:
        print(it["id"], it["size_mb"], "MB", it["video_url"])
    print(up["long"]["thumb_url"])
    for r in report:
        print(r)


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]).resolve())
