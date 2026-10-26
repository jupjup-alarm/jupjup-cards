
// ===== 성과 자동 수집 (스레드·인스타 인사이트 → '성과' 탭, 팔로워 → '계정추이' 탭) =====
// 매시간 실행: 게시 후 24시간·7일이 지난 글은 그 시점 값을 한 번 기록하고,
// 매일 04시대에는 최근 8일 글의 '최신' 값과 계정 팔로워 수를 갱신해요 (05:13 성과분석 담당이 읽음).
const PERF_SHEET = '성과';
const FOLLOW_SHEET = '계정추이';
const PERF_COL = { code: 1, point: 2, views: 8, replies: 9, reposts: 10, recorded: 17,
  likes: 18, shares: 19, reach: 20, watch: 21, age: 22, mediaId: 23, memo: 24 };

function collectInsights() { collectInsightsCore_(false); }
function collectInsightsNow() { collectInsightsCore_(true); notify_('성과 수집을 끝냈어요. 성과·계정추이 탭을 확인하세요.'); }

function collectInsightsCore_(force) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;
  try {
    const ss = SpreadsheetApp.getActive();
    const plan = ss.getSheetByName(SHEET_NAME);
    const perf = ss.getSheetByName(PERF_SHEET);
    const now = new Date();
    const daily = force || Utilities.formatDate(now, 'Asia/Seoul', 'H') === '4';
    const last = plan.getLastRow();
    if (last >= 2) {
      const rows = plan.getRange(2, 1, last - 1, COL.postLink).getValues();
      const idx = perfIndex_(perf);
      let calls = 0;
      for (const r of rows) {
        if (calls >= 80) break;
        const id = String(r[COL.postId - 1]).replace(/^'/, '').trim();
        const code = String(r[COL.code - 1]).trim();
        if (String(r[COL.status - 1]).trim() !== '발행' || !id || !code) continue;
        const at = slotTime_(fmtDate_(r[COL.date - 1]), r[COL.slot - 1]);
        if (!at) continue;
        const ageH = (now - at) / 3600000;
        if (ageH < 1 || ageH > 24 * 8) continue;
        const points = [];
        if (ageH >= 24 && !idx[code + '|24h']) points.push('24h');
        if (ageH >= 24 * 7 && !idx[code + '|7d']) points.push('7d');
        if (daily) points.push('최신');
        if (!points.length) continue;
        const ch = String(r[COL.channel - 1]).trim();
        let m;
        try { m = ch === 'T' ? threadsInsights_(id) : igInsights_(id, ch === 'R'); }
        catch (e) { m = { memo: '수집 실패: ' + String(e.message).slice(0, 120) }; }
        calls++;
        points.forEach(pt => writePerf_(perf, idx, code, pt, m, ageH, id, now));
      }
    }
    if (daily) recordFollowers_(ss, now);
  } finally { lock.releaseLock(); }
}

function perfIndex_(perf) {
  const n = Math.max(perf.getLastRow() - 1, 1);
  const v = perf.getRange(2, 1, n, 2).getValues();
  const idx = { _next: 2 };
  v.forEach((x, i) => {
    const code = String(x[0]).trim();
    if (!code) return;
    idx[code + '|' + String(x[1]).trim()] = i + 2;
    idx._next = i + 3;
  });
  return idx;
}

function writePerf_(perf, idx, code, point, m, ageH, id, now) {
  const key = code + '|' + point;
  let row = idx[key];
  if (!row) { row = idx._next; idx._next++; idx[key] = row; perf.getRange(row, 1, 1, 2).setValues([[code, point]]); }
  const num = x => (x === undefined || x === null || x === '') ? '' : Number(x);
  perf.getRange(row, PERF_COL.views, 1, 3).setValues([[num(m.views), num(m.replies), num(m.reposts)]]);
  perf.getRange(row, PERF_COL.recorded).setValue(Utilities.formatDate(now, 'Asia/Seoul', 'yyyy-MM-dd HH:mm'));
  perf.getRange(row, PERF_COL.likes, 1, 7).setValues([[num(m.likes), num(m.shares), num(m.reach), num(m.watch),
    Math.round(ageH), "'" + id, m.memo || '']]);
}

function insightValue_(item) {
  if (item.total_value && item.total_value.value !== undefined) return Number(item.total_value.value);
  const vals = item.values || [];
  return vals.length ? Number(vals[vals.length - 1].value) : 0;
}

function threadsInsights_(id) {
  const c = threadsCreds_();
  const j = getJson_(THREADS_BASE + '/' + id + '/insights?metric=views,likes,replies,reposts,quotes,shares&access_token=' + c.token);
  const o = {};
  (j.data || []).forEach(it => { o[it.name] = insightValue_(it); });
  return { views: o.views, likes: o.likes, replies: o.replies, reposts: (o.reposts || 0) + (o.quotes || 0), shares: o.shares };
}

function igInsights_(id, isReel) {
  const token = PropertiesService.getScriptProperties().getProperty('IG_TOKEN');
  const sets = isReel
    ? ['views,reach,likes,comments,saved,shares,ig_reels_avg_watch_time', 'reach,likes,comments,saved,shares']
    : ['views,reach,likes,comments,saved,shares', 'reach,likes,comments,saved,shares'];
  let j, err;
  for (const s of sets) {
    try { j = getJson_(IG_BASE + '/' + id + '/insights?metric=' + s + '&access_token=' + token); break; }
    catch (e) { err = e; }
  }
  if (!j) throw err;
  const o = {};
  (j.data || []).forEach(it => { o[it.name] = insightValue_(it); });
  return { views: o.views !== undefined ? o.views : o.reach, reach: o.reach, likes: o.likes, replies: o.comments,
    reposts: o.saved, shares: o.shares,
    watch: o.ig_reels_avg_watch_time !== undefined ? Math.round(o.ig_reels_avg_watch_time / 100) / 10 : '',
    memo: o.views === undefined ? '조회수 대신 도달' : '' };
}

