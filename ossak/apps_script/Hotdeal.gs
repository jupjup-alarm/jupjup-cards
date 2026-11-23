/**
 * 특가반장 핫딜 발행기 (2026-11-22)
 *
 * '쿠팡 가격오류·핫딜 수집기' 시트의 '필터통과' 탭에서 신규 딜을 골라
 *   쿠팡 링크를 내 파트너스 링크로 바꿔 L열에 적고 (카톡방에 올릴 때 쓰기)
 *   → 스레드에 본문(초성 후킹 3줄 + 그림: P열 쿠팡 캡처가 있으면 그것, 없으면 가격 카드) + 댓글("실시간 알림은 요기로!!!" + 채팅방 안내 글 인용)
 *   → 결과를 같은 행 J(상태)·L(변환링크)·M(스레드URL)·N(발행시각)·O(비고)에 적는다.
 *   쿠팡 링크는 스레드에 올리지 않는다 — 카톡방으로만 유도 (사용자 결정 2026-11-22).
 *
 * 설치: 운영시트(구 오싹알람)의 Apps Script 프로젝트에 '파일 +' → 스크립트 → 이름 Hotdeal → 이 내용 붙여넣기 → 저장.
 *   왼쪽 '서비스 +' → Google Slides API(식별자 Slides) 추가 (가격 카드 그림용).
 *   쿠팡 키(CP_ACCESS·CP_SECRET)와 스레드 토큰(TH_TOKEN)은 이 프로젝트에 이미 있는 것을 쓴다. 토큰 갱신은 기존 refreshTokens.
 *
 * 실행 (Apps Script 편집기 위쪽 함수 선택 → 실행):
 *   hotdealCheck      연결 점검 (키·토큰·시트·발행 잔량·채팅방 글) — 처음 한 번
 *   hotdealTestCard   가격 카드 그림만 한 장 그려 주소를 로그에 (30분 동안 열림)
 *   hotdealPreview    미리보기: 링크 변환 + 글·카드 만들기까지만. 발행·시트 쓰기 없음.
 *   hotdealPublishOne 지금 1건 실제 발행 (시간대·하루 한도·간격 검사는 건너뜀)
 *   hotdealAutoOn     5분마다 자동 발행 켜기 (맥 캡처기가 웹 앱 주소로 부르면 즉시) (하루 한도·간격·시간대 지킴) / hotdealAutoOff 끄기
 *
 * 설정 (프로젝트 설정 → 스크립트 속성, 없으면 기본값):
 *   HD_DAILY_MAX 10 · HD_GAP_MIN 60 · HD_HOURS 8-23 · HD_MAX_AGE_H 12 · HD_SUB_ID threads01
 *   HD_CHAT_POST 채팅방 안내 글 주소 (기본: 사용자가 준 share 링크) · HD_AD_TAG 기본 off (본문 끝에 붙일 글자, 예: (광고))
 *   HD_SEARCH_PER_RUN 1 · HD_SEARCH_PRICE_PCT 15 (검색 링크 딜의 상품 찾기: 한 번에 몇 건, 가격 허용 차이 %)
 *   HD_MODE mix (역전 딜 + 할인 HD_GENERAL_MIN_OFF(50)% 이상 일반 딜, 역전 먼저 · qty 면 역전만 · all 이면 모든 딜) · HD_MIN_CHEAPER 30 (개당 몇 % 이상 싸야 하는지)
 *   HD_WAIT_CAPTURE_MIN 20 (all 모드에서 P열 캡처를 기다리는 시간, 0이면 안 기다림)
 *   HD_TOSS on (토스 딜도 스레드에 — 일반 딜 조건 · off면 토스 제외) · HD_TOSS_TAG off (on이면 토스 글 첫 줄에 토스 대가성 문구)
 *   HD_HOOK_SOURCES 지금할인  (제목이 상품명이 아니라 홍보 문구인 출처 — 본문전체(K)가 없으면 보류)
 *
 * 주의: 기존 메뉴 '자동 실행 켜기'(installTriggers)는 모든 트리거를 지우고 다시 만든다.
 *       그걸 다시 눌렀다면 hotdealAutoOn 을 한 번 더 실행할 것.
 */

const HD_SHEET_ID = '13-ecoze8qCHs0rcBNWfer9feg7CU-cfVYDEUzA9t5d0';
const HD_TAB = '필터통과';
const HD = { at: 1, src: 2, title: 3, price: 4, kw: 5, score: 6, urls: 7, orig: 8, draft: 9, status: 10, body: 11,
  link: 12, thread: 13, postedAt: 14, note: 15, cap: 16, cmp: 17, prod: 18, inf: 23, page: 24, pname: 25 };
const HD_HEAD = ['변환링크', '스레드URL', '발행시각', '비고(에러)', '캡처', '수량비교', '상품주소'];   // S~U 카톡, V 토스링크, W 인플링크, X 딜페이지, Y 상품명 (맥이 씀)   // P·Q열은 맥북 캡처기, R열은 맥북(단축 링크 풀기)·발행기(파트너스 검색)
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
  try { const id = hdChatPostId_(); out.push('채팅방 글(2/3 인용): ' + (id ? '찾음 ' + id : '꺼짐')); } catch (e) { out.push('채팅방 글 못 찾음: ' + e.message); }
  try {
    const sh = hdSheet_();
    const head = sh.getRange(1, 1, 1, HD.pname).getDisplayValues()[0];
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
  ScriptApp.newTrigger('hotdealJob').timeBased().everyMinutes(5).create();   // 예비 주기 — 평소엔 맥 캡처기가 doPost로 바로 부름
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'hotdealWeekly').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('hotdealWeekly').timeBased().onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(21).inTimezone(TZ).create();   // 주간 총정리
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'hotdealGoldboxSync').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('hotdealGoldboxSync').timeBased().atHour(8).everyDays(1).inTimezone(TZ).create();    // 골드박스 08시
  ScriptApp.newTrigger('hotdealGoldboxSync').timeBased().atHour(14).everyDays(1).inTimezone(TZ).create();   // 골드박스 14시
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'hotdealDaily').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('hotdealDaily').timeBased().atHour(7).everyDays(1).inTimezone(TZ).create();   // 아침 '오늘의 특가'
  hdLog_('핫딜 자동 발행 켬: 5분마다 확인 + 맥 캡처기 신호 즉시 (검색 링크 딜 상품 찾기 포함), 하루 ' + hdNum_('HD_DAILY_MAX', 10) + '건, 간격 ' + hdNum_('HD_GAP_MIN', 60) + '분, ' + hdCfg_('HD_HOURS', '8-23') + '시');
}

/* ───────── 쿠팡 골드박스 시험 (2026-11-23) ─────────
   파트너스 API 골드박스(오늘의 초특가 목록)를 받아 몇 건·어떤 정보가 오는지 실행 로그에 찍는다. 시트·스레드는 건드리지 않음. */
function hotdealGoldboxTest() {
  let d;
  try { d = coupang_('GET', CP_BASE + '/v1/products/goldbox', 'subId=' + encodeURIComponent(hdCfg_('HD_SUB_ID', 'threads01'))); }
  catch (e) { hdLog_('골드박스 호출 실패: ' + e.message + (e.code === 404 ? ' (이 키로는 골드박스 API가 없거나 주소가 다름)' : '')); return; }
  const list = Array.isArray(d) ? d : (d && (d.productData || d.data)) || [];
  hdLog_('골드박스 ' + list.length + '건\n필드: ' + (list[0] ? Object.keys(list[0]).join(', ') : '(없음)') + '\n' +
    list.slice(0, 10).map((p, i) => (i + 1) + '. ' + String(p.productName || '').slice(0, 40) + ' · ' + Number(p.productPrice || 0).toLocaleString('ko-KR') + '원' +
      (p.discountRate !== undefined ? ' · ' + p.discountRate + '%' : '') + (p.isRocket ? ' · 로켓' : '')).join('\n'));
}

/* ───────── 골드박스 → 필터통과 (2026-11-23 사용자 결정) ─────────
   골드박스엔 할인율이 없으므로 '수량 역전 후보'로 넣는다: 맥 캡처기가 상품 페이지를 열어 Q열을 판단한다.
   하루 2번(08·14시) 받아 생필품·식품 위주로 상위 HD_GB_MAX(8)건, 48시간 안에 넣은 상품은 다시 넣지 않는다.
   행은 B열 출처 '쿠팡 골드박스', E열 '쿠팡,골드박스', J열 '대기', G열 상품 주소(남의 링크 아님). 수집기 행과 같은 형식. */
