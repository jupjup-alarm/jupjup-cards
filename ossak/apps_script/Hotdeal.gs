/**
 * 특가반장 핫딜 발행기 (2026-11-22)
 *
 * '쿠팡 가격오류·핫딜 수집기' 시트의 '필터통과' 탭에서 신규 딜을 골라
 *   쿠팡 링크를 내 파트너스 링크로 바꾸고 → 스레드에 본문 + 첫 댓글(링크·대가성 문구)로 올리고
 *   → 결과를 같은 행 J(상태)·L(변환링크)·M(스레드URL)·N(발행시각)·O(비고)에 적는다.
 *
 * 설치: 오싹알람(=특가반장) 운영시트의 Apps Script 프로젝트에 '파일 +' → 스크립트 → 이름 Hotdeal → 이 내용 붙여넣기 → 저장.
 *   쿠팡 키(CP_ACCESS·CP_SECRET)와 스레드 토큰(TH_TOKEN)은 이 프로젝트에 이미 있는 것을 그대로 쓴다.
 *   토큰 갱신도 기존 매주 월요일 refreshTokens 가 맡는다.
 *
 * 실행 (Apps Script 편집기 위쪽 함수 선택 → 실행):
 *   hotdealCheck      연결 점검 (키·토큰·시트·발행 잔량) — 처음 한 번
 *   hotdealPreview    미리보기: 링크 변환 + 글 만들기까지만. 발행·시트 쓰기 없음. 결과는 실행 로그에.
 *   hotdealPublishOne 지금 1건 실제 발행 (시간대·하루 한도·간격 검사는 건너뜀)
 *   hotdealAutoOn     30분마다 자동 발행 켜기 (하루 한도·간격·시간대 지킴)
 *   hotdealAutoOff    자동 발행 끄기
 *
 * 설정 (프로젝트 설정 → 스크립트 속성, 없으면 기본값):
 *   HD_DAILY_MAX 3 · HD_GAP_MIN 90 · HD_HOURS 8-23 · HD_MAX_AGE_H 12 · HD_SUB_ID threads01
 *   HD_HOOK_SOURCES 지금할인  (제목이 상품명이 아니라 홍보 문구인 출처 — 본문전체(K)가 없으면 보류)
 *
 * 주의: 기존 메뉴 '자동 실행 켜기'(installTriggers)는 모든 트리거를 지우고 다시 만든다.
 *       그걸 다시 눌렀다면 hotdealAutoOn 을 한 번 더 실행할 것.
 */

const HD_SHEET_ID = '13-ecoze8qCHs0rcBNWfer9feg7CU-cfVYDEUzA9t5d0';
const HD_TAB = '필터통과';
const HD = { at: 1, src: 2, title: 3, price: 4, kw: 5, score: 6, urls: 7, orig: 8, draft: 9, status: 10, body: 11,
  link: 12, thread: 13, postedAt: 14, note: 15 };
const HD_HEAD = ['변환링크', '스레드URL', '발행시각', '비고(에러)'];
const HD_DISCLOSURE = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.';
const HD_CACHE_DAYS = 7;
const HD_STALE_MIN = 10;

