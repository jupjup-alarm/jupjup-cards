"""자막(ASS): 넷플릭스 한국어 자막 스타일 가이드를 따른다.

- 한 줄 최대 16자(한글 1, 영문·숫자·공백·문장부호 0.5), 최대 2줄, 한 줄에 들어가면 한 줄.
  시니어용으로 글자를 키워서 숏츠는 한 줄 13자(넷플릭스 상한 16자보다 짧게)로 쓴다. setup(portrait)로 정한다.
- 줄을 나눌 자리가 여럿이면 아랫줄이 긴 피라미드 모양.
- 줄 끝에 마침표·쉼표를 남기지 않는다. 한 자막에 두 문장이 들어가면 쉼표로 잇는다.
- 꾸미는 말과 명사, 본용언과 보조용언(보태 줍니다), 부정어와 동사(못 해요),
  숫자와 단위·날짜(50만 원, 11월 27일), 의존명사(만들 수, 우체국 등)는 떼지 않는다(kiwipiepy 형태소 분석).
- 한 자막 5/6초 이상 7초 이하, 다음 자막과 12프레임 안이면 2프레임 간격으로 붙인다. 장면 경계는 넘지 않는다.
- 흰 글자 + 검은 테두리·그림자, 상자 없음. 롱폼 80px, 숏츠 76px.
- 자막 단위는 내레이션 구절(대본의 / 와 문장 끝)에 맞춘다.
"""
import re

FPS = 30
MAXC, MIN_DUR, MAX_DUR = 16, 5 / 6, 7.0
GAP, CLOSE = 2 / FPS, 12 / FPS

_kiwi = None


def setup(portrait):
    """포맷별 한 줄 글자 수. 롱폼 16자(80px), 숏츠 13자(76px)."""
    global MAXC
    MAXC = 13 if portrait else 16


def kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def clen(s):
    return sum(1 if ("가" <= c <= "힣" or "㄰" <= c <= "㆏" or "一" <= c <= "鿿") else 0.5 for c in s)


NEG = {"안", "못"}


