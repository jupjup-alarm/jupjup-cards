// 공식 페이지 캡처: node lib/capture.cjs <url> <강조할 글자> <out.png> [width] [height]
const { chromium } = require('playwright');
(async () => {
  const [url, needle, out, w = '1600', h = '900'] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1.5, locale: 'ko-KR' });
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(2500);
  const hit = await p.evaluate((needle) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n; while ((n = walker.nextNode())) {
      if (n.textContent.includes(needle)) {
        const el = n.parentElement; el.scrollIntoView({ block: 'center' });
        el.style.background = 'rgba(242,181,68,.45)'; el.style.outline = '6px solid #E8693A'; el.style.outlineOffset = '4px';
        return el.textContent.trim().slice(0, 120);
      }
    }
    return null;
  }, needle);
  await p.waitForTimeout(500);
  // 강조 박스 위치(화면 비율) — 장면이 그쪽으로 다가가게 official.json에 남긴다
  const box = await p.evaluate(() => {
    const el = [...document.querySelectorAll('*')].find(x => x.style && x.style.outline && x.style.outline.includes('solid'));
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: (r.left + r.width / 2) / innerWidth, y: (r.top + r.height / 2) / innerHeight };
  });
  await p.screenshot({ path: out });
  require('fs').writeFileSync(out.replace(/\.png$/, '.json'), JSON.stringify({ hit, box }));
  console.log(JSON.stringify({ hit, box }));
  await b.close();
})();
