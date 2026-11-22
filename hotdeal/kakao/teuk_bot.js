/**
 * 특가반장 공기계 봇 (메신저봇R, 레거시 API)
 *
 * 맥이 올린 '보낼 목록'(GitHub 공개 파일)을 5분마다 읽어, 아직 안 보낸 메시지를
 * 오픈채팅방 "특가반장 초특가 알림!!"에 보낸다. 링크·문구는 맥이 이미 만들어 둔 것을 그대로 쓴다.
 * 보낸 결과는 맥이 방 대화를 읽어 시트(S·T·U)에 적는다.
 *
 * 지키는 것
 *  - 목록의 room이 ROOM과 정확히 같은 항목만, ROOM에만 보낸다. 다른 방으로는 보내지 않는다.
 *  - 만든 지 2시간 넘은 항목은 보내지 않는다(지난 딜).
 *  - 한 번에 최대 2건, 건 사이 10~20초, 정숙시간 23:30~07:30에는 보내지 않는다.
 *  - 같은 id는 한 번만 (보낸 목록을 휴대폰 파일에 기록).
 *  - Api.replyRoom이 false면(그 방 알림을 아직 못 받음) 이번 회차는 멈춘다.
 *    → 방장 계정(맥·원래 폰)으로 그 방에 아무 글이나 한 번 올리면 다시 보낼 수 있다.
 */

var QUEUE_URL = "https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/hotdeal/kakao/queue.json";
var ROOM = "특가반장 초특가 알림!!";
var SENT_PATH = "/sdcard/msgbot/teuk_sent.json";
var LOG_PATH = "/sdcard/msgbot/teuk_log.txt";
var POLL_MS = 5 * 60 * 1000;
var MAX_PER_ROUND = 2;
var MAX_AGE_MIN = 120;

var worker = null;

function log(s) {
  var line = new Date().toLocaleString() + " " + s;
  try { FileStream.append(LOG_PATH, line + "\n"); } catch (e) {}
  Log.i(line);
}

function loadSent() {
  try { return JSON.parse(FileStream.read(SENT_PATH)) || {}; } catch (e) { return {}; }
}

function saveSent(sent) {
  // 3일 지난 기록은 정리
  var cut = Date.now() - 3 * 24 * 3600 * 1000, out = {};
  for (var k in sent) if (sent[k] > cut) out[k] = sent[k];
  FileStream.write(SENT_PATH, JSON.stringify(out));
}

function inQuiet() {
  var d = new Date(), m = d.getHours() * 60 + d.getMinutes();
  return m >= 23 * 60 + 30 || m < 7 * 60 + 30;
}

function parseKst(s) {
  // "2026-11-22 17:38:14" (KST) → ms
  var p = s.split(/[- :]/);
  return Date.UTC(+p[0], +p[1] - 1, +p[2], +p[3] - 9, +p[4], +p[5]);
}

function round() {
  if (inQuiet()) return;
  var body;
  try {
    body = org.jsoup.Jsoup.connect(QUEUE_URL + "?t=" + Date.now())
      .ignoreContentType(true).timeout(15000).execute().body();
  } catch (e) {
    log("목록 받기 실패: " + e);
    return;
  }
  var q;
  try { q = JSON.parse(body); } catch (e) { log("목록 형식 오류"); return; }
  var sent = loadSent(), n = 0;
  var items = (q.items || []).slice().sort(function (a, b) { return a.created < b.created ? -1 : 1; });
  for (var i = 0; i < items.length && n < MAX_PER_ROUND; i++) {
    var it = items[i];
    if (sent[it.id]) continue;
    if (it.room !== ROOM) continue; // 다른 방 항목은 보내지 않음
    if ((Date.now() - parseKst(it.created)) / 60000 > MAX_AGE_MIN) { sent[it.id] = Date.now(); log("지남, 건너뜀 " + it.id); continue; }
    if (n > 0) java.lang.Thread.sleep(10000 + Math.floor(Math.random() * 10000));
    var ok = false;
    try { ok = Api.replyRoom(ROOM, it.message); } catch (e) { log("보내기 오류 " + it.id + ": " + e); }
    if (!ok) {
      log("보내기 실패(방 알림 세션 없음?) " + it.id + " — 방장 계정으로 방에 글 하나 올려 주세요");
      break;
    }
    sent[it.id] = Date.now();
    saveSent(sent);
    log("보냄 " + it.id);
    n++;
  }
  saveSent(sent);
}

function start() {
  if (worker) return;
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
}

// 다시 컴파일하거나 봇을 끌 때 이전 스레드를 멈춘다 (중복 전송 방지)
function onStartCompile() {
  if (worker) { worker.interrupt(); worker = null; }
}

// 알림이 올 때 호출된다. 이 방 알림을 받아야 replyRoom 세션이 생긴다.
function response(room, msg, sender, isGroupChat, replier, imageDB, packageName) {
  // 아무 답도 하지 않는다 (방에 엉뚱한 글이 올라가지 않게). 알림을 받는 것만으로 세션이 생긴다.
  if (room === ROOM) log("방 알림 받음 — 보내기 세션 준비됨");
}

start();
