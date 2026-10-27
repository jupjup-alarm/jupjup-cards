
// ===== 댓글 키워드 → 팔로우 확인 → 자료 DM (인스타) =====
// 사용자 결정 2026-10-27: 댓글에 키워드를 단 사람에게 팔로우 확인 메시지를 보내고,
// 팔로우가 확인된 사람에게만 'DM 자료'(공식 신청 링크 모음)를 보내요. 상품 링크는 보내지 않아요.
// 대상: '발행계획'에서 상태 '발행' + 채널 I·R + K열(DM 키워드)·AD열(DM 자료 메시지)이 있는 게시물, 게시 후 7일까지.
// 흐름: ① 키워드 댓글 → 비공개 답장(팔로우 확인 버튼) ② 상대가 버튼을 누르거나 답장하면 팔로우 여부 확인
//       ③ 팔로우 O → 자료 발송 / 팔로우 X → 다시 안내 (최대 3번). 기록은 'DM로그' 탭.
const DM_SHEET = 'DM로그';
const DM_COL_MSG = 30;                       // 발행계획 AD열: DM 자료 메시지
const DM_DAYS = 7;                           // 댓글 비공개 답장은 댓글 후 7일까지만 가능
const DM_WAIT_H = 23;                        // 상대가 답한 뒤 24시간 안에만 메시지를 보낼 수 있음
const IG_V = 'https://graph.instagram.com/v21.0';
const DM_BTN = '팔로우 확인';
const DM_HEAD = ['시각', '게시물 코드', '키워드', '댓글 ID', '아이디', '댓글', '상대 ID', '상태', '확인 횟수', '마지막 확인', '메모'];

function dmRun() { dmCore_(false); }
function dmRunNow() { notify_('댓글 DM 확인: ' + dmCore_(true)); }

