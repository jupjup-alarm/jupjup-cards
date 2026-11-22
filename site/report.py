"""월간 청약 결산 (/report/, /report/YYYY-MM/) — 2026-11-20 사용자 요청.

접수 시작일이 그 달인 공고를 모아, 줍줍알람이 모은 데이터로만 숫자를 낸다:
공고 수(유형·지역), 청약홈 공식 경쟁률(평균·최고·미달), 무순위 경쟁률, 84㎡ 최고 분양가 범위, 주변 시세보다 싼 공고(추정),
당첨 가점(site/data/scores.json 이 있으면), 다음 달 접수 예정. 글은 숫자로 자동으로 쓴다(빌드마다 다시 만듦).
"""
import re
import statistics as st

MIN_NOTICES = 5   # 공고가 이보다 적은 달은 만들지 않음 (얇은 페이지 방지)


def _f(x):
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _ro(word):
    """'로/으로' — 받침 없거나 ㄹ받침이면 '로'."""
    ch = (word or " ").strip()[-1]
    if "가" <= ch <= "힣":
        jong = (ord(ch) - 0xAC00) % 28
        return "로" if jong in (0, 8) else "으로"
    return "로"


def _rates(n):
    return [float(r["rate"]) for r in (n.get("comp") or {}).get("rows", []) if re.fullmatch(r"[\d.]+", r["rate"])]


def _avg(n):
    m = re.search(r"평균\s*([\d.]+)대 1|·\s*([\d.]+)대 1", (n.get("comp") or {}).get("short") or "")
    return float(m.group(1) or m.group(2)) if m else None


def _under(n):
    return sum(1 for r in (n.get("comp") or {}).get("rows", []) if "△" in r["rate"])


def _excl(t):
    m = re.match(r"\s*0*(\d{2,3})", str(t))
    return int(m.group(1)) if m else None


