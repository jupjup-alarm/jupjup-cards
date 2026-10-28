# jupjupalarm.com 사이트 (⑦ SEO 발행 담당용)

정적 사이트. `python3 site/build.py` → `site/public/` → Cloudflare Pages가 그대로 배포 (빌드 명령 없음, 출력 폴더 `site/public`, 감시 경로 `site/**`).

## 매일 하는 일 (⑦)
1. `git pull --rebase origin main`
2. '청약홈API' 탭 전체를 `site/data/applyhome.json`의 `rows`로 덮어쓰기 (열 이름 = 시트 머리글, `fetched_at` = A열 값).
3. 새 공고마다 `site/data/apt/{주택관리번호}.json` 작성 — 형식은 기존 파일 참고. 사실은 '청약조사' 탭·청약홈API 값만.
   - 필수: `title, kind, region{sido,sigungu}, take(한마디 2줄+), who, eligibility(행 배열), faq(3개+), account`
   - `aliases`: '청약조사' C열 단지명과 '오늘의 발행 플랜' C열 단지명이 title과 다르면 넣는다 (시트 스크립트가 스레드 링크·DM에서 이 이름으로 페이지를 찾음 — `public/links.json`).
   - 선택: `photo{image,credit,alt,pos}`(AA·X열), `map`(Y열), `coords`(Z열 [경도,위도]), `plans[{type,image,alt}]`(AC열 — 반드시 이미지를 열어 타입 확인), `areas`, `gap`(H열에 근거 단지가 있을 때만), `schedule`(자동 일정이 틀릴 때), `info_extra`, `sources_extra`, `related_extra`
   - 문장 속 날짜는 `{d:2026-11-02}` · `{r:2026-11-02:2026-11-03}`로 쓰면 '11.2(월)' 형식으로 바뀜.
   - 확인 못 한 자격은 `["항목", "공고문 기준 적용", "공고문 확인"]`.
   - 한마디·FAQ는 공고마다 새로 쓴다(템플릿 문장 돌려쓰기 금지). 차익은 근거 단지가 있을 때만 '약 O억 저렴(추정)'.
4. 시·군·구가 `site/data/regions.json`에 없으면 로마자 슬러그를 추가 (한 번 정하면 안 바꿈).
5. `python3 site/build.py` — 종료 코드 1이면 푸시하지 말고 `site/build-report.json`의 errors를 보고.
6. `git add site && git commit -m "site: 새 N · 고침 N" && git push origin HEAD:main`

## 임대·공고 전·배치도 (2026-10-28 추가)
- **임대** (LH공고·마이홈공고 탭): 파일 이름·key = `lh{공고ID}` (LH공고 D열) 또는 `mh{공고ID}-{주택순번}` (마이홈 공고ID). `"kind": "rental"`, `"source": "lh"`, `"source_name": "LH청약플러스"`, `source_url`(공식 공고), `rcpt`, `announce`, `notice_date`, `schedule`(직접), `rent_models`[{type, target, excl, supply_area, units, deposit, monthly}] — 금액이 '공고문 참조'면 deposit·monthly 빼기. `rent_summary`{deposit, monthly, basis}는 마이홈 대표 조건(임대보증금·월임대료 열)일 때 basis에 "마이홈 대표 조건 · 주택형별 상이". 예시: `lh0000061190.json`(금액 있음), `lh2015122300020925.json`(계층별·금액 공고문 참조).
  - 단지 없이 여러 지역 다가구를 모집하는 매입임대·전세임대는 만들지 않는다 (단지·주소가 있는 공고만).