function dmCore_(force) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return '다른 실행 중이라 건너뜀';
  try {
    const ss = SpreadsheetApp.getActive();
    const log = dmSheet_(ss);
    const token = PropertiesService.getScriptProperties().getProperty('IG_TOKEN');
    const myName = dmMyName_(token);
    const now = new Date();
    const n0 = log.getLastRow() - 1;
    const old = n0 > 0 ? log.getRange(2, 1, n0, DM_HEAD.length).getValues() : [];
    const seenC = {}, seenU = {};
    old.forEach(x => { seenC[String(x[3]).replace(/^'/, '')] = 1; seenU[String(x[4]) + '|' + x[1]] = 1; });

    // ① 새 키워드 댓글 → 팔로우 확인 메시지
    const plan = ss.getSheetByName(SHEET_NAME);
    const last = plan.getLastRow();
    const rows = last >= 2 ? plan.getRange(2, 1, last - 1, DM_COL_MSG).getValues() : [];
    const posts = {};
    const add = [];
    let calls = 0;
    for (const r of rows) {
      const ch = String(r[COL.channel - 1]).trim(), code = String(r[COL.code - 1]).trim();
      const kw = String(r[COL.dmKeyword - 1]).trim(), msg = String(r[DM_COL_MSG - 1]).trim();
      const mediaId = String(r[COL.postId - 1]).replace(/^'/, '').trim();
      if (!['I', 'R'].includes(ch) || !kw || !msg || !code) continue;
      posts[code] = { msg: msg, item: String(r[COL.item - 1]).trim() };
      if (String(r[COL.status - 1]).trim() !== '발행' || !mediaId) continue;
      const at = slotTime_(fmtDate_(r[COL.date - 1]), r[COL.slot - 1]);
      if (!at) continue;
      const ageH = (now - at) / 3600000;
      if (ageH < 0 || ageH > DM_DAYS * 24) continue;
      if (!force && ageH > 48 && now.getMinutes() % 30 >= 5) continue;   // 이틀 지난 글은 30분마다만
      if (calls >= 30) break;
      let list;
      try { list = dmComments_(mediaId, token); calls++; }
      catch (e) { console.log('댓글 읽기 실패 ' + code + ': ' + e.message); continue; }
      const kws = kw.split(/[,，\/]/).map(dmNorm_).filter(Boolean);
      for (const c of list) {
        const name = c.username || (c.from && c.from.username) || '';
        if (seenC[c.id] || (myName && name === myName)) continue;
        if (!kws.some(k => dmNorm_(c.text).includes(k))) continue;
        seenC[c.id] = 1;
        const row = [dmTime_(now), code, kw, "'" + c.id, name, String(c.text || '').slice(0, 200), '', '', 0, dmTime_(now), ''];
        if (seenU[name + '|' + code]) { row[7] = '중복'; add.push(row); continue; }
        seenU[name + '|' + code] = 1;
        try {
          const res = dmSendIntro_(c.id, posts[code], token);
          row[6] = "'" + res.recipient_id; row[7] = '확인대기';
        } catch (e) { row[7] = '실패'; row[10] = String(e.message).slice(0, 150); }
        add.push(row);
      }
    }
    if (add.length) log.getRange(log.getLastRow() + 1, 1, add.length, DM_HEAD.length).setValues(add);

    // ② 버튼을 누르거나 답장한 사람 → 팔로우 확인 → 자료 발송
    let sent = 0, waiting = 0;
    const n1 = log.getLastRow() - 1;
    const all = n1 > 0 ? log.getRange(2, 1, n1, DM_HEAD.length).getValues() : [];
    all.forEach((x, i) => {
      const st = String(x[7]);
      if (st !== '확인대기' && st !== '팔로우대기') return;
      const rowNo = i + 2, igsid = String(x[6]).replace(/^'/, '').trim();
      const started = dmParse_(x[0]);
      if (!igsid || !started) return;
      if (now - started > DM_DAYS * 86400000) { log.getRange(rowNo, 8).setValue('만료'); return; }
      waiting++;
      if (calls >= 60) return;
      try {
        const lastSeen = dmParse_(x[9]) || started;
        const msgs = dmUserMessages_(igsid, token); calls++;
        const fresh = msgs.filter(m => m.from && String(m.from.id) === igsid && dmIso_(m.created_time) > lastSeen);
        if (!fresh.length) return;
        const newest = new Date(Math.max.apply(null, fresh.map(m => dmIso_(m.created_time).getTime())));
        if (now - newest > DM_WAIT_H * 3600000) return;
        const post = posts[String(x[1])];
        if (!post) { log.getRange(rowNo, 8, 1, 4).setValues([['실패', x[8], dmTime_(newest), '발행계획 AD열(DM 자료)이 비어 있음']]); return; }
        let follows = null, memo = '';
        try { follows = dmFollows_(igsid, token); calls++; }
        catch (e) { memo = '팔로우 확인 실패(자료는 발송): ' + String(e.message).slice(0, 100); }
        const tries = Number(x[8] || 0) + 1;
        if (follows === false) {
          if (tries <= 3) dmSendText_(igsid, '아직 팔로우가 확인되지 않았어요 🥲\n@' + (myName || '2kids_note') +
            ' 팔로우하고 아래 버튼을 다시 눌러주세요!', token, true);
          log.getRange(rowNo, 8, 1, 4).setValues([[tries >= 3 ? '팔로우 안 함' : '팔로우대기', tries, dmTime_(newest), memo]]);
          return;
        }
        dmSendGuide_(igsid, post, token);
        sent++;
        log.getRange(rowNo, 8, 1, 4).setValues([['자료발송', tries, dmTime_(newest), memo]]);
      } catch (e) {
        log.getRange(rowNo, 11).setValue(String(e.message).slice(0, 150));
      }
    });
    return '새 키워드 댓글 ' + add.length + '건 · 자료 발송 ' + sent + '건 · 확인 대기 ' + waiting + '건';
  } finally { lock.releaseLock(); }
}

function dmComments_(mediaId, token) {
  const out = [];
  let url = IG_V + '/' + mediaId + '/comments?fields=id,text,username,timestamp,from&limit=50&access_token=' + token;
  for (let i = 0; i < 3 && url; i++) {
    const j = getJson_(url);
    (j.data || []).forEach(c => out.push(c));
    url = j.paging && j.paging.next;
  }
  return out;
}

function dmApi_(path, body, token) {
  return parse_(UrlFetchApp.fetch(IG_V + path, { method: 'post', contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token }, payload: JSON.stringify(body), muteHttpExceptions: true }));
}

function dmQuick_() { return [{ content_type: 'text', title: DM_BTN + ' 🙌', payload: 'FOLLOW_CHECK' }]; }

function dmTitle_(post) {
  const first = String(post.msg).split('\n')[0].replace(/^[^0-9A-Za-z가-힣]+/, '').trim();
  return (first || post.item + ' 신청 링크 모음').slice(0, 40);
}

function dmSendIntro_(commentId, post, token) {
  const t = '댓글 남겨주셔서 고마워요 🙌\n\n🎁 팔로우하고 아래 \'' + DM_BTN + '\' 버튼을 눌러주시면\n「' + dmTitle_(post) + '」 바로 보내드릴게요!';
  try {
    return dmApi_('/me/messages', { recipient: { comment_id: commentId }, message: { text: t, quick_replies: dmQuick_() } }, token);
  } catch (e) {
    if (!/quick|reply|param/i.test(e.message)) throw e;
    const t2 = '댓글 남겨주셔서 고마워요 🙌\n\n🎁 팔로우하고 이 대화창에 "확인"이라고 보내주시면\n「' + dmTitle_(post) + '」 바로 보내드릴게요!';
    return dmApi_('/me/messages', { recipient: { comment_id: commentId }, message: { text: t2 } }, token);
  }
}

function dmSendText_(igsid, text, token, withButton) {
  const message = { text: text };
  if (withButton) message.quick_replies = dmQuick_();
  return dmApi_('/me/messages', { recipient: { id: igsid }, message: message }, token);
}

function dmSendGuide_(igsid, post, token) {
  const full = '팔로우 확인됐어요! 고마워요 💛\n\n' + post.msg + '\n\n저장해두고 신청 기한 놓치지 마세요. 두배맘이 또 찾아올게요 🙌';
  const parts = [];
  let cur = '';
  full.split('\n').forEach(line => {
    if ((cur + '\n' + line).length > 950) { parts.push(cur); cur = line; }
    else cur = cur ? cur + '\n' + line : line;
  });
  if (cur) parts.push(cur);
  parts.forEach(p => dmSendText_(igsid, p, token, false));
}

function dmUserMessages_(igsid, token) {
  const f = encodeURIComponent('messages{id,created_time,from,message}');
  const j = getJson_(IG_V + '/me/conversations?platform=instagram&user_id=' + igsid + '&fields=' + f + '&access_token=' + token);
  const conv = (j.data || [])[0];
  return conv && conv.messages ? (conv.messages.data || []) : [];
}

function dmFollows_(igsid, token) {
  const j = getJson_(IG_V + '/' + igsid + '?fields=username,is_user_follow_business&access_token=' + token);
  if (typeof j.is_user_follow_business !== 'boolean') throw new Error('is_user_follow_business 없음');
  return j.is_user_follow_business;
}

function dmMyName_(token) {
  const cache = CacheService.getScriptCache();
  let n = cache.get('ig_username');
  if (!n) {
    try { n = getJson_(IG_BASE + '/me?fields=username&access_token=' + token).username; cache.put('ig_username', n, 21600); }
    catch (e) { n = ''; }
  }
  return n;
}

function dmSheet_(ss) {
  let sh = ss.getSheetByName(DM_SHEET);
  if (!sh) {
    sh = ss.insertSheet(DM_SHEET);
    sh.getRange(1, 1, 1, DM_HEAD.length).setValues([DM_HEAD]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

function dmNorm_(s) { return String(s || '').replace(/\s+/g, '').toLowerCase(); }
function dmTime_(d) { return Utilities.formatDate(d, 'Asia/Seoul', 'yyyy-MM-dd HH:mm:ss'); }
function dmIso_(s) { return new Date(String(s).replace(/([+-]\d\d)(\d\d)$/, '$1:$2')); }
function dmParse_(v) {
  if (v instanceof Date) return v;
  const m = String(v || '').trim().match(/^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d)(?::(\d\d))?/);
  return m ? new Date(m[1] + '-' + m[2] + '-' + m[3] + 'T' + m[4] + ':' + m[5] + ':' + (m[6] || '00') + '+09:00') : null;
}

function dmOn() {
  dmOff_();
  ScriptApp.newTrigger('dmRun').timeBased().everyMinutes(5).create();
  notify_('댓글 DM 자동 확인을 켰어요 (5분마다).');
}
function dmOff_() { ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'dmRun') ScriptApp.deleteTrigger(t); }); }
function dmOff() { dmOff_(); notify_('댓글 DM 자동 확인을 껐어요.'); }

// 권한 확인용 (메시지를 보내지 않음): 대화 목록·댓글·사용자 정보를 읽을 수 있는지
function dmTest() {
  const token = PropertiesService.getScriptProperties().getProperty('IG_TOKEN');
  const out = [];
  try { const j = getJson_(IG_V + '/me/conversations?platform=instagram&limit=1&access_token=' + token); out.push('대화 읽기 OK (' + (j.data || []).length + '개)'); }
  catch (e) { out.push('대화 읽기 실패: ' + e.message); }
  try {
    const m = getJson_(IG_V + '/me/media?fields=id,comments_count&limit=5&access_token=' + token);
    const withC = (m.data || []).filter(x => x.comments_count > 0)[0] || (m.data || [])[0];
    const c = dmComments_(withC.id, token);
    out.push('댓글 읽기 OK (최근 글 댓글 ' + c.length + '개)');
  } catch (e) { out.push('댓글 읽기 실패: ' + e.message); }
  console.log(out.join('\n'));
  notify_(out.join('\n'));
}
