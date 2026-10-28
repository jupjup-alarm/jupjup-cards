"""LH 매입임대 공고의 주택 목록 → apt 파일의 "houses" 배열

'LH공고' 탭 L열(단지·공급 상세)의 "[공급] 호: … · 모집지역: … · 전용면적(㎡): … · 층수: … · 주소: …" 줄을 읽는다.
손으로 옮겨 적지 말고 이 스크립트로 바꿔서 붙인다.

사용:
    python3 site/tools/lh_houses.py L열.txt > houses.json
    python3 site/tools/lh_houses.py L열.txt --into site/data/apt/lh2015122300020945.json   # houses만 바꿔 넣기
"""
import json
import re
import sys
from pathlib import Path

SIDO = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
        "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
        "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
        "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}


def parse_line(line):
    f = {}
    for part in line.replace("[공급]", "").split(" · "):
        if ":" in part:
            k, v = part.split(":", 1)
            f[k.strip()] = v.strip()
    addr = f.get("주소", "")
    if not addr:
        return None
    toks = addr.split()
    sido = SIDO.get(toks[0], toks[0])
    # 시·군·구: '부천시 소사구'처럼 시+구는 둘 다
    sgg = [toks[1]] if len(toks) > 1 else []
    if len(toks) > 2 and re.search(r"(구|군)$", toks[2]) and toks[1].endswith("시"):
        sgg.append(toks[2])
    m = re.search(r"\(([^)]*)\)", addr)
    inner = [x.strip() for x in (m.group(1).split(",") if m else [])]
    dong = inner[0] if inner and re.search(r"(동|읍|면|리|가)$", inner[0]) else ""
    name = inner[1] if len(inner) > 1 else ""
    rest = addr[m.end():] if m else ""
    rest = re.sub(r"\[구[^\]]*\]", " ", rest)            # [구 570-25] 옛 지번
    rest = re.sub(r"/\s*\S+(구|군|시)\s*$", " ", rest)    # 끝의 /소사구
    rest = re.sub(r"[()]", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    if rest and not name:
        name = rest
    elif rest and rest != name and rest not in name:
        name = (name + " " + rest).strip() if name else rest
    road = addr[:m.start()].strip() if m else addr
    floor = re.sub(r"\D", "", f.get("층수", "")) or None
    excl = f.get("전용면적(㎡)")
    return {"sido": sido, "sigungu": " ".join(sgg), "dong": dong, "name": name, "road": road,
            "unit": f.get("호", ""), "floor": int(floor) if floor else None,
            "excl": float(excl) if excl else None, "area_label": f.get("모집지역", "")}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lines = [l for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if "[공급]" in l]
    houses = [h for h in (parse_line(l) for l in lines) if h]
    houses.sort(key=lambda h: (h["sido"], h["sigungu"], h["dong"], h["road"], h["unit"]))
    if "--into" in sys.argv:
        p = Path(sys.argv[sys.argv.index("--into") + 1])
        d = json.loads(p.read_text(encoding="utf-8"))
        d["houses"] = houses
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{p.name}: houses {len(houses)}호")
    else:
        print(json.dumps(houses, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
