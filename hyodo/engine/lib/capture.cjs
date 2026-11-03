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
  await p.screenshot({ path: out });
  console.log(JSON.stringify({ hit }));
  await b.close();
})();
