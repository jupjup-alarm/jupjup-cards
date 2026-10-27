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
- `photos/` — 시트 스크립트가 올리는 단지 사진 ('청약조사' W열 → AA열), 평면도 `photos/plan-…` (AB열 → AC열)
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
- **실사 표지**: '청약조사' AA열에 `photos/…jpg`(png·webp)가 있으면 cover에 `"photo": "photos/…"`, `"photo_credit": "이미지: <X열 출처 기관> 제공 조감도 · 실제와 다를 수 있음"`(실사진이면 "이미지: <출처> · <라이선스>")을 넣는다. 위쪽은 사진, 아래는 시리즈 색 위에 큰 글자. 사진에서 단지가 잘리면 `"photo_pos": "center 30%"`처럼 조정. AA열이 비었거나 "없음"·"사용 불가"·"사진 실패"면 photo 없이 기본 표지. 파일이 없으면 warnings에 `PHOTO:`가 나오고 기본 표지로 대체된다.
  - 사진 출처 우선순위(사용자 결정 2026-10-25): ① 공공누리 1유형(정책브리핑·국토부·LH 보도자료) ② 위키미디어 커먼즈 CC BY·BY-SA ③ 사업주체 공식 홍보 이미지(LH청약플러스 '단지조감도' 탭·팸플릿·분양 홈페이지 조감도). 공공누리 2·3·4유형, CC NC·ND, 네이버·카카오·구글 로드뷰·지도 캡처, 블로그·카페·부동산 앱 사진은 쓰지 않는다.
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
- plan (평면도): `{"type": "plan", "eyebrow": "평면도", "title": "84A 이렇게 생겼어요", "image": "photos/plan-….jpg", "rows": [["공급", "일반 19·특공 53세대"], ["최고 분양가", "5억7,026만원"]], "credit": "이미지: LH 제공 평면도 · 실제와 다를 수 있음"}` — 가격 장 바로 뒤에 1~2장(주력 타입). rows 최대 2개, 값은 '청약홈API' 탭·원고 숫자 그대로.
  - 이미지 출처: '청약조사' AC열 `photos/plan-…` (분양 홈페이지 평면 이미지를 시트 스크립트가 받아둔 것)만 쓴다. AC열이 비었거나 "없음"·"실패"면 평면도 카드를 **빼고** 만든다 (사용자 결정 2026-10-26: 팸플릿 PDF는 올리지 않음). 반드시 Read로 열어 타입명이 맞는지 확인.
  - credit은 X열 출처(사업주체)로: "이미지: <사업주체> 제공 평면도 · 실제와 다를 수 있음".
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

## 숏츠(릴스) — `reel.py`
- 원고: `reels/specs/<slug>.json` → `python3 reel.py reels/specs/<slug>.json` → `reels/<slug>/reel.mp4`, `cover.jpg`, `preview.jpg`, `manifest.json`
- ⭐ 이야기 장면 `beat` (2026-10-27 릴스 재구성 — 슬라이드형 표 대신 이야기형): `{"type": "beat", "eyebrow": "가격", "big": "4억 8,600만원", "big_sub": "43㎡ 최고가", "highlight": "4억 8,600만원", "say": "<그 장면 내레이션 대본 그대로>", "bg": "photos/…jpg 또는 maps/…png 또는 none", "bg_credit": "…", "bg_pos": "center 40%"}` — 풀화면 배경(사진은 천천히 흐름, 네이버 지도는 핀 쪽으로 확대·출처 자동) 위에 숫자·핵심어 하나를 크게(`big`, 한 줄, 넘치면 자동 축소, 줄을 나누려면 `\n`), 아래에 `say` 자막이 음성에 맞춰 단어별로 켜짐(숫자 든 단어는 강조색). 원고 맨 위에 `"bg"`·`"bg_credit"`을 주면 배경 없는 beat에 공통으로 깔림. hook도 `"bg": "maps/…png"`로 지도 확대 배경 가능. cta는 `"ask"`(댓글 질문·팔로우 한 줄) 추가 가능. 새 릴스는 hook → beat 3~4개 → cta가 기본 (points는 예전 형식 호환용).
- 장면: `hook`(첫 프레임부터 훅이 보임 — 1초 룰, lines의 `{n}` 자리에 `count.to` 숫자가 강조 펄스), `points`(rows 2~4개, text 선택), `cta`. 1080×1920. 핵심 내용은 세로 가운데(피드 4:5 영역 y≈285~1635)에 모으고, 위 300px·아래 420px·오른쪽 140px(인스타 버튼 자리)는 비운다 — 2026-10-25 "너무 위로 몰림" 피드백 반영.
- 훅 장면 실사 배경: hook에 `"photo"`, `"photo_credit"`(카드 표지와 같은 값), 선택 `"photo_pos"`를 넣으면 위쪽에 단지 사진이 천천히 확대되고 글자는 아래로 내려간다 (종이 캐릭터는 숨김). 표지 cover.jpg에도 사진이 들어간다.
- 평면도 장면: `{"type": "plan", "eyebrow", "title", "image", "rows"(최대 2개, 한 줄 요약으로 표시), "credit"}` — ③ 원고에 평면도 장면이 있을 때만 (장면 수 = 대본 블록 수 유지).
- 내레이션: 원고에 `"voice": "voices/<id>/"` (시트 '오늘의 발행 플랜' AA열 값)을 넣으면 `voices/<id>/01.mp3`… 를 장면 순서대로 붙이고, 장면 길이를 음성에 맞춰 늘리고, 종이 캐릭터 입을 음성 크기에 맞춰 움직인다. 음성은 시트 스크립트가 Z열 대본(장면마다 `---`로 구분)으로 구글 TTS를 돌려 올린다. 렌더링 전 `git pull --rebase origin main`.
- 올리기: `git add reels && git commit -m "reels: <slug>" && git push origin HEAD:main` (`reel.html`은 올리지 않음). S열에 `manifest.json`의 video, cover 주소를 줄바꿈으로 → 시트 스크립트가 릴스로 게시.