/* ───────── 실행 함수 ───────── */
function hotdealCheck() {
  const out = [];
  ['CP_ACCESS', 'CP_SECRET', 'TH_TOKEN'].forEach(k => out.push(k + ': ' + (hdProp_(k) ? '있음' : '없음')));
  try {
    const me = api_('get', TH + '/me', { fields: 'id,username', access_token: prop_('TH_TOKEN') });
    out.push('스레드 계정: @' + me.username);
  } catch (e) { out.push('스레드 연결 실패: ' + e.message); }
  try { out.push('발행 잔량: ' + hdQuotaText_()); } catch (e) { out.push('발행 잔량 확인 실패: ' + e.message); }
  try {
    const sh = hdSheet_();
    const head = sh.getRange(1, 1, 1, HD.note).getDisplayValues()[0];
    out.push('시트: ' + HD_TAB + ' ' + (sh.getLastRow() - 1) + '행, A~K 헤더 ' + (head[HD.urls - 1] === '쿠팡URL(전체)' && head[HD.status - 1] === '상태' ? '정상' : '다름!'));
    out.push('L~O 헤더: ' + (head.slice(HD.link - 1).join('') ? head.slice(HD.link - 1).join(' / ') : '비어 있음 (첫 발행 때 채움)'));
    const counts = {};
    sh.getRange(2, HD.status, Math.max(sh.getLastRow() - 1, 1), 1).getDisplayValues().forEach(r => {
      const s = String(r[0]).split(':')[0] || '(빈칸)'; counts[s] = (counts[s] || 0) + 1; });
    out.push('상태별: ' + Object.keys(counts).map(k => k + ' ' + counts[k]).join(', '));
  } catch (e) { out.push('시트 접근 실패: ' + e.message); }
  try {
    const r = hdDeeplink_(['https://www.coupang.com/np/search?q=' + encodeURIComponent('생수')], true);
    out.push('쿠팡 링크 변환: ' + (r.ok ? '성공 ' + r.map[Object.keys(r.map)[0]] : '실패 — ' + r.err));
  } catch (e) { out.push('쿠팡 링크 변환 실패: ' + e.message); }
  hdLog_(out.join('\n'));
  return out.join('\n');
}

function hotdealPreview() { return hdRun_({ dry: true, limit: 3 }); }
function hotdealPublishOne() { return hdRun_({ dry: false, limit: 1, manual: true }); }
function hotdealJob() { return hdRun_({ dry: false, limit: 1 }); }

function hotdealAutoOn() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'hotdealJob').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('hotdealJob').timeBased().everyMinutes(30).create();
  hdLog_('핫딜 자동 발행 켬: 30분마다 확인, 하루 ' + hdNum_('HD_DAILY_MAX', 3) + '건, 간격 ' + hdNum_('HD_GAP_MIN', 90) + '분, ' + hdCfg_('HD_HOURS', '8-23') + '시');
}

function hotdealAutoOff() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'hotdealJob').forEach(t => ScriptApp.deleteTrigger(t));
  hdLog_('핫딜 자동 발행 끔');
}

/* ───────── 본체 ───────── */
function hdRun_(o) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) { hdLog_('다른 실행 중 — 건너뜀'); return; }
  try {
    const sh = hdSheet_();
    const last = sh.getLastRow();
    if (last < 2) { hdLog_('필터통과 탭이 비어 있음'); return; }
    const rows = sh.getRange(2, 1, last - 1, HD.note).getDisplayValues();
    const now = new Date();
    const today = Utilities.formatDate(now, TZ, 'yyyy-MM-dd');

    if (!o.dry) {
      if (!o.manual) {
        const gate = hdGate_(rows, now, today);
        if (gate) { hdLog_('발행 안 함: ' + gate); return; }
      }
      if (!hdProp_('TH_TOKEN')) { hdLog_('발행 보류: 스레드 토큰 없음'); return; }
      const q = hdQuota_();
      if (q && q.used >= q.total * 0.8) {
        mail_('[특가반장] 스레드 발행 한도 80% 넘음', '24시간 발행 ' + q.used + '/' + q.total + ' — 핫딜 발행을 멈췄어요.');
        hdLog_('발행 보류: 24시간 발행 ' + q.used + '/' + q.total); return;
      }
      hdEnsureHeader_(sh);
    }

    // 댓글만 다시 달 행 (본문은 올라갔고 댓글이 실패한 행) — 본문 재발행 금지
    if (!o.dry) {
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i];
        if (r[HD.status - 1] === '실패: 댓글 발행 실패' && r[HD.thread - 1]) { hdRetryReply_(sh, i + 2, r); return; }
      }
    }

    // 보류(상품 불확실) 행은 한도에 세지 않고 다음 후보로 넘어간다
    const picks = hdPick_(rows, now);
    const report = [];
    let done = 0;
    for (let i = 0; i < picks.length && done < o.limit; i++) {
      const p = picks[i];
      const hold = hdHoldReason_(p.v);
      if (hold) {
        report.push('행 ' + p.row + ' · ' + p.v[HD.title - 1] + '\n보류: ' + hold);
        if (!o.dry) hdWrite_(sh, p.row, { status: '보류: 상품명 미확정', note: hold });
        continue;
      }
      done++;
      try { report.push(hdOne_(sh, p.row, p.v, p.recover, o.dry)); }
      catch (e) { report.push('행 ' + p.row + ' 오류: ' + e.message); }
    }
    if (!report.length) { hdLog_('처리할 신규 행 없음'); return; }
    hdLog_(report.join('\n\n════════════\n\n'));
    return report.join('\n');
  } finally { lock.releaseLock(); }
}

