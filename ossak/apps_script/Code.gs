/**
 * 오싹알람 운영시트 스크립트 (Apps Script)
 *
 * 하는 일
 *  - 10분마다: 발행계획에서 시각이 된 '예약' 행을 인스타 캐러셀·릴스·스레드에 게시
 *    (릴스는 영상 처리가 길면 '처리중'으로 두고 다음 확인 때 게시)
 *  - 매시간: 성과(24시간·7일) 기록, 댓글 수집·위험 댓글 메일 알림, '답변대기' 답변 게시
 *  - 매일 08시: 팔로워 수 기록, 비축분 점검, 유튜브 동기화(업로드 링크·상태·조회수·평균 시청률·구독 증가)
 *  - 매주 월요일 04시: 인스타·스레드 토큰 자동 갱신 (60일 만료 방지)
 *
 * 설치: 시트 메뉴 확장 프로그램 → Apps Script 에 이 파일 내용을 붙여넣고 저장
 *       → 시트를 새로고침 → 메뉴 '오싹알람' → '토큰 입력·연결 확인' → '자동 실행 켜기'
 * 토큰은 시트가 아니라 스크립트 속성(Script Properties)에 저장됩니다.
 *
 * 유튜브 동기화 (2026-10-27 추가): Apps Script 왼쪽 '서비스 +'에서 YouTube Data API v3(식별자 YouTube)와
 *   YouTube Analytics API(식별자 YouTubeAnalytics)를 추가 → 메뉴 '오싹알람' → '유튜브 지금 동기화'를 한 번 실행해 권한 허용.
 *   스크립트를 실행하는 구글 계정이 유튜브 채널(@ossak_alarm) 주인이어야 합니다.
 */

const IG = 'https://graph.instagram.com/v26.0';
const TH = 'https://graph.threads.net/v1.0';
const TZ = 'Asia/Seoul';
const SH = { plan: '발행계획', perf: '성과', fol: '팔로워', cmt: '댓글함', cfg: '설정', topic: '소재조사', yt: '유튜브', prod: '상품' };
// 상품 탭 열 (2026-11-12 자취생 먹거리 채널): 쿠팡 검색으로 가격·링크·사진을 채운다
const PR = { id: 1, name: 2, price: 4, priceDate: 5, link: 9, image: 11, memo: 14, cpName: 15, rocket: 16 };
const CP = 'https://api-gateway.coupang.com';
const CP_BASE = '/v2/providers/affiliate_open_api/apis/openapi';
const DISCLOSURE = '이 글은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.';
const SLOTS = ['11:30', '18:30', '22:00', '07:30', '19:30', '12:30', '21:00', '08:40', '15:30', '17:10'];
// 유튜브 탭 열 번호
const Y = { date: 1, time: 2, id: 3, kind: 4, title: 5, status: 11, link: 12, len: 13, views: 14, avgPct: 15,
  swipe: 16, subs: 17, hook: 18, likes: 19, comments: 20, shares: 21, avgSec: 22, asOf: 23 };
// 발행계획 열 번호 (1부터)
const P = { date: 1, time: 2, ch: 3, id: 4, series: 5, title: 6, hook: 7, risk: 8, status: 9, caption: 10,
  threads: 11, images: 12, count: 13, postId: 14, link: 15, postedAt: 16, log: 17, alert: 18, memo: 19 };
// 댓글함 열 번호
const C = { at: 1, ch: 2, id: 3, link: 4, cid: 5, user: 6, text: 7, time: 8, parent: 9, kind: 10, state: 11,
  reply: 12, note: 13, replyId: 14, replyAt: 15 };

/* ───────── 메뉴 ───────── */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('스레드 운영')
    .addItem('토큰 입력·연결 확인', 'setupTokens')
    .addItem('쿠팡 파트너스 키 입력', 'setupCoupang')
    .addItem('자동 실행 켜기 (트리거 설치)', 'installTriggers')
    .addSeparator()
    .addItem('상품 정보 지금 채우기 (쿠팡 검색)', 'syncProducts')
    .addItem('오늘 발행분 지금 예약', 'scheduleToday')
    .addItem('지금 발행 확인', 'publishDue')
    .addItem('선택한 행 지금 발행 (시각 무시)', 'publishSelected')
    .addItem('성과·댓글 지금 수집', 'hourlyJob')
    .addItem('팔로워 지금 기록', 'dailyJob')
    .addItem('유튜브 지금 동기화', 'syncYouTube')
    .addItem('토큰 지금 갱신', 'refreshTokens')
    .addToUi();
}

/* ───────── 토큰 ───────── */
function setupTokens() {
  const ui = SpreadsheetApp.getUi();
  const props = PropertiesService.getScriptProperties();
  const a = ui.prompt('인스타그램 토큰', '인스타그램 액세스 토큰을 붙여넣으세요 (IGAA…). 바꾸지 않으려면 비워 두고 확인.', ui.ButtonSet.OK_CANCEL);
  if (a.getSelectedButton() !== ui.Button.OK) return;
  if (a.getResponseText().trim()) props.setProperty('IG_TOKEN', a.getResponseText().trim());
  const b = ui.prompt('스레드 토큰', '스레드 액세스 토큰을 붙여넣으세요 (THAA…). 바꾸지 않으려면 비워 두고 확인.', ui.ButtonSet.OK_CANCEL);
  if (b.getSelectedButton() !== ui.Button.OK) return;
  if (b.getResponseText().trim()) props.setProperty('TH_TOKEN', b.getResponseText().trim());
  ui.alert('연결 확인', checkConnection_(), ui.ButtonSet.OK);
}

function checkConnection_() {
  const props = PropertiesService.getScriptProperties();
  const out = [];
  try {
    const me = api_('get', IG + '/me', { fields: 'user_id,username,followers_count', access_token: prop_('IG_TOKEN') });
    props.setProperty('IG_USER_ID', String(me.user_id || me.id));
    props.setProperty('IG_USERNAME', me.username);
    setCfg_('인스타 계정', '@' + me.username);
    out.push('인스타: @' + me.username + ' 연결됨 (팔로워 ' + (me.followers_count || 0) + ')');
  } catch (e) { out.push('인스타: 실패 — ' + e.message); }
  try {
    const me = api_('get', TH + '/me', { fields: 'id,username', access_token: prop_('TH_TOKEN') });
    props.setProperty('TH_USER_ID', String(me.id));
    props.setProperty('TH_USERNAME', me.username);
    setCfg_('스레드 계정', '@' + me.username);
    out.push('스레드: @' + me.username + ' 연결됨');
  } catch (e) { out.push('스레드: 실패 — ' + e.message); }
  return out.join('\n');
}

