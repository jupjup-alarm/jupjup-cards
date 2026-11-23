// 줍줍알람 쇼츠 고정 댓글 (ego lite, Claude 없이) — 2026-11-23
// 실행: ego-browser nodejs < /Users/den/줍줍알람/jupjup-cards/tools/yt_comment.mjs   (보통 tools/yt_daily.sh가 부름)
// 입력: ~/줍줍알람/유튜브/comment_job.json  { id, url, comment }
// 하는 일: 댓글 쓰는 이름이 '줍줍알람'인지 확인(아니면 계정 전환) → 같은 댓글이 이미 있으면 고정만 → 없으면 달고 → ⋮ → 고정.
// 출력: 마지막 줄 RESULT {"status": 고정완료 | 이미고정 | 달았지만고정못함, ...}  예외는 그대로 던진다(쉘이 fail 처리).
// 댓글을 두 번 달지 않으려고, 실패해도 같은 편을 바로 다시 돌리지 않는다(다음 날 다시: 이미 단 댓글을 찾아 고정만 한다).

const fs = await import("node:fs/promises");
const NAME = "줍줍알람";
const job = JSON.parse(await fs.readFile("/Users/den/줍줍알람/유튜브/comment_job.json", "utf8"));
const vid = job.url.match(/(?:shorts\/|v=|youtu\.be\/)([\w-]{11})/)?.[1];
if (!vid) throw new Error(`영상 ID를 못 읽음: ${job.url}`);
const first = job.comment.trim().split("\n")[0].trim();
const log = [];

// 지난번 실패로 남은 같은 이름 공간이 있으면 그걸 이어 쓴다(새 공간을 계속 만들지 않게)
const leftover = (await listTaskSpaces()).find((s) => s.name === "줍줍알람 유튜브 고정 댓글");
const task = leftover ? await taskSpace(leftover.id) : await taskSpace("줍줍알람 유튜브 고정 댓글");
const page = task.page("p1");
try {

async function openComments() {
  await page.goto(`https://www.youtube.com/watch?v=${vid}`);
  await page.waitForTimeout(4000);
  for (let i = 0; i < 6; i++) {
    if (await page.evaluate(() => !!document.querySelector("#simplebox-placeholder"))) break;
    await page.mouse.wheel(0, 700);
    await page.waitForTimeout(2000);
  }
  await page.waitForSelector("#simplebox-placeholder", { state: "attached", timeout: 20000 });
}
const who = () =>
  page.evaluate(() => document.querySelector("ytd-comment-simplebox-renderer #author-thumbnail img, ytd-comment-simplebox-renderer img")?.alt?.trim() || "");

await openComments();
if ((await who()) !== NAME) {
  log.push(`댓글 이름이 '${await who()}' → 계정 전환`);
  await page.click("button#avatar-btn", { label: "open account menu" });
  await page.waitForTimeout(1500);
  await page.click("text=계정 전환", { label: "open switch account" });
  await page.waitForTimeout(2000);
  await page.click("text=@jupjup_alarm", { label: "switch to 줍줍알람" });
  await page.waitForTimeout(5000);
  await openComments();
  if ((await who()) !== NAME) throw new Error(`댓글 이름이 줍줍알람이 아님: ${await who()}`);
}

// 우리 댓글 스레드 찾기 (작성자 @jupjup_alarm 또는 줍줍알람 + 첫 줄 일치)
const findMine = () =>
  page.evaluate((first) => {
    const ts = [...document.querySelectorAll("ytd-comment-thread-renderer")];
    const i = ts.findIndex((t) => {
      const a = t.querySelector("#author-text")?.innerText.trim() || "";
      const c = t.querySelector("#content-text")?.innerText.trim() || "";
      return /jupjup_alarm|줍줍알람/.test(a) && c.startsWith(first.slice(0, 20));
    });
    if (i < 0) return null;
    const t = ts[i];
    // 고정된 댓글엔 '#pinned-comment-badge' 안에 "○○ 님이 고정함" 글자가 생긴다
    const pinned = /고정/.test(t.querySelector("#pinned-comment-badge")?.innerText || "");
    t.setAttribute("data-mine", "1");
    return { index: i, pinned };
  }, first);

let mine = await findMine();
if (mine?.pinned) {
  console.log("RESULT " + JSON.stringify({ id: job.id, status: "이미고정", log: log.join(" · ") }));
} else {
if (!mine) {
  await page.click("#simplebox-placeholder", { label: "open comment box" });
  await page.waitForSelector("#contenteditable-root", { state: "visible", timeout: 10000 });
  await page.focus("#contenteditable-root");
  await page.keyboard.paste(job.comment.trim());
  await page.waitForTimeout(800);
  const typed = await page.evaluate(() => document.querySelector("#contenteditable-root")?.innerText.trim() || "");
  if (!typed.startsWith(first.slice(0, 20))) throw new Error(`댓글 입력 불일치: ${typed.slice(0, 40)}`);
  await page.click("ytd-commentbox #submit-button button", { label: "post comment" });
  for (let i = 0; i < 15 && !mine; i++) {
    await page.waitForTimeout(1500);
    mine = await findMine();
  }
  if (!mine) throw new Error("댓글을 단 뒤 목록에서 못 찾음 — 다시 달지 말고 화면 확인");
  log.push("댓글 달음");
}

// ⋮ → 고정 → 확인 창 '고정'
await page.click("ytd-comment-thread-renderer[data-mine='1'] #action-menu button", { label: "open comment menu" });
await page.waitForTimeout(1200);
// 메뉴 항목은 ytd-menu-navigation-item-renderer(예전엔 service-item) — 보이는 '고정' 항목에 표시를 달고 누른다
const marked = await page.evaluate(() => {
  const it = [...document.querySelectorAll("ytd-menu-navigation-item-renderer, ytd-menu-service-item-renderer")].find(
    (e) => e.offsetParent && e.innerText.trim() === "고정",
  );
  if (it) it.setAttribute("data-pin", "1");
  return !!it;
});
if (!marked) throw new Error("댓글 메뉴에 '고정'이 없음 — 줍줍알람 이름으로 단 댓글인지 확인");
await page.click("[data-pin='1']", { label: "pin comment" });
await page.waitForTimeout(1500);
const confirm = await page.evaluate(() => {
  const b = [...document.querySelectorAll("yt-confirm-dialog-renderer button, tp-yt-paper-dialog button")].find(
    (x) => x.offsetParent && /^고정$/.test(x.innerText.trim()),
  );
  if (b) { b.click(); return true; }
  return false;
});
await page.waitForTimeout(2500);
await page.reload();
await page.waitForTimeout(4000);
await openComments();
mine = await findMine();
const status = mine?.pinned ? "고정완료" : "달았지만고정못함";
console.log("RESULT " + JSON.stringify({ id: job.id, status, confirm, log: log.join(" · ") }));
}
} finally {
  await task.finish({ keep: [] });
}