// 자동 발행 문턱: 시간대 · 오늘 건수 · 마지막 발행 후 간격
function hdGate_(rows, now, today) {
  const h = Number(Utilities.formatDate(now, TZ, 'H'));
  const hours = String(hdCfg_('HD_HOURS', '8-23')).split('-').map(Number);
  if (h < hours[0] || h >= hours[1]) return '발행 시간대 아님 (' + hdCfg_('HD_HOURS', '8-23') + '시)';
  let n = 0, lastAt = null;
  rows.forEach(r => {
    const at = r[HD.postedAt - 1];
    if (!at || !r[HD.thread - 1]) return;
    if (at.indexOf(today) === 0) n++;
    const d = hdParse_(at);
    if (d && (!lastAt || d > lastAt)) lastAt = d;
  });
  if (n >= hdNum_('HD_DAILY_MAX', 3)) return '오늘 ' + n + '건 발행함 (하루 한도 ' + hdNum_('HD_DAILY_MAX', 3) + ')';
  if (lastAt && (now - lastAt) / 60000 < hdNum_('HD_GAP_MIN', 90)) return '마지막 발행 후 ' + Math.round((now - lastAt) / 60000) + '분 (간격 ' + hdNum_('HD_GAP_MIN', 90) + '분)';
  return '';
}

// 고르기: 신규·대기(+10분 넘게 멈춘 처리중) 중 HD_MAX_AGE_H 시간 안의 딜, 점수 높은 순 → 최신 순
function hdPick_(rows, now) {
  const maxAge = hdNum_('HD_MAX_AGE_H', 12);
  const c = [];
  rows.forEach((r, i) => {
    const st = r[HD.status - 1];
    let recover = false;
    if (st === '처리중') {
      const m = String(r[HD.note - 1]).match(/처리중 시작 (\d{4}-\d{2}-\d{2} \d{2}:\d{2})/);
      const t = m ? hdParse_(m[1]) : null;
      if (!t || (now - t) / 60000 < HD_STALE_MIN || r[HD.thread - 1]) return;
      recover = true;
    } else if (st !== '신규' && st !== '대기') return;
    const at = hdParse_(r[HD.at - 1]);
    if (st !== '대기' && at && (now - at) / 3600000 > maxAge) return;   // 사람이 '대기'로 돌린 건 나이 무시
    c.push({ row: i + 2, v: r, recover: recover, score: Number(r[HD.score - 1]) || 0, at: at ? at.getTime() : 0 });
  });
  c.sort((a, b) => b.score - a.score || b.at - a.at);
  return c;
}