const HD_GB_SKIP = /가전|디지털|컴퓨터|노트북|휴대폰|패션|의류|신발|잡화|가구|인테리어|여행|투어|숙박|호텔|리조트|펜션|티켓|항공|렌터카|캐리어|스포츠|자동차|도서|완구|명품|쥬얼리/;
function hotdealGoldboxPreview() { return hdGoldboxSync_(true); }
function hotdealGoldboxSync() { return hdGoldboxSync_(false); }

function hdGoldboxSync_(dry) {
  if (!hdProp_('CP_ACCESS')) return;
  let d;
  try { d = coupang_('GET', CP_BASE + '/v1/products/goldbox', 'subId=' + encodeURIComponent(hdCfg_('HD_SUB_ID', 'threads01'))); }
  catch (e) { hdLog_('골드박스 받기 실패: ' + e.message); return; }
  const list = (Array.isArray(d) ? d : (d && (d.productData || d.data)) || [])
    .filter(p => p.productId && !HD_GB_SKIP.test(String(p.categoryName || '') + ' ' + String(p.productName || '')))
    .sort((a, b) => (a.rank || 99) - (b.rank || 99))
    .slice(0, hdNum_('HD_GB_MAX', 8));
  const sh = hdSheet_();
  const last = sh.getLastRow();
  const now = new Date();
  const recent = {};
  if (last >= 2) {
    sh.getRange(2, 1, last - 1, HD.urls).getDisplayValues().forEach(r => {
      const t = hdParse_(r[HD.at - 1]);
      if (!t || (now - t) / 3600000 > 48) return;
      (String(r[HD.urls - 1]).match(/vp\/products\/(\d+)/g) || []).forEach(m => { recent[m.replace(/\D/g, '')] = 1; });
    });
  }
  const stamp = Utilities.formatDate(now, TZ, 'yyyy-MM-dd HH:mm:ss');
  const add = list.filter(p => !recent[String(p.productId)]);
  const out = add.map(p => {
    const price = Number(p.productPrice || 0).toLocaleString('ko-KR');
    const url = 'https://www.coupang.com/vp/products/' + p.productId;
    return ["'" + stamp, '쿠팡 골드박스', String(p.productName), "'" + price, '쿠팡,골드박스' + (p.isRocket ? ',로켓' : ''), 7, url, '',
      '[쿠팡 골드박스] ' + p.productName + '\n' + price + '원 · ' + (p.categoryName || ''), '대기', ''];
  });
  hdLog_('골드박스 ' + list.length + '건 중 새로 넣을 것 ' + out.length + '건' + (dry ? ' (미리보기 — 시트에 안 씀)' : '') + '\n' +
    add.map(p => '· ' + String(p.productName).slice(0, 40) + ' · ' + Number(p.productPrice || 0).toLocaleString('ko-KR') + '원 · ' + (p.categoryName || '')).join('\n'));
  if (dry || !out.length) return out.length;
  out.forEach(row => sh.appendRow(row));   // appendRow: 수집기 쓰기와 겹쳐도 행이 덮이지 않음
  return out.length;
}

/* ───────── 주간 총정리 (2026-11-23) ─────────
   매주 일요일 21시: 지난 7일 스레드에 올린 딜 중 센 것 7개를 한 글로. 링크 없음, 답글로 알림방 글 인용. */
function hotdealWeeklyPreview() { return hdWeekly_(true); }
function hotdealWeekly() { return hdWeekly_(false); }

function hdTopItems_(rows, from, to) {
  const items = [];
  rows.forEach((r, i) => {
    if (r[HD.status - 1] !== '발행완료') return;
    const t = hdParse_(r[HD.postedAt - 1]);
    if (!t || t < from || t >= to) return;
    const d = hdFacts_(r), pr = hdPair_(r);
    const nm = hdShortName_(d.name) || d.cat;
    if (!nm) return;
    if (pr) {
      // 2026-11-23 사용자 결정: '개당 N% 쌈' 대신 실제 금액 두 개를 나란히 (계산 없이 바로 이상하다고 느끼게)
      items.push({ s: 100 + pr.cheaper, line: nm + (pr.size && nm.indexOf(pr.size) < 0 ? ' ' + pr.size : '') + '\n' + pr.a.q + pr.a.u + ' ' + pr.a.p.toLocaleString('ko-KR') + '원 👉 ' +
        pr.b.q + pr.b.u + ' ' + pr.b.p.toLocaleString('ko-KR') + '원' });
    } else if (d.off) {
      items.push({ s: Number(d.off), line: nm + '\n' + d.off + '% 할인 👉 ' + d.priceTxt });
    }
  });
  items.sort((a, b) => b.s - a.s);
  return items;
}

function hdWeekly_(dry) {
  const sh = hdSheet_();
  const rows = sh.getRange(2, 1, sh.getLastRow() - 1, HD.pname).getDisplayValues();
  const now = new Date();
  const top = hdTopItems_(rows, new Date(now - 7 * 86400000), now).slice(0, 7);
  if (top.length < 3) { hdLog_('주간 총정리: 이번 주 딜이 ' + top.length + '건뿐이라 건너뜀'); return; }
  const nums = ['①', '②', '③', '④', '⑤', '⑥', '⑦'];
  let text = '';
  for (let n = top.length; n >= 3; n--) {
    text = ['🧾 이번 주 놓쳤으면 아까운 딜 TOP ' + n, '']
      .concat(top.slice(0, n).map((x, i) => nums[i] + ' ' + x.line).join('\n\n'))
      .concat(['', '지금은 가격이 돌아간 것도 있어요. 저장해두고 다음에 비교해 봐', '이번 주 제일 잘 산 거 하나만 말해줘 👀']).join('\n');
    if (text.length <= 480) break;
  }
  let chatId = '';
  try { chatId = hdChatPostId_(); } catch (e) {}
  const reply = '다음 주에도 이런 거 뜨면 알림방에 제일 먼저 올려요 👇';
  hdLog_('── 주간 총정리 (' + text.length + '자) ──\n' + text + '\n── 답글 ──\n' + reply + (chatId ? ' [인용]' : ''));
  if (dry) return text;
  const main = hdPostText_(text, null);
  if (chatId) { try { hdPostText_(reply, main.id, { quote_post_id: chatId }); } catch (e) { console.error('주간 총정리 답글 실패: ' + e.message); } }
  hdLog_('주간 총정리 발행: ' + (main.link || main.id));
  return main.link;
}

/* ───────── 아침 '오늘의 특가' 새 글 (2026-11-23 사용자 결정) ─────────
   매일 07시: 어제 스레드에 올린 딜 중 센 것 3개를 새 글로. 링크 없음, 답글로 알림방 글 인용.
   하루 발행 한도(HD_DAILY_MAX)에는 세지 않는다 (시트 행이 아니므로). 어제 올린 딜이 2건 미만이면 건너뜀. */
function hotdealDailyPreview() { return hdDaily_(true); }
function hotdealDaily() { return hdDaily_(false); }

function hdDaily_(dry) {
  const sh = hdSheet_();
  const rows = sh.getRange(2, 1, sh.getLastRow() - 1, HD.pname).getDisplayValues();
  const now = new Date();
  const today = hdParse_(Utilities.formatDate(now, TZ, 'yyyy-MM-dd') + ' 00:00');
  const yest = new Date(today.getTime() - 86400000);
  const top = hdTopItems_(rows, yest, today).slice(0, 3);
  if (top.length < 2) { hdLog_('아침 정리: 어제 올린 딜이 ' + top.length + '건뿐이라 건너뜀'); return; }
  const dow = ['일', '월', '화', '수', '목', '금', '토'][Number(Utilities.formatDate(now, TZ, 'u')) % 7];
  const nums = ['①', '②', '③'];
  const text = ['☀️ ' + Utilities.formatDate(now, TZ, 'M/d') + '(' + dow + ') 아침 특가 정리', '어제 놓쳤으면 아까운 딜 ' + top.length + '개', '']
    .concat(top.map((x, i) => nums[i] + ' ' + x.line).join('\n\n'))
    .concat(['', '지금은 가격이 돌아간 것도 있어요. 오늘 뜨는 건 알림방에 먼저 올려요']).join('\n');
  let chatId = '';
  try { chatId = hdChatPostId_(); } catch (e) {}
  const reply = '오늘 뜨는 딜은 여기서 제일 먼저 받아보세요 👇';
  hdLog_('── 아침 정리 (' + text.length + '자) ──\n' + text + '\n── 답글 ──\n' + reply + (chatId ? ' [인용]' : ''));
  if (dry) return text;
  const main = hdPostText_(text, null);
  if (chatId) { try { hdPostText_(reply, main.id, { quote_post_id: chatId }); } catch (e) { console.error('아침 정리 답글 실패: ' + e.message); } }
  hdLog_('아침 정리 발행: ' + (main.link || main.id));
  return main.link;
}

