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
"광고 · 링크 구매 시 수수료를 받아요"가 자동으로 들어가고, 마무리 장에는 platform에 맞는 전체 대가성 문구가 자동으로 들어간다.

## 원고(JSON) 형식
```json
{
  "slug": "2026-10-25-wipes",          // 영문 소문자·숫자·하이픈 (주소에 들어감)
  "title": "물티슈 특가",
  "series": "오늘 특가",                // 오늘 특가 → 표지 잉크(어두운) 테마, 그 외 → 종이 테마
  "platform": "toss",                  // toss | coupang (마무리 장 대가성 문구)
  "cards": [ ... 5~7장 ... ]
}
```
카드 종류 (`type`):
- `cover` 표지 (항상 1장째): `chips` [시리즈 태그, 보조 태그(선택)], `lines` 메인 카피 2줄(한 줄 7자 안팎), `highlight` 강조 단어, `sub` 서브 카피 1줄(**굵게** 가능), `badge` 원형 스티커 3줄(선택, 예 ["마트 대비","반값","1팩 기준"]), `hand` 손글씨 한 줄(선택, badge와 같이 쓰지 말 것), `theme` "deal"|"note"(선택).
- `deal` 특가 상세: `num`, `name`(\n 줄바꿈 가능), `tags` 최대 3개, `original` 정가, `price` 판매가, `percent` 할인율, `unit` 단가 환산(예 "1팩 약 **459원**"), `deadline`, `points` 1~2줄, `note` "가격은 MM/DD HH:MM 기준 · 바뀔 수 있어요".
- `calc` 두 배 계산기: `title` 2줄, `rows` [{label, value, amount(숫자)}] 2~3개(막대 길이 = amount 비율), `result` 결론 한 줄, `hand`, `note` 계산 기준.
- `list` 숫자 리스트: `eyebrow`, `icon`(box|tag|cart|bell|clock), `title`, `items` [[굵은 줄, 설명]] 최대 4개.
- `compare` 비교표: `title`, `cols` (첫 칸 ""), `rows`, `best` 강조 열 번호(1부터), `hand`, `note`.
- `check` 체크리스트: `eyebrow`, `title`, `items` 최대 3개, `postit` 포스트잇 손글씨(선택).
- `photo` 실사: `name`, `badge`(예 "실사용 6개월째"), `image` "2kids/photos/<사진ID>.jpg", `text` 한 줄. **사진은행에 있는 실사용 제품만.**
- `closing` 마무리 (항상 마지막): `lines` 2줄, `highlight`, `link` story|dm|profile, `keyword`(dm일 때), `where` 손글씨 위치 안내(예 "하이라이트 ‘오늘 특가’").

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
