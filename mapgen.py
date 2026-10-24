"""위치 지도 SVG 생성 (오프라인, 통계청 SGIS 2018 행정구역 경계 · 공공누리 제1유형).

make_map(sigungu, dong=None, sido=None, ...) -> (svg_str, info)
- sigungu: '강동구', '계양구', '성남시 분당구'처럼 시군구 이름
- dong: 행정동 이름 ('강일동', '계양1동'). 못 찾으면 시군구 전체를 강조하고 info['candidates']에 그 시군구의 행정동 목록을 돌려줌
- sido: 같은 이름 시군구가 여러 곳일 때 구분용 ('서울', '인천', '경기' 등 앞부분만 써도 됨)
"""
import json
import math
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SIDO_CODE = {"11": "서울", "21": "부산", "22": "대구", "23": "인천", "24": "광주", "25": "대전", "26": "울산",
             "29": "세종", "31": "경기", "32": "강원", "33": "충북", "34": "충남", "35": "전북", "36": "전남",
             "37": "경북", "38": "경남", "39": "제주"}


@lru_cache(None)
def _load(name):
    topo = json.loads((DATA / name).read_text())
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        out = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out

    feats = []
    for g in list(topo["objects"].values())[0]["geometries"]:
        polys = []
        if g["type"] == "Polygon":
            polys = [[ring(r) for r in g["arcs"]]]
        elif g["type"] == "MultiPolygon":
            polys = [[ring(r) for r in p] for p in g["arcs"]]
        feats.append({"props": g["properties"], "polys": polys})
    return feats


def _bbox(polys):
    xs = [p[0] for poly in polys for r in poly for p in r]
    ys = [p[1] for poly in polys for r in poly for p in r]
    return min(xs), min(ys), max(xs), max(ys)


def _centroid(polys):
    # 가장 큰 외곽 링의 면적 중심
    best, area_best = None, 0
    for poly in polys:
        r = poly[0]
        a = cx = cy = 0
        for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
            f = x0 * y1 - x1 * y0
            a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
        if abs(a) > area_best:
            area_best, best = abs(a), (cx / (3 * a), cy / (3 * a))
    return best


def _find_sgg(sigungu, sido=None):
    sgg = [f for f in _load("skorea-municipalities-2018-topo.json")
           if f["props"]["name"].replace(" ", "") == sigungu.replace(" ", "")
           or f["props"]["name"].replace(" ", "").endswith(sigungu.replace(" ", ""))]
    if sido and len(sgg) > 1:
        sgg = [f for f in sgg if SIDO_CODE.get(f["props"]["code"][:2], "") and sido.startswith(SIDO_CODE[f["props"]["code"][:2]])] or sgg
    return sgg[0] if sgg else None