function hotdealAutoOff() {
  ScriptApp.getProjectTriggers().filter(t => ['hotdealJob', 'hotdealWeekly', 'hotdealDaily', 'hotdealGoldboxSync'].indexOf(t.getHandlerFunction()) >= 0).forEach(t => ScriptApp.deleteTrigger(t));
  hdLog_('핫딜 자동 발행 끔');
}

/* ───────── 맥 캡처기 신호 → 즉시 발행 (2026-11-22) ─────────
   맥 캡처기가 Q열(수량비교)을 쓴 직후 이 웹 앱 주소로 POST {"key": "<HD_HOOK_KEY>"} 를 보내면
   5분 주기를 기다리지 않고 바로 발행 확인을 한다 (하루 한도·간격·시간대는 그대로 지킴).
   설치: hotdealHookKey 실행 → 로그의 키를 맥 .env 에 → 배포 → 새 배포 → 웹 앱 (실행: 나, 액세스: 모든 사용자) → 주소를 맥 .env 에. */
function doPost(e) {
  let body = {};
  try { body = JSON.parse(e.postData.contents); } catch (x) {}
  const key = hdProp_('HD_HOOK_KEY');
  if (!key || body.key !== key) return ContentService.createTextOutput('forbidden');
  const out = hdRun_({ dry: false, limit: 1 });
  return ContentService.createTextOutput('ok ' + String(out || '').slice(0, 300));
}

function hotdealHookKey() {
  let key = hdProp_('HD_HOOK_KEY');
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, '');
    PropertiesService.getScriptProperties().setProperty('HD_HOOK_KEY', key);
  }
  console.log('맥 .env 에 넣을 값\nHOTDEAL_HOOK_KEY=' + key + '\n(웹 앱 주소는 배포 후 HOTDEAL_HOOK_URL 로)');
}

/* ───────── 본체 ───────── */
function hdRun_(o) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) { hdLog_('다른 실행 중 — 건너뜀'); return; }
  try {
    const sh = hdSheet_();
    const last = sh.getLastRow();
    if (last < 2) { hdLog_('필터통과 탭이 비어 있음'); return; }
    const rows = sh.getRange(2, 1, last - 1, HD.pname).getDisplayValues();
    const now = new Date();
    const today = Utilities.formatDate(now, TZ, 'yyyy-MM-dd');

    // 검색 링크뿐인 딜은 파트너스 상품 검색으로 상품 주소를 찾아 R열에 (맥북 캡처기가 그 주소로 연다) — 발행 문턱과 상관없이
    if (!o.dry && !o.manual) {
      hdEnsureHeader_(sh);
      try { hdFindProducts_(sh, rows, now); } catch (e) { console.log('상품 찾기 오류: ' + e.message); }
    }

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
  if (n >= hdNum_('HD_DAILY_MAX', 10)) return '오늘 ' + n + '건 발행함 (하루 한도 ' + hdNum_('HD_DAILY_MAX', 10) + ')';
  if (lastAt && (now - lastAt) / 60000 < hdNum_('HD_GAP_MIN', 60)) return '마지막 발행 후 ' + Math.round((now - lastAt) / 60000) + '분 (간격 ' + hdNum_('HD_GAP_MIN', 60) + '분)';
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
    if (at && (now - at) / 3600000 > maxAge) return;   // 수집기도 새 행을 '대기'로 쓰므로(2026-11-22 확인) '대기'도 나이 제한
    // PC 캡처기가 P열을 채울 때까지 잠깐 기다림 (P열이 비어 있고 들어온 지 HD_WAIT_CAPTURE_MIN 분 안이면 다음 차례로)
    // 2026-11-23 사용자 결정: 토스 딜도 스레드에 (일반 딜 조건만, 첫 줄에 토스 대가성 문구). 쿠팡·토스 링크가 둘 다 없으면 건너뜀
    // 2026-11-23 맥 요청: 네이버 딜(E열에 '네이버')은 쿠팡처럼 다루지 않는다 — 스레드 발행 대상 아님 (수집기가 G열에 쿠팡 검색 링크를 채워도)
    if (hdIsNaver_(r)) return;
    const toss = hdIsToss_(r);
    if (!toss && !String(r[HD.urls - 1]).split('\n').some(u => /coupang\.com/.test(u))) return;
    if (toss && (hdCfg_('HD_TOSS', 'on') === 'off' || !hdGeneralOk_(r, now, null))) return;
    const mode = hdCfg_('HD_MODE', 'mix');
    const pair = hdPair_(r);
    if (mode === 'qty') {
      // 수량 역전 딜만 (2026-11-22 사용자 결정): Q열에 'A개 X원 → B개 Y원'이 있는 행만 올린다
      if (!pair) return;
    } else if (mode === 'mix') {
      // 2026-11-23 사용자 결정: 역전 딜 + 할인율 50% 이상 일반 쿠팡 딜 (하루 총 HD_DAILY_MAX 안에서, 역전 먼저)
      if (!pair && !hdGeneralOk_(r, now, at)) return;
    } else {
      const wait = hdNum_('HD_WAIT_CAPTURE_MIN', 20);
      if (wait > 0 && !String(r[HD.cap - 1]).trim() && at && (now - at) / 60000 < wait) return;
    }
    c.push({ row: i + 2, v: r, recover: recover, pair: hdPair_(r) ? 1 : 0, score: Number(r[HD.score - 1]) || 0, at: at ? at.getTime() : 0 });
  });
  c.sort((a, b) => b.pair - a.pair || b.score - a.score || b.at - a.at);
  return c;
}