- **공고 전** (수도권, '청약조사'에서 청약홈 공고가 아직 없는 분양 단지): key = `pre-{영문 슬러그}`, `"pre": true`, 모든 값 보도 기준. `rcpt`(예정 접수일), `price_text`·`price_short`, `pre_rows`, `schedule`(note "예정 · 보도 기준"), `source_line`, `sources_extra` 필수. 예시: `pre-the-h-banpo-124.json`.
  - 공고가 나오면 새 공고 파일을 만들고, pre 파일에 `"moved_to": "{주택관리번호}"`를 추가한다. pre 페이지는 **지우지도 옮기지도 않는다** (사용자 결정 2026-10-28 — 이미 검색 상위에 있을 수 있음). 빌드가 자동으로: 배지 '공고 나옴', 제목 위 파란 CTA '공식 공고가 나왔어요 → 확정 분양가·청약 일정 보기', '예상과 실제 비교' 표(분양가·접수 시작·공급), 제목을 '… 예상 vs 실제 분양가 — 공고 전 전망 정리'로 바꾸고, 새 공고 페이지 출처에 이 페이지 링크를 단다. 목록에서는 빠지고 사이트맵에는 남는다.
  - 이때 pre 파일의 take·who·faq를 '공고 전 예상은 …였고 실제 공고는 …' 식의 비교·회고 문장으로 고쳐 쓴다 (새 공고 페이지와 같은 문장을 쓰지 않기 — 검색어가 겹치지 않게 이 페이지는 '예상·전망·비교'에 집중).
- **배치도·동호배치도**: '청약조사' AE·AG열 파일을 반드시 Read로 열어 확인한 뒤 `"layouts": [{"kind": "배치도", "image": "photos/layout-….jpg", "alt": "…"}]` (동호배치도는 kind "동호배치도"). 출처는 `image_credit_owner`. 공고당 이미지(조감도·평면도·배치도 합계) 최대 6장.

## 검색 키워드 (2026-10-29 추가 — 청약노트 블로그와 같은 네이버 API)
- 키: 구글 시트 '청약노트 블로그 운영'(id 1B20bC25MYQl5uHGCFx6_QQp2G_7AEJ-rTPTSbrM9d4E) '키' 탭 B2:B6 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, SEARCHAD_API_KEY, SEARCHAD_SECRET_KEY, SEARCHAD_CUSTOMER_ID). 세션 임시 폴더에 `KEY=VALUE` 파일(권한 600)로 만들어 `CHEONGYAK_ENV=그 경로`로 넘긴다. **값을 출력·커밋하지 않는다.** 끝나면 파일을 지운다.
- `python3 site/tools/keywords.py` → 키워드 파일이 없거나 7일 지난 공고만 조회해 `site/data/keywords/{key}.json`(월간 검색량 PC·모바일, 상위 8개는 블로그 문서 수, 단지명이 들어간 연관 키워드). 새 공고·고친 공고는 `python3 site/tools/keywords.py {key} …`로 바로 조회. 목록용 일반 키워드는 `--site`(월 1회).
- 빌드가 자동으로 쓰는 곳: ① 제목 단어 — 페이지에 실제로 있는 주제(분양가·청약 일정·평면도·경쟁률·줍줍·보증금·월세 …) 중 검색량 많은 2개 (발표 후엔 경쟁률 고정, 무순위는 줍줍 검색이 많으면 '무순위(줍줍)') ② 설명 끝 문장 ③ 검색량 50 이상 주제의 소제목 앞에 단지명 (최대 3개).
- `site/build-report.json`의 `seo_gaps` = 검색은 많은데(월 100+) 페이지에 없는 주제 (예: '고덕강일3단지 모델하우스 (2,020)'). 시트·공고문에 사실이 있으면 FAQ나 본문에 채우고, 없으면 그대로 둔다 (지어내지 않기). 모델하우스 위치는 공고문·공식 홈페이지에 있을 때만 `model_house` {"address": "…", "note": "…"}로 넣고 FAQ에 쓴다.
- FAQ 질문은 검색량 상위 롱테일 키워드의 말투로 쓴다 (예: '충정로역자이르네 줍줍 자격은?'). 검색량이 단지명 줄임말 쪽이 크면(`names`) `aliases`·`search_names`에 넣는다.
- 단지명 변형이 자동으로 안 잡히면(블록 번호 가운데 등) apt 파일에 `"search_names": ["시흥하중 신혼희망타운"]`을 넣고 다시 조회.

## 규칙
- 공개한 공고 파일은 지우지 않는다. 취소된 공고는 `"status_override": "announced"` 등으로 둔다.
- 주소를 옮길 때만 `site/data/redirects.json`에 `["/옛주소/", "/새주소/"]`를 추가 (301).
- `state.json`은 빌드가 관리 (첫 공개일·내용 지문). 손대지 않는다.
- 디자인·표기 규칙: '줍줍알람 사이트 디자인 방향' 문서. 날짜는 11.2(월), 다른 해는 2027.2.16(화), 월만 2029.10.
