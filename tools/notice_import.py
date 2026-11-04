"""공고문 PDF → site/data/notice_text/<key>.txt (2026-11-04 — 청약홈 공고문을 사용자 Mac의 ego lite가 받아 오면 여기로).

청약홈 상세 페이지는 자동 접속을 막아서, 사용자 Mac의 ego lite 브라우저가 사람처럼 열어 공고문 PDF를
~/줍줍알람/공고문/<key>.pdf 로 받는다 (받을 목록: site/data/notice_wanted.json — 빌드가 매일 만든다).
이 도구는 그 PDF를 글자로 뽑아 저장소에 넣는다. ⑦ SEO 발행 담당이 LH 공고문과 똑같이 읽어 페이지를 채운다.

사용 (Mac의 저장소 사본 ~/줍줍알람/jupjup-cards 에서):
  python3 tools/notice_import.py ~/줍줍알람/공고문/*.pdf          # 파일 이름(확장자 앞)이 공고 key
  python3 tools/notice_import.py 받은파일.pdf --key 2026940245
  python3 tools/notice_import.py ~/줍줍알람/공고문/*.pdf --push   # 커밋·푸시까지
글자 뽑기: pdftotext(-layout)가 있으면 그것, 없으면 pypdf (pip install pypdf).
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
APT = ROOT / "site" / "data" / "apt"
OUT_T = ROOT / "site" / "data" / "notice_text"
OUT_F = ROOT / "site" / "data" / "notice_files"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--key")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    done = []
    for f in a.pdfs:
        p = Path(f).expanduser()
        key = a.key or p.stem
        if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z_-]{2,60}", key) or not (APT / f"{key}.json").exists():
            print(f"건너뜀: {p.name} — 공고 key({key})에 맞는 site/data/apt/{key}.json 없음")
            continue
        raw = p.read_bytes()
        if not raw.startswith(b"%PDF"):
            print(f"건너뜀: {p.name} — PDF가 아님 (차단 화면을 저장했을 수 있음)")
            continue
        md5 = hashlib.md5(raw).hexdigest()
        meta_p = OUT_F / f"{key}.json"
        old = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        if old.get("files") and old["files"][0].get("md5") == md5:
            print(f"그대로: {key} (같은 파일)")
            continue
        txt, how = text_of(p)
        if len(txt.strip()) < 500:
            print(f"경고: {key} 글자가 거의 없어요({len(txt.strip())}자) — 그림으로 된 PDF일 수 있음")
        OUT_T.mkdir(parents=True, exist_ok=True)
        OUT_F.mkdir(parents=True, exist_ok=True)
        (OUT_T / f"{key}.txt").write_text(f"===== {p.name} =====\n{txt}", encoding="utf-8")
        meta_p.write_text(json.dumps({"key": key, "source": "ego lite (사용자 브라우저)", "checked": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                      "files": [{"name": p.name, "kind": "notice", "md5": md5, "bytes": len(raw), "got": "ok", "text_by": how}],
                                      "changed": True}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        done.append(key)
        print(f"저장: {key} ({len(txt):,}자, {how})")
    if a.push and done:
        g = lambda *c: subprocess.run(["git", "-C", str(ROOT), *c], check=True)
        g("add", "site/data/notice_text", "site/data/notice_files")
        g("commit", "-m", f"data: 청약홈 공고문 글자 {len(done)}건 (ego lite)")
        for _ in range(3):
            if subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "origin", "main"]).returncode == 0 and \
               subprocess.run(["git", "-C", str(ROOT), "push", "origin", "HEAD:main"]).returncode == 0:
                break
        else:
            sys.exit("푸시 실패 — 다음 실행에서 다시")


if __name__ == "__main__":
    main()
