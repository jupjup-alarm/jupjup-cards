# 2kids — 두아이 살림노트(@2kids_note) 카드뉴스

인스타 카드뉴스(1080×1350 JPG)를 원고(JSON)로 자동 생성한다. 공개 주소
`https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/main/2kids/cards/<slug>/NN.jpg`
를 '2kids_note 운영시트' 발행계획 U열에 줄바꿈으로 넣으면 시트 스크립트가 인스타에 게시한다.
줍줍알람 카드(`cards/`, `render.py`)와는 폴더·렌더러가 완전히 분리돼 있다. 섞지 말 것.

## 구조
- `2kids/render.py` — 원고 → `2kids/cards/<slug>/NN.jpg`, `preview.jpg`, `manifest.json`
- `2kids/specs/<slug>.json` — 원고 (`sample-*.json`은 형식 예시)
- `2kids/fonts/` — Gamja Flower(손글씨, OFL). 본문 Noto Sans KR은 저장소 `fonts/` 것을 씀
- `2kids/photos/` — 사진은행 실사 (얼굴 가린 사진만, 파일명 = 사진ID.jpg)

## 브랜드
종이 #FBF7EF · 잉크 #2B3040 · 형광펜 #F5C84C · 세이지 #9DBB97 · 코랄 #E8735F.
속지는 스프링 노트, 표지 하단엔 쌍둥이 뒷모습(1번 리본·2번 방울). 표지에는
"광고 · 링크 구매 시 수수료를 받아요"가, 마무리 장에는 platform에 맞는 전체 대가성 문구가 들어간다 — 단, 원고에 `"ad": true`가 있을 때만 (정보 카드에는 광고 표시가 없다).

## 원고(JSON) 형식
```json
{
  "slug": "2026-10-25-wipes",          // 영문 소문자·숫자·하이픈 (주소에 들어감)
  "title": "물티슈 특가",
  "series": "오늘 특가",                // 오늘 특가 → 표지 잉크(어두운) 테마, 그 외 → 종이 테마
  "ad": true,                           // 상품(제휴 링크)을 다룰 때만. 없으면 광고 표시·대가성 문구 없음 (정보 카드 기본)
  "platform": "toss",                  // ad일 때만: toss | coupang (마무리 장 대가성 문구)
  "cards": [ ... 5~7장 ... ]
}
```
카드 종류 (`type`):
- `info` 정보 정리 (정보글의 기본 속지): `eyebrow`(예 "첫만남이용권"), `icon`(bell|tag|calc|box|clock|check), `title` 2줄, `rows` [[라벨, 값]] 2~5개(값에 **굵게**·\n 가능), `text` 한 줄(선택), `note` 출처 "출처: 기관명 · YYYY.MM.DD".
- `cover` 표지 (항상 1장째): `chips` [시리즈 태그, 보조 태그(선택)], `lines` 메인 카피 2줄(한 줄 7자 안팎), `highlight` 강조 단어, `sub` 서브 카피 1줄(**굵게** 가능), `badge` 원형 스티커 3줄(선택, 예 ["마트 대비","반값","1팩 기준"]), `hand` 손글씨 한 줄(선택, badge와 같이 쓰지 말 것), `theme` "deal"|"note"(선택).
- `deal` 특가 상세: `num`, `name`(\n 줄바꿈 가능), `tags` 최대 3개, `original` 정가, `price` 판매가, `percent` 할인율, `unit` 단가 환산(예 "1팩 약 **459원**"), `deadline`, `points` 1~2줄, `note` "가격은 MM/DD HH:MM 기준 · 바뀔 수 있어요".
- `calc` 두 배 계산기: `title` 2줄, `rows` [{label, value, amount(숫자)}] 2~3개(막대 길이 = amount 비율), `result` 결론 한 줄, `hand`, `note` 계산 기준.
- `list` 숫자 리스트: `eyebrow`, `icon`(box|tag|cart|bell|clock), `title`, `items` [[굵은 줄, 설명]] 최대 4개.
- `compare` 비교표: `title`, `cols` (첫 칸 ""), `rows`, `best` 강조 열 번호(1부터), `hand`, `note`.
- `check` 체크리스트: `eyebrow`, `title`, `items` 최대 3개, `postit` 포스트잇 손글씨(선택).
- `photo` 실사: `name`, `badge`(예 "실사용 6개월째"), `image` "2kids/photos/<사진ID>.jpg", `text` 한 줄. **사진은행에 있는 실사용 제품만.**
- `closing` 마무리 (항상 마지막): `lines` 2줄, `highlight`, 버튼 저장·공유·팔로우. 정보 카드는 `share` "누구에게 보내면 좋은지" 한 줄(예 "어린이집 보내는 친구한테 보내주세요"). 상품 카드(`"ad": true`)만 `link` story|dm|profile, `keyword`(dm일 때), `where` 손글씨 위치 안내 + 대가성 문구.

## 정보 카드 구성 (기본)
- 지원금·정책: cover → info(대상·금액·신청·기한) → info 또는 check(신청 방법·주의) → closing
- 시즌 꿀팁: cover → list 또는 check → (compare) → closing
- 육아뉴스: cover → info(무엇이 바뀌나·언제부터·누구) → check(우리 집 체크) → closing
- 혜택·할인: cover → info(혜택·기간·조건) → compare(선택) → closing
- 모든 정보 카드 note에 출처(기관·발표일). 보도 기준이면 "(보도 기준)".
- **A형 총정리 캐러셀** (2026-10-27 PD 기획, 매일 11:00 기본): cover(theme "deal" 남색 대비 표지, chips ["(저장)", 요일 시리즈], lines 2줄 = 개수·대상·손해·기한 중 2개 이상, sub 한 줄) → 항목마다 info 1장(eyebrow "1 / 5 · 제도명", title 2줄, rows 2~3개 — 금액을 첫 행에 **굵게**, 3번째 항목 근처 장의 text에 "다둥이 친구 있으면 태그해 주세요") → check(eyebrow "우리 집 체크", title "우리 집 / 몇 개 해당?") → closing(share 공유 대상 지목, where 화자 "두배맘" 한마디 + 댓글 키워드 안내 — 발행계획 K열 키워드). 7~10장. 예시: `specs/sample-bundle.json`.