def build(E, notices, write, common, base, today, won, kinds, d):
    by = {}
    for n in notices:
        if n.get("is_pre") or not n["rcpt"][0]:
            continue
        by.setdefault(n["rcpt"][0][:7], []).append(n)
    months = sorted(m for m, v in by.items() if len(v) >= MIN_NOTICES)
    if not months:
        return []
    tpl = E.get_template("report.html")
    cur = today.isoformat()[:7]
    out = []
    for i, mk in enumerate(months):
        lst = sorted(by[mk], key=lambda n: (n["rcpt"][0], n["title"]))
        y, m = int(mk[:4]), int(mk[5:])
        ongoing = mk >= cur
        kc = {}
        for n in lst:
            kc[kinds[n["kind"]][0]] = kc.get(kinds[n["kind"]][0], 0) + 1
        sc = {}
        for n in lst:
            sc[n["sido"]] = sc.get(n["sido"], 0) + 1
        sc = sorted(sc.items(), key=lambda kv: -kv[1])
        # 경쟁률
        comp = [(n, _avg(n), max(_rates(n)) if _rates(n) else None, _under(n)) for n in lst if n.get("comp") and n["comp"]["rows"]]
        comp = [c for c in comp if c[1] is not None]
        top = sorted(comp, key=lambda c: -c[1])[:5]
        under = [c for c in comp if c[1] < 1]
        mu = [c[1] for c in comp if c[0]["kind"] == "mujeonwi"]
        mu_med = st.median(mu) if mu else None
        # 84㎡ 최고 분양가
        p84 = []
        for n in lst:
            if n.get("is_rental"):
                continue
            for md in n.get("models") or []:
                if md.get("max") and _excl(md["type"]) in (84, 85):
                    p84.append((md["max"], n))
        p84.sort(key=lambda x: x[0])
        # 시세보다 싼 공고
        cheap = [n for n in lst if (n.get("gap") or {}).get("verdict", "").find("저렴") >= 0 and "건물분양가" not in n["gap"]["verdict"]]
        # 당첨 가점
        scored = sorted([n for n in lst if n.get("score_min")], key=lambda n: -n["score_min"][1])
        # 다음 달
        nm = f"{y + (m == 12)}-{(m % 12) + 1:02d}"
        nxt = sorted([n for n in notices if (n["rcpt"][0] or "")[:7] == nm or (n.get("is_pre") and (n.get("rcpt") or [""])[0][:7] == nm)],
                     key=lambda n: (n["rcpt"][0] or "", n["title"]))[:10]
        # 요약 글 (숫자로만)
        lead = [f"{y}년 {m}월에 접수를 시작한 청약 공고는 {len(lst)}곳이에요"
                + (f" ({d(today.isoformat())}까지 집계)" if ongoing else "") + "."]
        lead.append("유형별로는 " + ", ".join(f"{k} {v}곳" for k, v in sorted(kc.items(), key=lambda kv: -kv[1])) + "이고, "
                    + "지역은 " + ", ".join(f"{k} {v}곳" for k, v in sc[:3]) + " 순으로 많았어요.")
        if top:
            t0 = top[0]
            nm0 = t0[0].get('complex') or t0[0]['title']
            lead.append(f"경쟁률이 가장 높았던 곳은 {nm0}{_ro(nm0)} 평균 {_f(t0[1])}대 1"
                        + (f"(주택형 최고 {_f(t0[2])}대 1)" if t0[2] and t0[2] != t0[1] else "") + "이었어요.")
        if comp:
            lead.append(f"경쟁률이 공개된 {len(comp)}곳 가운데 평균 1대 1에 못 미친 미달 공고는 {len(under)}곳이에요.")
        if mu_med is not None:
            lead.append(f"무순위(줍줍) {len(mu)}곳의 평균 경쟁률 가운데값은 {_f(round(mu_med, 1))}대 1이에요.")
        if len(p84) >= 2:
            lead.append(f"전용 84㎡ 최고 분양가는 {won(p84[0][0])}({p84[0][1]['sido']} {p84[0][1].get('sigungu') or ''})부터 "
                        f"{won(p84[-1][0])}({p84[-1][1]['sido']} {p84[-1][1].get('sigungu') or ''})까지 나왔어요.")
        if cheap:
            lead.append(f"주변 실거래보다 분양가가 낮게 나온 공고는 {len(cheap)}곳이에요.")
        url = f"/report/{mk}/"
        prev_ = (f"/report/{months[i - 1]}/", f"{int(months[i - 1][5:])}월 결산") if i > 0 else None
        next_ = (f"/report/{months[i + 1]}/", f"{int(months[i + 1][5:])}월 결산") if i < len(months) - 1 else None
        title = f"{y}년 {m}월 청약 결산 | 공고 {len(lst)}곳 경쟁률·미달·분양가 · 줍줍알람"
        desc = " ".join(lead[:3])[:155]
        h = tpl.render(mk=mk, y=y, m=m, ongoing=ongoing, lst=lst, kc=kc, sc=sc, comp=comp, top=top, under=under, mu=mu, mu_med=mu_med,
                       p84=p84, cheap=cheap, scored=scored[:10], nxt=nxt, nm=nm, lead=lead, prev_=prev_, next_=next_,
                       **common, page_url=url, title=title, desc=desc, og="/og-default.jpg",
                       crumb=[("홈", "/"), ("월간 결산", "/report/"), (f"{y}년 {m}월", "")], nav="competition")
        write(url, h, title, desc, "list", max(n["modified"] for n in lst))
        out.append({"mk": mk, "y": y, "m": m, "url": url, "n": len(lst), "lead": lead[0], "ongoing": ongoing, "under": len(under), "ncomp": len(comp)})
    out.reverse()
    title = "월간 청약 결산 | 달마다 공고 수·경쟁률·미달·분양가 정리 · 줍줍알람"
    desc = "줍줍알람이 모은 청약 공고와 청약홈 공식 경쟁률로 달마다 정리하는 청약 결산. 공고 수, 경쟁률 상위·미달 단지, 무순위 경쟁률, 84㎡ 분양가 범위, 당첨 가점."
    h = E.get_template("report_index.html").render(reports=out, **common, page_url="/report/", title=title, desc=desc, og="/og-default.jpg",
                                                   crumb=[("홈", "/"), ("월간 결산", "")], nav="competition")
    write("/report/", h, title, desc, "list", max(n["modified"] for n in notices))
    return out


def _tname(t):
    """'084.9443A' → '84A' (청약홈 주택형 표기를 사람들이 부르는 이름으로)."""
    m = re.match(r"\s*0*(\d{2,3})(?:\.\d+)?\s*([A-Za-z가-힣]*)", str(t))
    return f"{m.group(1)}{m.group(2)}" if m else str(t)


def _band(t):
    e = _excl(t)
    if e is None:
        return "기타"
    return "60㎡ 이하" if e <= 60 else ("60~85㎡" if e <= 85 else "85㎡ 초과")