function hdOne_(sh, row, v, recover, dry) {
  const notes = [];
  if (recover) notes.push('이전 실행 중단 복구');
  const lines = ['행 ' + row + ' · ' + v[HD.title - 1]];

  // 1) 잠그기
  if (!dry) hdWrite_(sh, row, { status: '처리중', note: '처리중 시작 ' + hdStamp_(new Date()) + (recover ? ' · 복구' : '') });

  // 2) 링크 변환
  const conv = hdConvert_(v);
  notes.push.apply(notes, conv.notes);
  lines.push('링크 ' + conv.pairs.length + '개');
  conv.pairs.forEach(p => lines.push('  ' + p.from + '\n   → ' + p.to));
  if (!dry) hdWrite_(sh, row, { link: conv.pairs.map(p => p.from + ' → ' + p.to).join('\n') });
  if (!conv.pairs.length) return hdFail_(sh, row, dry, lines, '쿠팡 링크 없음', notes);
  if (conv.rateLimited) return hdFail_(sh, row, dry, lines, '쿠팡 API 429', notes);

  // 3) 글 만들기 + 검사
  const post = hdCompose_(v, conv.pairs.map(p => p.to));
  const checks = hdCheck_(post);
  lines.push('── 본문 (' + post.main.length + '자) ──\n' + post.main);
  lines.push('── 첫 댓글 (' + post.reply.length + '자) ──\n' + post.reply);
  lines.push(checks.map(c => (c.ok ? 'PASS ' : 'FAIL ') + c.name).join(' · '));
  const bad = checks.filter(c => !c.ok);
  if (bad.length) return hdFail_(sh, row, dry, lines, bad[0].name, notes);
  if (dry) { lines.push('(미리보기 — 발행 안 함)' + (notes.length ? ' 비고: ' + notes.join(' · ') : '')); return lines.join('\n'); }

  // 4) 발행 — 본문
  let main;
  try { main = hdPostText_(post.main, null); }
  catch (e) { console.error('행 ' + row + ' 본문 발행 실패: ' + e.message); return hdFail_(sh, row, dry, lines, '본문 발행 실패', notes.concat([e.message])); }
  const at = hdStamp_(new Date());
  try { hdWrite_(sh, row, { thread: main.link || main.id, postedAt: at }); }
  catch (e) {   // 올라갔는데 시트에 못 적음 → 절대 재발행하지 않게 크게 남김
    const msg = '!!! 스레드에 올라갔지만 시트 기록 실패 — 재발행 금지 !!!\n행 ' + row + ' 글 ' + main.id + ' ' + main.link + '\n' + post.main;
    console.error(msg); mail_('[특가반장] 발행됨·시트 기록 실패 (행 ' + row + ')', msg);
    throw e;
  }
  lines.push('본문 발행: ' + (main.link || main.id));

  // 5) 첫 댓글
  try {
    const rep = hdPostText_(post.reply, main.id);
    lines.push('첫 댓글: ' + rep.id);
    hdWrite_(sh, row, { status: '발행완료', note: hdShort_(notes.join(' · ')) });
  } catch (e) {
    console.error('행 ' + row + ' 댓글 실패: ' + e.message);
    hdWrite_(sh, row, { status: '실패: 댓글 발행 실패', note: hdShort_('본문만 발행됨 · ' + e.message) });
    lines.push('첫 댓글 실패: ' + e.message + ' (다음 실행 때 댓글만 다시)');
  }
  return lines.join('\n');
}

function hdRetryReply_(sh, row, v) {
  const pairs = String(v[HD.link - 1]).split('\n').map(s => s.split(' → ')[1]).filter(Boolean);
  const post = hdCompose_(v, pairs);
  const id = String(v[HD.thread - 1]).split('/').pop();
  const real = /^\d+$/.test(id) ? id : hdFindPostId_(v[HD.thread - 1]);
  if (!real) { hdWrite_(sh, row, { status: '실패: 댓글 재시도 불가', note: '글 ID를 못 찾음 — 손으로 댓글' }); return; }
  try {
    hdPostText_(post.reply, real);
    hdWrite_(sh, row, { status: '발행완료', note: '댓글 재시도 성공' });
    hdLog_('행 ' + row + ' 댓글만 다시 달음');
  } catch (e) {
    hdWrite_(sh, row, { status: '실패: 댓글 재시도 실패', note: hdShort_(e.message) });
    hdLog_('행 ' + row + ' 댓글 재시도 실패: ' + e.message);
  }
}