function refreshTokens() {
  const props = PropertiesService.getScriptProperties();
  const msgs = [];
  try {
    const r = api_('get', 'https://graph.instagram.com/refresh_access_token',
      { grant_type: 'ig_refresh_token', access_token: prop_('IG_TOKEN') });
    props.setProperty('IG_TOKEN', r.access_token);
    msgs.push('인스타 토큰 갱신 (' + Math.round((r.expires_in || 0) / 86400) + '일)');
  } catch (e) { msgs.push('인스타 토큰 갱신 실패: ' + e.message); }
  try {
    const r = api_('get', 'https://graph.threads.net/refresh_access_token',
      { grant_type: 'th_refresh_token', access_token: prop_('TH_TOKEN') });
    props.setProperty('TH_TOKEN', r.access_token);
    msgs.push('스레드 토큰 갱신 (' + Math.round((r.expires_in || 0) / 86400) + '일)');
  } catch (e) { msgs.push('스레드 토큰 갱신 실패: ' + e.message); }
  if (msgs.some(m => m.indexOf('실패') >= 0)) mail_('[자취 스레드] 토큰 갱신 실패', msgs.join('\n') + '\n\n메뉴 오싹알람 → 토큰 입력으로 새 토큰을 넣어 주세요.');
  return msgs.join('\n');
}

/* ───────── 트리거 ───────── */
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('publishDue').timeBased().everyMinutes(10).create();
  ScriptApp.newTrigger('hourlyJob').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('dailyJob').timeBased().atHour(8).everyDays(1).inTimezone(TZ).create();
  ScriptApp.newTrigger('refreshTokens').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(4).inTimezone(TZ).create();
  SpreadsheetApp.getUi().alert('자동 실행을 켰어요: 10분마다 발행 확인, 매시간 성과·댓글, 매일 08시 팔로워, 매주 월요일 토큰 갱신.');
}

/* ───────── 발행 ───────── */
function publishDue() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return;
  try {
    if (String(cfg_('자동 발행')).toUpperCase() !== 'ON') return;
    const sh = sheet_(SH.plan);
    const last = sh.getLastRow();
    if (last < 2) return;
    const vals = sh.getRange(2, 1, last - 1, 19).getValues();
    const disp = sh.getRange(2, 1, last - 1, 19).getDisplayValues();
    const now = new Date();
    let done = 0;
    for (let i = 0; i < vals.length && done < 2; i++) {
      const st = String(vals[i][P.status - 1]).trim();
      if (st === '처리중') { resumeReel_(sh, i + 2, vals[i]); done++; continue; }
      if (st !== '예약') continue;
      const when = when_(vals[i][P.date - 1], disp[i][P.date - 1], vals[i][P.time - 1], disp[i][P.time - 1]);
      if (!when || when > now) continue;
      publishRow_(sh, i + 2, vals[i]);
      done++;
    }
  } finally { lock.releaseLock(); }
}

function publishSelected() {
  const ui = SpreadsheetApp.getUi();
  const sh = SpreadsheetApp.getActiveSheet();
  if (sh.getName() !== SH.plan) { ui.alert('발행계획 탭에서 행을 선택해 주세요.'); return; }
  const row = sh.getActiveRange().getRow();
  if (row < 2) return;
  const v = sh.getRange(row, 1, 1, 19).getValues()[0];
  const ok = ui.alert('지금 발행', row + '행 (' + v[P.ch - 1] + ' · ' + v[P.title - 1] + ')을 지금 올릴까요?', ui.ButtonSet.YES_NO);
  if (ok !== ui.Button.YES) return;
  publishRow_(sh, row, v);
  ui.alert(sh.getRange(row, P.log).getValue());
}

