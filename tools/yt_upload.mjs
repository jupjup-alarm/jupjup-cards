// 줍줍알람(@jupjup_alarm) 유튜브 쇼츠 예약 업로드 (ego lite, Claude 없이) — 투키즈노트 youtube/upload.mjs를 고쳐 씀, 2026-11-23
// 실행: ego-browser nodejs < /Users/den/줍줍알람/jupjup-cards/tools/yt_upload.mjs   (보통 tools/yt_daily.sh가 부름)
// 입력: ~/줍줍알람/유튜브/job.json  { id, title, description, tags[], video, thumb, date:"2026-11-24", time:"17:00", mode }
//   mode: "schedule"(예약까지) | "review"(예약 화면에서 멈춤) | 그 밖(비공개 초안 저장)
// 고정값: 아동용 아님 · 유료 프로모션 아니요 · 변경·합성 콘텐츠 아니요
// 출력: 마지막 줄 RESULT {"status", "link", ...}  status: 예약완료 | 초안저장 | 확인대기 | 중복(아무것도 안 올림)
// 실패해도 같은 편을 바로 다시 돌리지 말 것 — 이미 올라갔을 수 있다(다음 실행의 중복 확인이 막아 줌).

const fs = await import("node:fs/promises");
const JOBDIR = "/Users/den/줍줍알람/유튜브";
const CHANNEL = "UCbIKC-joj_M279Tii7sLSiA"; // 줍줍알람 @jupjup_alarm
const STUDIO = `https://studio.youtube.com/channel/${CHANNEL}`;
const job = JSON.parse(await fs.readFile(`${JOBDIR}/job.json`, "utf8"));
const log = [];
const thumb = job.thumb ? await fs.access(job.thumb).then(() => job.thumb, () => null) : null;
await fs.access(job.video);

// 지난번 실패로 남은 같은 이름 공간이 있으면 그걸 이어 쓴다(새 공간을 계속 만들지 않게)
const leftover = (await listTaskSpaces()).find((s) => s.name === "줍줍알람 유튜브 업로드");
const task = leftover ? await taskSpace(leftover.id) : await taskSpace("줍줍알람 유튜브 업로드");
const page = task.page("p1");

// 0) 활성 채널 확인 — 같은 구글 계정에 투키즈노트·효도알람 채널이 있다.
await page.goto("https://studio.youtube.com");
await page.waitForTimeout(4000);
if (!(await page.url()).includes(CHANNEL)) {
  await page.click('loc=css:button[aria-label="Account"]', { label: "open account menu" });
  await page.waitForTimeout(1500);
  await page.click("text=계정 전환", { label: "open switch account" });
  await page.waitForTimeout(2000);
  await page.click("text=@jupjup_alarm", { label: "switch to 줍줍알람" });
  await page.waitForTimeout(5000);
  await page.goto("https://studio.youtube.com");
  await page.waitForTimeout(4000);
  if (!(await page.url()).includes(CHANNEL)) throw new Error("줍줍알람 채널이 아님 — 스튜디오에서 채널 전환 필요");
  log.push("채널을 줍줍알람으로 전환함");
}

