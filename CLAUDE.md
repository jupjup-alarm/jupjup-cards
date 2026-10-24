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

## 원고(JSON) 형식
```json
{
  "slug": "2026-10-24-gyeonggi-happyhouse",      // 영문 소문자·숫자·하이픈만 (주소에 들어감)
  "title": "단지명",
  "series": "임대알람",                          // 줍줍알람 | 강남로또 | 내집마련 | 임대알람 | 주거꿀팁
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
- info: `rows`는 2~4개. 값이 길면 줄바꿈된다. `title`은 문자열 또는 줄 배열.
- check: `items` 최대 3개.
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
git add specs cards && git commit -m "cards: <slug>" && git push origin HEAD:main
```
main에 푸시가 거절되면 `cards` 브랜치에 푸시하고 `CARDS_BRANCH=cards`로 다시 렌더링해 주소를 맞춘다.
