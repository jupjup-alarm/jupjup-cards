/**
 * 줍줍알람 — 유튜브 탭 자동 동기화 (2026-11-02)
 * 오싹알람 시트의 syncYouTube를 줍줍알람 '유튜브' 탭(A~Y)에 맞게 옮긴 것. 기존 스크립트와 이름이 겹치지 않게 yt 접두어를 씀.
 *
 * 하는 일 (1시간마다):
 *  1) 채널 업로드 목록(예약 공개 영상 포함)에서 E열 제목과 같은 영상을 찾아 L열에 쇼츠 링크를 넣음
 *     — 제목이 조금 달라도 앞부분이 같으면 찾고, 그래도 없으면 A열 날짜에 예약·공개된 영상이 하나뿐일 때 그걸로 짝지음
 *  2) K열 상태: 예약만 걸려 있으면 "예약완료", 공개되면 "게시됨" ("보류" 행은 건드리지 않음)
 *  3) 공개된 영상은 하루 한 번 공개일부터 7일치 성과를 채움: N 조회수 · O 평균 시청률(%) · Q 구독 증가 ·
 *     S 좋아요 · T 댓글 · U 공유 · V 평균 시청(초) · W 수치 기준일 (P 시청함 비율은 API가 없어 수동)
 *
 * 설치 (한 번만):
 *  1) 줍줍알람 시트 → 확장 프로그램 → Apps Script → 왼쪽 '파일 +' → 스크립트 → 이름 YouTubeSync → 이 파일 내용을 그대로 붙여넣기 → 저장
 *  2) 왼쪽 '서비스 +' → YouTube Data API v3 (식별자 YouTube) 추가, 다시 '서비스 +' → YouTube Analytics API (식별자 YouTubeAnalytics) 추가
 *  3) 위쪽 함수 목록에서 ytInstallTrigger 선택 → 실행 → 권한 허용
 *     (유튜브 채널 주인 구글 계정으로 허용해야 예약 영상·분석 수치까지 보임. 채널이 여러 개면 줍줍알람 채널을 고르기)
 *     → 바로 한 번 동기화하고, 이후 1시간마다 자동으로 돌아요.
 */
const YT_SHEET = '유튜브';
const YT_CHANNEL_ID = 'UCbIKC-joj_M279Tii7sLSiA';   // 줍줍알람 유튜브 채널 (youtube.com/channel/UCbIKC-joj_M279Tii7sLSiA)
const YT_TZ = 'Asia/Seoul';
const YT = { date: 1, time: 2, id: 3, kind: 4, title: 5, status: 11, link: 12, len: 13, views: 14, avgPct: 15,
  swipe: 16, subs: 17, hook: 18, likes: 19, comments: 20, shares: 21, avgSec: 22, asOf: 23 };

function ytInstallTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'ytSync')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('ytSync').timeBased().everyHours(1).create();
  ytSync();
}