function publishRow_(sh, row, v) {
  const ch = String(v[P.ch - 1]).trim();
  sh.getRange(row, P.status).setValue('발행중');
  SpreadsheetApp.flush();
  const stamp = Utilities.formatDate(new Date(), TZ, 'MM/dd HH:mm');
  try {
    let res;
    if (ch === '인스타 캐러셀') {
      const urls = String(v[P.images - 1]).split(/\r?\n/).map(s => s.trim()).filter(Boolean);
      if (!urls.length) throw new Error('이미지 URL이 비어 있어요');
      if (urls.length > 20) throw new Error('캐러셀은 최대 20장이에요 (' + urls.length + '장)');
      res = publishIg_(urls, String(v[P.caption - 1]));
    } else if (ch === '인스타 릴스') {
      const urls = String(v[P.images - 1]).split(/\r?\n/).map(s => s.trim()).filter(Boolean);
      if (!urls.length || !/\.mp4$/i.test(urls[0])) throw new Error('L열 첫 줄에 영상(.mp4) 주소가 필요해요');
      res = publishReel_(urls[0], urls[1] || '', String(v[P.caption - 1]));
      if (res.pending) {
        sh.getRange(row, P.postId).setValue("'c:" + res.pending);
        sh.getRange(row, P.log).setValue(stamp + ' 영상 처리 중 — 다음 확인 때 게시');
        sh.getRange(row, P.status).setValue('처리중');
        return;
      }
    } else if (ch === '스레드') {
      const pm = productMap_();
      const r = resolve_(String(v[P.threads - 1]), pm);
      if (r.missing.length) throw new Error('상품 정보가 아직 없어요: ' + r.missing.join(', ') + ' — 상품 탭 확인');
      const pics = String(v[P.images - 1]).split(/\r?\n/).map(s => s.trim()).filter(s => /^https:\/\//i.test(s));
      let pic = pics[0] || '';
      const pid = String(v[P.caption - 1]).trim();   // J열 = 상품ID. 강추형(B)에 상품이 하나면 그 상품 사진
      if (!pic && /^B/.test(String(v[P.series - 1])) && pm[pid] && pm[pid].image) pic = pm[pid].image;
      res = publishThreads_(withDisclosure_(r.text), pic);
    } else {
      throw new Error('아직 지원하지 않는 채널: ' + ch);
    }
    done_(sh, row, v, ch, res, stamp);
  } catch (e) {
    fail_(sh, row, v, ch, e, stamp);
  }
}

function done_(sh, row, v, ch, res, stamp) {
  {
    sh.getRange(row, P.postId).setValue("'" + res.id);
    sh.getRange(row, P.link).setValue(res.link || '');
    sh.getRange(row, P.postedAt).setValue("'" + Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'));
    sh.getRange(row, P.log).setValue(stamp + ' 게시 완료' + (res.note ? ' / ' + res.note : ''));
    sh.getRange(row, P.status).setValue('발행완료');
    if (ch === '인스타 캐러셀') markTopic_(String(v[P.id - 1]), '발행');
    const risk = String(v[P.risk - 1]).trim();
    if (risk === '중' || risk === '고') {
      mail_('[자취 스레드] 리스크 ' + risk + ' 게시물이 올라갔어요: ' + v[P.title - 1],
        ch + ' · ' + v[P.title - 1] + '\n' + (res.link || '') + '\n\n확인 후 문제가 있으면 앱에서 삭제하고, 발행계획 상태를 \'삭제\'·메모에 사유를 적어 주세요.');
      sh.getRange(row, P.alert).setValue("'" + stamp + ' 메일 보냄');
    }
  }
}

function fail_(sh, row, v, ch, e, stamp) {
  sh.getRange(row, P.status).setValue('발행오류');
  sh.getRange(row, P.log).setValue(stamp + ' 오류: ' + e.message);
  mail_('[자취 스레드] 발행 오류: ' + v[P.title - 1], ch + ' · ' + row + '행\n' + e.message);
}

/* 릴스: 컨테이너를 만들고 최대 약 2분 기다린다. 덜 끝났으면 {pending: id} */
function publishReel_(video, cover, caption) {
  const uid = prop_('IG_USER_ID'), t = prop_('IG_TOKEN');
  const params = { media_type: 'REELS', video_url: video, caption: caption, share_to_feed: 'true', access_token: t };
  if (cover) params.cover_url = cover;
  const creation = api_('post', IG + '/' + uid + '/media', params).id;
  if (waitIg_(creation, t, 24, 5000, true) !== 'FINISHED') return { pending: creation };
  return igPublish_(creation, t, '릴스');
}

function resumeReel_(sh, row, v) {
  const stamp = Utilities.formatDate(new Date(), TZ, 'MM/dd HH:mm');
  const ch = String(v[P.ch - 1]).trim();
  try {
    const creation = String(v[P.postId - 1]).replace(/^'?c:/, '');
    const t = prop_('IG_TOKEN');
    const s = waitIg_(creation, t, 12, 5000, true);
    if (s === 'FINISHED') { done_(sh, row, v, ch, igPublish_(creation, t, '릴스'), stamp); return; }
    const when = when_(v[P.date - 1], '', v[P.time - 1], '');
    if (when && (new Date() - when) > 90 * 60000) throw new Error('영상 처리가 90분 넘게 끝나지 않았어요 (' + creation + ')');
    sh.getRange(row, P.log).setValue(stamp + ' 영상 처리 중 (' + s + ')');
  } catch (e) { fail_(sh, row, v, ch, e, stamp); }
}

function igPublish_(creation, t, note) {
  const uid = prop_('IG_USER_ID');
  const id = api_('post', IG + '/' + uid + '/media_publish', { creation_id: creation, access_token: t }).id;
  let link = '';
  try { link = api_('get', IG + '/' + id, { fields: 'permalink', access_token: t }).permalink; } catch (e) {}
  return { id: id, link: link, note: note };
}

function publishIg_(urls, caption) {
  const uid = prop_('IG_USER_ID'), t = prop_('IG_TOKEN');
  let creation;
  if (urls.length === 1) {
    creation = api_('post', IG + '/' + uid + '/media', { image_url: urls[0], caption: caption, access_token: t }).id;
  } else {
    const kids = urls.map(u => api_('post', IG + '/' + uid + '/media',
      { image_url: u, is_carousel_item: 'true', access_token: t }).id);
    kids.forEach(k => waitIg_(k, t));
    creation = api_('post', IG + '/' + uid + '/media',
      { media_type: 'CAROUSEL', children: kids.join(','), caption: caption, access_token: t }).id;
  }
  waitIg_(creation, t);
  const id = api_('post', IG + '/' + uid + '/media_publish', { creation_id: creation, access_token: t }).id;
  let link = '';
  try { link = api_('get', IG + '/' + id, { fields: 'permalink', access_token: t }).permalink; } catch (e) {}
  return { id: id, link: link, note: urls.length + '장' };
}

function waitIg_(id, t, tries, ms, soft) {
  let s = '';
  for (let i = 0; i < (tries || 20); i++) {
    const r = api_('get', IG + '/' + id, { fields: 'status_code,status', access_token: t });
    s = r.status_code;
    if (s === 'FINISHED' || s === 'PUBLISHED') return 'FINISHED';
    if (s === 'ERROR' || s === 'EXPIRED') throw new Error('인스타 컨테이너 ' + s + ' (' + id + ') ' + (r.status || ''));
    Utilities.sleep(ms || 3000);
  }
  if (soft) return s || 'IN_PROGRESS';
  throw new Error('인스타 컨테이너 준비 시간 초과 (' + id + ')');
}

// image: 첫 글에 붙일 사진 주소(공개 jpg·png). 없으면 글자만 (2026-11-12 자취생 먹거리 채널)
function publishThreads_(text, image) {
  const t = prop_('TH_TOKEN');
  const posts = text.split(/\r?\n\s*-{3,}\s*\r?\n/).map(s => s.trim()).filter(Boolean);
  if (!posts.length) throw new Error('스레드 본문이 비어 있어요');
  let first = null, prev = null;
  const ids = [];
  posts.forEach((p, i) => {
    const params = { media_type: 'TEXT', text: p.slice(0, 500), access_token: t };
    if (i === 0 && image) { params.media_type = 'IMAGE'; params.image_url = image; }
    if (prev) params.reply_to_id = prev;
    let c;
    try { c = api_('post', TH + '/me/threads', params).id; }
    catch (e) {   // 사진 주소를 스레드가 못 받으면 글자만으로 다시
      if (!(i === 0 && image)) throw e;
      image = ''; params.media_type = 'TEXT'; delete params.image_url;
      c = api_('post', TH + '/me/threads', params).id;
    }
    Utilities.sleep(i === 0 ? (image ? 8000 : 2000) : 4000);
    const id = api_('post', TH + '/me/threads_publish', { creation_id: c, access_token: t }).id;
    ids.push(id);
    if (!first) first = id;
    prev = id;
  });
  let link = '';
  try { link = api_('get', TH + '/' + first, { fields: 'permalink', access_token: t }).permalink; } catch (e) {}
  return { id: first, link: link, note: '글 ' + ids.length + '개 (' + ids.slice(1).join(',') + ')' };
}

/* ───────── 쿠팡 파트너스 (2026-11-12) ───────── */
function setupCoupang() {
  const ui = SpreadsheetApp.getUi();
  const props = PropertiesService.getScriptProperties();
  const a = ui.prompt('쿠팡 파트너스 Access Key', '바꾸지 않으려면 비워 두고 확인.', ui.ButtonSet.OK_CANCEL);
  if (a.getSelectedButton() !== ui.Button.OK) return;
  if (a.getResponseText().trim()) props.setProperty('CP_ACCESS', a.getResponseText().trim());
  const b = ui.prompt('쿠팡 파트너스 Secret Key', '바꾸지 않으려면 비워 두고 확인.', ui.ButtonSet.OK_CANCEL);
  if (b.getSelectedButton() !== ui.Button.OK) return;
  if (b.getResponseText().trim()) props.setProperty('CP_SECRET', b.getResponseText().trim());
  let msg;
  try { const r = coupangSearch_('냉동 볶음밥'); msg = '연결됨 — 검색 결과 ' + r.length + '개 (예: ' + (r[0] ? r[0].productName : '없음') + ')'; }
  catch (e) { msg = '연결 실패: ' + e.message; }
  ui.alert('쿠팡 파트너스', msg, ui.ButtonSet.OK);
}

function coupang_(method, path, query, body) {
  const ak = prop_('CP_ACCESS'), sk = prop_('CP_SECRET');
  const dt = Utilities.formatDate(new Date(), 'GMT', "yyMMdd'T'HHmmss'Z'");
  const sig = Utilities.computeHmacSha256Signature(dt + method + path + (query || ''), sk)
    .map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
  const opt = { method: method.toLowerCase(), muteHttpExceptions: true, contentType: 'application/json;charset=UTF-8',
    headers: { Authorization: 'CEA algorithm=HmacSHA256, access-key=' + ak + ', signed-date=' + dt + ', signature=' + sig } };
  if (body) opt.payload = JSON.stringify(body);
  const r = UrlFetchApp.fetch(CP + path + (query ? '?' + query : ''), opt);
  const code = r.getResponseCode();
  let j;
  try { j = JSON.parse(r.getContentText()); } catch (e) { j = {}; }
  if (code >= 300 || (j.rCode !== undefined && String(j.rCode) !== '0')) {
    const err = new Error('쿠팡 ' + code + ' ' + (j.rMessage || j.message || r.getContentText().slice(0, 150)));
    err.code = code;
    throw err;
  }
  return j.data;
}

// 검색은 시간당 호출 수가 적게 잡혀 있어 한 번 실행에 몇 건만 부른다
function coupangSearch_(keyword) {
  const q = 'keyword=' + encodeURIComponent(keyword) + '&limit=10';
  let d;
  try { d = coupang_('GET', CP_BASE + '/v1/products/search', q); }
  catch (e) { if (e.code !== 404) throw e; d = coupang_('GET', CP_BASE + '/products/search', q); }
  return (d && d.productData) || [];
}

function coupangShort_(productId, fallback) {
  try {
    const d = coupang_('POST', CP_BASE + '/v1/deeplink', '', { coupangUrls: ['https://www.coupang.com/vp/products/' + productId] });
    return (d && d[0] && d[0].shortenUrl) || fallback;
  } catch (e) { return fallback; }
}

function syncProducts() { syncProducts_(); SpreadsheetApp.getUi().alert('상품 탭을 확인하세요. 한 번에 최대 6개씩 채워요.'); }

// 상품 탭에서 링크가 빈 행을 쿠팡에서 검색해 가격·링크·사진을 채운다 (한 번에 6개, 매시간)
function syncProducts_() {
  if (!PropertiesService.getScriptProperties().getProperty('CP_ACCESS')) return;
  const sh = sheet_(SH.prod);
  const last = sh.getLastRow();
  if (last < 2) return;
  const v = sh.getRange(2, 1, last - 1, PR.rocket).getDisplayValues();
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  let n = 0;
  for (let i = 0; i < v.length && n < 6; i++) {
    const name = v[i][PR.name - 1].trim();
    if (!name || v[i][PR.link - 1].trim() || v[i][PR.cpName - 1].trim()) continue;
    n++;
    const row = i + 2;
    let list;
    try { list = coupangSearch_(name); }
    catch (e) { sh.getRange(row, PR.memo).setValue((v[i][PR.memo - 1] + ' / ' + today + ' 쿠팡 검색 오류: ' + e.message).slice(0, 300)); break; }
    // 브랜드(첫 단어)와 나머지 단어 하나 이상이 상품명에 들어 있어야 같은 상품으로 본다
    const words = name.split(/\s+/);
    const norm = t => String(t).replace(/\s+/g, '');
    const hit = list.filter(p => norm(p.productName).indexOf(norm(words[0])) >= 0 &&
      (words.length < 2 || words.slice(1).some(w => norm(p.productName).indexOf(norm(w)) >= 0)));
    const pick = hit.filter(p => p.isRocket)[0] || hit[0];
    if (!pick) { sh.getRange(row, PR.cpName).setValue('못 찾음 (' + today + ') — 상품명을 쿠팡 표기대로 고치고 이 칸을 지우면 다시 찾아요'); continue; }
    sh.getRange(row, PR.price).setValue(pick.productPrice);
    sh.getRange(row, PR.priceDate).setValue("'" + today);
    sh.getRange(row, PR.link).setValue(coupangShort_(pick.productId, pick.productUrl));
    sh.getRange(row, PR.image).setValue(pick.productImage || '');
    sh.getRange(row, PR.cpName).setValue(pick.productName);
    sh.getRange(row, PR.rocket).setValue(pick.isRocket ? '로켓' : '');
  }
}

function productMap_() {
  const sh = sheet_(SH.prod);
  const last = sh.getLastRow();
  const m = {};
  if (last < 2) return m;
  sh.getRange(2, 1, last - 1, PR.rocket).getDisplayValues().forEach(r => {
    if (r[0]) m[r[0].trim()] = { name: r[PR.name - 1],
      price: r[PR.price - 1], date: r[PR.priceDate - 1], link: r[PR.link - 1], image: r[PR.image - 1] };
  });
  return m;
}

// 본문의 {{P-001:링크}} {{P-001:가격}} {{P-001:이름}} 을 상품 탭 값으로 바꾼다
function resolve_(text, pm) {
  const missing = [];
  const out = text.replace(/\{\{\s*(P-\d+)\s*:\s*(링크|가격|이름)\s*\}\}/g, (m, id, f) => {
    const p = pm[id];
    let val = '';
    if (p) {
      if (f === '링크') val = p.link;
      else if (f === '이름') val = p.name;
      else if (p.price) {
        const n = Number(String(p.price).replace(/[^0-9]/g, ''));
        const d = String(p.date).slice(5).replace('-', '/');
        val = n ? n.toLocaleString('ko-KR') + '원' + (d ? ' (' + d + ' 조회, 바뀔 수 있음)' : '') : '';
      }
    }
    if (!val) { if (missing.indexOf(id) < 0) missing.push(id); return m; }
    return val;
  });
  return { text: out, missing: missing };
}

// 쿠팡 링크가 있는 글타래인데 대가성 문구가 없으면, 링크가 처음 나오는 글 맨 위에 붙인다
function withDisclosure_(text) {
  if (!/coupang\.com/i.test(text) || /쿠팡 파트너스 활동/.test(text)) return text;
  const parts = text.split(/\r?\n\s*-{3,}\s*\r?\n/);
  for (let i = 0; i < parts.length; i++) if (/coupang\.com/i.test(parts[i])) { parts[i] = DISCLOSURE + '\n\n' + parts[i].trim(); break; }
  return parts.join('\n---\n');
}

/* ───────── 하루 발행분 자동 예약 (2026-11-12) ─────────
   설정: '하루 발행 시작일'(그날 '하루 발행 시작 편수'), 매일 +1, '하루 발행 최대 편수'까지.
   '대기' 글 중 준비된 것(상품 정보가 다 있는 것)을 위에서부터 오늘 빈 시각에 넣고 '예약'으로 바꾼다.
   강추·목록형(형식 B·C)은 하루의 '링크 글 최대 비율(%)' 이하, 연달아 두 개 안 됨 — 다른 형식은 답글에만 링크가 붙어 세지 않는다
   (2026-11-12 사용자 결정: 모든 글에 답글 링크). 매시간 다시 확인해 모자란 만큼 채운다. */
function scheduleToday() { const n = scheduleToday_(); SpreadsheetApp.getUi().alert('오늘 새로 예약한 글: ' + n + '개'); }

function scheduleToday_() {
  const start = String(cfg_('하루 발행 시작일')).trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return 0;
  const now = new Date();
  const today = Utilities.formatDate(now, TZ, 'yyyy-MM-dd');
  const days = Math.round((new Date(today + 'T00:00:00+09:00') - new Date(start + 'T00:00:00+09:00')) / 86400000);
  if (days < 0) return 0;
  const quota = Math.min(Number(cfg_('하루 발행 최대 편수')) || 10, (Number(cfg_('하루 발행 시작 편수')) || 3) + days);
  const maxLink = Math.floor(quota * (Number(cfg_('링크 글 최대 비율(%)')) || 55) / 100);
  const sh = sheet_(SH.plan);
  const last = sh.getLastRow();
  if (last < 2) return 0;
  const v = sh.getRange(2, 1, last - 1, 19).getDisplayValues();
  const isLink = t => /\{\{|coupang\.com|toss\./i.test(t);
  const hhmm = t => { const m = String(t).match(/(\d{1,2}):(\d{2})/); return m ? ('0' + m[1]).slice(-2) + ':' + m[2] : ''; };
  const used = {};
  let have = 0, links = 0;
  v.forEach(r => {
    if (r[P.date - 1] !== today || ['예약', '발행중', '발행완료', '발행오류', '처리중'].indexOf(r[P.status - 1].trim()) < 0) return;
    const hard = /^[BC]/.test(r[P.series - 1]);
    have++; used[hhmm(r[P.time - 1])] = hard ? 'L' : 'N';
    if (hard) links++;
  });
  if (have >= quota) return 0;
  const nowHm = Utilities.formatDate(new Date(now.getTime() + 10 * 60000), TZ, 'HH:mm');
  const day = SLOTS.slice(0, quota).sort();
  const free = day.filter(t => !used[t] && t > nowHm).slice(0, quota - have);
  const pm = productMap_();
  const picked = {};
  let done = 0;
  free.forEach(t => {
    const k = day.indexOf(t);
    const nearLink = used[day[k - 1]] === 'L' || used[day[k + 1]] === 'L';
    for (let i = 0; i < v.length; i++) {
      if (picked[i] || v[i][P.status - 1].trim() !== '대기' || v[i][P.ch - 1].trim() !== '스레드') continue;
      const text = v[i][P.threads - 1];
      if (!text.trim()) continue;
      const hard = /^[BC]/.test(v[i][P.series - 1]);
      if (resolve_(text, pm).missing.length) continue;            // 상품 정보가 아직 안 채워진 글
      if (hard && (!isLink(text) || nearLink || links >= maxLink)) continue;
      picked[i] = true; used[t] = hard ? 'L' : 'N'; if (hard) links++;
      sh.getRange(i + 2, P.date, 1, 2).setValues([["'" + today, "'" + t]]);
      sh.getRange(i + 2, P.status).setValue('예약');
      done++;
      break;
    }
  });
  return done;
}

/* ───────── 매시간: 상품·예약·성과·댓글·답변 ───────── */
function hourlyJob() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return;
  try {
    safe_(syncProducts_);
    safe_(scheduleToday_);
    safe_(collectMetrics_);
    safe_(collectComments_);
    safe_(postReplies_);
  } finally { lock.releaseLock(); }
}

function collectMetrics_() {
  const plan = sheet_(SH.plan), perf = sheet_(SH.perf);
  const rows = planRows_(plan);
  const have = {};
  if (perf.getLastRow() > 1) perf.getRange(2, 1, perf.getLastRow() - 1, 21).getValues()
    .forEach(r => { have[String(r[19]) + '|' + r[7]] = true; });
  const now = new Date();
  const marks = [['24시간', 24], ['7일', 168]];
  if (perf.getRange(1, 22).getValue() === '') perf.getRange(1, 22).setValue('릴스 평균 시청(초)');
  rows.forEach(r => {
    if (r.status !== '발행완료' || !r.postId || !r.postedAt) return;
    const memo = String(plan.getRange(r.row, P.memo).getValue());
    if (memo.indexOf('성과 수집 중지') >= 0) return;       // 삭제됐거나 볼 수 없는 게시물
    const hours = (now - r.postedAt) / 36e5;
    marks.forEach(([label, h]) => {
      if (hours < h || have[r.postId + '|' + label]) return;
      if (label === '24시간' && hours > 72) return; // 놓친 24시간 기록은 건너뜀
      // 한 게시물이 실패해도 나머지는 계속 기록하고, 실패 이유는 발행계획 메모(S열)에 남긴다 (2026-10-29)
      let m;
      try {
        m = r.ch === '스레드' ? threadInsights_(r.postId) : igInsights_(r.postId, r.ch === '인스타 릴스');
      } catch (e) {
        const gone = /does not exist|cannot be loaded/i.test(e.message);
        plan.getRange(r.row, P.memo).setValue((gone ? '성과 수집 중지 — 게시물이 없거나 볼 수 없음: ' : '성과 수집 실패: ')
          + Utilities.formatDate(now, TZ, 'MM/dd HH:mm') + ' ' + String(e.message).slice(0, 120));
        return;
      }
      const base = r.ch === '스레드' ? m.views : (m.reach || m.views);
      const pct = x => base ? Math.round(x / base * 1000) / 10 : '';
      const share = (m.shares || 0) + (r.ch === '스레드' ? (m.reposts || 0) : 0);
      perf.appendRow([
        Utilities.formatDate(now, TZ, 'yyyy-MM-dd HH:mm'), r.date, r.id, r.title, r.series, r.ch,
        Utilities.formatDate(r.postedAt, TZ, 'yyyy-MM-dd HH:mm'), label,
        num_(m.views), num_(m.reach), num_(m.likes), num_(m.comments !== undefined ? m.comments : m.replies),
        share, num_(m.saved), num_(m.quotes), num_(m.follows),
        pct(m.saved || 0), pct(share), pct((m.likes || 0) + (m.comments || m.replies || 0) + share + (m.saved || 0)),
        "'" + r.postId, r.link,
        m.ig_reels_avg_watch_time !== undefined ? Math.round(m.ig_reels_avg_watch_time / 100) / 10 : ''
      ]);
    });
  });
}

function igInsights_(id, reel) {
  const t = prop_('IG_TOKEN');
  const sets = (reel ? ['views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time'] : [])
    .concat(['views,reach,likes,comments,shares,saved,follows', 'views,reach,likes,comments,shares,saved', 'reach,likes,comments,saved']);
  for (let i = 0; i < sets.length; i++) {
    try { return parseInsights_(api_('get', IG + '/' + id + '/insights', { metric: sets[i], access_token: t })); }
    catch (e) { if (i === sets.length - 1) {
      const f = api_('get', IG + '/' + id, { fields: 'like_count,comments_count', access_token: t });
      return { likes: f.like_count, comments: f.comments_count };
    } }
  }
}

function threadInsights_(id) {
  const t = prop_('TH_TOKEN');
  try { return parseInsights_(api_('get', TH + '/' + id + '/insights', { metric: 'views,likes,replies,reposts,quotes,shares', access_token: t })); }
  catch (e) { return parseInsights_(api_('get', TH + '/' + id + '/insights', { metric: 'likes,replies,reposts,quotes', access_token: t })); }
}

function parseInsights_(res) {
  const m = {};
  (res.data || []).forEach(d => {
    let v = d.total_value ? d.total_value.value : (d.values && d.values.length ? d.values[d.values.length - 1].value : '');
    m[d.name] = typeof v === 'number' ? v : Number(v) || 0;
  });
  return m;
}

function collectComments_() {
  const plan = sheet_(SH.plan), box = sheet_(SH.cmt);
  const seen = {};
  if (box.getLastRow() > 1) box.getRange(2, C.cid, box.getLastRow() - 1, 1).getValues().forEach(r => { seen[String(r[0])] = true; });
  const igMe = PropertiesService.getScriptProperties().getProperty('IG_USERNAME');
  const thMe = PropertiesService.getScriptProperties().getProperty('TH_USERNAME');
  const keys = String(cfg_('위험 키워드') || '').split(',').map(s => s.trim()).filter(Boolean);
  const now = new Date();
  const fresh = [], risky = [];
  planRows_(plan).forEach(r => {
    if (r.status !== '발행완료' || !r.postId || !r.postedAt) return;
    if ((now - r.postedAt) / 864e5 > 14) return; // 게시 후 2주까지만
    let list = [];
    try {
      if (r.ch === '스레드') {
        const res = api_('get', TH + '/' + r.postId + '/conversation',
          { fields: 'id,text,username,timestamp,replied_to', access_token: prop_('TH_TOKEN') });
        list = (res.data || []).filter(c => c.username !== thMe)
          .map(c => ({ id: c.id, user: c.username, text: c.text || '', time: c.timestamp, parent: c.replied_to ? c.replied_to.id : r.postId }));
      } else {
        const res = api_('get', IG + '/' + r.postId + '/comments',
          { fields: 'id,text,username,timestamp,replies{id,text,username,timestamp}', access_token: prop_('IG_TOKEN') });
        (res.data || []).forEach(c => {
          if (c.username !== igMe) list.push({ id: c.id, user: c.username, text: c.text || '', time: c.timestamp, parent: r.postId });
          ((c.replies && c.replies.data) || []).forEach(x => {
            if (x.username !== igMe) list.push({ id: x.id, user: x.username, text: x.text || '', time: x.timestamp, parent: c.id });
          });
        });
      }
    } catch (e) { return; }
    list.forEach(c => {
      if (seen[c.id]) return;
      seen[c.id] = true;
      const hit = keys.filter(k => c.text.indexOf(k) >= 0);
      const kind = hit.length ? '위험' : (c.text.indexOf('?') >= 0 ? '질문' : '일반');
      const row = [Utilities.formatDate(now, TZ, 'yyyy-MM-dd HH:mm'), r.ch, r.id, r.link, "'" + c.id, c.user, c.text,
        c.time ? Utilities.formatDate(new Date(c.time), TZ, 'yyyy-MM-dd HH:mm') : '', "'" + c.parent,
        kind, hit.length ? '확인필요' : '새 댓글', '', hit.length ? '키워드: ' + hit.join(', ') : '', '', ''];
      fresh.push(row);
      if (hit.length) risky.push(r.ch + ' · ' + r.title + '\n@' + c.user + ': ' + c.text + '\n' + r.link);
    });
  });
  if (fresh.length) box.getRange(box.getLastRow() + 1, 1, fresh.length, fresh[0].length).setValues(fresh);
  if (risky.length) mail_('[자취 스레드] 확인이 필요한 댓글 ' + risky.length + '개',
    risky.join('\n\n') + '\n\n삭제 요청·유족 관련이면 24시간 안에 게시물을 확인·삭제하고, 댓글함 상태와 발행계획 메모에 사유를 남겨 주세요.');
}

function postReplies_() {
  if (String(cfg_('자동 답변 게시')).toUpperCase() !== 'ON') return;
  const box = sheet_(SH.cmt);
  const last = box.getLastRow();
  if (last < 2) return;
  const vals = box.getRange(2, 1, last - 1, 15).getValues();
  vals.forEach((v, i) => {
    if (String(v[C.state - 1]) !== '답변대기' || !String(v[C.reply - 1]).trim() || v[C.replyId - 1]) return;
    const row = i + 2, cid = String(v[C.cid - 1]).replace(/^'/, ''), text = String(v[C.reply - 1]).trim();
    try {
      let rid;
      if (v[C.ch - 1] === '스레드') {
        const t = prop_('TH_TOKEN');
        const c = api_('post', TH + '/me/threads', { media_type: 'TEXT', text: text.slice(0, 500), reply_to_id: cid, access_token: t }).id;
        Utilities.sleep(2000);
        rid = api_('post', TH + '/me/threads_publish', { creation_id: c, access_token: t }).id;
      } else {
        rid = api_('post', IG + '/' + cid + '/replies', { message: text, access_token: prop_('IG_TOKEN') }).id;
      }
      box.getRange(row, C.replyId).setValue("'" + rid);
      box.getRange(row, C.replyAt).setValue("'" + Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'));
      box.getRange(row, C.state).setValue('답변완료');
    } catch (e) {
      box.getRange(row, C.note).setValue('답변 실패: ' + e.message);
      box.getRange(row, C.state).setValue('확인필요');
    }
  });
}

/* ───────── 매일: 팔로워·비축분 ───────── */
function dailyJob() {
  safe_(recordFollowers_);
  safe_(checkStock_);
  safe_(syncYouTube);
}

function recordFollowers_() {
  const sh = sheet_(SH.fol);
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  const last = sh.getLastRow();
  let prev = null;
  if (last > 1) {
    prev = sh.getRange(last, 1, 1, 3).getDisplayValues()[0];
    if (prev[0] === today) return;
  }
  let ig = '', th = '';
  try { ig = api_('get', IG + '/me', { fields: 'followers_count', access_token: prop_('IG_TOKEN') }).followers_count; } catch (e) {}
  try {
    const r = api_('get', TH + '/' + prop_('TH_USER_ID') + '/threads_insights', { metric: 'followers_count', access_token: prop_('TH_TOKEN') });
    th = parseInsights_(r).followers_count;
  } catch (e) {}
  const d = (a, b) => (a === '' || b === '' || b === undefined || b === null || b === '') ? '' : Number(a) - Number(b);
  sh.appendRow(["'" + today, ig, th, prev ? d(ig, prev[1]) : '', prev ? d(th, prev[2]) : '', '']);
}

function checkStock_() {
  const min = Number(cfg_('비축 최소 편수')) || 0;
  if (!min) return;
  const now = new Date();
  const n = planRows_(sheet_(SH.plan)).filter(r => r.ch === '인스타 릴스' && r.status === '예약' && r.when && r.when > now).length;
  if (n < min) mail_('[자취 스레드] 비축분이 ' + n + '편 남았어요', '예약된 인스타 릴스가 ' + n + '편이에요 (기준 ' + min + '편). 새 편 제작을 확인해 주세요.');
}

/* ───────── 유튜브: 업로드 찾기 + 성과 (매일 08시, 메뉴) ───────── */
function syncYouTube() {
  if (typeof YouTube === 'undefined' || typeof YouTubeAnalytics === 'undefined')
    throw new Error('Apps Script 서비스에 YouTube Data API와 YouTube Analytics API를 추가해 주세요');
  const sh = sheet_(SH.yt);
  const last = sh.getLastRow();
  if (last < 2) return;
  // 채널 주인 계정으로 허용했으면 분석 수치까지, 아니면(브랜드 계정 채널 등) 공개 수치(조회·좋아요·댓글)만
  let ch = YouTube.Channels.list('id,contentDetails', { mine: true });
  let publicOnly = false;
  if (!ch.items || !ch.items.length) {
    ch = YouTube.Channels.list('id,contentDetails', { forHandle: '@' + (cfg_('유튜브 핸들') || 'ossak_alarm').replace(/^@/, '') });
    publicOnly = true;
  }
  if (!ch.items || !ch.items.length) throw new Error('유튜브 채널을 찾을 수 없어요');
  const uploads = ch.items[0].contentDetails.relatedPlaylists.uploads;

  // 1) 채널 업로드 목록 (예약 공개 영상 포함)
  const vids = [];
  let token;
  do {
    const r = YouTube.PlaylistItems.list('snippet,contentDetails', { playlistId: uploads, maxResults: 50, pageToken: token });
    (r.items || []).forEach(it => vids.push({ id: it.contentDetails.videoId, title: it.snippet.title }));
    token = r.nextPageToken;
  } while (token && vids.length < 300);
  const info = {};
  for (let i = 0; i < vids.length; i += 50) {
    const r = YouTube.Videos.list('status,snippet,statistics', { id: vids.slice(i, i + 50).map(v => v.id).join(',') });
    (r.items || []).forEach(v => { info[v.id] = v; });
  }
  const norm = t => String(t).replace(/【[^】]*】/g, '').replace(/#\S+/g, '').replace(/[\s,.?!…·'"“”‘’~\-]/g, '');

  // 2) 탭의 각 행과 제목으로 짝짓기 → 링크·상태
  const rows = sh.getRange(2, 1, last - 1, Y.asOf).getValues();
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  rows.forEach((r, i) => {
    const row = i + 2;
    if (String(r[Y.status - 1]).trim() === '보류') return;
    let vid = String(r[Y.link - 1]).match(/(?:shorts\/|v=|youtu\.be\/)([\w-]{11})/);
    vid = vid ? vid[1] : null;
    if (!vid) {
      const want = norm(r[Y.title - 1]);
      const hit = vids.find(v => want && (norm(v.title) === want || norm(v.title).indexOf(want) === 0 || want.indexOf(norm(v.title)) === 0));
      if (!hit) return;
      vid = hit.id;
      sh.getRange(row, Y.link).setValue('https://www.youtube.com/shorts/' + vid);
    }
    const v = info[vid];
    if (!v) return;
    const st = v.status || {};
    const live = st.privacyStatus === 'public';
    const state = live ? '게시됨' : (st.publishAt ? '예약완료' : String(r[Y.status - 1]));
    if (state !== String(r[Y.status - 1])) sh.getRange(row, Y.status).setValue(state);
    if (!live) return;
    if (publicOnly) {                       // 공개 수치만: 누적 조회·좋아요·댓글
      const stt = v.statistics || {};
      sh.getRange(row, Y.views).setValue(Number(stt.viewCount || 0));
      sh.getRange(row, Y.likes, 1, 2).setValues([[Number(stt.likeCount || 0), Number(stt.commentCount || 0)]]);
      sh.getRange(row, Y.asOf).setValue("'" + today + ' (공개 수치)');
      return;
    }

    // 3) 성과: 공개일부터 7일 (분석 수치는 1~2일 늦게 들어옴)
    const pub = new Date(v.snippet.publishedAt);
    const start = Utilities.formatDate(pub, TZ, 'yyyy-MM-dd');
    const endD = new Date(pub.getTime() + 6 * 864e5);
    const end = Utilities.formatDate(endD < new Date() ? endD : new Date(), TZ, 'yyyy-MM-dd');
    if (String(r[Y.asOf - 1]) === end && endD < new Date(Date.now() - 2 * 864e5)) return;   // 7일치 확정 뒤에는 그만
    let rep;
    try {
      rep = YouTubeAnalytics.Reports.query({ ids: 'channel==MINE', startDate: start, endDate: end, filters: 'video==' + vid,
        metrics: 'views,averageViewPercentage,averageViewDuration,subscribersGained,likes,comments,shares' });
    } catch (e) { console.error('분석 실패 ' + vid + ': ' + e.message); return; }
    const row0 = (rep.rows && rep.rows[0]) || [];
    const val = k => { const ix = (rep.columnHeaders || []).findIndex(h => h.name === k); return ix >= 0 && row0.length ? row0[ix] : ''; };
    sh.getRange(row, Y.views).setValue(val('views'));
    sh.getRange(row, Y.avgPct).setValue(val('averageViewPercentage') === '' ? '' : Math.round(val('averageViewPercentage') * 10) / 10);
    sh.getRange(row, Y.subs).setValue(val('subscribersGained'));
    sh.getRange(row, Y.likes, 1, 5).setValues([[val('likes'), val('comments'), val('shares'), val('averageViewDuration'), "'" + end]]);
  });
}

/* ───────── 공통 ───────── */
function planRows_(sh) {
  const last = sh.getLastRow();
  if (last < 2) return [];
  const vals = sh.getRange(2, 1, last - 1, 19).getValues();
  const disp = sh.getRange(2, 1, last - 1, 19).getDisplayValues();
  return vals.map((v, i) => ({
    row: i + 2, date: disp[i][P.date - 1], ch: String(v[P.ch - 1]).trim(), id: String(v[P.id - 1]),
    series: String(v[P.series - 1]), title: String(v[P.title - 1]), status: String(v[P.status - 1]).trim(),
    postId: String(v[P.postId - 1]).replace(/^'/, '').trim(), link: String(v[P.link - 1]),
    postedAt: parseStamp_(v[P.postedAt - 1], disp[i][P.postedAt - 1]),
    when: when_(v[P.date - 1], disp[i][P.date - 1], v[P.time - 1], disp[i][P.time - 1])
  }));
}

function when_(dv, dd, tv, td) {
  let date = dv instanceof Date ? Utilities.formatDate(dv, TZ, 'yyyy-MM-dd') : String(dd || dv).trim();
  let m = date.match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  if (!m) return null;
  let time = tv instanceof Date ? Utilities.formatDate(tv, TZ, 'HH:mm') : String(td || tv).trim();
  let t = time.match(/(\d{1,2}):(\d{2})/);
  if (!t) return null;
  let h = Number(t[1]);
  if (/오후|PM/i.test(time) && h < 12) h += 12;
  const pad = n => ('0' + n).slice(-2);
  return new Date(m[1] + '-' + pad(m[2]) + '-' + pad(m[3]) + 'T' + pad(h) + ':' + t[2] + ':00+09:00');
}

function parseStamp_(v, d) {
  if (v instanceof Date) return v;
  const m = String(d || v).match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,2}):(\d{2})/);
  if (!m) return null;
  const pad = n => ('0' + n).slice(-2);
  return new Date(m[1] + '-' + pad(m[2]) + '-' + pad(m[3]) + 'T' + pad(m[4]) + ':' + m[5] + ':00+09:00');
}

function markTopic_(id, status) {
  const sh = SpreadsheetApp.getActive().getSheetByName(SH.topic);
  if (!sh || sh.getLastRow() < 2) return;
  const ids = sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues();
  for (let i = 0; i < ids.length; i++) if (String(ids[i][0]) === id) { sh.getRange(i + 2, 9).setValue(status); return; }
}

function api_(method, url, params) {
  const opt = { method: method, muteHttpExceptions: true };
  if (method === 'post') opt.payload = params || {};
  else if (params) url += (url.indexOf('?') >= 0 ? '&' : '?') + Object.keys(params).map(k => k + '=' + encodeURIComponent(params[k])).join('&');
  const r = UrlFetchApp.fetch(url, opt);
  const code = r.getResponseCode();
  let body;
  try { body = JSON.parse(r.getContentText()); } catch (e) { body = { raw: r.getContentText().slice(0, 300) }; }
  if (code >= 300 || body.error) {
    const msg = body.error ? (body.error.error_user_msg || body.error.message) : JSON.stringify(body).slice(0, 200);
    throw new Error(code + ' ' + msg);
  }
  return body;
}

function cfg_(label) {
  const sh = sheet_(SH.cfg);
  const v = sh.getRange(1, 1, sh.getLastRow(), 2).getDisplayValues();
  for (let i = 0; i < v.length; i++) if (v[i][0] === label) return v[i][1];
  return '';
}

function setCfg_(label, value) {
  const sh = sheet_(SH.cfg);
  const v = sh.getRange(1, 1, sh.getLastRow(), 1).getValues();
  for (let i = 0; i < v.length; i++) if (v[i][0] === label) { sh.getRange(i + 1, 2).setValue(value); return; }
}

function prop_(k) {
  const v = PropertiesService.getScriptProperties().getProperty(k);
  if (!v) throw new Error(k + ' 없음 — 메뉴 오싹알람 → 토큰 입력·연결 확인을 먼저 실행하세요');
  return v;
}

function sheet_(name) {
  const sh = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sh) throw new Error('탭 없음: ' + name);
  return sh;
}

function mail_(subject, body) {
  const to = cfg_('알림 메일') || Session.getEffectiveUser().getEmail();
  if (to) MailApp.sendEmail(to, subject, body);
}

function safe_(fn) { try { fn(); } catch (e) { console.error(fn.name + ': ' + e.message); } }

function num_(v) { return v === undefined || v === null ? '' : v; }
