/* 특가반장 공기계 봇 v9 (메신저봇R, 레거시 API) — v9: 두 번째 말풍선을 방 이름 보내기로 */
/* 맥이 올린 보낼 목록을 1분마다 읽어, 아직 안 보낸 메시지를 오픈채팅방에 보낸다. 본문 뒤 3~6초 후 두 번째 말풍선(followup)도 보낸다. */
/* 목록 받기: 평소는 raw 주소(?t=시각). GitHub API(raw 헤더)는 두 경우만 - 방 알림이 와서 바로 확인할 때, raw 목록이 5분 넘게 그대로일 때(5분에 한 번까지). API가 403·429면 raw로 돌아간다. */
/* 방 알림마다 3초 뒤 확인한다(30초 안에 확인했으면 건너뜀). 회차마다 목록 건수를 로그에 남긴다. */
/* 실제로 보낸 뒤 hotdeal/kakao/sent/항목id.json 영수증을 GitHub에 올린다. 맥은 영수증을 보고서야 시트 S열을 전송완료로 쓴다. */
/* 영수증에는 /sdcard/msgbot/teuk_token.txt 의 GitHub 토큰(이 저장소 Contents 읽기·쓰기만)이 필요하다. 토큰은 이 스크립트에 넣지 않는다. */
/* 붙여넣을 때 줄바꿈이 사라져도 돌도록: 줄 주석을 쓰지 않고, 문장마다 세미콜론을 붙인다. */
/* 지키는 것: 이 방에만 · 만든 지 2시간 넘은 항목은 안 보냄 · 한 번에 2건, 10~20초 간격 · 23:30~07:30 정숙 · 같은 항목 한 번만. */

var API_BASE = "https://api.github.com/repos/jupjup-alarm/jupjup-cards/contents/";
var QUEUE_API = API_BASE + "hotdeal/kakao/queue.json?ref=main";
var QUEUE_RAW = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/hotdeal/kakao/queue.json";
var ROOM = "특가반장 초특가 알림!!";
/* 카톡 알림에는 이 방이 '특가반장', 단체방=false로 찍힌다(2026-11-22 확인). 이름이 정확히 같을 때만 인정한다. */
var ROOM_NAMES = ["특가반장 초특가 알림!!", "특가반장"];
var SENT_PATH = "/sdcard/msgbot/teuk_sent.json";
var LOG_PATH = "/sdcard/msgbot/teuk_log.txt";
var TOKEN_PATH = "/sdcard/msgbot/teuk_token.txt";
var POLL_MS = 60 * 1000;
var STALE_MS = 5 * 60 * 1000;
var MAX_PER_ROUND = 2;
var MAX_AGE_MIN = 120;
var worker = null;
var savedReplier = null;
var lastCheck = 0;
var lastRawBody = "";
var lastRawChange = Date.now();
var lastApi = 0;
var roundLock = new java.util.concurrent.locks.ReentrantLock();

function norm(t) { return String(t || "").replace(/\s+/g, ""); };
function isOurRoom(name) { for (var i = 0; i < ROOM_NAMES.length; i++) { if (norm(name) === norm(ROOM_NAMES[i])) { return true; } } return false; };

function log(s) {
  var line = new Date().toLocaleString() + " " + s;
  try {
    var f = new java.io.File(LOG_PATH);
    if (f.exists() && f.length() > 1024 * 1024) { FileStream.write(LOG_PATH, ""); }
    FileStream.append(LOG_PATH, line + "\n");
  } catch (e) { }
  try { Log.i(line); } catch (e) { }
};

function loadSent() {
  try { return JSON.parse(FileStream.read(SENT_PATH)) || {}; } catch (e) { return {}; }
};

function saveSent(sent) {
  var cut = Date.now() - 3 * 24 * 3600 * 1000;
  var out = {};
  for (var k in sent) { if (sent[k] > cut) { out[k] = sent[k]; } }
  FileStream.write(SENT_PATH, JSON.stringify(out));
};

function token() {
  try { var t = String(FileStream.read(TOKEN_PATH) || "").replace(/\s+/g, ""); return t.length > 10 ? t : ""; } catch (e) { return ""; }
};