function hdFail_(sh, row, dry, lines, reason, notes) {
  lines.push('실패: ' + reason + (notes.length ? ' · ' + notes.join(' · ') : ''));
  if (!dry) hdWrite_(sh, row, { status: '실패: ' + reason, note: hdShort_(notes.join(' · ')) });
  return lines.join('\n');
}

/* ───────── 상품 판단 ───────── */
function hdHoldReason_(v) {
  const title = String(v[HD.title - 1]);
  const src = String(v[HD.src - 1]);
  const hasBody = String(v[HD.body - 1]).trim().length > 0;
  if (/TOP\s*\d/i.test(title)) return '여러 상품 묶음 글 — 상품명·가격 짝을 확인할 수 없음';
  const hookSrc = String(hdCfg_('HD_HOOK_SOURCES', '지금할인')).split(',').map(s => s.trim()).filter(Boolean);
  if (!hasBody && hookSrc.some(s => src.indexOf(s) >= 0)) return '제목이 홍보 문구라 상품명을 모름 (본문전체 없음)';
  if (!hdName_(title)) return '제목에서 상품명을 못 뽑음';
  return '';
}

// 제목 → 상품명 (쇼핑몰 표시·가격·배송 괄호·원산지 꼬리표 제거)
function hdName_(title) {
  return String(title)
    .replace(/\[[^\]]*(쿠팡|원산지)[^\]]*\]/g, ' ')
    .replace(/\([^)]*(원|무료|무배|와우|배송|쿠폰|카드)[^)]*\)/g, ' ')
    .replace(/\d{1,3}(,\d{3})+\s*원/g, ' ')
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '')
    .replace(/\s+/g, ' ').replace(/[\s,·\-/]+$/, '').trim();
}

function hdShip_(title) {
  const t = String(title);
  if (/와우\s*(무배|무료)/.test(t)) return '와우 무료배송';
  if (/무료|무배/.test(t)) return '무료배송';
  return '';
}

/* ───────── 링크 변환 ───────── */
function hdConvert_(v) {
  const title = hdName_(v[HD.title - 1]);
  const raw = String(v[HD.urls - 1]).split('\n').map(s => s.trim()).filter(Boolean);
  const seen = {}, srcs = [];
  raw.forEach(u => { if (!seen[u]) { seen[u] = 1; srcs.push(u); } });
  const notes = [];
  const targets = srcs.map(u => {
    if (/link\.coupang\.com\//.test(u)) {
      const fin = hdResolve_(u);
      const clean = fin && hdCleanProduct_(fin);
      if (clean) return { from: u, target: clean };
      notes.push('검색URL 폴백');
      return { from: u, target: 'https://www.coupang.com/np/search?q=' + encodeURIComponent(title) };
    }
    const clean = hdCleanProduct_(u);
    if (clean) return { from: u, target: clean };
    if (/coupang\.com\/np\/search/.test(u)) { notes.push('검색URL 폴백'); return { from: u, target: u }; }
    return { from: u, target: u };
  });
  const r = hdDeeplink_(targets.map(t => t.target), false);
  if (!r.ok) notes.push(r.err);
  const pairs = targets.map(t => ({ from: t.from, to: (r.map && r.map[t.target]) || t.target }));
  return { pairs: pairs, notes: hdUniq_(notes), rateLimited: r.code === 429 };
}