def build_scores(E, notices, write, common, today, d):
    """당첨 가점 커트라인 (/scores/, 2026-11-20 사용자 요청) — 청약홈 공식 당첨 가점을 지역·면적대별로."""
    ns = [n for n in notices if n.get("scores")]
    rows = []
    for n in ns:
        for g in n["scores"]:
            loc = [r for r in g["rows"] if "기타" not in (r.get("area") or "")]
            oth = [r for r in g["rows"] if "기타" in (r.get("area") or "")]
            rows.append({"n": n, "type": g["type"].replace("타입", ""), "band": _band(g["type"]),
                         "lmin": min((r["min"] for r in loc if r.get("min")), default=None),
                         "lavg": loc[0].get("avg") if loc else None,
                         "omin": min((r["min"] for r in oth if r.get("min")), default=None)})
    if not rows:
        return None
    rows.sort(key=lambda r: (r["n"].get("announce") or "", r["lmin"] or 0), reverse=True)
    by_sido = {}
    for r in rows:
        if r["lmin"]:
            by_sido.setdefault(r["n"]["sido"], []).append(r["lmin"])
    sido = sorted(((k, len(v), min(v), st.median(v), max(v)) for k, v in by_sido.items()), key=lambda x: -x[1])
    by_band = {}
    for r in rows:
        if r["lmin"]:
            by_band.setdefault(r["band"], []).append(r["lmin"])
    band = [(b, len(by_band[b]), min(by_band[b]), st.median(by_band[b]), max(by_band[b])) for b in ("60㎡ 이하", "60~85㎡", "85㎡ 초과", "기타") if b in by_band]
    allv = [r["lmin"] for r in rows if r["lmin"]]
    # 2026-11-22 사용자 결정 "내 가점이면 붙었을 단지": 점수 구간마다 최저 당첨 가점이 그 점수 이하였던 주택형 수 (실제 청약홈 가점)
    pts = []
    for th in (30, 40, 50, 60, 70):
        ok = [r for r in rows if r["lmin"] and r["lmin"] <= th]
        oko = [r for r in rows if (r["omin"] or 0) and r["omin"] <= th]
        sd = {}
        for r in ok:
            sd[r["n"]["sido"]] = sd.get(r["n"]["sido"], 0) + 1
        ex = sorted(ok, key=lambda r: -(r["lmin"] or 0))[:3]
        pts.append({"th": th, "n": len(ok), "no": len(oko), "cx": len({r["n"]["key"] for r in ok}),
                    "sido": sorted(sd.items(), key=lambda kv: -kv[1])[:3], "ex": ex})
    lead = (f"최근 당첨자를 발표한 공고 {len(ns)}곳, 주택형 {len(rows)}개의 청약홈 공식 당첨 가점이에요. "
            + (f"해당지역 최저 당첨 가점은 {int(min(allv))}점부터 {int(max(allv))}점까지, 가운데값은 {_f(round(st.median(allv), 1))}점이에요. " if allv else "")
            + "가점제로 뽑은 주택형만 나오고, 추첨·미달 주택형은 빠져요.")
    title = "청약 당첨 가점 커트라인 | 지역·면적별 최근 당첨 가점 · 줍줍알람"
    desc = lead[:155]
    h = E.get_template("scores.html").render(rows=rows, sido=sido, band=band, pts=pts, n_lmin=len(allv), n_notices=len(ns), lead=lead, **common, page_url="/scores/",
                                             title=title, desc=desc, og="/og-default.jpg", crumb=[("홈", "/"), ("당첨 가점", "")], nav="competition")
    write("/scores/", h, title, desc, "list", max(n["modified"] for n in ns))
    return len(ns)


