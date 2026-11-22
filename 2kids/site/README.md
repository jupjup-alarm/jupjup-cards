# 투키즈노트 숙소 사이트 (kids.jupjupalarm.com)

검색용 정적 사이트. `python3 2kids/site/media.py`(새 숙소 사진·릴스) → `python3 2kids/site/build.py` → `2kids/site/public/` → Cloudflare Pages가 그대로 배포 (빌드 명령 없음, 출력 폴더 `2kids/site/public`, 감시 경로 `2kids/site/**`).
기획: 「투키즈노트 숙소 페이지 SEO 기획안」(2026-11-22, 사용자 결정 — 주소는 kids.jupjupalarm.com, 전부 자동화, 캐릭터 기준 판정).

- `autodm.jupjupalarm.com/2kids`(DM·댓글 안내용, noindex)는 그대로 둔다. 이 사이트의 예약 버튼은 `…/2kids/go/N?src=kids-top|kids-bottom`으로 보내 클릭 통계를 한곳에 모은다.
- `site/`(jupjupalarm.com)와 섞지 않는다.

## 입력
- `data/sheet/숙소후보.json` — 시트 '키즈노트(여행)' › 숙소후보 탭 전체 (`rows` = 머리글 → 값). 숙소명·지역·유형·테마·공식 홈페이지·가격 확인일·파트너스 링크·상태는 여기서 읽는다.
- `data/stays/T###.json` — 숙소별 정리. 상태가 '발행완료'이고 타깃이 '아이 부모'인 숙소(티켓 제외)마다 하나.

## 사진·영상 (media.py → media/<slug>/, 커밋)
- 사진: `2kids/travel/out/photos/T###/A_*.jpg`(릴스·스레드에 쓴 사진) 최대 6장, 없으면 `NN.jpg`. 출처는 시트 사진출처 탭(`data/sheet/사진출처.json`) — 페이지에 "사진: 공식 홈페이지 · 실제와 다를 수 있어요".
- 표지 순서: stays JSON의 `photo_order`(media의 p번호 순서, 첫 번째가 카드·공유 썸네일). 새 숙소는 접촉 시트로 보고 고른다.
- 릴스: `2kids/travel/out/T###-A.mp4`를 720×1280으로 줄인 `reel.mp4` + `poster.webp`. 인스타·유튜브 주소와 게시일은 `data/sheet/채널.json`(발행계획 L열·유튜브 G열).

## stays 형식
```json
{
 "id": "T005", "slug": "rapunzel-kids-poolvilla-gapyeong",      // slug는 한 번 정하면 안 바꿈 (주소)
 "one": "한 줄 정체 (숙소만의 사실 하나 포함)",
 "price_basis": "쿠팡 트래블, 11/18(수) 성인 2인, 키즈풀빌라 C·D·E 객실", "room_price": 79000,
 "required": [["미온수 (필수, 현장결제)", 60000]],                  // 객실가 외 필수 현장결제
 "base": 3, "max": 5, "extra_fee": 30000,                          // 모르면 null
 "kids_free": "미취학 아동은 추가 요금 무료",                         // 선택: 아이 추가요금 면제 조건
 "note4": "…", "price4": 178199,                                   // 선택: 이 객실로 넷이 못 묵을 때 넷이 묵는 객실 안내·가격
 "rooms": [["객실", "설명"]], "costs": [["항목", "내용"]], "info": [["항목", "내용"]],
 "kids": {"first": "첫째(공주·노래·춤) 기준 한 줄 또는 null", "second": "둘째(자동차·블록·공) 기준 또는 null", "pool": "수영장 기준 또는 null"},
 "fit": {"good": "이런 집에 맞아요", "bad": "이런 집은 다시 생각해요"},
 "faq": [["질문", "답"]],
 "checked": "2026-11-21"                                           // 공식 안내 정리일
}
```
- 사실·숫자는 `숙소후보` 메모, `2kids/travel/out/T###-*.json` 캡션 '📌 참고'·스레드 답글(✔️), `cheongyak-note/posts/T###-*/draft.md`에 있는 것만. 없으면 칸을 비운다 (추측 금지).
- 캐릭터(프로젝트 기억 '2kids-persona'): 만 5세 딸 쌍둥이 엄마, 서울 강동구, 중산층. 첫째 공주·감성·노래·춤 / 둘째 자동차·블록·공 / 둘 다 수영장. 해당 시설이 없으면 그 칸은 null.
- 방문 기록이 없으므로 '가 봤어요·다녀왔·써 봤·좋아했어요·실사용' 같은 체험 표현은 빌드가 막는다 (종료 코드 1).

## 빌드가 자동으로 하는 것
- 거리: 강동구 중심 ↔ 숙소 시·군 중심 직선거리 (통계청 경계), 70/150km로 구간 문장.
- 4인 실제 1박: 객실가 + 필수 현장결제 + (4 − 기준 인원) × 추가 요금. 미취학 무료·최대 인원 부족은 문장으로.
- 가격 구간: 15만원 미만 '부담 적은', 25만원 미만 '주말 특별', 그 이상 '기념일급'.
- 색인 조건 (못 채우면 noindex + 사이트맵 제외, `build-report.json`의 `noindex`에 이유): 확인한 사실(rooms+costs+info) 6줄 이상 · 캐릭터 판정 5칸 중 4칸 이상 · FAQ 2개 이상 · 가격 확인 60일 이내 · 파트너스 링크 있음.
- 화면 (2026-11-22 대장 "에어비앤비·마이리얼트립 홈처럼, 지도 빼고, 우리 채널 영상"): 홈 = 테마 탭(물놀이·키즈룸·온천·눈·스키·풀빌라·호캉스·가까운 1박·15만원 안쪽·제주·해외, 태그는 build.py `tags_of`) + 숙소 이름·지역 찾기 + 릴스 줄 + 테마 줄 + 사진 카드 격자. 숙소 페이지 = 사진 모음 + 예약 카드(넷이서 실제 1박) + 쌍둥이 체크 + 릴스 + FAQ. 지도 페이지 없음(/map/ → / 301).
- 디자인 원칙: elayadesign/redesign-skill 진단 기준을 우리 브랜드에 맞춤 — 글꼴 Pretendard 한 종(500·600·700, 빌드 때 쓰인 글자만 woff2로 잘라 넣음, fonttools 필요), 강조색 하나(#D4512F), 배경 그라데이션 없음, 아이콘 Phosphor(icons/, MIT).

## 배포 (처음 한 번 — 사용자)
Cloudflare Pages 새 프로젝트 → 이 저장소 연결 → 빌드 명령 없음, 출력 폴더 `2kids/site/public`, 프로덕션 브랜치 `main` → 사용자 지정 도메인 `kids.jupjupalarm.com` → 구글 서치콘솔·네이버 서치어드바이저에 등록하고 `sitemap.xml` 제출.
