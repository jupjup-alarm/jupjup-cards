"""FAQ 보강 할 일 목록 → site/data/faq_todo.json (2026-11-20 사용자 요청 '서치콘솔 FAQ 루프', 모델 없음).

사람들이 실제로 검색하는데 공고 페이지가 아직 답하지 않는 질문을 찾는다.
  ① 네이버 검색량: site/data/keywords/{key}.json (tools/keywords.py가 모음) — '단지명 + 모델하우스' 같은 꼬리 검색어
  ② 구글 서치콘솔(선택): 서치콘솔 → 실적 → 내보내기(CSV)의 '검색어' 표를 site/data/gsc/queries.csv 로 두면
     노출 20회 이상·클릭률 2% 미만 검색어도 함께 본다 (열 이름: 인기 검색어/Top queries, 클릭수/Clicks, 노출/Impressions)
페이지의 소제목(h2·h3)과 '자주 묻는 질문'에 그 주제가 없으면 할 일로 적는다. 분양가·일정·자격·경쟁률처럼
본문 섹션이 이미 답하는 주제는 뺀다(FAQ에 넣으면 build.py FAQ_DUP가 어차피 거른다).

사용:  python3 site/tools/faq_todo.py   → site/data/faq_todo.json (검색량 큰 순)
⑦은 상위 몇 개를 골라 공고문(notice_text)에서 확인된 사실로만 data/apt/{key}.json 'faq'에 질문·답을 하나씩 더한다.
"""
import csv
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "data"
PUB = SITE / "public"

# 검색어 꼬리 → (FAQ 주제, 페이지에서 찾을 말들)
INTENTS = [
    (r"모델하우스|견본주택|홍보관", "모델하우스(견본주택) 위치·운영 시간", ["모델하우스", "견본주택", "홍보관"]),
    (r"실거주|거주의무", "실거주 의무", ["실거주", "거주의무", "거주 의무"]),
    (r"전매", "전매 제한", ["전매"]),
    (r"입주(?!자)", "입주 시기", ["입주 예정", "입주 시기", "입주는"]),
    (r"잔여", "잔여세대·추가 모집", ["잔여"]),
    (r"중도금|대출", "중도금·잔금 대출", ["중도금 대출", "대출"]),
    (r"계약금", "계약금", ["계약금"]),
    (r"옵션|발코니|확장", "발코니 확장·옵션 비용", ["발코니", "옵션"]),
    (r"동호수|동호|층", "동·호수 배정", ["동·호", "동호"]),
    (r"학군|학교|초품아", "학교·학군", ["학교", "학군"]),
    (r"주차", "주차", ["주차"]),
    (r"관리비", "관리비", ["관리비"]),
    (r"커뮤니티", "커뮤니티 시설", ["커뮤니티"]),
    (r"시세|실거래", "주변 시세", ["시세"]),
]


def page_topics(key):
    p = PUB / "apt" / key / "index.html"
    if not p.exists():
        return None
    h = p.read_text()
    heads = " ".join(re.sub(r"<[^>]+>", " ", m) for m in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", h, re.S))
    faqs = " ".join(re.sub(r"<[^>]+>", " ", m) for m in re.findall(r"<summary>(.*?)</summary>", h, re.S))
    return heads + " " + faqs


def intent_of(tail):
    for pat, label, terms in INTENTS:
        if re.search(pat, tail):
            return label, terms
    return None, None


def main():
    todo = {}
    for f in sorted((DATA / "keywords").glob("*.json")):
        if f.name.startswith("_"):
            continue
        k = json.loads(f.read_text())
        key = k.get("key") or f.stem
        topics = page_topics(key)
        if topics is None:
            continue
        names = sorted(k.get("names") or [], key=len, reverse=True)
        for r in k.get("rows", []):
            kw, tail = r["kw"], r["kw"]
            for nm in names:
                if kw.startswith(nm):
                    tail = kw[len(nm):].strip()
                    break
            label, terms = intent_of(tail)
            if not label or any(t in topics for t in terms):
                continue
            t = todo.setdefault((key, label), {"key": key, "page": f"/apt/{key}/", "topic": label, "queries": [], "volume": 0, "src": "naver"})
            t["queries"].append(kw)
            t["volume"] += int(r.get("total") or 0)
    # 서치콘솔 (선택)
    g = DATA / "gsc" / "queries.csv"
    if g.exists():
        apt_names = {}
        for f in (DATA / "apt").glob("*.json"):
            e = json.loads(f.read_text())
            for nm in [e.get("complex"), e.get("title")] + (e.get("aliases") or []):
                if nm:
                    apt_names[re.sub(r"\s+", "", nm)] = e["key"] if "key" in e else f.stem
        with g.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                q = row.get("인기 검색어") or row.get("Top queries") or ""
                imp = int(re.sub(r"\D", "", row.get("노출") or row.get("Impressions") or "0") or 0)
                clk = int(re.sub(r"\D", "", row.get("클릭수") or row.get("Clicks") or "0") or 0)
                if imp < 20 or (clk / imp if imp else 0) >= 0.02:
                    continue
                qs = re.sub(r"\s+", "", q)
                key = next((v for nm, v in sorted(apt_names.items(), key=lambda x: -len(x[0])) if nm and nm in qs), None)
                label, terms = intent_of(q)
                if not key or not label:
                    continue
                topics = page_topics(key) or ""
                if any(t in topics for t in terms):
                    continue
                t = todo.setdefault((key, label), {"key": key, "page": f"/apt/{key}/", "topic": label, "queries": [], "volume": 0, "src": "gsc"})
                t["queries"].append(q)
                t["volume"] += imp
    out = sorted((t for t in todo.values() if t["volume"] >= 20), key=lambda t: -t["volume"])
    (DATA / "faq_todo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"FAQ 할 일 {len(out)}건 → site/data/faq_todo.json")
    for t in out[:10]:
        print(f"  {t['volume']:>6}  {t['page']}  {t['topic']}  ({', '.join(t['queries'][:2])})")


if __name__ == "__main__":
    main()