## 문구 규칙 (프로젝트 규칙)
- 숫자·가격·마감은 시트(후보 G열·N열 출처)에서 확인된 값만. 모르면 그 칸을 빼라. 자리표시자(○○, [N], TBD) 금지.
- 사진은행에 없는 제품: "써봤다", "우리 애들이 쓴다", "실사용" 표현 금지 → 특가·정보형(cover/deal/calc/list/compare/check)만.
- 효능 주장 금지(아토피·면역력 등). 아이 얼굴·이름·어린이집 금지.
- 토스 상품 이미지는 원본만 허용(크롭·합성 금지)이라 카드에 넣지 않는다.

## 렌더링·점검
```bash
python3 2kids/render.py 2kids/specs/<slug>.json
```
- 출력 첫 줄 warnings: `OVERFLOW`, `text overlaps badge`가 있으면 원고를 줄이고 다시. `zoom 0.85` 이상은 괜찮고 0.8 미만이면 줄 정리.
- `preview.jpg`와 각 장을 직접 열어 잘림·겹침·어색한 줄바꿈·숫자 오타를 확인한다.

## 올리기
```bash
git pull --rebase origin main
git add 2kids/specs 2kids/cards && git commit -m "2kids: <slug>" && git push origin HEAD:main
```

## 숏츠(릴스) — `2kids/reel.py`
- 원고: `2kids/reels/specs/<slug>.json` → `python3 2kids/reel.py 2kids/reels/specs/<slug>.json` → `2kids/reels/<slug>/reel.mp4`, `cover.jpg`, `preview.jpg`, `manifest.json`
- 형식은 `2kids/reel.py` 맨 위 설명과 `2kids/reels/specs/sample-reel.json` 참고. 장면: `hook`(lines에 `{n}` → 0부터 `count.to`까지 숫자 올라감), `say`(한마디 + 손글씨 note), `points`(rows 2~4), `twins`(rows [항목, 한 명, 쌍둥이]), `checks`(items 3~4), `cta`(lines + 저장·팔로우 + 출처, 상품이면 `link_note`).
- **B형 루프 리스트 릴스** (2026-10-27 PD 기획): 원고에 `"loop": true`, 음성 없음(대본 Z열 비움), `"bgm"` 지정. 장면 2개 — `hook`(dur 1.5~1.8, chips 첫 칸 "(저장)") + `list`(`items` 최대 5개, 각 `["항목", "짧은 값"]`, `step` 0.9초). 6~9초. 마지막 0.4초에 표지로 돌아가 끊김 없이 반복돼요. 예시: `reels/specs/sample-loop-reel.json`.
- **C형 15초 체크 릴스**: `hook` → `ask` 3~4개(`{"n": "1 / 3", "q": "질문 두 줄", "a": "예", "note": 선택}`, 장면마다 2.8초, 예/아니오 버튼이 눌림) → `cta`. 음성 없이 배경음악만, 또는 장면 수 = 대본 블록 수로 음성. 예시: `reels/specs/sample-check-reel.json`.
- 1080×1920, 위 250px·아래 400px엔 핵심 글자 금지 (렌더 warnings에 '가림 영역 침범'이 나오면 문구를 줄임). 오른쪽 아래는 말하는 쌍둥이 자리.
- 내레이션: `"voice": "2kids/voices/<id>/"` (시트 발행계획 AA열 값의 앞부분). 시트 스크립트가 Z열 대본(장면마다 `---`)을 구글 TTS로 돌려 `2kids/voices/<id>/01.mp3`…를 올린다. 대본 조각 수 = 장면 수. 렌더 전 `git pull --rebase origin main`.
- 장면 길이는 음성에 맞춰 자동 (앞뒤 무음 잘라내고 장면 사이 약 0.5초). 음성이 있으면 `dur`는 무시, 오래 보여줘야 하는 장면만 `"min": 초`.
- 배경음악: `"bgm": "sunny"`(밝음·지원금/혜택) | `"cozy"`(잔잔·뉴스/공감) | `"bounce"`(경쾌·꿀팁/체크) | `false`. 생략하면 slug에 따라 골고루 돌려씀. 목소리가 나올 때 자동으로 작아진다(덕킹). 곡은 `2kids/bgm.py`로 직접 합성한 자체 음원이라 저작권 문제 없음.
- 목소리 기본값: 구글 TTS `ko-KR-Chirp3-HD-Leda`, 속도 1.2 (시트 스크립트 TTS_VOICE·TTS_RATE 속성으로 변경).
- 상품을 다루면 `"ad": true` → 첫 장면에 "광고 · 링크 구매 시 수수료를 받아요" 표시.
- 올리기: `git add 2kids/reels/specs 2kids/reels/<slug> && git commit -m "2kids reels: <slug>" && git push origin HEAD:main`. 발행계획 R행 U열에 manifest의 video, cover 주소를 줄바꿈으로, 짝이 되는 스레드 T행 U열에는 video 주소만.
