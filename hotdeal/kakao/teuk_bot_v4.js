/* 특가반장 공기계 봇 (메신저봇R, 레거시 API) */
/* 맥이 올린 보낼 목록(GitHub 공개 파일)을 5분마다 읽어, 아직 안 보낸 메시지를 오픈채팅방에 보낸다. */
/* 붙여넣을 때 줄바꿈이 사라져도 돌도록: // 주석을 쓰지 않고, 문장마다 세미콜론을 붙인다. */
/* 지키는 것: 이 방에만 · 만든 지 2시간 넘은 항목은 안 보냄 · 한 번에 2건, 10~20초 간격 · 23:30~07:30 정숙 · 같은 항목 한 번만. */
/* 이 방(단체방) 알림을 한 번 받아 답장 객체를 얻기 전에는 보내지 않는다. 방장 계정으로 방에 글 하나를 올리면 된다. 1:1 대화로는 절대 보내지 않는다. */

var QUEUE_URL = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/hotdeal/kakao/queue.json";
var ROOM = "특가반장 초특가 알림!!";
/* 카톡 알림에는 이 방이 '특가반장'으로 찍힌다(2026-11-22 확인). 방 제목과 알림 이름을 모두 인정하되, 단체방 알림일 때만. */
var ROOM_NAMES = ["특가반장 초특가 알림!!", "특가반장"];
var SENT_PATH = "/sdcard/msgbot/teuk_sent.json";
var LOG_PATH = "/sdcard/msgbot/teuk_log.txt";
var POLL_MS = 5 * 60 * 1000;
var MAX_PER_ROUND = 2;
var MAX_AGE_MIN = 120;
var worker = null;
var savedReplier = null;
function norm(t) { return String(t || "").replace(/\s+/g, ""); };
function isOurRoom(name) { for (var i = 0; i < ROOM_NAMES.length; i++) { if (norm(name) === norm(ROOM_NAMES[i])) { return true; } } return false; };

function log(s) {
  var line = new Date().toLocaleString() + " " + s;
  try { FileStream.append(LOG_PATH, line + "\n"); } catch (e) { }
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

function inQuiet() {
  var d = new Date();
  var m = d.getHours() * 60 + d.getMinutes();
  return m >= 23 * 60 + 30 || m < 7 * 60 + 30;
};

function parseKst(s) {
  var p = s.split(/[- :]/);
  return Date.UTC(+p[0], +p[1] - 1, +p[2], +p[3] - 9, +p[4], +p[5]);
};

function round() {
  if (inQuiet()) { return; }
  var body;
  try {
    body = org.jsoup.Jsoup.connect(QUEUE_URL + "?t=" + Date.now()).ignoreContentType(true).timeout(15000).execute().body();
  } catch (e) {
    log("목록 받기 실패: " + e);
    return;
  }
  var q;
  try { q = JSON.parse(String(body)); } catch (e) { log("목록 형식 오류"); return; }
  var sent = loadSent();
  var n = 0;
  var items = (q.items || []).slice().sort(function (a, b) { return a.created < b.created ? -1 : 1; });
  for (var i = 0; i < items.length && n < MAX_PER_ROUND; i++) {
    var it = items[i];
    if (sent[it.id]) { continue; }
    if (norm(it.room) !== norm(ROOM)) { continue; }
    if ((Date.now() - parseKst(it.created)) / 60000 > MAX_AGE_MIN) { sent[it.id] = Date.now(); log("지남, 건너뜀 " + it.id); continue; }
    if (n > 0) { java.lang.Thread.sleep(10000 + Math.floor(Math.random() * 10000)); }
    var ok = false;
    try {
      if (savedReplier) { savedReplier.reply(it.message); ok = true; }
      else { log("아직 이 방 알림을 못 받음 - 방장 계정으로 방에 글 하나 올려 주세요"); ok = false; }
    } catch (e) { log("보내기 오류 " + it.id + ": " + e); ok = false; }
    if (!ok) { log("보내기 실패(방 알림 세션 없음?) " + it.id + " - 방장 계정으로 방에 글 하나 올려 주세요"); break; }
    sent[it.id] = Date.now();
    saveSent(sent);
    log("보냄 " + it.id);
    n++;
  }
  saveSent(sent);
};

function start() {
  if (worker) { return; }
  worker = new java.lang.Thread(new java.lang.Runnable({
    run: function () {
      log("봇 시작 (" + ROOM + ")");
      while (!java.lang.Thread.currentThread().isInterrupted()) {
        try { round(); } catch (e) { log("회차 오류: " + e); }
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

/* 알림이 올 때 호출된다. 이 방(공백 빼고 같은 이름) 알림의 답장 객체를 기억해 두고 그걸로 보낸다. 방에는 아무 답도 하지 않는다. */
function response(room, msg, sender, isGroupChat, replier, imageDB, packageName) {
  log("알림: 방=[" + room + "] 단체방=" + isGroupChat + " 앱=" + packageName);
  if (packageName == "com.kakao.talk" && isGroupChat && isOurRoom(room)) {
    var first = (savedReplier === null);
    savedReplier = replier;
    log("방 알림 받음 - 보내기 세션 준비됨");
    if (first) {
      new java.lang.Thread(new java.lang.Runnable({ run: function () { try { java.lang.Thread.sleep(3000); round(); } catch (e) { log("바로 회차 오류: " + e); } } })).start();
    }
  }
};

start();
