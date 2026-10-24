# jupjup-cards — 줍줍알람 카드뉴스 이미지 저장소

이 저장소는 인스타그램 카드뉴스 JPG를 만들고 공개 주소로 제공하는 곳이다.
인스타 API는 공개 이미지 주소만 받기 때문에, 여기 올린 JPG의
`https://raw.githubusercontent.com/jupjup-alarm/jupjup-cards/<브랜치>/cards/<slug>/NN.jpg` 주소를
구글시트 '오늘의 발행 플랜' S열에 넣으면 시트 스크립트가 게시한다.

## 구조
- `render.py` — 카드 원고(JSON) → `cards/<slug>/NN.jpg`, `preview.jpg`, `manifest.json`, `dc/*.dc.html`
- `specs/<slug>.json` — 카드 원고
- `templates/char_*.svg` — 종이 캐릭터 (surprise=깜짝, happy=신남, wink=윙크, closing=마무리)
- `fonts/` — Black Han Sans, Noto Sans KR (OFL)
- `maps/` — 시트 스크립트가 올리는 네이버 지도 이미지
- `mapgen.py`, `data/` — 대체용 경계 지도 (통계청 SGIS 2018 행정구역 경계, 공공누리 제1유형)

## 원고(JSON) 형식
```json
{
  "slug": "2026-10-24-gyeonggi-happyhouse",      // 영문 소문자·숫자·하이픈만 (주소에 들어감)
  "title": "단지명",
  "series": "임대알람",                          // 줍줍알람 | 강남로또 | 내집마련 | 임대알람 | 주거꿀팁 | 이번주청약
  "cards": [
    {"type": "cover", "chips": ["임대알람", "청약통장 필요없음"], "lines": ["월세", "3만원대부터"],
     "highlight": "3만원대", "sub": "서브 카피 한 줄", "face": "신남"},
    {"type": "info", "eyebrow": "자격", "title": "누가 넣을 수 있나요?",
     "rows": [["대상", "무주택세대구성원"], ["통장", "필요없음"]],
     "text": "선택: 행 아래 문장", "note": "선택: ※ 보도 기준, 공고 확인 후 업데이트"},
    {"type": "check", "title": ["이것만은", "꼭 확인하세요"],
     "items": [["굵은 줄", "설명 줄"], ["…", "…"]], "note": "선택"},
    {"type": "closing", "lines": ["저장해두고", "일정 놓치지 마세요"], "highlight": "일정"}
  ]
}
```
- cover: `lines`는 2줄 권장, 한 줄 6~7자 이내 (넘치면 자동으로 글자가 줄어듦). `chips` 첫 칸은 시리즈 태그(괄호 없이), 둘째 칸은 문턱 태그(선택).
- info: `rows`는 2~4개. 값이 길면 자동 줄바꿈되고, 원하는 곳에서 끊으려면 값에 `\n`을 넣는다. `title`은 문자열 또는 줄 배열.
- check: `items` 최대 3개.
- week (주간 일정 목록, 이번주청약용): `{"type": "week", "title": "10/27 ~ 10/29", "items": [{"date": "10/27", "dow": "월", "series": "줍줍알람", "name": "단지명", "point": "한 줄 포인트"}]}` — 한 장에 최대 4건, 넘치면 장을 나눈다. 표지는 `chips: ["이번주청약", "10/27 ~ 11/02"]`.
- map (위치 지도): `{"type": "map", "eyebrow": "위치", "title": "어디에 있냐면요", "sido": "서울", "sigungu": "강동구", "dong": "강일동", "label": "강일동", "address": "서울 강동구 강일동 고덕강일3단지", "rows": [["가까운 역", "…"]]}`
  - **네이버 지도 우선**: 시트 스크립트가 '청약조사' 주소로 네이버 지도(길·역 표시)를 받아 `maps/xxxx.png`로 이 저장소에 올리고, '청약조사' Y열에 그 경로를 적는다. Y열에 `maps/…png`가 있으면 카드에 `"image": "maps/…png"`를 넣어라 (출처 "© NAVER Corp."가 자동으로 들어감). 렌더링 전에 반드시 `git pull --rebase origin main`으로 최신 지도를 받아라.
  - Y열이 비었거나 "주소 못 찾음"·"지도 실패"면 `image` 없이 아래 경계 지도로 그린다.
  - 경계 지도: 통계청 SGIS 2018 행정구역 경계(공공누리 1유형)로 오프라인 렌더링한다. 지도 하단 출처 문구는 자동으로 들어간다.
  - `dong`은 **행정동** 이름이다. 공고문 주소의 법정동(예: 박촌동)이 행정동 목록에 없으면 렌더링 warnings에 그 시군구의 행정동 후보가 나온다. 웹 검색("○○동 행정동")으로 관할 행정동을 찾아 `dong`에 넣고, `label`에는 "박촌동 일대"처럼 사람들이 아는 이름을 쓴다.
  - 행정동을 끝내 못 정하면 `dong`을 빼라 (시군구만 강조된다).
  - 단지가 여러 곳(예: 24개 단지 모집)이거나 생활정보·주간 일정이면 지도 카드를 넣지 않는다.
  - `rows`는 최대 2개 (가까운 역 등, 원고에 있는 사실만).
- 원고의 문구·숫자는 바꾸지 말 것. 칸 배치만 정리한다.

## 렌더링
```bash
pip install --break-system-packages playwright pillow  # 없을 때만
python3 render.py specs/<slug>.json
```
출력 첫 줄의 `warnings`에 `OVERFLOW`나 `cover text overlaps character`가 있으면 원고를 줄 나눔·행 정리로 고쳐 다시 렌더링한다.
`zoom 0.9x`는 자동으로 조금 줄였다는 뜻이라 괜찮다 (0.8 미만이면 행을 정리하는 게 좋다).
반드시 `preview.jpg`와 각 장을 직접 열어 눈으로 확인한다.

## 올리기
```bash
git pull --rebase origin main   # 시트 스크립트가 maps/ 에 지도를 올리므로 먼저 받기
git add specs cards && git commit -m "cards: <slug>" && git push origin HEAD:main
```
main에 푸시가 거절되면 `cards` 브랜치에 푸시하고 `CARDS_BRANCH=cards`로 다시 렌더링해 주소를 맞춘다.