// 남이 만든 단축 링크를 풀어 최종 주소만 얻는다 (본문은 읽지 않음)
function hdResolve_(url, debug) {
  let u = url;
  for (let i = 0; i < 5; i++) {
    let r;
    try {
      r = UrlFetchApp.fetch(u, { followRedirects: false, muteHttpExceptions: true,
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
          'Accept': 'text/html', 'Accept-Language': 'ko-KR,ko;q=0.9' } });
    } catch (e) { console.log('단축 링크 풀기 실패: ' + u + ' — ' + e.message); return ''; }
    const code = r.getResponseCode();
    const h = r.getAllHeaders();
    const key = Object.keys(h).filter(k => k.toLowerCase() === 'location')[0];
    const loc = key ? (Array.isArray(h[key]) ? h[key][0] : h[key]) : '';
    if (debug) console.log('[' + i + '] ' + code + ' ' + u.slice(0, 80) + '\n    헤더: ' + Object.keys(h).join(', ') + '\n    location: ' + String(loc).slice(0, 120));
    // 본문 안의 이동 주소(자바스크립트·meta refresh)도 확인
    const bodyLoc = !loc && code < 300 ? (r.getContentText().match(/https?:\/\/www\.coupang\.com\/vp\/products\/\d+[^"'\s<>]*/) || [])[0] : '';
    if (bodyLoc) return bodyLoc.replace(/&amp;/g, '&');
    if (!loc) { console.log('단축 링크 풀기 실패: ' + u + ' — HTTP ' + code + ', 이동 주소 없음'); return u === url ? '' : u; }
    u = loc;
    if (/www\.coupang\.com\/vp\/products\//.test(u)) return u;
  }
  return u;
}

// 단축 링크 풀기 시험 — 실행 로그에 단계별 응답이 찍힌다
function hotdealTestResolve() {
  const url = 'https://link.coupang.com/a/iSEdlDjtx6';
  const fin = hdResolve_(url, true);
  console.log('최종: ' + (fin || '(못 풀었음)') + '\n정리: ' + (hdCleanProduct_(fin) || '(상품 주소 아님)'));
}

// 상품 주소에서 상품 번호·옵션만 남기고 남의 제휴 표시(lptag·subid·traceid…)는 모두 버린다
function hdCleanProduct_(url) {
  const m = String(url).match(/coupang\.com\/vp\/products\/(\d+)/);
  if (!m) return '';
  const item = String(url).match(/[?&]itemId=(\d+)/);
  const vend = String(url).match(/[?&]vendorItemId=(\d+)/);
  let out = 'https://www.coupang.com/vp/products/' + m[1];
  const q = [];
  if (item) q.push('itemId=' + item[1]);
  if (vend) q.push('vendorItemId=' + vend[1]);
  return out + (q.length ? '?' + q.join('&') : '');
}

// 쿠팡 파트너스 딥링크 — 7일 캐시, 한 번에 최대 50개, 429·5xx는 3번까지 재시도
function hdDeeplink_(urls, noCache) {
  const map = {};
  if (!hdProp_('CP_ACCESS') || !hdProp_('CP_SECRET')) return { ok: false, err: '파트너스 키 없음 → 원본 링크 사용', map: map };
  const need = [];
  urls.forEach(u => {
    const c = noCache ? null : hdCacheGet_(u);
    if (c) { map[u] = c; console.log('딥링크 캐시 사용: ' + u); } else if (need.indexOf(u) < 0) need.push(u);
  });
  let err = '', code = 0;
  for (let i = 0; i < need.length; i += 50) {
    const chunk = need.slice(i, i + 50);
    for (let t = 0; t < 4; t++) {
      try {
        const d = coupang_('POST', CP_BASE + '/v1/deeplink', '', { coupangUrls: chunk, subId: hdCfg_('HD_SUB_ID', 'threads01') });
        (d || []).forEach(x => { if (x.shortenUrl) { map[x.originalUrl] = x.shortenUrl; hdCachePut_(x.originalUrl, x.shortenUrl); } });
        chunk.forEach(u => { if (!map[u]) err = '일부 링크 변환 거절'; });
        console.log('딥링크 API 호출: ' + chunk.length + '개');
        break;
      } catch (e) {
        code = e.code || 0;
        if ((code === 429 || code >= 500) && t < 3) { Utilities.sleep(2000 * Math.pow(2, t)); continue; }
        err = '쿠팡 API ' + (code || '') + ' ' + (code === 401 ? '인증 실패' : code === 403 ? '권한·IP' : e.message.slice(0, 40));
        break;
      }
    }
  }
  return { ok: !err, err: err, code: code, map: map };
}

function hdCacheGet_(u) {
  const v = PropertiesService.getScriptProperties().getProperty('HDC_' + hdHash_(u));
  if (!v) return '';
  const o = JSON.parse(v);
  return (Date.now() - o.at) / 86400000 < HD_CACHE_DAYS ? o.s : '';
}

function hdCachePut_(u, s) {
  const p = PropertiesService.getScriptProperties();
  p.setProperty('HDC_' + hdHash_(u), JSON.stringify({ s: s, at: Date.now() }));
  if (Math.random() < 0.1) {   // 가끔 오래된 캐시 청소
    const all = p.getProperties();
    Object.keys(all).forEach(k => {
      if (k.indexOf('HDC_') !== 0) return;
      try { if ((Date.now() - JSON.parse(all[k]).at) / 86400000 >= HD_CACHE_DAYS) p.deleteProperty(k); } catch (e) { p.deleteProperty(k); }
    });
  }
}

function hdHash_(s) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, s).map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
}

/* ───────── 글 만들기 ───────── */
function hdCompose_(v, links) {
  const title = String(v[HD.title - 1]);
  const name = hdName_(title);
  const price = String(v[HD.price - 1]).replace(/[^\d]/g, '');
  const priceTxt = price ? Number(price).toLocaleString('ko-KR') + '원' : '';
  const off = (String(v[HD.kw - 1]).match(/할인\s*(\d+)%/) || [])[1];
  const ship = hdShip_(title);
  const q = name.match(/(\d+)\s*(개|봉|팩|입|병|캔|매|롤|켤레|박스)(?!.*\d+\s*(개|봉|팩|입|병|캔|매|롤|켤레|박스))/);
  const qty = q ? Number(q[1]) : 0;
  const unit = q ? q[2] : '';
  const per = price && qty > 1 ? Math.round(Number(price) / qty) : 0;
  // 후킹 — 가장 센 숫자 하나를 앞에 (상품명은 다음 줄에 있으니 되풀이하지 않음)
  let hook;
  if (off && Number(off) >= 30) hook = off + '% 할인 떴어요';
  else if (per && per < 1000) hook = unit + '당 ' + per.toLocaleString('ko-KR') + '원 꼴이에요';
  else if (priceTxt) hook = priceTxt + (ship ? ', ' + ship : '') + ' 특가';
  else hook = '쿠팡 특가 떴어요';

  const info = [name];
  const priceLine = [priceTxt, per ? '(' + unit + '당 ' + per.toLocaleString('ko-KR') + '원)' : '', ship ? '· ' + ship : ''].filter(Boolean).join(' ');
  if (priceLine) info.push(priceLine);

  const main = [hook, '', info.join('\n'), '', '가격은 수시로 바뀌어요. 링크는 첫 댓글에 (광고)'].join('\n');

  const at = hdParse_(v[HD.at - 1]);
  const when = at ? Utilities.formatDate(at, TZ, 'M/d HH:mm') + ' 기준 가격이에요' : '가격은 수시로 바뀌어요';
  const reply = [when, links.slice(0, 5).join('\n'), '', HD_DISCLOSURE].join('\n');
  return { main: main, reply: reply };
}

function hdCheck_(post) {
  return [
    { name: '본문 500자 이하', ok: post.main.length <= 500 },
    { name: '본문 링크 0개', ok: !/https?:\/\//i.test(post.main) },
    { name: '댓글 500자 이하', ok: post.reply.length <= 500 },
    { name: '댓글 링크 1~5개', ok: (post.reply.match(/https?:\/\//g) || []).length >= 1 && (post.reply.match(/https?:\/\//g) || []).length <= 5 },
    { name: '대가성 문구 포함', ok: post.reply.indexOf(HD_DISCLOSURE) >= 0 }
  ];
}

/* ───────── 스레드 ───────── */
function hdPostText_(text, replyTo) {
  const t = prop_('TH_TOKEN');
  if (!replyTo) {   // 같은 글이 최근에 이미 올라가 있으면 그걸 쓴다 (중복 발행 방지)
    const dup = hdRecentSame_(text, t);
    if (dup) return dup;
  }
  const params = { media_type: 'TEXT', text: text, access_token: t };
  if (replyTo) params.reply_to_id = replyTo;
  const c = api_('post', TH + '/me/threads', params).id;
  Utilities.sleep(replyTo ? 4000 : 3000);
  const id = api_('post', TH + '/me/threads_publish', { creation_id: c, access_token: t }).id;
  let link = '';
  try { link = api_('get', TH + '/' + id, { fields: 'permalink', access_token: t }).permalink; } catch (e) {}
  return { id: id, link: link };
}

function hdRecentSame_(text, t) {
  try {
    const d = api_('get', TH + '/me/threads', { fields: 'id,text,permalink', limit: 15, access_token: t }).data || [];
    const hit = d.filter(x => String(x.text || '').trim() === text.trim())[0];
    return hit ? { id: hit.id, link: hit.permalink || '' } : null;
  } catch (e) { return null; }
}

function hdFindPostId_(link) {
  try {
    const d = api_('get', TH + '/me/threads', { fields: 'id,permalink', limit: 50, access_token: prop_('TH_TOKEN') }).data || [];
    const hit = d.filter(x => x.permalink === link)[0];
    return hit ? hit.id : '';
  } catch (e) { return ''; }
}

function hdQuota_() {
  try {
    const d = api_('get', TH + '/me/threads_publishing_limit', { fields: 'quota_usage,config', access_token: prop_('TH_TOKEN') }).data || [];
    if (!d[0]) return null;
    return { used: d[0].quota_usage || 0, total: (d[0].config && d[0].config.quota_total) || 250 };
  } catch (e) { return null; }
}

function hdQuotaText_() { const q = hdQuota_(); return q ? q.used + '/' + q.total + ' (24시간)' : '확인 못 함'; }

/* ───────── 시트 ───────── */
function hdSheet_() {
  const sh = SpreadsheetApp.openById(HD_SHEET_ID).getSheetByName(HD_TAB);
  if (!sh) throw new Error('탭 없음: ' + HD_TAB);
  return sh;
}

function hdEnsureHeader_(sh) {
  const r = sh.getRange(1, HD.link, 1, HD_HEAD.length);
  if (!r.getDisplayValues()[0].join('')) r.setValues([HD_HEAD]);
}

// A~K는 수집기 것 — 상태(J)와 L~O만 쓴다. 날짜는 시트가 바꾸지 않게 글자로.
function hdWrite_(sh, row, f) {
  const set = (col, val) => sh.getRange(row, col).setNumberFormat('@').setValue(String(val));
  if (f.status !== undefined) set(HD.status, f.status);
  if (f.link !== undefined) set(HD.link, f.link);
  if (f.thread !== undefined) set(HD.thread, f.thread);
  if (f.postedAt !== undefined) set(HD.postedAt, f.postedAt);
  if (f.note !== undefined) set(HD.note, hdShort_(f.note));
  SpreadsheetApp.flush();
}

/* ───────── 작은 도구 ───────── */
function hdStamp_(d) { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd HH:mm'); }

// 'YYYY-MM-DD HH:MM' (한국시간 글자) → Date
function hdParse_(s) {
  const m = String(s || '').match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 9, +m[5]));
}

function hdShort_(s) { s = String(s || ''); return s.length > 60 ? s.slice(0, 59) + '…' : s; }
function hdUniq_(a) { return a.filter((x, i) => x && a.indexOf(x) === i); }
function hdProp_(k) { return PropertiesService.getScriptProperties().getProperty(k) || ''; }
function hdCfg_(k, d) { return hdProp_(k) || d; }
function hdNum_(k, d) { const n = Number(hdProp_(k)); return isNaN(n) || !hdProp_(k) ? d : n; }
function hdLog_(s) { console.log(s); }