def boundary_costs(text):
    """공백 i(단어 i와 i+1 사이)에서 줄·자막을 나눌 때의 비용. 낮을수록 자연스럽다."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    toks = kiwi().tokenize(text)
    def inside(s, e):
        return [t for t in toks if s <= t.start < e and (not t.tag.startswith("S") or t.tag in ("SN", "SL", "SH"))]
    costs = []
    for i in range(len(spans) - 1):
        wa = text[spans[i][0]:spans[i][1]]
        a, b = inside(*spans[i]), inside(*spans[i + 1])
        la = a[-1] if a else None
        fb = b[0] if b else None
        c = 6.0
        if wa.endswith((",", ".", "?", "!")):
            c = 0.0
        elif la is None:
            c = 6.0
        elif la.tag.startswith("EC"):
            c = 1.0
        elif la.tag.startswith("EF"):
            c = 0.5
        elif la.tag in ("JX", "JKS", "JKO", "JKB", "JKC", "JC"):
            c = 3.0
        elif la.form in ("등", "및"):
            c = 2.0  # 나열 끝
        elif la.tag.startswith("ETM") or la.tag == "MM":
            c = 40.0
        elif la.tag == "JKG":
            c = 30.0
        elif la.tag == "MAG":
            c = 40.0 if la.form in NEG else 9.0
        elif la.tag in ("NNG", "NNP", "NNB", "NR", "SN", "SL", "XSN") and fb is not None and fb.tag in ("NNG", "NNP", "NNB", "NR", "SN", "SL", "XPN"):
            c = 14.0
            if any(t.tag in ("SN", "NR") for t in a) and any(t.tag in ("SN", "NR") for t in b):
                c = 25.0  # 날짜·금액 묶음
        if fb is not None:
            if fb.tag in ("VX", "NNB"):
                c = max(c, 40.0)
            elif fb.tag in ("VCN", "VCP"):
                c = max(c, 12.0)
        costs.append(c)
    return spans, costs


def _strip_end(s):
    return s.rstrip().rstrip(".,")


def break_lines(text):
    """자막 하나의 글자 → 1~2줄."""
    text = text.strip()
    if clen(_strip_end(text)) <= MAXC:
        return [_strip_end(text)]
    spans, costs = boundary_costs(text)
    best = None
    for i, c in enumerate(costs):
        top, bot = _strip_end(text[:spans[i][1]]), _strip_end(text[spans[i + 1][0]:])
        lt, lb = clen(top), clen(bot)
        over = max(0, lt - MAXC) + max(0, lb - MAXC)
        score = c + over * 60 + (lt - lb) * 0.6 * (lt > lb) + abs(lt - lb) * 0.15
        if best is None or score < best[0]:
            best = (score, [top, bot])
    return best[1]


def fits(text):
    ls = break_lines(text)
    return len(ls) <= 2 and all(clen(l) <= MAXC for l in ls)


def split_event(text):
    """두 줄에 들어가지 않는 구절을 자연스러운 자리에서 여러 자막으로 나눈다 → [글자]."""
    if fits(text):
        return [text]
    spans, costs = boundary_costs(text)
    total = clen(text)
    best = None
    for i, c in enumerate(costs):
        a, b = text[:spans[i][1]], text[spans[i + 1][0]:]
        score = c * 2 + abs(clen(a) - clen(b)) * 0.25 + (0 if fits(a) else 60) + (0 if fits(b) else 30)
        if best is None or score < best[0]:
            best = (score, a, b)
    return split_event(best[1]) + split_event(best[2])


def events_for_line(line_start, segs):
    """내레이션 구절(segs) → [(시작, 끝, 글자)]."""
    groups = []  # 각 그룹: [seg...]
    for s in segs:
        t = s["text"].replace("/", "").strip()
        s = dict(s, text=t)
        if groups:
            cur = groups[-1]
            ctext = " ".join(x["text"] for x in cur)
            ends_sent = ctext.endswith((".", "?", "!"))
            is_label = ends_sent and clen(ctext.rstrip(".?!")) <= 6
            comb = clen(_strip_end(ctext + " " + t))
            short_lead = clen(_strip_end(ctext)) <= 6  # '다만', '첫째,', '참고로' 같은 짧은 앞말
            if (not ends_sent or is_label) and (comb <= MAXC or short_lead) and fits(ctext + " " + t):
                cur.append(s); continue
        groups.append([s])
    ev = []
    for g in groups:
        st = line_start + g[0]["start"]
        en = line_start + g[-1]["start"] + g[-1]["dur"]
        text = " ".join(x["text"] for x in g)
        text = re.sub(r"(?<=\S)\.\s+(?=\S)", ", ", text)  # 한 자막 안 두 문장은 쉼표로
        parts = split_event(text)
        tot = sum(clen(p) for p in parts) or 1
        t = st
        for p in parts:
            d = (en - st) * clen(p) / tot
            ev.append([t, t + d, p])
            t += d
    return ev


def timing(ev, scene_ends):
    """최소·최대 길이와 간격 규칙. scene_ends[i] = 자막 i가 속한 장면의 끝 시각."""
    for i, e in enumerate(ev):
        nxt = ev[i + 1][0] if i + 1 < len(ev) else e[1] + 10
        limit = min(nxt - GAP, scene_ends[i] - GAP)
        if e[1] - e[0] < MIN_DUR:
            e[1] = min(e[0] + MIN_DUR, limit)
        if nxt - e[1] < CLOSE and nxt <= scene_ends[i]:
            e[1] = nxt - GAP
        e[1] = min(e[1], limit, e[0] + MAX_DUR)
    return ev


def ass_time(t):
    h, r = divmod(max(t, 0), 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass(ev, portrait):
    W, H = (1080, 1920) if portrait else (1920, 1080)
    fs, ml, mv = (76, 40, 400) if portrait else (80, 80, 48)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Noto Sans CJK KR,{fs},&H00FFFFFF,&H00FFFFFF,&H00141414,&H8C000000,-1,0,0,0,100,100,0,0,1,5,2.5,2,{ml},{ml},{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "\n".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Sub,,0,0,0,," + "\\N".join(break_lines(t)) for a, b, t in ev)
    return head + body + "\n"


def report(ev):
    """검사: 줄 길이, 줄 수, 길이, 읽기 속도(초당 12자)."""
    bad = []
    for a, b, t in ev:
        ls = break_lines(t)
        if len(ls) > 2 or any(clen(l) > MAXC for l in ls):
            bad.append(("길이", t, ls))
        if b - a < MIN_DUR - 0.01 or b - a > MAX_DUR + 0.01:
            bad.append(("시간", t, round(b - a, 2)))
        if clen("".join(ls)) / max(b - a, 0.01) > 12:
            bad.append(("속도", t, round(clen("".join(ls)) / (b - a), 1)))
    return bad