function inQuiet() {
  var d = new Date();
  var m = d.getHours() * 60 + d.getMinutes();
  return m >= 23 * 60 + 30 || m < 7 * 60 + 30;
};

function parseKst(s) {
  var p = s.split(/[- :]/);
  return Date.UTC(+p[0], +p[1] - 1, +p[2], +p[3] - 9, +p[4], +p[5]);
};

function kstNow() {
  var f = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
  f.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Seoul"));
  return String(f.format(new java.util.Date()));
};

function fetchRaw() {
  var body = String(org.jsoup.Jsoup.connect(QUEUE_RAW + "?t=" + Date.now()).ignoreContentType(true).timeout(15000).execute().body());
  if (body !== lastRawBody) { lastRawBody = body; lastRawChange = Date.now(); }
  return body;
};

function fetchApi() {
  lastApi = Date.now();
  var c = org.jsoup.Jsoup.connect(QUEUE_API).ignoreContentType(true).ignoreHttpErrors(true).timeout(15000)
    .header("Accept", "application/vnd.github.raw").header("User-Agent", "teuk-bot");
  var tk = token();
  if (tk) { c = c.header("Authorization", "Bearer " + tk); }
  var r = c.execute();
  var code = r.statusCode();
  if (code === 200) { return String(r.body()); }
  if (code === 403 || code === 429) { log("목록 API 거절 HTTP " + code + " - raw로 받음"); }
  else { log("목록 API HTTP " + code + " - raw로 받음"); }
  return null;
};

/* why: "알림" 이면 API로. 평소엔 raw, raw가 5분 넘게 그대로면 API(5분에 한 번까지). */
function fetchQueue(why) {
  var useApi = (why === "알림");
  if (!useApi && Date.now() - lastRawChange > STALE_MS && Date.now() - lastApi > STALE_MS) { useApi = true; why = "raw 5분 넘게 그대로"; }
  if (useApi) {
    try { var b = fetchApi(); if (b !== null) { return { body: b, src: "API(" + why + ")" }; } }
    catch (e) { log("목록 API 오류: " + e + " - raw로 받음"); }
  }
  return { body: fetchRaw(), src: "raw" };
};

function putReceipt(id, status) {
  var tk = token();
  if (!tk) { log("영수증 못 올림(토큰 없음) " + id + " - " + TOKEN_PATH + " 확인"); return; }
  try {
    var body = JSON.stringify({ id: id, status: status, at: kstNow() });
    var b64 = String(android.util.Base64.encodeToString(new java.lang.String(body).getBytes("UTF-8"), android.util.Base64.NO_WRAP));
    var payload = JSON.stringify({ message: "hotdeal: kakao sent " + id, content: b64, branch: "main" });
    var r = org.jsoup.Jsoup.connect(API_BASE + "hotdeal/kakao/sent/" + id + ".json").ignoreContentType(true).ignoreHttpErrors(true)
      .timeout(20000).method(org.jsoup.Connection.Method.PUT).requestBody(payload)
      .header("Accept", "application/vnd.github+json").header("Content-Type", "application/json")
      .header("User-Agent", "teuk-bot").header("Authorization", "Bearer " + tk).execute();
    var code = r.statusCode();
    if (code === 201 || code === 200 || code === 422) { log("영수증 올림 " + id + " (" + status + ")"); }
    else { log("영수증 실패 " + id + " HTTP " + code); }
  } catch (e) { log("영수증 오류 " + id + ": " + e); }
};

/* 두 번째 말풍선 (v9, 2026-11-23): 알림 답장은 한 번 쓰면 끊길 수 있어 방 이름 보내기(Api.replyRoom)를 먼저, 안 되면 답장으로 한 번 더. 결과를 로그에 남긴다. */
function sendFollowup(it) {
  var ok = false, how = "";
  try { ok = Api.replyRoom(ROOM, it.followup, true) === true; how = "replyRoom"; } catch (e) { how = "replyRoom 오류 " + e; }
  if (!ok) {
    try { java.lang.Thread.sleep(1500); savedReplier.reply(it.followup); ok = true; how += " → reply"; } catch (e) { how += " → reply 오류 " + e; }
  }
  log((ok ? "두 번째 말풍선 보냄 " : "두 번째 말풍선 실패 ") + it.id + " (" + how + ")");
  return ok;
};