def make_map(sigungu, dong=None, sido=None, width=920, height=600, accent="#E0401F", tint="#FFE3D9",
             base="#E9EDF2", line="#FFFFFF", ink="#0F1E3D", label_dong=None):
    info = {"found_sigungu": False, "found_dong": False, "candidates": []}
    sgg = _find_sgg(sigungu, sido)
    if not sgg:
        info["error"] = f"시군구 '{sigungu}'를 찾지 못함"
        return None, info
    info["found_sigungu"] = True
    code = sgg["props"]["code"]
    dongs = [f for f in _load("skorea-submunicipalities-2018-topo.json") if f["props"]["code"].startswith(code)]
    info["candidates"] = sorted(d["props"]["name"] for d in dongs)
    target = None
    if dong:
        key = dong.replace(" ", "")
        target = next((d for d in dongs if d["props"]["name"].replace(" ", "") == key), None)
        info["found_dong"] = bool(target)

    # 화면 범위: 시군구 범위를 넓혀서 주변 시군구도 보이게
    x0, y0, x1, y1 = _bbox(sgg["polys"])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    k = math.cos(math.radians(cy))
    w_deg, h_deg = (x1 - x0) * k, (y1 - y0)
    span = max(w_deg / width, h_deg / height) * 1.45
    if target:  # 동이 아주 작으면 동 중심으로 조금 더 확대
        tx0, ty0, tx1, ty1 = _bbox(target["polys"])
        cx, cy = (cx + (tx0 + tx1) / 2) / 2, (cy + (ty0 + ty1) / 2) / 2

    def P(lon, lat):
        return (width / 2 + (lon - cx) * k / span, height / 2 - (lat - cy) / span)

    def path(polys):
        d = []
        for poly in polys:
            for r in poly:
                pts = [P(*p) for p in r]
                d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        return "".join(d)

    def visible(polys):
        bx0, by0, bx1, by1 = _bbox(polys)
        (ax, ay), (bx, by) = P(bx0, by1), P(bx1, by0)
        return bx > -50 and ax < width + 50 and by > -50 and ay < height + 50

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
             f'<rect width="{width}" height="{height}" fill="#F6F8FA"/>']
    labels = []
    for f in _load("skorea-municipalities-2018-topo.json"):
        if f is sgg or not visible(f["polys"]):
            continue
        parts.append(f'<path d="{path(f["polys"])}" fill="{base}" stroke="{line}" stroke-width="3"/>')
        lx, ly = P(*_centroid(f["polys"]))
        if 40 < lx < width - 40 and 30 < ly < height - 30:
            labels.append((lx, ly, f["props"]["name"].split()[-1], 24, "#8A94A3", 500))
    for d in dongs:
        fill = accent if d is target else tint
        parts.append(f'<path d="{path(d["polys"])}" fill="{fill}" stroke="{line}" stroke-width="2"/>')
    parts.append(f'<path d="{path(sgg["polys"])}" fill="none" stroke="{ink}" stroke-width="4" stroke-linejoin="round"/>')
    gx, gy = P(*_centroid(sgg["polys"]))
    for lx, ly, t, fs, col, fw in labels:
        parts.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" font-size="{fs}" font-weight="{fw}" fill="{col}" '
                     f'font-family="Noto Sans KR">{t}</text>')
    if target:
        px, py = P(*_centroid(target["polys"]))
    else:
        px, py = gx, gy
    # 핀
    parts.append(f'<g transform="translate({px:.0f},{py:.0f})">'
                 f'<ellipse cx="0" cy="4" rx="16" ry="6" fill="#0F1E3D" opacity="0.25"/>'
                 f'<path d="M0,0 C-6,-14 -26,-26 -26,-46 A26,26 0 1 1 26,-46 C26,-26 6,-14 0,0Z" fill="{ink}"/>'
                 f'<circle cx="0" cy="-46" r="10" fill="#FFFFFF"/></g>')
    name = label_dong or (target["props"]["name"] if target else sgg["props"]["name"].split()[-1])
    tw = 30 * len(name) + 40
    lx = min(max(px - tw / 2, 10), width - tw - 10)
    ly = py - 132 if py > 160 else py + 20
    parts.append(f'<g transform="translate({lx:.0f},{ly:.0f})"><rect width="{tw}" height="54" rx="27" fill="{ink}"/>'
                 f'<text x="{tw / 2:.0f}" y="37" text-anchor="middle" font-size="30" font-weight="900" fill="#FFFFFF" '
                 f'font-family="Noto Sans KR">{name}</text></g>')
    if target:  # 시군구 이름은 핀과 겹치지 않을 때만
        if abs(gx - px) > 120 or abs(gy - py) > 80:
            parts.append(f'<text x="{gx:.0f}" y="{gy:.0f}" text-anchor="middle" font-size="34" font-weight="900" fill="{ink}" '
                         f'font-family="Noto Sans KR" opacity="0.85">{sgg["props"]["name"].split()[-1]}</text>')
    parts.append("</svg>")
    return "".join(parts), info


if __name__ == "__main__":
    import sys
    svg, info = make_map(*sys.argv[1:4])
    print(json.dumps(info, ensure_ascii=False))
    if svg:
        Path("map_test.svg").write_text(svg)
