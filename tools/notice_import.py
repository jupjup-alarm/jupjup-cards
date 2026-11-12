"""공고문 PDF → site/data/notice_text/<key>.txt (2026-11-04 — 청약홈 공고문을 사용자 Mac의 ego lite가 받아 오면 여기로).

청약홈 상세 페이지는 자동 접속을 막아서, 사용자 Mac의 ego lite 브라우저가 사람처럼 열어 공고문 PDF를
~/줍줍알람/공고문/<key>.pdf 로 받는다 (받을 목록: site/data/notice_wanted.json — 빌드가 매일 만든다).
이 도구는 그 PDF를 글자로 뽑아 저장소에 넣는다. ⑦ SEO 발행 담당이 LH 공고문과 똑같이 읽어 페이지를 채운다.

팸플릿도 받는다 (2026-11-04 사용자 결정 "공고문과 팜플렛이 있으면 팜플렛도 받아야 해"):
  공고문 = <key>.pdf, 팸플릿 = <key>-pamphlet.pdf (여러 개면 <key>-pamphlet2.pdf …).
  팸플릿은 저장소에 PDF를 올리지 않고, 큰 그림만 뽑아 pamphlets/<key>/cand-NN.jpg(긴 변 1600px) + contact.jpg로 올린다.
  ⑦이 그중 조감도·배치도·동호배치도·평면도·인테리어를 골라 photos/site/<key>/로 옮긴다.
  청약홈·분양 홈페이지 어디에도 팸플릿이 없으면 `--no-pamphlet <key>`로 '없음'을 남긴다 (다음 날 다시 찾지 않게).

사용 (Mac의 저장소 사본 ~/줍줍알람/jupjup-cards 에서):
  python3 tools/notice_import.py ~/줍줍알람/공고문/*.pdf          # 파일 이름(확장자 앞)이 공고 key (팸플릿은 key-pamphlet)
  python3 tools/notice_import.py 받은파일.pdf --key 2026940245
  python3 tools/notice_import.py ~/줍줍알람/공고문/*.pdf --push   # 커밋·푸시까지
글자 뽑기: pdftotext(-layout)가 있으면 그것, 없으면 pypdf (pip install pypdf). 팸플릿 그림: pdfimages가 있으면 그것, 없으면 pypdf + Pillow.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
APT = ROOT / "site" / "data" / "apt"
OUT_T = ROOT / "site" / "data" / "notice_text"
OUT_F = ROOT / "site" / "data" / "notice_files"
PAM = ROOT / "pamphlets"


def text_of(pdf):
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout, "pdftotext"
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pdftotext도 pypdf도 없어요 — `pip3 install pypdf` 후 다시")
    rd = PdfReader(str(pdf))
    return "\n\f".join((p.extract_text() or "") for p in rd.pages), "pypdf"


def pamphlet_images(pdf, folder, limit=40):
    """팸플릿 PDF의 큰 그림(긴 변 1000px+, 짧은 변 400px+)을 긴 변 1600px JPEG로 → folder/cand-NN.jpg, contact.jpg."""
    import io
    import tempfile
    from PIL import Image, ImageDraw
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("cand-*.jpg"):
        old.unlink()
    ims = []
    if shutil.which("pdfimages"):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdfimages", "-j", str(pdf), f"{td}/i"], capture_output=True, timeout=900)
            for f in sorted(Path(td).glob("i-*")):
                try:
                    im = Image.open(f)
                    im.load()
                    ims.append(im)
                except Exception:  # noqa: BLE001
                    pass
    else:
        from pypdf import PdfReader
        for page in PdfReader(str(pdf)).pages:
            for x in getattr(page, "images", []):
                try:
                    ims.append(Image.open(io.BytesIO(x.data)))
                except Exception:  # noqa: BLE001
                    pass
    out = []
    for im in ims:
        if max(im.size) < 1000 or min(im.size) < 400:
            continue
        im = im.convert("RGB")
        im.thumbnail((1600, 1600))
        n = len(out) + 1
        dst = folder / f"cand-{n:02d}.jpg"
        im.save(dst, "JPEG", quality=82, optimize=True)
        out.append({"file": str(dst.relative_to(ROOT)), "w": im.width, "h": im.height})
        if len(out) >= limit:
            break
    if out:
        tw, th, cols = 260, 200, 6
        rows = (len(out) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + 18)), "white")
        d = ImageDraw.Draw(sheet)
        for i, o in enumerate(out):
            x, y = (i % cols) * tw, (i // cols) * (th + 18)
            with Image.open(ROOT / o["file"]) as im:
                im.thumbnail((tw - 6, th - 6))
                sheet.paste(im, (x + 3, y + 3))
            d.text((x + 4, y + th), Path(o["file"]).name, fill="red")
        sheet.save(folder / "contact.jpg", quality=80)
    return out


def notice_images(pdf, folder, limit=12):
    """공고문 PDF 그림 (2026-11-11 — 홈페이지가 없거나 막힌 단지용): 큰 그림(pamphlet_images와 같은 기준) +
    pdftoppm이 있으면 '배치도·동호·평면·위치도' 글자가 있는 쪽을 통째로 그림으로(선으로 그린 배치도는 그림 파일이 아니라서).
    → folder/cand-NN.jpg (+ cand-pNN.jpg). collect.py가 팸플릿처럼 검수 대기로 넣는다."""
    out = pamphlet_images(pdf, folder, limit=limit)
    if not shutil.which("pdftoppm"):
        return out
    import tempfile
    from PIL import Image
    try:
        if shutil.which("pdftotext"):
            pages = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=300).stdout.split("\f")
        else:
            from pypdf import PdfReader
            pages = [(pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages]
    except Exception:  # noqa: BLE001
        return out
    want = [i + 1 for i, t in enumerate(pages) if re.search(r"(단지\s*)?배치도|동\s*·?\s*호수?\s*배치|평면도|위치도", t) and len(t.strip()) < 2500][:6]
    for pno in want:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdftoppm", "-r", "130", "-f", str(pno), "-l", str(pno), "-jpeg", str(pdf), f"{td}/p"], capture_output=True, timeout=300)
            for f in Path(td).glob("p*.jpg"):
                with Image.open(f) as im:
                    im = im.convert("RGB")
                    im.thumbnail((1600, 1600))
                    dst = folder / f"cand-p{pno:02d}.jpg"
                    im.save(dst, "JPEG", quality=82)
                    out.append({"file": str(dst.relative_to(ROOT)), "w": im.width, "h": im.height})
    return out


def load_meta(key):
    p = OUT_F / f"{key}.json"
    return p, (json.loads(p.read_text()) if p.exists() else {"key": key, "source": "ego lite (사용자 브라우저)", "files": []})


def save_meta(p, meta):
    OUT_F.mkdir(parents=True, exist_ok=True)
    meta["checked"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="*")
    ap.add_argument("--key")
    ap.add_argument("--no-pamphlet", nargs="*", default=[], metavar="KEY", help="팸플릿을 찾았지만 없던 공고 key")
    ap.add_argument("--site", nargs="*", default=[], metavar="TXT", help="분양 홈페이지 이미지 목록(AI열 형식, 첫 줄 key:) — tools/site_photos.py로 받음")
    ap.add_argument("--no-site", nargs="*", default=[], metavar="KEY", help="홈페이지에 쓸 그림이 없던 공고 key")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    done = []
    for key in a.no_pamphlet:
        if (APT / f"{key}.json").exists():
            mp, meta = load_meta(key)
            if not meta.get("pamphlet_none"):
                meta["pamphlet_none"] = dt.date.today().isoformat()
                save_meta(mp, meta)
                done.append(key)
                print(f"팸플릿 없음 기록: {key}")
    for key in a.no_site:
        if (APT / f"{key}.json").exists():
            mp, meta = load_meta(key)
            if not meta.get("site_none"):
                meta["site_none"] = dt.date.today().isoformat()
                save_meta(mp, meta)
                done.append(key)
                print(f"홈페이지 그림 없음 기록: {key}")
    for f in a.site:   # 2026-11-04 사용자 결정 "공식 홈페이지에서 평면도·단지배치도·동호수배치도·단지 둘러보기도, 원본 크기로"
        t = Path(f).expanduser()
        m = re.search(r"^\s*key\s*[:：]\s*([0-9A-Za-z_-]+)", t.read_text(encoding="utf-8"), re.M)
        if not m or not (APT / f"{m.group(1)}.json").exists():
            print(f"건너뜀: {t.name} — 첫 줄 key: 가 없거나 공고 파일이 없음")
            continue
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "site_photos.py"), "--file", str(t)], capture_output=True, text=True)
        print(r.stdout[-1500:] or r.stderr[-800:])
        if r.returncode == 0:
            mp, meta = load_meta(m.group(1))
            meta["site"] = dt.date.today().isoformat()
            meta.pop("site_none", None)
            save_meta(mp, meta)
            done.append(m.group(1))
    for f in a.pdfs:
        p = Path(f).expanduser()
        stem = a.key or p.stem
        m = re.fullmatch(r"(.+?)-pamphlet(\d*)", stem)
        key, kind = (m.group(1), "pamphlet") if m else (stem, "notice")
        if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z_-]{2,60}", key) or not (APT / f"{key}.json").exists():
            print(f"건너뜀: {p.name} — 공고 key({key})에 맞는 site/data/apt/{key}.json 없음")
            continue
        raw = p.read_bytes()
        if not raw.startswith(b"%PDF"):
            print(f"건너뜀: {p.name} — PDF가 아님 (차단 화면을 저장했을 수 있음)")
            continue
        md5 = hashlib.md5(raw).hexdigest()
        mp, meta = load_meta(key)
        if any(x.get("md5") == md5 for x in meta.get("files", [])):
            print(f"그대로: {p.name} (같은 파일)")
            continue
        rec = {"name": p.name, "kind": kind, "md5": md5, "bytes": len(raw), "got": "ok"}
        if kind == "notice":
            txt, how = text_of(p)
            if len(txt.strip()) < 500:
                print(f"경고: {key} 글자가 거의 없어요({len(txt.strip())}자) — 그림으로 된 PDF일 수 있음")
            OUT_T.mkdir(parents=True, exist_ok=True)
            (OUT_T / f"{key}.txt").write_text(f"===== {p.name} =====\n{txt}", encoding="utf-8")
            rec["text_by"] = how
            print(f"공고문 저장: {key} ({len(txt):,}자, {how})")
            try:
                c = notice_images(p, PAM / key / "notice")
                rec["cands"] = len(c)
                print(f"공고문 그림: {key} {len(c)}장 → pamphlets/{key}/notice/")
            except Exception as e:  # noqa: BLE001
                print(f"공고문 그림 실패: {key} {e}")
            try:   # 2026-11-12 공고문 화면 컷 (공급금액·신청일정·신청자격) — 이야기형 릴스 증거 카드
                import notice_shots
                r = notice_shots.make(key, p)
                print(f"공고문 화면 컷: {key} {len(r.get('notice_shots') or [])}장 → photos/site/{key}/notice-*.jpg")
            except Exception as e:  # noqa: BLE001
                print(f"공고문 화면 컷 실패: {key} {e}")
        else:
            sub = PAM / key / (m.group(2) or "1")
            c = pamphlet_images(p, sub)
            rec["cands"] = len(c)
            rec["folder"] = str(sub.relative_to(ROOT))
            print(f"팸플릿 그림: {key} {len(c)}장 → {rec['folder']}/contact.jpg")
        meta["files"] = [x for x in meta.get("files", []) if not (x.get("kind") == kind and x.get("name") == p.name)] + [rec]
        meta["changed"] = True
        meta.pop("pamphlet_none", None) if kind == "pamphlet" else None
        save_meta(mp, meta)
        done.append(key)
    if a.push and done:
        g = lambda *c: subprocess.run(["git", "-C", str(ROOT), *c], check=True)
        g("add", "site/data/notice_text", "site/data/notice_files")
        if PAM.exists():
            g("add", "pamphlets")
        if (ROOT / "photos" / "site").exists():
            g("add", "photos/site")
        g("commit", "-m", f"data: 청약홈 공고문·팸플릿·홈페이지 그림 {len(set(done))}건 (ego lite)")
        for _ in range(3):
            if subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "origin", "main"]).returncode == 0 and \
               subprocess.run(["git", "-C", str(ROOT), "push", "origin", "HEAD:main"]).returncode == 0:
                break
        else:
            sys.exit("푸시 실패 — 다음 실행에서 다시")


if __name__ == "__main__":
    main()
