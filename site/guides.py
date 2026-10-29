"""가이드 칼럼 (/guide/{slug}/) — site/data/guide/*.json → 페이지. 형식은 site/data/guide/README.md."""
import html
import json
import re
from pathlib import Path

from markupsafe import Markup
try:
    import markdown
except ImportError:  # pip install --break-system-packages markdown
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--break-system-packages', 'markdown'], check=False)
    import markdown

SITE = Path(__file__).resolve().parent
import os
GDIR = Path(os.environ["GUIDE_DIR"]) if os.environ.get("GUIDE_DIR") else SITE / "data" / "guide"
CATS = ["청약 자격", "무순위", "임대", "대출", "신도시"]
CAT_SLUG = {"청약 자격": "eligibility", "무순위": "mujeonwi", "임대": "rental", "대출": "loan", "신도시": "new-town"}
TOOLS = {"gajeom", "dsr", "selfcheck"}


def load():
    out = []
    for f in sorted(GDIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        g = json.loads(f.read_text(encoding="utf-8"))
        g.setdefault("slug", f.stem)
        out.append(g)
    return out


def _md(text):
    return markdown.markdown(text, extensions=["tables", "sane_lists"], output_format="html")


def render_body(md_text, img_dir=None):
    """본문 마크다운 + ::: 상자 → (html, 목차, 쓰인 도구). img_dir: :::image·:::gallery 그림 파일이 있는 폴더(site/data/guide/img/{slug})."""
    lines = (md_text or "").replace("\r", "").split("\n")
    out, raw, tools = [], {}, []
    i = 0

    def stash(h):
        k = f"GRAW{len(raw)}X"
        raw[k] = h
        return f"\n\n{k}\n\n"

    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^:::\s*(\w+)\s*(.*)$", ln.strip())
        if not m or ln.strip() == ":::":
            out.append(ln)
            i += 1
            continue
        kind, arg = m.group(1), m.group(2).strip()
        if kind == "tool" and arg.split()[0] in ("gajeom", "dsr"):
            tools.append(arg.split()[0])
            out.append(stash(f'<div class="g-tool" data-tool="{arg.split()[0]}"></div>'))
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip() != ":::":
            j += 1
        inner = "\n".join(lines[i + 1:j])
        i = j + 1
        if kind in ("image", "gallery"):
            # 한 줄에 "파일명 | 설명". 파일은 site/data/guide/img/{slug}/ — 빌드가 /guide/{slug}/ 로 복사
            figs = []
            for x in inner.split("\n"):
                if not x.strip():
                    continue
                fn, _, label = (p.strip() for p in x.partition("|"))
                wh = ""
                try:
                    from PIL import Image
                    with Image.open(Path(img_dir) / fn) as im:
                        wh = f' width="{im.width}" height="{im.height}"'
                except Exception:
                    pass
                cap = f"<figcaption>{html.escape(label)}</figcaption>" if kind == "gallery" and label else ""
                figs.append(f'<figure><a href="{html.escape(fn)}" target="_blank" rel="noopener"><img src="{html.escape(fn)}" alt="{html.escape(label or arg)}" loading="lazy" decoding="async"{wh}></a>{cap}</figure>')
            cls = "g-gal" if kind == "gallery" else "g-one"
            out.append(stash(f'<div class="g-img"><div class="{cls}">{"".join(figs)}</div><p class="g-imgcap">{html.escape(arg)}</p></div>'))
            continue
        if kind == "figure":
            svg = inner.strip()
            out.append(stash(f'<figure class="g-fig">{svg}<figcaption>{html.escape(arg)}</figcaption></figure>'))
        elif kind in ("note", "tip"):
            cls = "g-note" if kind == "note" else "g-tip"
            out.append(stash(f'<aside class="{cls}"><b>{html.escape(arg)}</b>{_md(inner)}</aside>'))
        elif kind == "check":
            items = [re.sub(r"^\s*[-*]\s*", "", x) for x in inner.split("\n") if x.strip()]
            lis = "".join(f"<li>{_md(x)[3:-4] if _md(x).startswith('<p>') else _md(x)}</li>" for x in items)
            out.append(stash(f'<section class="g-check"><h3>{html.escape(arg or "놓치기 쉬운 것")}</h3><ul>{lis}</ul></section>'))
        elif kind == "cases":
            parts = re.split(r"^###\s+(.+)$", inner, flags=re.M)
            cards = []
            for k in range(1, len(parts), 2):
                cards.append(f'<div class="g-case"><span class="g-ex">예시</span><h3>{html.escape(parts[k].strip())}</h3>{_md(parts[k + 1])}</div>')
            out.append(stash(f'<div class="g-cases">{"".join(cards)}</div><p class="g-casenote">예시 가구는 이해를 돕기 위한 가상 사례예요.</p>'))
        elif kind == "tool" and arg.startswith("selfcheck"):
            tools.append("selfcheck")
            title = arg[len("selfcheck"):].strip() or "나는 해당될까요?"
            qs, result = [], ""
            for x in inner.split("\n"):
                x = x.strip()
                if x.startswith("-"):
                    qs.append(x.lstrip("-* ").strip())
                elif x.startswith("결과:"):
                    result = x[3:].strip()
            rows = "".join(f'<li><span>{html.escape(q)}</span><span class="g-yn" role="group"><button type="button" data-v="1" aria-pressed="false">예</button><button type="button" data-v="0" aria-pressed="false">아니오</button></span></li>' for q in qs)
            out.append(stash(f'<div class="g-tool g-self" data-tool="selfcheck"><h3>{html.escape(title)}</h3><ol>{rows}</ol>'
                             f'<p class="g-selfres" aria-live="polite"><b data-yes>0</b> / {len(qs)}개 \'예\'</p><p class="g-toolnote">{html.escape(result)}</p></div>'))
        else:
            out.append(inner)
    body = _md("\n".join(out))
    for k, v in raw.items():
        body = body.replace(f"<p>{k}</p>", v).replace(k, v)
    toc = []

    def h2(m):
        n = len(toc) + 1
        text = re.sub(r"<[^>]+>", "", m.group(1))
        toc.append((f"s{n}", text))
        return f'<h2 id="s{n}"><span class="n">{n:02d}</span>{m.group(1)}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    body = re.sub(r"<table>", '<div class="tbl"><table class="g-table">', body).replace("</table>", "</table></div>")
    return Markup(body), toc, tools


def read_min(g):
    n = len(re.sub(r"\s+", "", (g.get("body") or "") + " ".join(g.get("answer") or [])))
    return max(3, round(n / 600))


def og_image(g, out_path):
    """1200×630 공유 이미지: 남색 바탕 + 분류 + 제목."""
    from PIL import Image, ImageDraw, ImageFont
    fonts = SITE.parent / "fonts"
    im = Image.new("RGB", (1200, 630), (15, 30, 61))
    dr = ImageDraw.Draw(im)
    big = ImageFont.truetype(str(fonts / "BlackHanSans-Regular.ttf"), 76)
    mid = ImageFont.truetype(str(fonts / "NotoSansKR-VF.ttf"), 34)
    try:
        mid.set_variation_by_name("Bold")
    except Exception:
        pass
    dr.rounded_rectangle((80, 84, 80 + 22, 84 + 22), 11, fill=(255, 82, 51))
    dr.text((118, 74), f"{g.get('category', '')} 가이드", font=mid, fill=(255, 241, 236))
    words, lines, cur = g["h1"].split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if dr.textlength(t, font=big) > 1040 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    y = 170
    for ln in lines[:3]:
        dr.text((80, y), ln, font=big, fill=(255, 255, 255))
        y += 100
    dr.text((80, 540), "줍줍알람 · jupjupalarm.com", font=mid, fill=(154, 163, 178))
    im.save(out_path, quality=88)


def build(E, notices, write, common, pub, base, today, problems):
    guides = load()
    by = {g["slug"]: g for g in guides}
    tpl = E.get_template("guide.html")
    open_n = [n for n in notices if n["status"] in ("open", "upcoming")]
    import shutil
    for g in guides:
        idir = GDIR / "img" / g["slug"]
        body, toc, tools = render_body(g.get("body", ""), idir)
        if idir.is_dir():
            d = pub / "guide" / g["slug"]
            d.mkdir(parents=True, exist_ok=True)
            for f in idir.iterdir():
                if f.is_file():
                    shutil.copy2(f, d / f.name)
        g["html"], g["toc"], g["tools"] = body, toc, tools
        g["url"] = f"/guide/{g['slug']}/"
        g["read_min"] = read_min(g)
        g["cat_slug"] = CAT_SLUG.get(g.get("category"), "etc")
        g["faq_ld"] = [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in (g.get("faq") or [])]
    for g in guides:
        kinds = set(g.get("notice_kinds") or [])
        match = g.get("notice_match") or []
        lst = [n for n in open_n if n["kind"] in kinds and (not match or any(w in (n["title"] + (n.get("kind_label") or "") + " ".join(n.get("aliases") or [])) for w in match))]
        lst.sort(key=lambda n: n["rcpt"][0])
        g["notices"] = lst[:4]
        g["rel"] = [by[s] for s in (g.get("related") or []) if s in by and s != g["slug"]][:3]
        if len(g["rel"]) < 2:
            g["rel"] += [x for x in guides if x is not g and x.get("category") == g.get("category") and x not in g["rel"]][:2 - len(g["rel"])]
        d = pub / "guide" / g["slug"]
        d.mkdir(parents=True, exist_ok=True)
        try:
            og_image(g, d / "og.jpg")
            og = f"{g['url']}og.jpg"
        except Exception as e:  # 글꼴이 없으면 기본 이미지
            problems.append((g["slug"], f"경고 — 공유 이미지 실패: {e}"))
            og = "/og-default.jpg"
        title = f"{g['title']} · 줍줍알람"
        desc = g.get("description") or (g.get("answer") or [g.get("dek", "")])[0]
        crumb = [("홈", "/"), ("가이드", "/guide/"), (g.get("category", ""), f"/guide/#{g['cat_slug']}")]
        h = tpl.render(g=g, **common, page_url=g["url"], title=title, desc=desc, og=og, og_type="article", crumb=crumb, nav="guide")
        write(g["url"], h, title, desc, "page", g.get("checked") or g.get("published"))
    # 모음
    cats = [(c, CAT_SLUG[c], [g for g in guides if g.get("category") == c]) for c in CATS]
    cats = [c for c in cats if c[2]]
    h = E.get_template("guide_index.html").render(
        cats=cats, guides=guides, guides_ld=[{"@type": "ListItem", "position": i, "url": base + g["url"], "name": g["h1"]} for i, g in enumerate(guides, 1)], **common, page_url="/guide/", title="청약·임대·대출 가이드 — 칼럼 모음 · 줍줍알람",
        desc=f"청약 가점·무순위·임대주택·주택담보대출(DSR·LTV)·신도시까지, 법령과 공식 안내를 근거로 정리한 칼럼 {len(guides)}편.",
        og="/og-default.jpg", crumb=[("홈", "/"), ("가이드", None)], nav="guide")
    write("/guide/", h, "청약·임대·대출 가이드 — 칼럼 모음 · 줍줍알람", "", "list", index=bool(guides))
    return guides