function round(why) {
  if (inQuiet()) { return; }
  if (!roundLock.tryLock()) { return; }
  try {
    lastCheck = Date.now();
    var got;
    try { got = fetchQueue(why); } catch (e) { log("목록 받기 실패: " + e); return; }
    var q;
    try { q = JSON.parse(got.body); } catch (e) { log("목록 형식 오류 (" + got.src + ")"); return; }
    var sent = loadSent();
    var all = (q.items || []).slice().sort(function (a, b) { return a.created < b.created ? -1 : 1; });
    var todo = [];
    for (var j = 0; j < all.length; j++) {
      var x = all[j];
      if (sent[x.id] || norm(x.room) !== norm(ROOM)) { continue; }
      if ((Date.now() - parseKst(x.created)) / 60000 > MAX_AGE_MIN) { sent[x.id] = Date.now(); log("지남, 건너뜀 " + x.id); putReceipt(x.id, "expired"); continue; }
      todo.push(x);
    }
    saveSent(sent);
    log("목록 " + all.length + "건, 보낼 것 " + todo.length + "건 · " + got.src + (savedReplier ? "" : " · 방 알림 세션 없음"));
    var n = 0;
    for (var i = 0; i < todo.length && n < MAX_PER_ROUND; i++) {
      var it = todo[i];
      if (n > 0) { java.lang.Thread.sleep(10000 + Math.floor(Math.random() * 10000)); }
      var ok = false;
      try {
        if (savedReplier) { savedReplier.reply(it.message); ok = true; }
      } catch (e) { log("보내기 오류 " + it.id + ": " + e); ok = false; }
      if (!ok) { log("보내기 실패(방 알림 세션 없음?) " + it.id + " - 방장 계정으로 방에 글 하나 올려 주세요"); break; }
      sent[it.id] = Date.now();
      saveSent(sent);
      log("보냄 " + it.id);
      if (it.followup) {
        java.lang.Thread.sleep(3000 + Math.floor(Math.random() * 3000));
        sendFollowup(it);
      }
      putReceipt(it.id, "sent");
      n++;
    }
  } finally {
    roundLock.unlock();
  }
};

function start() {
  if (worker) { return; }
  worker = new java.lang.Thread(new java.lang.Runnable({
    run: function () {
      log("봇 시작 v9 (" + ROOM + ")" + (token() ? "" : " - 토큰 없음: 영수증을 못 올림"));
      while (!java.lang.Thread.currentThread().isInterrupted()) {
        try { round("주기"); } catch (e) { log("회차 오류: " + e); }
        try { java.lang.Thread.sleep(POLL_MS); } catch (e) { break; }
      }
      log("봇 멈춤");
    }
  }));
  worker.start();
};

/* 다시 컴파일하거나 봇을 끌 때 이전 스레드를 멈춘다 (중복 전송 방지) */
function onStartCompile() {
  if (worker) { worker.interrupt(); worker = null; }
};

/* 이 방 알림이 올 때마다 답장 객체를 기억하고, 3초 뒤 API로 한 번 확인한다(30초 안에 확인했으면 건너뜀). 방에는 아무 답도 하지 않는다. */
function response(room, msg, sender, isGroupChat, replier, imageDB, packageName) {
  if (packageName == "com.kakao.talk" && isOurRoom(room)) {
    var first = (savedReplier === null);
    savedReplier = replier;
    if (first) { log("방 알림 받음 - 보내기 세션 준비됨"); }
    if (Date.now() - lastCheck > 30000) {
      new java.lang.Thread(new java.lang.Runnable({ run: function () { try { java.lang.Thread.sleep(3000); if (Date.now() - lastCheck > 30000) { round("알림"); } } catch (e) { log("바로 회차 오류: " + e); } } })).start();
    }
  }
};

start();