function recordFollowers_(ss, now) {
  const sh = ss.getSheetByName(FOLLOW_SHEET);
  if (!sh) return;
  const p = PropertiesService.getScriptProperties();
  const today = Utilities.formatDate(now, 'Asia/Seoul', 'yyyy-MM-dd');
  let th = '', ig = '', thViews = '';
  try {
    const j = getJson_(THREADS_BASE + '/' + p.getProperty('THREADS_USER_ID') + '/threads_insights?metric=followers_count&access_token=' + p.getProperty('THREADS_TOKEN'));
    (j.data || []).forEach(it => { if (it.name === 'followers_count') th = insightValue_(it); });
  } catch (e) { th = '실패: ' + String(e.message).slice(0, 60); }
  try {
    const until = Math.floor(now.getTime() / 1000), since = until - 86400;
    const j = getJson_(THREADS_BASE + '/' + p.getProperty('THREADS_USER_ID') + '/threads_insights?metric=views&since=' + since + '&until=' + until + '&access_token=' + p.getProperty('THREADS_TOKEN'));
    (j.data || []).forEach(it => { if (it.name === 'views') thViews = (it.values || []).reduce((a, v) => a + Number(v.value || 0), 0) || insightValue_(it); });
  } catch (e) { thViews = ''; }
  try {
    const j = getJson_(IG_BASE + '/' + p.getProperty('IG_USER_ID') + '?fields=followers_count&access_token=' + p.getProperty('IG_TOKEN'));
    ig = j.followers_count;
  } catch (e) { ig = '실패: ' + String(e.message).slice(0, 60); }
  const last = sh.getLastRow();
  let row = last + 1, prev = null;
  if (last >= 2) {
    const v = sh.getRange(2, 1, last - 1, 3).getValues();
    v.forEach((x, i) => { if (fmtDate_(x[0]) === today) row = i + 2; });
    const pi = (row <= last ? row - 3 : last - 2);
    if (pi >= 0 && pi < v.length) prev = v[pi];
  }
  const diff = (a, b) => (typeof a === 'number' && b !== null && typeof b === 'number') ? a - b : '';
  sh.getRange(row, 1, 1, 7).setValues([[today, th, ig, diff(th, prev && prev[1]), diff(ig, prev && prev[2]), thViews,
    Utilities.formatDate(now, 'Asia/Seoul', 'MM/dd HH:mm')]]);
}

function installInsightsTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'collectInsights') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('collectInsights').timeBased().everyHours(1).create();
  notify_('성과 자동 수집을 켰어요 (매시간, 매일 04시대에 최신값·팔로워 기록).');
}

// '분석' 탭을 지금 쓰는 소재·훅 이름으로 다시 만들기 (한 번 실행)
function setupAnalysisTab() {
  const sh = SpreadsheetApp.getActive().getSheetByName('분석');
  sh.clear();
  const out = [['성과 비교 (집계 시점별 중앙값)'],
    ["B3 칸의 집계 시점(24h·7d·최신)을 기준으로 비교해요. 그룹당 게시물이 '설정' 탭의 '비교 최소 게시물 수' 미만이면 '표본 부족'. 평균 대신 중앙값이라 바이럴 글 하나에 흔들리지 않아요."],
    ['기준 집계 시점', '24h']];
  const groups = [['소재', 'E', ['텍스트', '카드뉴스', '숏츠', '실사']],
    ['훅', 'F', ['돈숫자', '기한', '몰라서손해', '쌍둥이2배', '부모님', '퀴즈', '체크리스트']],
    ['채널', 'C', ['T', 'I', 'R']], ['링크플랫폼', 'G', ['없음', '토스', '쿠팡']]];
  const hdr = ['구분', '값', '게시물 수', '조회수 중앙값', '참여율 중앙값', '1천당 클릭 중앙값', '수익 합계(원)', '판단'];
  groups.forEach(([g, col, vals]) => {
    out.push([]); out.push(hdr);
    vals.forEach(v => {
      const r = out.length + 1, c = "'성과'!" + col + '2:' + col;
      const med = x => '=IFERROR(MEDIAN(FILTER(\'성과\'!' + x + '2:' + x + ',' + c + '=$B' + r + ",'성과'!B2:B=$B$3,ISNUMBER('성과'!" + x + '2:' + x + '))),"")';
      out.push([g, v, '=COUNTIFS(' + c + ',$B' + r + ",'성과'!B2:B,$B$3)", med('H'), med('Y'), med('O'),
        '=SUMIFS(\'성과\'!N2:N,' + c + ',$B' + r + ",'성과'!B2:B,$B$3)",
        '=IF(C' + r + '=0,"데이터 없음",IF(C' + r + "<'설정'!$B$9,\"표본 부족\",\"비교 가능\"))"]);
    });
  });
  const grid = out.map(r => { const a = r.slice(); while (a.length < 8) a.push(''); return a; });
  sh.getRange(1, 1, grid.length, 8).setValues(grid);
  sh.getRange('A1').setFontWeight('bold').setFontSize(13);
  sh.getRange('B3').setBackground('#FFF2CC');
}