function hdOne_(sh, row, v, recover, dry) {
  const notes = [];
  if (recover) notes.push('이전 실행 중단 복구');
  const lines = ['행 ' + row + ' · ' + v[HD.title - 1]];

  // 1) 잠그기
  if (!dry) hdWrite_(sh, row, { status: '처리중', note: '처리중 시작 ' + hdStamp_(new Date()) + (recover ? ' · 복구' : '') });

  // 2) 링크 변환 (토스 딜은 스레드에 링크를 안 올리므로 변환하지 않음 — 쉐어링크는 맥이 V열에)
  const conv = hdIsToss_(v) ? { pairs: [{ from: '토스', to: '(스레드엔 링크 없음)' }], notes: [], rateLimited: false } : hdConvert_(v);
  notes.push.apply(notes, conv.notes);
  lines.push('링크 ' + conv.pairs.length + '개');
  conv.pairs.forEach(p => lines.push('  ' + p.from + '\n   → ' + p.to));
  if (!dry && !hdIsToss_(v)) hdWrite_(sh, row, { link: conv.pairs.map(p => p.from + ' → ' + p.to).join('\n') });
  if (!conv.pairs.length) return hdFail_(sh, row, dry, lines, '쿠팡 링크 없음', notes);
  if (conv.rateLimited) return hdFail_(sh, row, dry, lines, '쿠팡 API 429', notes);

  // 3) 글 만들기 + 검사 (2026-11-22: 쿠팡 링크는 스레드에 올리지 않음 — 카톡방으로만 유도. 변환 링크는 L열에)
  const post = hdCompose_(v, row);
  let chatId = '';
  try { chatId = hdChatPostId_(); } catch (e) { notes.push('채팅방 글 못 찾음'); console.log('채팅방 글: ' + e.message); }
  const checks = hdCheck_(post).concat([{ name: '채팅방 글 찾음', ok: !!chatId }]);
  lines.push('── 1/2 본문 (' + post.main.length + '자) ──\n' + post.main);
  if (post.link) lines.push('── 답글 1 (링크) ──\n' + post.link);
  lines.push('── 답글 ' + (post.link ? 2 : 1) + ' ──\n' + post.quote + (chatId ? '  [인용: 글 ' + chatId + ']' : ''));

  // 4) 가격 카드 그림
  let card = null;
  const cap = String(v[HD.cap - 1] || '').trim();
  if (/^https:\/\/\S+\.(png|jpe?g)(\?\S*)?$/i.test(cap)) { card = { url: cap, external: true }; lines.push('쿠팡 캡처: ' + cap); }
  else try { card = hdCard_(v, row); lines.push('가격 카드: ' + card.url + (dry ? '\n  (30분 동안 열어볼 수 있음)' : '') + (cap ? '  [캡처 없음: ' + cap + ']' : '')); }
  catch (e) { notes.push('카드 실패'); lines.push('가격 카드 실패: ' + e.message + ' → 글만 올림'); console.error('카드 실패: ' + e.stack); }

  lines.push(checks.map(c => (c.ok ? 'PASS ' : 'FAIL ') + c.name).join(' · '));
  const bad = checks.filter(c => !c.ok);
  if (bad.length) { if (card) hdCardDrop_(card); return hdFail_(sh, row, dry, lines, bad[0].name, notes); }
  if (dry) { lines.push('(미리보기 — 발행 안 함)' + (notes.length ? ' 비고: ' + notes.join(' · ') : '')); return lines.join('\n'); }

  // 5) 발행 — 본문(+카드)
  let main;
  try { main = hdPostText_(post.main, null, card ? { media_type: 'IMAGE', image_url: card.url } : null); }
  catch (e) {
    if (!card) { console.error('행 ' + row + ' 본문 발행 실패: ' + e.message); return hdFail_(sh, row, dry, lines, '본문 발행 실패', notes.concat([e.message])); }
    console.error('카드 붙여 올리기 실패 → 글만: ' + e.message); notes.push('카드 업로드 실패');
    try { main = hdPostText_(post.main, null); }
    catch (e2) { return hdFail_(sh, row, dry, lines, '본문 발행 실패', notes.concat([e2.message])); }
  } finally { if (card) hdCardDrop_(card); }
  const at = hdStamp_(new Date());
  try { hdWrite_(sh, row, { thread: main.link || main.id, postedAt: at }); }
  catch (e) {   // 올라갔는데 시트에 못 적음 → 절대 재발행하지 않게 크게 남김
    const msg = '!!! 스레드에 올라갔지만 시트 기록 실패 — 재발행 금지 !!!\n행 ' + row + ' 글 ' + main.id + ' ' + main.link + '\n' + post.main;
    console.error(msg); mail_('[특가반장] 발행됨·시트 기록 실패 (행 ' + row + ')', msg);
    throw e;
  }
  lines.push('본문 발행: ' + (main.link || main.id));

  // 6) 댓글 — (역전 딜이면 링크 답글 먼저) → 채팅방 글 인용
  try {
    let parent = main.id;
    if (post.link) {
      try { parent = hdPostText_(post.link, main.id).id; lines.push('링크 답글 발행'); }
      catch (e) { notes.push('링크 답글 실패'); console.error('행 ' + row + ' 링크 답글 실패: ' + e.message); }
    }
    const rep = hdPostText_(post.quote, parent, { quote_post_id: chatId });
    lines.push('인용 댓글: ' + rep.id);
    hdWrite_(sh, row, { status: '발행완료', note: hdShort_(notes.join(' · ')) });
  } catch (e) {
    console.error('행 ' + row + ' 댓글 실패: ' + e.message);
    hdWrite_(sh, row, { status: '실패: 댓글 발행 실패', note: hdShort_('본문만 발행됨 · ' + e.message) });
    lines.push('댓글 실패: ' + e.message + ' (다음 실행 때 댓글만 다시)');
  }
  return lines.join('\n');
}