def build_weeks(E, notices, write, common, today, d):
    """주간 청약 정리 (/week/YYYY-wNN/, 2026-11-20 사용자 요청) — 그 주 접수·당첨자 발표·결과를 숫자로만."""
    import datetime as dt
    def wk(iso):
        y, w, _ = dt.date.fromisoformat(iso).isocalendar()
        return f"{y}-w{w:02d}"
    live = [n for n in notices if not n.get("is_pre") and n["rcpt"][0]]
    weeks = {}
    for n in live:
        weeks.setdefault(wk(n["rcpt"][0]), {"start": [], "ann": [], "res": []})["start"].append(n)
        if n.get("announce"):
            weeks.setdefault(wk(n["announce"]), {"start": [], "ann": [], "res": []})["ann"].append(n)
        if n.get("comp") and n["comp"]["rows"] and (n["rcpt"][1] or n["rcpt"][0]):
            weeks.setdefault(wk(n["rcpt"][1] or n["rcpt"][0]), {"start": [], "ann": [], "res": []})["res"].append(n)
    cur = wk(today.isoformat())
    keys = sorted(k for k, v in weeks.items() if len(v["start"]) + len(v["ann"]) + len(v["res"]) >= 5 and k <= cur)
    if not keys:
        return []
    tpl = E.get_template("week.html")
    out = []
    for i, k in enumerate(keys):
        y, w = int(k[:4]), int(k[6:])
        mon = dt.date.fromisocalendar(y, w, 1)
        sun = mon + dt.timedelta(days=6)
        v = weeks[k]
        start = sorted(v["start"], key=lambda n: (n["rcpt"][0], n["title"]))
        ann = sorted(v["ann"], key=lambda n: (n["announce"], n["title"]))
        res = sorted(v["res"], key=lambda n: -(_avg(n) or 0))
        ongoing = k == cur
        label = f"{mon.month}월 {mon.day}일~{sun.month}월 {sun.day}일"
        kc = {}
        for n in start:
            kc[kinds_label(n)] = kc.get(kinds_label(n), 0) + 1
        lead = [f"{label}에 접수를 시작한 청약 공고는 {len(start)}곳이에요" + (f" ({d(today.isoformat())}까지 집계)" if ongoing else "") + "."]
        if kc:
            lead.append("유형별로는 " + ", ".join(f"{a} {b}곳" for a, b in sorted(kc.items(), key=lambda x: -x[1])) + "이에요.")
        if ann:
            lead.append(f"당첨자 발표는 {len(ann)}곳이에요.")
        ra = [(n, _avg(n)) for n in res if _avg(n) is not None]
        if ra:
            t0 = ra[0]
            nm0 = t0[0].get("complex") or t0[0]["title"]
            lead.append(("이번 주" if ongoing else "이 주에") + f" 접수를 마친 곳 가운데 경쟁률이 가장 높았던 곳은 {nm0}{_ro(nm0)} 평균 {_f(t0[1])}대 1이고, "
                        f"평균 1대 1에 못 미친 곳은 {sum(1 for _, a in ra if a < 1)}곳이에요.")
        nxt = sorted([n for n in live if wk(n["rcpt"][0]) > k and (dt.date.fromisoformat(n["rcpt"][0]) - sun).days <= 7], key=lambda n: n["rcpt"][0])
        url = f"/week/{k}/"
        title = f"{y}년 {label} 청약 정리 | 접수 {len(start)}곳·발표 {len(ann)}곳·경쟁률 · 줍줍알람"
        desc = " ".join(lead)[:155]
        prev_ = (f"/week/{keys[i - 1]}/", "지난주") if i > 0 else None
        next_ = (f"/week/{keys[i + 1]}/", "다음 주") if i < len(keys) - 1 else None
        h = tpl.render(k=k, y=y, label=label, ongoing=ongoing, start=start, ann=ann, res=res, ra=ra, nxt=nxt[:8], lead=lead, prev_=prev_, next_=next_,
                       **common, page_url=url, title=title, desc=desc, og="/og-default.jpg",
                       crumb=[("홈", "/"), ("주간 정리", "/week/"), (label, "")], nav="schedule")
        write(url, h, title, desc, "list", max(n["modified"] for n in start + ann + res))
        out.append({"k": k, "url": url, "label": label, "y": y, "n": len(start), "ann": len(ann), "res": len(res), "ongoing": ongoing, "lead": lead[0]})
    out.reverse()
    title = "주간 청약 정리 | 주마다 접수·당첨자 발표·경쟁률 모음 · 줍줍알람"
    desc = "주마다 접수를 시작한 청약 공고, 당첨자 발표, 접수를 마친 곳의 청약홈 공식 경쟁률을 자동으로 정리해요."
    h = E.get_template("week_index.html").render(weeks=out, **common, page_url="/week/", title=title, desc=desc, og="/og-default.jpg",
                                                 crumb=[("홈", "/"), ("주간 정리", "")], nav="schedule")
    write("/week/", h, title, desc, "list", max(n["modified"] for n in notices))
    return out


def kinds_label(n):
    return {"mujeonwi": "무순위·줍줍", "private": "민간분양", "public": "공공분양", "newlywed": "신혼희망타운", "rental": "공공임대"}.get(n["kind"], "기타")


