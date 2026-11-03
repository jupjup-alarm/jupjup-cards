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
- `photos/` — 시트 스크립트가 올리는 단지 사진 ('청약조사' W열 → AA열), 평면도 `photos/plan-…` (AB열 → AC열), 배치도 `photos/layout-…` (AD열 → AE열), 동호배치도 `photos/dongho-…` (AF열 → AG열) — 배치도·동호배치도는 사이트(jupjupalarm.com) 공고 페이지용, AH열은 공식 홈페이지 주소
- `photos/site/<key>/` — 분양 홈페이지 자료 (2026-11-02): ① 조사 담당이 `tools/site_assets.py`로 홈페이지를 훑고 고른 이미지 주소를 '청약조사' AI열(홈페이지 자료, 첫 줄 `key: …`)에 적으면, ④·⑦이 `python3 tools/site_photos.py --text "<AI열>"`로 받는다 → `<분류>-….jpg`(birdseye 조감도·siteplan 단지배치·dongho 동호배치·plan 평면·community 커뮤니티·interior 인테리어), `index.json`(분류·label·w·h·photo 여부·E모델하우스 링크), `contact.jpg`(미리보기). 출처 문구 "이미지: <사업주체> 분양 홈페이지 · 실제와 다를 수 있음".
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
- **꽉 찬 실사 표지** (2026-10-27, @donnamu_grow 참고 — 첫 장은 항상 실사): cover에 `"photo_style": "full"`을 주면 사진이 카드 전체를 채우고 아래만 어둡게, 흰 글씨 2줄 + 칩 + 서브 (종이 캐릭터 없음). 사진 후보는 '오늘의 발행 플랜' AC열 `photos/mood/…jpg`(시트 스크립트가 AB열 검색어로 Pixabay/Pexels에서 받음 — 무료·출처 표기 불필요라 photo_credit 없이)와 단지 조감도(AA열, 이때는 photo_credit 유지) 중 가장 눈에 띄는 것. 표지는 주목용이라 실제 단지가 아니어도 됨 (사용자 결정).
- **근거 한 줄 + 둘째 줄 강조 (주비서식, 2026-11-02 사용자 결정)**: cover에 `"basis": "<③ 원고 1장의 '근거:' 줄 그대로>"`를 넣으면 칩 아래·메인 위에 작은 근거 한 줄(한 줄 고정, 넘치면 자동 축소)이 들어가고, 메인 둘째 줄 전체가 강조색이 된다(`accent_line` 기본 2, 다른 줄이면 `"accent_line": 1`). '서브:' 줄은 `sub`에 — 근거를 sub에 넣지 말 것. 릴스 hook도 같은 `basis`·`accent_line`.
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
- **홈페이지 사진 카드** (2026-11-02): plan 카드는 평면도 말고도 `photos/site/<key>/`의 커뮤니티·조감도·동호배치도에 쓸 수 있다. 사진(index.json `photo: true` — 커뮤니티·조감도 컷)은 `"fit": "cover"`(칸을 꽉 채움, 선택 `"pos": "center 40%"`), 그림(평면·배치·동호·커뮤니티 평면)은 fit 없이. 예: `{"type":"plan","eyebrow":"커뮤니티","title":"단지 안에 이런 게 있어요","image":"photos/site/2026940241/community-2.jpg","fit":"cover","credit":"이미지: <사업주체> 분양 홈페이지 · 실제와 다를 수 있음"}`
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
- 원고: `reels/specs/<slug>.json` → `python3 reel.py reels/specs/<slug>.json` → `reels/<slug>/reel.mp4`, `cover.jpg`, `preview.jpg`, `manifest.json` + 이름 붙은 사본 `<slug>.mp4`·`<slug>_thumb.jpg` (manifest의 video·cover 주소는 사본 쪽 — 내려받아도 파일명이 겹치지 않게, 2026-11-02)
- 썸네일 (2026-11-02 "썸네일이 너무 구려서"): reel.py가 끝에 `thumb.py`로 `<slug>_thumb.jpg`를 큰 글자 표지(사진 꽉 채움 + 칩·빨간 띠 + 근거 한 줄 + 2줄, 둘째 줄 노랑)로 다시 만든다. hook의 photo·chips(둘째 칩 = 빨간 띠)·basis(없으면 sub)·lines를 쓰고, 원고 맨 위 `"thumb": {"badge": "11/4 마감", "lines": [...], "basis": ...}`로 덮어쓸 수 있다. 사진이 없으면 첫 프레임 사본 그대로. 단독 실행: `python3 thumb.py thumbs/<slug>.json`.
- ⭐ 이야기 장면 `beat` (2026-10-27 릴스 재구성 — 슬라이드형 표 대신 이야기형): `{"type": "beat", "eyebrow": "가격", "big": "4억 8,600만원", "big_sub": "43㎡ 최고가", "highlight": "4억 8,600만원", "say": "<그 장면 내레이션 대본 그대로>", "bg": "photos/…jpg 또는 maps/…png 또는 none", "bg_credit": "…", "bg_pos": "center 40%"}` — 풀화면 배경(사진은 천천히 흐름, 네이버 지도는 핀 쪽으로 확대·출처 자동) 위에 숫자·핵심어 하나를 크게(`big`, 한 줄, 넘치면 자동 축소, 줄을 나누려면 `\n`), 아래에 `say` 자막이 음성에 맞춰 단어별로 켜짐(숫자 든 단어는 강조색). 원고 맨 위에 `"bg"`·`"bg_credit"`을 주면 배경 없는 beat에 공통으로 깔림. hook도 `"bg": "maps/…png"`로 지도 확대 배경 가능. cta는 `"ask"`(댓글 질문·팔로우 한 줄) 추가 가능. 새 릴스는 hook → beat 3~4개 → cta가 기본 (points는 예전 형식 호환용).
- ⚡ **템포형 (2026-11-03 사용자 결정 — 상위 계정 10곳 비교: 1~2초마다 컷, 맨 위 고정 제목, 증거 화면)**: 원고 맨 위에 `"tempo": "fast"`와 `"title_bar": "SH 토지임대부 · 고덕강일3단지\n강동 신축 59㎡ 3억대 떴다"`(1~2줄, 줄당 18자 안팎, 둘째 줄은 강조색 — 영상 내내 맨 위 고정)를 넣는다. 그러면:
  - beat 배경 사진이 약 1.8초마다 다른 구도로 끊겨 바뀌고(컷), 장면이 바뀔 때 '휙'·숫자/카드가 나올 때 '톡' 효과음이 작게 들어간다 (`"sfx": false`로 끔, 효과음은 ffmpeg로 직접 만든 것).
  - 자막은 지금 말하는 구절(숨 단위)만 크게 화면 아래쪽에 나온다.
  - beat에 `"proof"`(증거 카드)를 넣을 수 있다 — 장면 30% 지점에 튀어나오고 그때 큰 숫자는 물러난다:
    · 비교 막대 `{"kind":"compare","head":"59㎡ 비교 (추정)","items":[{"label":"고덕강일3단지 건물분양가","value":"3억9,050만원"},{"label":"옆 강동리버스트8단지 실거래","value":"13억원"}],"src":"국토부 실거래가 2026.09"}` — 첫 줄이 이 단지(강조색). 막대 길이는 value 숫자로 자동(억·만 단위 읽음, 직접 주려면 `"n"`). 숫자는 '청약조사' H열 근거 그대로.
    · 공고문 요약 메모 `{"kind":"doc","head":"고덕강일3단지","lines":["59㎡ 건물분양가 3억9,050만원","월 토지임대료 51만1,500원","거주의무 5년 · 전매 10년"],"mark":1,"src":"출처: SH 입주자모집공고"}` — '공고문 요약' 딱지가 붙은 우리 메모(진짜 공고문 캡처처럼 꾸미지 않음), mark 줄에 형광펜.
    · 그림 `{"kind":"image","img":"photos/site/<key>/plan-….jpg","credit":"이미지: <사업주체> 분양 홈페이지 · 실제와 다를 수 있음"}` — 평면도·조감도·동호배치도.
  - 단지 소개 릴스의 beat 배경은 그 단지 자료(홈페이지 사진·조감도·네이버 지도)만 — 단지와 상관없는 분위기 사진은 hook 표지 말고는 쓰지 않는다 (없으면 `"bg": "none"` + proof 카드).