function hdRetryReply_(sh, row, v) {
  const post = hdCompose_(v, row);
  const id = String(v[HD.thread - 1]).split('/').pop();
  const real = /^\d+$/.test(id) ? id : hdFindPostId_(v[HD.thread - 1]);
  if (!real) { hdWrite_(sh, row, { status: '실패: 댓글 재시도 불가', note: '글 ID를 못 찾음 — 손으로 댓글' }); return; }
  try {
    hdPostText_(post.quote, real, { quote_post_id: hdChatPostId_() });
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

/* ───────── 일반 딜 (역전 아님) 스레드 조건 — 2026-11-23 ───────── */
const HD_HEALTH = /영양제|루테인|유산균|비타민|오메가|홍삼|프로바이오틱|콜라겐|밀크씨슬|부항|혈압계|혈당|의료기기|다이어트/;
const HD_DISCLOSURE_TOSS = '[광고] 토스쇼핑 쉐어링크 활동으로, 링크 구매 시 수수료를 지급받습니다.';
function hdIsNaver_(r) { return /네이버/.test(String(r[HD.kw - 1])); }

function hdIsToss_(r) {
  const u = String(r[HD.urls - 1]);
  return /toss\.(shopping|im)\//.test(u) && !/coupang\.com/.test(u);
}

function hdGeneralOk_(r, now, at) {
  const off = Number((String(r[HD.kw - 1]).match(/할인\s*(\d+)%/) || [])[1] || 0);
  if (off < hdNum_('HD_GENERAL_MIN_OFF', 50)) return false;
  const q = String(r[HD.cmp - 1] || '').trim();
  if (/품절|가격 바뀜|다른 상품/.test(q)) return false;                        // 끝났거나 판단이 틀린 딜
  if (!q && at && (now - at) / 60000 < 15) return false;                     // 캡처기가 역전인지 보는 중 — 잠깐 기다림
  if (HD_HEALTH.test(hdProduct_(r))) return false;                           // 건강기능식품·의료기기 제외
  return true;
}

/* ───────── 상품 판단 ───────── */
function hdHoldReason_(v) {
  const title = String(v[HD.title - 1]);
  const src = String(v[HD.src - 1]);
  const hasBody = String(v[HD.body - 1]).trim().length > 0;
  if (/TOP\s*\d/i.test(title)) return '여러 상품 묶음 글 — 상품명·가격 짝을 확인할 수 없음';
  const hookSrc = String(hdCfg_('HD_HOOK_SOURCES', '지금할인')).split(',').map(s => s.trim()).filter(Boolean);
  const hasName = String(v[HD.pname - 1] || '').trim().length > 0;   // 맥이 Y열에 진짜 상품명을 적었으면 보류 안 함
  if (!hasBody && !hasName && hookSrc.some(s => src.indexOf(s) >= 0)) return '제목이 홍보 문구라 상품명을 모름 (본문전체 없음)';
  if (!hdProduct_(v)) return '제목·본문에서 상품명을 못 뽑음';
  return '';
}

// 행 → 상품명. 제목이 '🔥 무지성 7,400원 (64.0% 할인) 🔥'처럼 홍보 문구면 본문전체(K)에서 상품명 줄을 찾는다.
function hdProduct_(v) {
  // 2026-11-23 맥 요청: 캡처기가 Y열 '상품명'(쿠팡 페이지 제목)을 적으면 그걸 최우선으로 쓴다
  const y = String(v[HD.pname - 1] || '').trim();
  if (y) return hdName_(y.replace(/,\s*1개$/, ''));
  const t0 = hdName_(v[HD.title - 1]);
  // 제목이 홍보 문장('…7천원도 안 해 🍋', '…딱 걸렸다')이면 제목을 상품명으로 쓰지 않고 K열에서 찾는다
  const hookSrc = String(hdCfg_('HD_HOOK_SOURCES', '지금할인')).split(',').map(x => x.trim()).filter(Boolean);
  const sentence = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(String(v[HD.title - 1])) ||
    /(안 해|안 돼|떴어|떴다|걸렸다|이거|해요|어요|다$|야$|\?|!)/.test(t0) || hookSrc.some(x => String(v[HD.src - 1]).indexOf(x) >= 0);
  const t = sentence ? '무지성' : t0;   // '무지성'이면 아래에서 K열로 넘어간다
  const HYPE = /무지성|선구매후고민|선구매|역대급|최저가|가격오류|오류|특가|핫딜|역대가|초특가|할인|알림|대박|[\d.,%()☆★~]+|원/g;
  const core = t.replace(HYPE, '').trim();
  if (!/무지성|선구매/.test(t) && /[가-힣A-Za-z]{2,}/.test(core)) return t;
  const lines = String(v[HD.body - 1] || '').split('\n').map(x => x.trim()).filter(Boolean);
  for (let i = 1; i < lines.length; i++) {
    const l = lines[i];
    if (/https?:|%|\d원|정상가|할인|바로\s*가기|포스팅|선구매|가격 현황/.test(l)) continue;
    if (!hdName_(l).replace(HYPE, '').trim()) continue;   // '역대급최저가'처럼 홍보 단어뿐인 줄
    const n = hdName_(l);
    if (n.length >= 4 && /[가-힣A-Za-z]{2,}/.test(n)) return n;
  }
  return '';
}

// 제목 → 상품명 (쇼핑몰 표시·가격·배송 괄호·원산지 꼬리표 제거)
function hdName_(title) {
  return String(title)
    .replace(/\[[^\]]*(쿠팡|원산지|로켓|와우|특가)[^\]]*\]/g, ' ')
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
  const title = hdProduct_(v);
  const raw = String(v[HD.urls - 1]).split('\n').map(s => s.trim()).filter(u => /coupang\.com/.test(u));   // 토스 링크는 맥이 V열에서 따로
  const seen = {}, srcs = [];
  raw.forEach(u => { if (!seen[u]) { seen[u] = 1; srcs.push(u); } });
  const notes = [];
  // R열에 상품 주소가 있으면(맥북이 단축 링크를 풀었거나 파트너스 검색으로 찾음) 그걸로 변환
  const prod = hdCleanProduct_(String(v[HD.prod - 1] || ''));
  const targets = prod ? [{ from: srcs[0] || prod, target: prod }] : srcs.map(u => {
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

/* ───────── 검색 링크 딜 → 상품 주소 (파트너스 상품 검색 API) ─────────
   10초핫딜·딜바다처럼 쿠팡 '검색 링크'만 있는 딜은 맥북 캡처기가 상품 페이지를 열 수 없다.
   제목으로 파트너스 상품 검색을 해서, 가격이 시트 가격과 ±HD_SEARCH_PRICE_PCT % 안이고 이름이 충분히 겹치는 상품을 R열에 적는다.
   검색 API는 시간당 호출 수가 적고 운영시트의 상품 탭 채우기(syncProducts_)와 같이 쓰므로 한 번에 HD_SEARCH_PER_RUN(기본 1)건만. */
function hdFindProducts_(sh, rows, now) {
  if (!hdProp_('CP_ACCESS')) return;
  const per = hdNum_('HD_SEARCH_PER_RUN', 1);
  let n = 0;
  for (let i = 0; i < rows.length && n < per; i++) {
    const r = rows[i];
    if (String(r[HD.prod - 1]).trim() || String(r[HD.cmp - 1]).trim()) continue;
    if (r[HD.status - 1] !== '신규' && r[HD.status - 1] !== '대기') continue;
    if (hdIsNaver_(r)) continue;   // 네이버 딜은 쿠팡 상품을 찾지 않음
    const at = hdParse_(r[HD.at - 1]);
    if (!at || (now - at) / 3600000 > 6) continue;
    const urls = String(r[HD.urls - 1]).split('\n').filter(u => /coupang\.com/.test(u));
    if (!urls.length || urls.some(u => /link\.coupang\.com|\/vp\/products\//.test(u))) continue;   // 검색 링크뿐인 행만
    if (hdHoldReason_(r)) continue;
    n++;
    let res;
    try { res = hdSearchMatch_(r); }
    catch (e) {
      if (e.code === 429) { console.log('파트너스 검색 한도 — 다음 차례에'); return; }
      res = { note: '없음: 검색 오류 ' + (e.code || '') };
    }
    sh.getRange(i + 2, HD.prod).setNumberFormat('@').setValue(res.url || res.note);
    console.log('상품 찾기 행 ' + (i + 2) + ': ' + (res.url ? res.url + ' (' + res.why + ')' : res.note));
  }
}

function hdSearchMatch_(r) {
  const name = hdProduct_(r);
  const price = Number(String(r[HD.price - 1]).replace(/[^\d]/g, '')) || 0;
  const list = coupangSearch_(name.slice(0, 50));
  if (!list.length) return { note: '없음: 검색 결과 없음' };
  const words = name.toLowerCase().split(/[\s,()\[\]\/·+]+/).filter(w => w.length >= 2);
  const pct = hdNum_('HD_SEARCH_PRICE_PCT', 15);
  let best = null;
  list.forEach(p => {
    const pn = String(p.productName || '').toLowerCase().replace(/\s+/g, '');
    const hit = words.filter(w => pn.indexOf(w.replace(/\s+/g, '')) >= 0).length / Math.max(words.length, 1);
    const pp = Number(p.productPrice) || 0;
    const diff = price && pp ? Math.abs(pp - price) / price * 100 : 999;
    if (hit < 0.6 || diff > pct) return;
    const score = hit * 100 - diff;
    if (!best || score > best.score) best = { score: score, p: p, hit: hit, diff: diff };
  });
  if (!best) return { note: '없음: 가격·이름 맞는 상품 없음' };
  return { url: 'https://www.coupang.com/vp/products/' + best.p.productId,
    why: '이름 ' + Math.round(best.hit * 100) + '% · 가격차 ' + Math.round(best.diff) + '% · ' + String(best.p.productName).slice(0, 30) };
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

/* ───────── 글 만들기 ─────────
   2026-11-22 사용자 결정 (참고: 반말 핫딜 채널 형식)
   1/2 본문: 초성 퀴즈 + 짧은 반말 3줄 (링크 없음) + 가격 카드 그림
   2/2 댓글: "실시간 알림은 요기로!!!" + 채팅방 링크가 있는 내 글 인용 (HD_CHAT_POST)
   → 같은 날 수정: 3/3(쿠팡 링크)는 뺌 — 카톡방으로만 유도. 본문에 가격 카드 그림(hdCard_). */
function hdCompose_(v, rowNo) {
  // 2026-11-23 사용자 결정(운영 전략 문서): 첫 줄에 브랜드+용량, 둘째 줄에 숫자(수량 함정·단가), 셋째 줄에 판단, 마지막에 질문 한 줄
  const d = hdFacts_(v);
  const pr = hdPair_(v);
  const nm = hdShortName_(d.name) || d.cat || '이거';
  const k = Number(rowNo) || 0;
  const lines = [];
  if (pr) {
    const per = (o) => Math.round(o.p / o.q).toLocaleString('ko-KR');
    lines.push(nm + (pr.size && nm.indexOf(pr.size) < 0 ? ' ' + pr.size : '') + ' 가격 이상한데??');
    const diff = pr.b.p - pr.a.p, ratio = pr.b.q / pr.a.q;
    const more = Number.isInteger(ratio) ? ratio + '배' : (pr.b.q - pr.a.q) + pr.a.u + ' 더';
    lines.push(pr.a.q + pr.a.u + ' ' + pr.a.p.toLocaleString('ko-KR') + '원인데 ' + pr.b.q + pr.b.u + '가 ' + pr.b.p.toLocaleString('ko-KR') + '원' +
      (diff <= 0 ? ' (더 많은데 더 쌈)' : ' (' + diff.toLocaleString('ko-KR') + '원 더 내면 ' + more + ')'));
    lines.push(pr.a.u + '당 ' + per(pr.a) + '원 → ' + per(pr.b) + '원, ' + pr.cheaper + '% 싸짐. ' + pr.a.q + pr.a.u + ' 말고 ' + pr.b.q + pr.b.u + '짜리로 달려!!!');
  } else {
    lines.push(nm === '이거' ? (d.off ? d.off + '% 빠진 특가 떴어!!' : '특가 떴어!!') : nm + ' ' + (d.off ? d.off + '% 빠졌어!!' : '특가 떴어!!'));
    lines.push(d.priceTxt + (d.per ? ' · ' + d.unit + '당 ' + d.per.toLocaleString('ko-KR') + '원' : '') + (d.ship ? ' · ' + d.ship : ''));
  }
  const at = hdParse_(v[HD.at - 1]);
  lines.push('(' + (at ? Utilities.formatDate(at, TZ, 'M/d HH:mm') + ' 기준, ' : '') + '가격은 금방 바뀌어요)');
  lines.push(hdQuestion_(d.cat, k));
  const tag = String(hdCfg_('HD_AD_TAG', 'off'));
  // 2026-11-23 사용자 결정: 토스 딜도 카톡방에서 안내하므로 스레드 본문엔 토스 문구를 넣지 않음 (HD_TOSS_TAG=on 이면 첫 줄에 넣음)
  if (hdIsToss_(v) && hdCfg_('HD_TOSS_TAG', 'off') === 'on') lines.unshift(HD_DISCLOSURE_TOSS);
  const main = lines.join('\n') + (tag && tag.toLowerCase() !== 'off' && !hdIsToss_(v) ? '\n' + tag : '');

  // 답글 1 (역전 딜만): 딜 페이지 링크 + 대가성 문구. X열(맥이 만든 autodm 딜 페이지)이 있을 때만.
  let linkReply = '';
  const page = String(v[HD.page - 1] || '').trim();
  if (pr && /^https:\/\/autodm\.jupjupalarm\.com\/d\//.test(page)) {
    const inf = /^https?:\/\//.test(String(v[HD.inf - 1] || '').trim());
    linkReply = '가격·옵션 다시 확인 👉 ' + page + '\n\n' + (inf ? HD_DISCLOSURE_INF : HD_DISCLOSURE);
  }
  // 답글 2: 같은 문장 반복 대신 이유가 있는 안내 (돌려 씀) + 채팅방 글 인용
  return { main: main, link: linkReply, quote: HD_FOMO[k % HD_FOMO.length] };
}

const HD_DISCLOSURE_INF = '이 포스팅은 쿠팡 인플루언서 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.';
const HD_FOMO = [
  '이런 딜은 몇 분 만에 품절되거나 가격이 돌아가요. 뜨는 순간 알림 받는 방 켜두면 편해요 👇',
  '스레드엔 다 못 올려요. 오늘 뜬 건 알림방에 먼저 올려요 👇',
  '어제 올린 것도 몇 시간 만에 가격 돌아갔어요. 알림방에서 바로 받아보세요 👇',
  '1개보다 n개가 싼 것만 골라서 알림방에 바로 올려요 👇',
  '가격 이상한 거 뜨면 알림방이 제일 빨라요. 알림 켜두고 대기 👇'
];
const HD_Q = {
  '생수': ['생수 한 달에 몇 박스 써?', '생수 브랜드 정해놓고 사? 그때그때 싼 거?'],
  '휴지': ['휴지는 브랜드 정해놓고 써, 그때그때 싼 거 사?', '휴지 한 달에 몇 롤 써?'],
  '라면': ['라면 한 번에 몇 봉씩 쟁여?', '이 라면 최애인 사람?'],
  '세제': ['세제 떨어지면 바로 사, 미리 쟁여놔?'],
  '탄산수': ['탄산수 한 달에 몇 캔 마셔?'],
  '커피': ['캡슐 하루에 몇 개 써?'],
  '즉석밥': ['즉석밥 집에 몇 개 쟁여둬?'],
  '': ['이 가격이면 몇 개 쟁여?', '평소에 이거 얼마에 샀어?', '이거 써본 사람 후기 좀!', '이거 쟁여두는 편이야?']
};
function hdQuestion_(cat, k) {
  const list = HD_Q[cat] || HD_Q[''];
  return list[k % list.length];
}

// 짧은 상품명 = 브랜드 + 상품 + 용량 (쉼표 앞 본 이름 + 첫 용량), 수량 표기는 둘째 줄에 있으니 뺀다. 26자 안쪽.
function hdShortName_(name) {
  const parts = String(name).split(',').map(x => x.trim()).filter(Boolean);
  let main = (parts[0] || '').replace(/\(.*?\)/g, ' ');
  const size = (String(name).match(/\d+(?:\.\d+)?\s*(?:ml|mL|L|l|g|kg|KG|매|m|구|인분)(?![가-힣A-Za-z])/) || [])[0] || '';
  main = main.replace(/\s*\d+\s*(개입|개|봉|팩|입|병|캔|롤|박스|세트)(?![가-힣A-Za-z]).*$/, '').trim();
  if (size && main.indexOf(size.replace(/\s+/g, '')) < 0 && main.indexOf(size) < 0) main += ' ' + size.replace(/\s+/g, '');
  main = main.replace(/\s+/g, ' ').trim();
  if (main.length > 26) {   // 문장 중간에서 끊기지 않게: 26자 안의 단어까지, 끝의 조사·숫자 꼬리 제거
    main = main.slice(0, 26).replace(/\s+\S*$/, '').replace(/\s+(\S*\d\S*|두|세|네|한)$/, '').replace(/(도|는|은|이|가|을|를|에|의|만)$/, '');
  }
  return main;
}

function hdFacts_(v) {
  const title = String(v[HD.title - 1]);
  const name = hdProduct_(v);
  const price = String(v[HD.price - 1]).replace(/[^\d]/g, '');
  const q = name.match(/(\d+)\s*(개|봉|팩|입|병|캔|매|롤|켤레|박스)(?!.*\d+\s*(개|봉|팩|입|병|캔|매|롤|켤레|박스))/);
  const qty = q ? Number(q[1]) : 0;
  return {
    name: name, qty: qty, unit: q ? q[2] : '',
    priceTxt: price ? Number(price).toLocaleString('ko-KR') + '원' : '',
    per: price && qty > 1 ? Math.round(Number(price) / qty) : 0,
    off: (String(v[HD.kw - 1]).match(/할인\s*(\d+)%/) || [])[1],
    ship: hdShip_(title),
    cho: hdCho_(name),
    cat: hdCategory_(name)
  };
}

// 상품군 힌트: 자주 나오는 말은 사전으로, 나머지는 상품명에서 '종류' 단어(수식어 빼고)를 뽑는다
const HD_CAT = [
  [/생수|삼다수|백산수|아이시스|제주수|스파클/, '생수'], [/탄산수|씨그램|트레비|라임.*무라벨/, '탄산수'],
  [/콜라|사이다|에이드|이온음료|포카리|게토레이/, '음료'], [/두유/, '두유'], [/우유|요거트|요구르트/, '우유'],
  [/커피|캡슐|아메리카노|콜드브루/, '커피'], [/컵라면|라면|짜파게티|불닭/, '라면'], [/햇반|즉석밥|컵밥/, '즉석밥'],
  [/만두/, '만두'], [/화장지|휴지|키친타올|크리넥스|깨끗한나라|잘풀리는집|모나리자|코디 /, '휴지'], [/물티슈/, '물티슈'], [/섬유유연제/, '섬유유연제'],
  [/세제/, '세제'], [/샴푸|린스|트리트먼트|헤어/, '헤어케어'], [/치약|칫솔/, '치약'], [/기저귀/, '기저귀'],
  [/충전기|보조배터리|케이블/, '충전기'], [/이어폰|버즈|에어팟|헤드폰/, '이어폰'],
  [/도가니탕|설렁탕|곰탕|갈비탕|해장국|국밥|순대국|내장탕|김치찌개|찌개/, ''],
  [/삼겹살|목살|갈매기살|항정살|한우|등심|안심|닭가슴살/, ''], [/민찌|다짐육/, '다짐육'],
  [/과메기|고등어|오징어|새우|쭈꾸미|주꾸미|연어|참치/, ''],
  [/사과|배즙|귤|감귤|키위|토마토|딸기|포도|바나나/, ''], [/고무장갑|수세미|행주/, '주방용품'],
  [/간식|쫀디기|과자|젤리|초콜릿|다쿠아즈/, '간식'], [/샌들|운동화|슬리퍼|신발/, '신발'], [/내복|양말|속옷/, '의류']
];
const HD_CAT_SKIP = /^(무라벨|대용량|국내산|수입산|냉동|냉장|무료배송|프리미엄|오리지널|진한|쫄깃|휴대용|반영구|원터치|국산|햇|신상|정품|특가|무지성)$/;
function hdCategory_(name) {
  // 쉼표·+ 앞의 본 상품명을 먼저 본다 ('김치찌개 8입+훌라면' → 찌개, '부항기, 혼합형' → 부항기)
  const main = String(name).split(/[,+]/)[0];
  const scan = t => { for (let i = 0; i < HD_CAT.length; i++) { const m = t.match(HD_CAT[i][0]); if (m) return HD_CAT[i][1] || m[0]; } return ''; };
  const hit = scan(main) || scan(name);
  if (hit) return hit;   // 값이 ''인 항목은 찾은 단어 그대로 (도가니탕, 토마토, 갈매기살…)
  // 사전에 없으면: 숫자·용량 앞의 마지막 '종류' 단어 (수식어·브랜드처럼 보이는 첫 단어는 건너뜀)
  const words = main.split(/[\s()\[\]\/]+/).filter(Boolean);
  let pick = '';
  for (let i = 1; i < words.length; i++) {
    const h = (words[i].match(/^[가-힣]+/) || [''])[0];
    if (h.length >= 2 && !HD_CAT_SKIP.test(h)) pick = h;
    if (/\d/.test(words[i])) break;
  }
  return pick.length <= 6 ? pick : '';
}

// 상품 종류 단어의 초성 (예: 제로콜라 → ㅈㄹㅋㄹ). 숫자가 나오기 전 마지막 한글 단어(2~5자)를 쓴다.
function hdCho_(name) {
  const words = String(name).split(/\s+/);
  let pick = '';
  for (let i = 0; i < words.length; i++) {
    const h = (words[i].match(/^[가-힣]+/) || [''])[0];
    if (h.length >= (/\d/.test(words[i]) ? 3 : 2)) pick = h;   // '동시4대충전'처럼 숫자가 붙은 짧은 말은 건너뜀
    if (/\d/.test(words[i])) break;
  }
  if (!pick) return '';
  const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
  return pick.slice(0, 5).split('').map(c => CHO[Math.floor((c.charCodeAt(0) - 0xAC00) / 588)]).join('');
}

function hdCheck_(post) {
  return [
    { name: '본문 500자 이하', ok: post.main.length <= 500 },
    { name: '본문 링크 0개', ok: !/https?:\/\//i.test(post.main) },
    { name: '링크 답글엔 대가성 문구', ok: !post.link || post.link.indexOf('수수료를 제공받습니다') >= 0 }
  ];
}

/* ───────── 채팅방 안내 글 (2/3에서 인용) ─────────
   스크립트 속성 HD_CHAT_POST 에 그 글 주소(threads.com/@…/post/… 또는 share 링크) 또는 글 ID.
   찾은 ID는 HD_CHAT_POST_ID 에 저장해 다시 찾지 않는다. 비우면 2/3 없이 올린다. */
const HD_CHAT_POST_DEFAULT = 'https://www.threads.com/share/GrUChWmKR';

function hdChatPostId_() {
  const raw = hdCfg_('HD_CHAT_POST', HD_CHAT_POST_DEFAULT).trim();
  if (!raw || raw.toLowerCase() === 'off') return '';
  if (/^\d+$/.test(raw)) return raw;
  const cached = hdProp_('HD_CHAT_POST_ID');
  if (cached && hdProp_('HD_CHAT_POST_SRC') === raw) return cached;
  let url = raw;
  if (/\/share\//.test(url)) {   // share 링크 → 실제 글 주소
    for (let i = 0; i < 4; i++) {
      const r = UrlFetchApp.fetch(url, { followRedirects: false, muteHttpExceptions: true });
      const h = r.getAllHeaders();
      const k = Object.keys(h).filter(x => x.toLowerCase() === 'location')[0];
      if (!k) break;
      url = Array.isArray(h[k]) ? h[k][0] : h[k];
      if (/\/post\//.test(url)) break;
    }
  }
  const code = (String(url).match(/\/post\/([A-Za-z0-9_-]+)/) || [])[1];
  if (!code) throw new Error('채팅방 글 주소에서 글 코드를 못 찾음: ' + String(url).slice(0, 80));
  let after = '';
  for (let page = 0; page < 6; page++) {   // 내 글 최대 600개에서 찾기
    const p = { fields: 'id,permalink', limit: 100, access_token: prop_('TH_TOKEN') };
    if (after) p.after = after;
    const res = api_('get', TH + '/me/threads', p);
    const hit = (res.data || []).filter(x => String(x.permalink || '').indexOf('/post/' + code) >= 0)[0];
    if (hit) {
      const pr = PropertiesService.getScriptProperties();
      pr.setProperty('HD_CHAT_POST_ID', hit.id); pr.setProperty('HD_CHAT_POST_SRC', raw);
      return hit.id;
    }
    after = res.paging && res.paging.cursors && res.paging.cursors.after;
    if (!after) break;
  }
  throw new Error('채팅방 글(' + code + ')이 @' + (hdProp_('TH_USERNAME') || '내 계정') + ' 글 목록에 없음');
}

/* ───────── 가격 카드 그림 (2026-11-22) ─────────
   구글 슬라이드에 카드 한 장을 그려 PNG 썸네일 주소(30분 동안 공개)로 스레드에 붙인다.
   쿠팡 화면 캡처가 아니라 시트의 숫자(가격·수량·개당·할인율·배송)로 직접 그린 그림.
   슬라이드 파일은 처음 한 번 만들고(HD_CARD_DECK) 쓴 장은 지운다.
   Apps Script 왼쪽 '서비스 +'에서 Google Slides API(식별자 Slides)를 추가해 두면 가장 확실하다. */
const HD_C = { blue: '#2F6BFF', red: '#E0352B', green: '#1E9E4A', ink: '#111111', sub: '#444444', gray: '#8A8F98',
  line: '#E3E5E8', bg: '#F4F5F7', font: 'Noto Sans KR' };
let hdDeckClean = false;

function hdDeck_() {
  const id = hdProp_('HD_CARD_DECK');
  let deck = null;
  if (id) { try { deck = SlidesApp.openById(id); } catch (e) { deck = null; } }
  if (!deck) {
    deck = SlidesApp.create('특가반장 가격카드 (자동 생성 — 지우지 마세요)');
    PropertiesService.getScriptProperties().setProperty('HD_CARD_DECK', deck.getId());
  }
  if (!hdDeckClean) {   // 지난 실행에서 남은 장 정리 (첫 장은 남김)
    deck.getSlides().slice(1).forEach(x => x.remove());
    hdDeckClean = true;
  }
  return deck;
}

function hdCard_(v, row) {
  const d = hdFacts_(v);
  const deck = hdDeck_();
  const W = deck.getPageWidth(), H = deck.getPageHeight();   // 기본 720 x 405 pt
  const sl = deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  sl.getBackground().setSolidFill(HD_C.bg);

  const box = sl.insertShape(SlidesApp.ShapeType.ROUND_RECTANGLE, 24, 24, W - 48, H - 48);
  box.getFill().setSolidFill('#FFFFFF');
  box.getBorder().getLineFill().setSolidFill(HD_C.line);
  box.getBorder().setWeight(1.5);

  // 맨 위: 상품명
  const nm = d.name.length > 30 ? d.name.slice(0, 30).replace(/\s+\S*$/, '') + '…' : d.name;
  hdT_(sl, nm, 56, 40, W - 112, 40, 18, HD_C.gray, false);
  const ln = sl.insertLine(SlidesApp.LineCategory.STRAIGHT, 56, 88, W - 56, 88);
  ln.getLineFill().setSolidFill(HD_C.line); ln.setWeight(1.5);

  const pr = hdPair_(v);
  if (pr) hdCardCmp_(sl, pr, W, H);
  else hdCardOne_(sl, d, W, H);

  // 맨 아래: 기준 시각
  const at = hdParse_(v[HD.at - 1]);
  hdT_(sl, (at ? Utilities.formatDate(at, TZ, 'M/d HH:mm') + ' 기준 · ' : '') + '가격은 수시로 바뀌어요', 56, H - 62, W - 112, 28, 13, HD_C.gray, false);

  const slideId = sl.getObjectId(), deckId = deck.getId();
  deck.saveAndClose();
  return { url: hdThumb_(deckId, slideId), deck: deckId, slide: slideId };
}

// 한 줄 카드: 수량 + 할인율 · 가격 · 개당
function hdCardOne_(sl, d, W, H) {
  // 오른쪽 줄들(할인율 빨강 · 가격 크게+배송 · 개당 초록)을 카드 가운데(구분선~아랫줄 사이)에 세로로 모은다
  const items = [];
  if (d.off) items.push({ h: 38, draw: y => hdT_(sl, d.off + '% 할인', x, y, w, 38, 22, HD_C.red, true) });
  items.push({ h: 78, draw: y => {
    const pb = hdT_(sl, d.priceTxt + (d.ship ? '  ' + d.ship : ''), x, y, w, 78, 50, HD_C.ink, true);
    if (d.ship) pb.getText().getRange(d.priceTxt.length, d.priceTxt.length + 2 + d.ship.length).getTextStyle()
      .setFontSize(20).setBold(false).setForegroundColor(HD_C.sub);
  } });
  if (d.per) items.push({ h: 46, draw: y => hdT_(sl, d.unit + '당 ' + d.per.toLocaleString('ko-KR') + '원', x, y, w, 46, 26, HD_C.green, true) });
  const x = 290, w = W - x - 50;
  const top = 88, bottom = H - 76, mid = (top + bottom) / 2;
  const total = items.reduce((t, it) => t + it.h, 0);
  let y = mid - total / 2;
  items.forEach(it => { it.draw(y); y += it.h; });

  // 왼쪽: 고른 표시 + 수량 (가운데 높이)
  hdDot_(sl, 92, mid, 46, HD_C.blue); hdDot_(sl, 92, mid, 28, '#FFFFFF'); hdDot_(sl, 92, mid, 14, HD_C.blue);
  hdT_(sl, d.qty ? d.qty + d.unit : '특가', 126, mid - 34, 160, 68, d.qty >= 100 ? 32 : 40, HD_C.blue, true);
}

// 두 줄 비교 카드 (예시 형식): 위 = 적은 수량(회색), 아래 = 많은 수량(파랑, 고른 표시)
function hdCardCmp_(sl, pr, W, H) {
  const rows = [
    { o: pr.a, c: 150, on: false },
    { o: pr.b, c: 276, on: true }
  ];
  const mid = sl.insertLine(SlidesApp.LineCategory.STRAIGHT, 56, 213, W - 56, 213);
  mid.getLineFill().setSolidFill(HD_C.line); mid.setWeight(1.5);
  rows.forEach(r => {
    if (r.on) { hdDot_(sl, 92, r.c, 44, HD_C.blue); hdDot_(sl, 92, r.c, 26, '#FFFFFF'); hdDot_(sl, 92, r.c, 13, HD_C.blue); }
    else { hdDot_(sl, 92, r.c, 44, '#CFD3D8'); hdDot_(sl, 92, r.c, 38, '#FFFFFF'); }
    const qtxt = r.o.q + r.o.u;
    hdT_(sl, qtxt, 128, r.c - 30, 150, 60, qtxt.length > 4 ? 30 : 38, r.on ? HD_C.blue : HD_C.sub, r.on);
    hdT_(sl, r.o.p.toLocaleString('ko-KR') + '원', 290, r.c - 44, W - 340, 54, 40, HD_C.ink, true);
    const per = Math.round(r.o.p / r.o.q);
    let sub = r.o.u + '당 ' + per.toLocaleString('ko-KR') + '원';
    if (r.on && pr.cheaper > 0) sub += ' · ' + pr.cheaper + '% 더 싸요';
    hdT_(sl, sub, 290, r.c + 8, W - 340, 34, 20, r.on ? HD_C.green : HD_C.gray, r.on);
  });
}

// Q열 '수량비교' → { a: 적은 수량, b: 많은 수량, cheaper: 개당 몇 % 싼지 }
// 형식: "12개 11,840원 → 24개 13,530원" (맥북 캡처기가 쿠팡 옵션에서 읽어 적음). 역전 조건을 여기서 다시 확인한다.
function hdPair_(v) {
  const m = String(v[HD.cmp - 1] || '').match(/(\d+)\s*([가-힣A-Za-z]+)\s+([\d,]+)\s*원\s*(?:→|->)\s*(\d+)\s*([가-힣A-Za-z]+)\s+([\d,]+)\s*원/);
  if (!m) return null;
  const a = { q: +m[1], u: m[2], p: +m[3].replace(/,/g, '') }, b = { q: +m[4], u: m[5], p: +m[6].replace(/,/g, '') };
  if (!(b.q > a.q) || !a.p || !b.p) return null;
  // 2026-11-23: 용량 탭이 있는 상품(예: 코카콜라 300ml/1.5L)은 캡처기가 끝에 '(1.5L)'처럼 용량을 붙인다
  const size = (String(v[HD.cmp - 1]).match(/\(([^)]+)\)\s*$/) || [])[1] || '';
  const cheaper = Math.round((1 - (b.p / b.q) / (a.p / a.q)) * 100);
  // 많이 사는 쪽이 더 싸거나(역전), 개당 HD_MIN_CHEAPER % 이상 싸야 '가격 이상한' 딜
  if (!(b.p <= a.p || cheaper >= hdNum_('HD_MIN_CHEAPER', 30))) return null;
  return { a: a, b: b, cheaper: cheaper, size: size };
}

function hdThumb_(deckId, slideId) {
  const opt = { 'thumbnailProperties.mimeType': 'PNG', 'thumbnailProperties.thumbnailSize': 'LARGE' };
  if (typeof Slides !== 'undefined') return Slides.Presentations.Pages.getThumbnail(deckId, slideId, opt).contentUrl;
  const url = 'https://slides.googleapis.com/v1/presentations/' + deckId + '/pages/' + slideId + '/thumbnail?' +
    Object.keys(opt).map(k => k + '=' + opt[k]).join('&');
  const r = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true });
  if (r.getResponseCode() !== 200) throw new Error('썸네일 ' + r.getResponseCode() + ' — 서비스 +에서 Google Slides API 추가 필요할 수 있음: ' + r.getContentText().slice(0, 120));
  return JSON.parse(r.getContentText()).contentUrl;
}

function hdCardDrop_(card) {
  if (card.external) return;
  try { const s = SlidesApp.openById(card.deck).getSlideById(card.slide); if (s) s.remove(); } catch (e) {}
}

function hdT_(sl, txt, x, y, w, h, size, color, bold) {
  const t = sl.insertTextBox(txt, x, y, w, h);
  t.getText().getTextStyle().setFontFamily(HD_C.font).setFontSize(size).setForegroundColor(color).setBold(!!bold);
  t.setContentAlignment(SlidesApp.ContentAlignment.MIDDLE);
  return t;
}

function hdDot_(sl, cx, cy, size, color) {
  const e = sl.insertShape(SlidesApp.ShapeType.ELLIPSE, cx - size / 2, cy - size / 2, size, size);
  e.getFill().setSolidFill(color);
  e.getBorder().setTransparent();
  return e;
}

// 가격 카드만 시험 — 신규 첫 행으로 그려 주소를 로그에 (30분 동안 열림)
function hotdealTestCard() {
  const sh = hdSheet_();
  const rows = sh.getRange(2, 1, sh.getLastRow() - 1, HD.pname).getDisplayValues();
  const i = rows.findIndex(r => !hdHoldReason_(r));
  const c = hdCard_(rows[i], i + 2);
  console.log('행 ' + (i + 2) + ' 가격 카드: ' + c.url);
}

/* ───────── 스레드 ───────── */
function hdPostText_(text, replyTo, extra) {
  const t = prop_('TH_TOKEN');
  if (!replyTo) {   // 같은 글이 최근에 이미 올라가 있으면 그걸 쓴다 (중복 발행 방지)
    const dup = hdRecentSame_(text, t);
    if (dup) return dup;
  }
  const params = { media_type: 'TEXT', text: text, access_token: t };
  if (replyTo) params.reply_to_id = replyTo;
  Object.keys(extra || {}).forEach(k => { params[k] = extra[k]; });
  const c = api_('post', TH + '/me/threads', params).id;
  Utilities.sleep(params.media_type === 'IMAGE' ? 10000 : replyTo ? 4000 : 3000);
  const id = api_('post', TH + '/me/threads_publish', { creation_id: c, access_token: t }).id;
  let link = '';
  try { link = api_('get', TH + '/' + id, { fields: 'permalink', access_token: t }).permalink; } catch (e) {}
  return { id: id, link: link };
}

function hdRecentSame_(text, t) {
  try {
    // 본문이 짧아 다른 딜과 같을 수 있으니 30분 안에 올라간 같은 글만 같은 글로 본다
    const d = api_('get', TH + '/me/threads', { fields: 'id,text,permalink,timestamp', limit: 15, access_token: t }).data || [];
    const hit = d.filter(x => String(x.text || '').trim() === text.trim() && (Date.now() - new Date(x.timestamp).getTime()) < 30 * 60000)[0];
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
  const cur = r.getDisplayValues()[0];
  if (cur.some((x, i) => !x && HD_HEAD[i])) r.setValues([cur.map((x, i) => x || HD_HEAD[i])]);
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