def build_watch(E, notices, write, common, today, d, won):
    """줍줍 나올 수 있는 단지 (/mujeonwi-watch/, 2026-11-22 사용자 결정) — 1순위에서 미달 난 주택형이 있는 최근 공고.
    예측하지 않는다: 청약홈 공식 경쟁률에서 '미달(△)'로 나온 주택형과 계약 일정, 그 뒤 실제로 올라온 무순위 공고만 적는다."""
    import datetime as dt
    lim = (today - dt.timedelta(days=150)).isoformat()
    rows = []
    for n in notices:
        if n.get("is_pre") or n["status"] not in ("waiting", "announced") or not n.get("comp"):
            continue
        end = n["rcpt"][1] or n["rcpt"][0] or ""
        if end < lim:
            continue
        crows = n["comp"].get("rows") or []
        und = list(dict.fromkeys(_tname(r["name"].split()[0]) for r in crows if "△" in r["rate"]))
        if not und:
            continue
        tot = list(dict.fromkeys(_tname(r["name"].split()[0]) for r in crows))
        later = (n.get("result") or {}).get("later") or []
        ct = n.get("contract") or [None, None]
        rows.append({"n": n, "und": und, "tot": len(tot), "avg": _avg(n), "end": end, "later": later,
                     "contract": ct, "after": bool(ct[1] and ct[1] < today.isoformat())})
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["end"], reverse=True)
    waiting = [r for r in rows if not r["later"]]
    came = [r for r in rows if r["later"]]
    sd = {}
    for r in rows:
        sd[r["n"]["sido"]] = sd.get(r["n"]["sido"], 0) + 1
    nu = sum(len(r["und"]) for r in rows)
    lead = [f"최근 150일 안에 접수가 끝난 공고 중 청약홈 공식 1순위 경쟁률에서 미달(△)이 나온 단지는 {len(rows)}곳, 미달 주택형은 모두 {nu}개예요"
            + " (" + ", ".join(f"{k} {v}곳" for k, v in sorted(sd.items(), key=lambda kv: -kv[1])) + ")."]
    if came:
        lead.append(f"이 가운데 {len(came)}곳은 이미 무순위·임의공급 공고가 다시 올라왔고, {len(waiting)}곳은 아직 줍줍알람에 새 공고가 없어요.")
    hi = max((r for r in rows if r["avg"] is not None), key=lambda r: (len(r["und"]) / max(r["tot"], 1), len(r["und"])), default=None)
    if hi:
        nm = hi["n"].get("complex") or hi["n"]["title"]
        lead.append(f"주택형 대비 미달이 가장 많았던 곳은 {nm}{_ro(nm)} {hi['tot']}개 주택형 중 {len(hi['und'])}개가 미달이었어요.")
    lead.append("미달 물량과 당첨자가 계약하지 않은 물량은 보통 계약 기간이 끝난 뒤 무순위(사후)·임의공급으로 다시 나와요. 다만 2순위나 예비입주자에서 채워지면 나오지 않을 수 있어서, 이 목록은 예측이 아니라 '나올 수 있는 후보'예요.")
    title = "줍줍 나올 수 있는 단지 — 1순위 미달 주택형 모음 · 줍줍알람"
    desc = "청약홈 공식 경쟁률에서 1순위 미달이 난 최근 단지와 주택형, 계약 일정, 다시 올라온 무순위 공고를 모았어요."
    faq = [["줍줍(무순위)은 언제 나오나요?", "정해진 날짜는 없어요. 보통 당첨자 계약 기간이 끝나고 남은 세대(미달·미계약·부적격)가 확정된 뒤 사업주체가 모집공고를 다시 내요. 이 목록의 '계약' 칸이 지난 단지부터 살펴보면 돼요."],
           ["미달이면 꼭 무순위가 나오나요?", "아니요. 1순위 미달 물량은 2순위나 예비입주자에게서 채워질 수 있어요. 끝까지 남은 물량만 무순위·임의공급으로 나오니, 공식 공고가 나오기 전까지는 후보로만 보세요."],
           ["무순위 공고가 나오면 어떻게 알 수 있나요?", "줍줍알람이 매일 아침 청약홈·LH 공고를 받아 이 페이지와 줍줍 공고 목록에 바로 올려요. 이 목록에서 '다시 나옴'으로 바뀐 단지를 누르면 새 공고로 이어져요."]]
    h = E.get_template("watch.html").render(rows=rows, waiting=waiting, came=came, lead=lead, faq=faq,
                                            faq_ld={"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, **common, page_url="/mujeonwi-watch/",
                                            title=title, desc=desc, og="/og-default.jpg", crumb=[("홈", "/"), ("줍줍", "/type/mujeonwi/"), ("줍줍 나올 수 있는 단지", "")],
                                            nav="type")
    write("/mujeonwi-watch/", h, title, desc, "list", max(r["n"]["modified"] for r in rows))
    return len(rows)