- 장면: `hook`(첫 프레임부터 훅이 보임 — 1초 룰, lines의 `{n}` 자리에 `count.to` 숫자가 강조 펄스), `points`(rows 2~4개, text 선택), `cta`. 1080×1920. 핵심 내용은 세로 가운데(피드 4:5 영역 y≈285~1635)에 모으고, 위 300px·아래 420px·오른쪽 140px(인스타 버튼 자리)는 비운다 — 2026-10-25 "너무 위로 몰림" 피드백 반영.
- 훅 장면 실사 배경: hook에 `"photo"`, `"photo_credit"`(카드 표지와 같은 값), 선택 `"photo_pos"`를 넣으면 위쪽에 단지 사진이 천천히 확대되고 글자는 아래로 내려간다 (종이 캐릭터는 숨김). 표지 cover.jpg에도 사진이 들어간다.
- 평면도 장면: `{"type": "plan", "eyebrow", "title", "image", "rows"(최대 2개, 한 줄 요약으로 표시), "credit"}` — ③ 원고에 평면도 장면이 있을 때만 (장면 수 = 대본 블록 수 유지).
- 호흡 (2026-10-27, 오싹알람 규칙 적용): 내레이션 대본(Z열)의 쉼표·말줄임표 = '여기서 숨 쉰다'. 시트 스크립트가 [pause short]로 바꿔 Chirp3-HD 목소리로 읽히고, reel.py가 실제 쉼 위치에 맞춰 단어 자막을 켠다. 쉼이 대본과 다르면 warnings에 `호흡:`이 나온다 (영상은 만들어짐 — ③ 대본 쉼표 위치 문제).
- 내레이션 이어 붙이기 (2026-11-03 "대사가 쉬는 부분이 많다"): reel.py가 음성 앞뒤 무음을 잘라 장면을 말 길이에 딱 맞춘다(장면 사이 숨 약 0.4초, 장면 기본 길이 5초 무시). 시트 스크립트가 대본 전체를 한 번에 읽힌 `voices/<id>/full.mp3`도 올리면 그걸 장면 경계(가장 긴 쉼)에서 잘라 써서 장면이 바뀌어도 말투가 이어진다 (없으면 장면별 파일).
- 내레이션: 원고에 `"voice": "voices/<id>/"` (시트 '오늘의 발행 플랜' AA열 값)을 넣으면 `voices/<id>/01.mp3`… 를 장면 순서대로 붙이고, 장면 길이를 음성에 맞춰 늘리고, 종이 캐릭터 입을 음성 크기에 맞춰 움직인다. 음성은 시트 스크립트가 Z열 대본(장면마다 `---`로 구분)으로 구글 TTS를 돌려 올린다. 렌더링 전 `git pull --rebase origin main`.
- 올리기: `git add reels && git commit -m "reels: <slug>" && git push origin HEAD:main` (`reel.html`은 올리지 않음). S열에 `manifest.json`의 video, cover 주소를 줄바꿈으로 → 시트 스크립트가 릴스로 게시.

## 사이트 (jupjupalarm.com) — `site/`
- `python3 site/build.py` → `site/public/` (Cloudflare Pages 배포). 데이터·규칙은 `site/README.md`.
- 카드·릴스 작업 때 `site/`는 건드리지 않는다 (⑦ SEO 발행 담당 영역).