function ytSync() {
  if (typeof YouTube === 'undefined')
    throw new Error("Apps Script '서비스 +'에서 YouTube Data API v3를 추가해 주세요");
  const sh = SpreadsheetApp.getActive().getSheetByName(YT_SHEET);
  if (!sh) throw new Error("'" + YT_SHEET + "' 탭이 없어요");
  const last = sh.getLastRow();
  if (last < 2) return;

  // 채널 주인 계정이면 예약 영상·분석 수치까지, 아니면 공개 영상·공개 수치만
  // (허용한 계정의 채널이 줍줍알람이 아니면 — 예: 오싹알람 채널로 허용 — 공개 수치만)
  let ch = YouTube.Channels.list('id,contentDetails', { mine: true });
  let publicOnly = false;
  if (!ch.items || !ch.items.length || ch.items[0].id !== YT_CHANNEL_ID) {
    if (ch.items && ch.items.length) console.warn('허용한 채널이 줍줍알람이 아님: ' + ch.items[0].id + ' → 공개 영상·공개 수치만');
    ch = YouTube.Channels.list('id,contentDetails', { id: YT_CHANNEL_ID });
    publicOnly = true;
  }
  if (!ch.items || !ch.items.length) throw new Error('유튜브 채널을 찾을 수 없어요 (' + YT_CHANNEL_ID + ')');
  const uploads = ch.items[0].contentDetails.relatedPlaylists.uploads;

  // 1) 업로드 목록
  const vids = [];
  let token;
  do {
    const r = YouTube.PlaylistItems.list('snippet,contentDetails', { playlistId: uploads, maxResults: 50, pageToken: token });
    (r.items || []).forEach(it => vids.push({ id: it.contentDetails.videoId, title: it.snippet.title }));
    token = r.nextPageToken;
  } while (token && vids.length < 300);
  const info = {};
  for (let i = 0; i < vids.length; i += 50) {
    const r = YouTube.Videos.list('status,snippet,statistics,contentDetails', { id: vids.slice(i, i + 50).map(v => v.id).join(',') });
    (r.items || []).forEach(v => { info[v.id] = v; });
  }
  const norm = t => String(t).replace(/#\S+/g, '').replace(/[\s,.?!…·|'"“”‘’~\-()\[\]]/g, '');
  const dayOf = v => {               // 예약 공개일(없으면 공개일) — 한국 날짜
    const st = (info[v.id] || {}).status || {};
    const t = st.publishAt || ((info[v.id] || {}).snippet || {}).publishedAt;
    return t ? Utilities.formatDate(new Date(t), YT_TZ, 'yyyy-MM-dd') : '';
  };

  const rows = sh.getRange(2, 1, last - 1, YT.asOf).getValues();
  const disp = sh.getRange(2, 1, last - 1, YT.asOf).getDisplayValues();
  const used = new Set();
  rows.forEach(r => { const m = String(r[YT.link - 1]).match(/(?:shorts\/|v=|youtu\.be\/)([\w-]{11})/); if (m) used.add(m[1]); });
  const today = Utilities.formatDate(new Date(), YT_TZ, 'yyyy-MM-dd');

  rows.forEach((r, i) => {
    const row = i + 2;
    const status = String(r[YT.status - 1]).trim();
    if (status === '보류' || !String(r[YT.id - 1]).trim()) return;

    // 2) 링크 찾기
    let m = String(r[YT.link - 1]).match(/(?:shorts\/|v=|youtu\.be\/)([\w-]{11})/);
    let vid = m ? m[1] : null;
    if (!vid) {
      const want = norm(r[YT.title - 1]);
      let hit = vids.find(v => !used.has(v.id) && want &&
        (norm(v.title) === want || norm(v.title).indexOf(want.slice(0, 20)) === 0));
      if (!hit) {                                    // 제목을 고쳐 올렸으면: 같은 날짜에 남은 영상이 하나뿐일 때만
        const d = disp[i][YT.date - 1];
        const same = vids.filter(v => !used.has(v.id) && dayOf(v) === d);
        const rowsSameDay = disp.filter((x, j) => x[YT.date - 1] === d && !String(rows[j][YT.link - 1]).trim()).length;
        if (same.length === 1 && rowsSameDay === 1) hit = same[0];
      }
      if (!hit) return;
      vid = hit.id;
      used.add(vid);
      sh.getRange(row, YT.link).setValue('https://www.youtube.com/shorts/' + vid);
    }
    const v = info[vid];
    if (!v) return;

    // 3) 상태
    const st = v.status || {};
    const live = st.privacyStatus === 'public';
    const state = live ? '게시됨' : (st.publishAt ? '예약완료' : status);
    if (state !== status) sh.getRange(row, YT.status).setValue(state);
    if (!live) return;

    // 4) 성과 — 하루 한 번만
    if (String(disp[i][YT.asOf - 1]).indexOf(today) === 0) return;
    if (publicOnly || typeof YouTubeAnalytics === 'undefined') {
      const s = v.statistics || {};
      sh.getRange(row, YT.views).setValue(Number(s.viewCount || 0));
      sh.getRange(row, YT.likes, 1, 2).setValues([[Number(s.likeCount || 0), Number(s.commentCount || 0)]]);
      sh.getRange(row, YT.asOf).setValue("'" + today + ' (공개 수치)');
      return;
    }
    const pub = new Date(v.snippet.publishedAt);
    const start = Utilities.formatDate(pub, YT_TZ, 'yyyy-MM-dd');
    const endD = new Date(pub.getTime() + 6 * 864e5);
    const end = Utilities.formatDate(endD < new Date() ? endD : new Date(), YT_TZ, 'yyyy-MM-dd');
    if (String(disp[i][YT.asOf - 1]) === end && endD < new Date(Date.now() - 2 * 864e5)) return;   // 7일치 확정 뒤엔 그만
    let rep;
    try {
      rep = YouTubeAnalytics.Reports.query({ ids: 'channel==MINE', startDate: start, endDate: end, filters: 'video==' + vid,
        metrics: 'views,averageViewPercentage,averageViewDuration,subscribersGained,likes,comments,shares' });
    } catch (e) { console.error('분석 실패 ' + vid + ': ' + e.message); return; }
    const row0 = (rep.rows && rep.rows[0]) || [];
    const val = k => { const ix = (rep.columnHeaders || []).findIndex(h => h.name === k); return ix >= 0 && row0.length ? row0[ix] : ''; };
    sh.getRange(row, YT.views).setValue(val('views'));
    sh.getRange(row, YT.avgPct).setValue(val('averageViewPercentage') === '' ? '' : Math.round(val('averageViewPercentage') * 10) / 10);
    sh.getRange(row, YT.subs).setValue(val('subscribersGained'));
    sh.getRange(row, YT.likes, 1, 5).setValues([[val('likes'), val('comments'), val('shares'), val('averageViewDuration'), "'" + end]]);
  });
}