// 1) 중복 확인: 같은 제목이 동영상·Shorts 목록에 있으면 올리지 않는다.
const existing = [];
for (const tab of ["upload", "short"]) {
  await page.goto(`${STUDIO}/videos/${tab}`);
  if (!(await page.url()).includes(CHANNEL)) throw new Error("줍줍알람 채널이 아님 — 스튜디오에서 채널 전환 필요");
  await page.waitForSelector("ytcp-video-row", { state: "attached", timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1500);
  existing.push(
    ...(await page.evaluate(() =>
      [...document.querySelectorAll("ytcp-video-row")].map((r) => ({
        title: r.querySelector("#video-title")?.innerText.trim(),
        id: r.querySelector("a[href*='/video/']")?.href.split("/")[4],
        vis: r.querySelector(".tablecell-visibility")?.innerText.replace(/\s+/g, " ").trim(),
      })),
    )),
  );
}
const dup = existing.find((v) => v.title === job.title);
if (dup) {
  console.log("RESULT " + JSON.stringify({ id: job.id, status: "중복", link: dup.id ? `https://youtu.be/${dup.id}` : "", log: `같은 제목 영상 있음 (${dup.vis})` }));
  process.exit(0);
}

// 2) 업로드
await page.goto(`${STUDIO}/videos/upload?d=ud`);
await page.waitForSelector("input[type=file]", { state: "attached", timeout: 20000 });
await page.setInputFiles("input[type=file]", [job.video]);
await page.waitForSelector("ytcp-uploads-dialog #title-textarea #textbox", { state: "visible", timeout: 120000 });
await page.waitForTimeout(2000);

async function setBox(sel, text) {
  await page.click(sel, { label: "focus text box" });
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Backspace");
  await page.keyboard.paste(text);
}
await setBox("ytcp-uploads-dialog #title-textarea #textbox", job.title);
await setBox("ytcp-uploads-dialog #description-textarea #textbox", job.description);
// 설명이 '#shorts' 같은 해시태그로 끝나면 추천 목록이 떠서 아래 칸을 가린다.
// Esc는 업로드 창 전체를 닫으므로 쓰지 않고, 제목 칸을 눌러 포커스를 옮긴다.
// 클릭은 제목 칸이 화면 밖이면 실패하므로 focus만 옮긴다.
await page.focus("ytcp-uploads-dialog #title-textarea #textbox");
await page.waitForTimeout(500);
if (thumb) {
  const canThumb = await page.evaluate(() => !!document.querySelector("ytcp-uploads-dialog #file-loader"));
  if (canThumb) await page.setInputFiles("ytcp-uploads-dialog #file-loader", [thumb]);
  else log.push("썸네일 업로드 칸 없음");
}
// 채널 일회성(전화번호) 인증 전에는 맞춤 썸네일·설명란 링크가 막힌다. 업로드는 계속하고 로그에 남긴다.
if (await page.evaluate(() => /일회성 인증/.test(document.querySelector("ytcp-uploads-dialog")?.innerText || ""))) {
  log.push("채널 인증 필요 — 썸네일·설명 링크 미적용, 스튜디오에서 직접 확인");
}

// 3) 재생목록: 있으면 고르고, 없으면 로그만 남긴다 (새로 만들지 않음).
if (job.playlist) {
  await page.click("ytcp-uploads-dialog ytcp-video-metadata-playlists ytcp-dropdown-trigger", { label: "open playlist picker" });
  // 목록이 늦게 뜬다 — 항목이 보일 때까지 최대 10초 기다린다.
  await page
    .waitForFunction(() => document.querySelectorAll("ytcp-playlist-dialog label[id^=checkbox-item]").length > 0, undefined, { timeout: 10000 })
    .catch(() => {});
  const picked = await page.evaluate((name) => {
    const dlg = document.querySelector("ytcp-playlist-dialog");
    const label = [...(dlg?.querySelectorAll("span, label, div") || [])].find(
      (el) => el.children.length === 0 && el.innerText?.trim() === name && el.offsetParent,
    );
    if (!label) return false;
    const box = label.closest("li, ytcp-ve, label")?.querySelector("[role=checkbox], ytcp-checkbox-lit") || label;
    if (box.getAttribute("aria-checked") !== "true") box.click();
    return true;
  }, job.playlist);
  if (!picked) log.push(`재생목록 '${job.playlist}' 없음 — 건너뜀`);
  await page.evaluate(() => {
    const dlg = document.querySelector("ytcp-playlist-dialog");
    [...(dlg?.querySelectorAll("button") || [])].find((b) => /^(완료|Done)$/.test(b.innerText.trim()) && b.offsetParent)?.click();
  });
  await page.waitForTimeout(800);
}

await page.click('ytcp-uploads-dialog tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]', { label: "not made for kids" });
await page.click("ytcp-uploads-dialog #toggle-button", { label: "show more options" });
await page.waitForSelector("ytcp-uploads-dialog #tags-container #text-input", { state: "visible", timeout: 10000 });
await page.click("ytcp-uploads-dialog #tags-container #text-input", { label: "focus tags input" });
for (const t of job.tags || []) {
  await page.keyboard.insertText(t);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
}
// 유료 프로모션: 아니요 / 변경·합성 콘텐츠: 아니요 (AI 음성이지만 실제 인물·사건을 꾸민 것이 아님 — docs/youtube_ego.md 3절, 설명란에 'AI 음성' 표기)
await page.click('ytcp-uploads-dialog tp-yt-paper-radio-button[name="VIDEO_PAID_PRODUCT_PLACEMENT_NO"]', { label: "no paid promotion" });
await page.waitForTimeout(800);
await page.click('ytcp-uploads-dialog tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_NO"]', { label: "no altered content" });

const filled = await page.evaluate(() => ({
  radios: Object.fromEntries(
    ["VIDEO_MADE_FOR_KIDS_NOT_MFK", "VIDEO_PAID_PRODUCT_PLACEMENT_NO", "VIDEO_HAS_ALTERED_CONTENT_NO"].map((n) => [
      n,
      document.querySelector(`ytcp-uploads-dialog tp-yt-paper-radio-button[name="${n}"]`)?.getAttribute("aria-checked"),
    ]),
  ),
  title: document.querySelector("ytcp-uploads-dialog #title-textarea #textbox")?.innerText.trim(),
  tags: [...document.querySelectorAll("ytcp-uploads-dialog #tags-container ytcp-chip")].map((c) => c.innerText.trim()),
  playlist: document.querySelector("ytcp-uploads-dialog ytcp-video-metadata-playlists ytcp-dropdown-trigger")?.innerText.trim(),
}));
if (filled.title !== job.title) throw new Error(`제목 불일치: ${filled.title}`);
const unset = Object.entries(filled.radios).filter(([, v]) => v !== "true").map(([k]) => k);
if (unset.length) throw new Error(`선택 안 됨: ${unset.join(", ")}`);
if (filled.tags.length !== (job.tags || []).length) log.push(`태그 ${filled.tags.length}/${job.tags.length}개 들어감`);

// 4) 공개 상태 → 예약 날짜·시각
for (let i = 0; i < 3; i++) {
  await page.click("ytcp-uploads-dialog #next-button", { label: "next step" });
  await page.waitForTimeout(1500);
}
await page.waitForFunction(
  () => !!(document.querySelector("ytcp-uploads-dialog #second-container-expand-button")?.offsetParent || document.querySelector("ytcp-uploads-dialog #datepicker-trigger")?.offsetParent),
  undefined,
  { timeout: 15000 },
);
const expanded = await page.evaluate(() => !!document.querySelector("ytcp-uploads-dialog #datepicker-trigger")?.offsetParent);
if (!expanded) await page.click("ytcp-uploads-dialog #second-container-expand-button", { label: "expand schedule section" });
await page.waitForSelector("ytcp-uploads-dialog #datepicker-trigger", { state: "visible", timeout: 10000 });

const [y, m, d] = job.date.split("-").map(Number);
const [hh, mm] = job.time.split(":").map(Number);
const wantDate = `${y}. ${m}. ${d}.`;
const wantTime = `${hh < 12 ? "오전" : "오후"} ${hh % 12 === 0 ? 12 : hh % 12}:${String(mm).padStart(2, "0")}`;
await page.click("ytcp-uploads-dialog #datepicker-trigger", { label: "open date picker" });
await page.click("ytcp-date-picker tp-yt-paper-input input", { label: "focus date input" });
await page.keyboard.press("ControlOrMeta+a");
await page.keyboard.insertText(wantDate);
await page.keyboard.press("Enter");
await page.waitForTimeout(600);
await page.click("ytcp-uploads-dialog #time-of-day-container input", { label: "focus time input" });
await page.keyboard.press("ControlOrMeta+a");
await page.keyboard.insertText(wantTime);
await page.keyboard.press("Enter");
await page.waitForTimeout(800);

const sched = await page.evaluate(() => ({
  date: document.querySelector("ytcp-uploads-dialog #datepicker-trigger")?.innerText.trim(),
  time: document.querySelector("ytcp-uploads-dialog #time-of-day-container input")?.value,
}));
if (sched.date !== wantDate || sched.time !== wantTime) throw new Error(`예약 시각 불일치: ${sched.date} ${sched.time}`);

// 5) 롱폼은 파일 전송이 끝날 때까지 기다린다 (최대 20분).
await page.waitForFunction(
  () => !/업로드 중|업로드하는 중|Uploading/.test(document.querySelector("ytcp-video-upload-progress")?.innerText || ""),
  undefined,
  { timeout: 20 * 60_000 },
);
const meta = await page.evaluate(() => ({
  link: document.querySelector("ytcp-video-info a")?.href,
  length: document.querySelector("ytcp-uploads-dialog")?.innerText.match(/0:00 \/ (\d+:\d{2})/)?.[1] ?? "",
  progress: document.querySelector("ytcp-video-upload-progress")?.innerText.trim(),
}));
const shot = await page.screenshot({ path: `${JOBDIR}/${job.id}/${job.id}_review.png` });

let status = "초안저장";
if (job.mode === "schedule") {
  await page.click("ytcp-uploads-dialog #done-button", { label: "schedule video" });
  // 처리 전이면 '동영상 처리 중', 끝났으면 '동영상 예약됨' 창이 뜬다. 둘 다 예약된 것.
  await page.waitForFunction(() => /동영상 예약됨|동영상 처리 중/.test(document.body.innerText), undefined, { timeout: 60000 });
  await page.waitForTimeout(1500);
  status = "예약완료";
  sched.confirm = await page.evaluate(() => {
    const m = document.body.innerText.match(/(동영상 예약됨|동영상 처리 중)[^\n]*\n[^\n]*/);
    [...document.querySelectorAll("button")].find((b) => b.innerText.trim() === "닫기" && b.offsetParent)?.click();
    return m?.[0].replace(/\s+/g, " ");
  });
} else if (job.mode === "review") {
  status = "확인대기"; // 예약 화면을 연 채로 둔다. 확인 후 #done-button을 누른다.
} else {
  // 닫기 버튼 이름이 저장 중엔 '저장 후 닫기', 저장이 끝나면 '닫기'
  const closeLabel = await page.evaluate(() =>
    [...document.querySelectorAll("ytcp-uploads-dialog button[aria-label]")]
      .map((b) => b.getAttribute("aria-label"))
      .find((l) => l === "저장 후 닫기" || l === "닫기"),
  );
  await page.click(`ytcp-uploads-dialog button[aria-label="${closeLabel}"]`, { label: "save draft and close" });
}
await page.waitForTimeout(1500);

console.log(
  "RESULT " +
    JSON.stringify({ id: job.id, status, ...meta, tags: filled.tags, playlist: filled.playlist, ...sched, log: log.join(" · "), screenshot: shot }),
);
await task.finish({ keep: [] });
