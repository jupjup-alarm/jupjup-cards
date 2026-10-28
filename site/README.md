# jupjupalarm.com 사이트 (⑦ SEO 발행 담당용)

정적 사이트. `python3 site/build.py` → `site/public/` → Cloudflare Pages가 그대로 배포 (빌드 명령 없음, 출력 폴더 `site/public`, 감시 경로 `site/**`).

## 매일 하는 일 (⑦)
1. `git pull --rebase origin main`
2. '청약홈API' 탭 전체를 `site/data/applyhome.json`의 `rows`로 덮어쓰기 (열 이름 = 시트 머리글, `fetched_at` = A열 값).
3. 새 공고마다 `site/data/apt/{주택관리번호}.json` 작성 — 형식은 기존 파일 참고. 사실은 '청약조사' 탭·청약홈API 값만.
   - 필수: `title, kind, region{sido,sigungu}, take(한마디 2줄+), who, eligibility(행 배열), faq(3개+), account`
   - 선택: `photo{image,credit,alt,pos}`(AA·X열), `map`(Y열), `coords`(Z열 [경도,위도]), `plans[{type,image,alt}]`(AC열 — 반드시 이미지를 열어 타입 확인), `areas`, `gap`(H열에 근거 단지가 있을 때만), `schedule`(자동 일정이 틀릴 때), `info_extra`, `sources_extra`, `related_extra`
   - 문장 속 날짜는 `{d:2026-11-02}` · `{r:2026-11-02:2026-11-03}`로 쓰면 '11.2(월)' 형식으로 바뀜.
   - 확인 못 한 자격은 `["항목", "공고문 기준 적용", "공고문 확인"]`.
   - 한마디·FAQ는 공고마다 새로 쓴다(템플릿 문장 돌려쓰기 금지). 차익은 근거 단지가 있을 때만 '약 O억 저렴(추정)'.
4. 시·군·구가 `site/data/regions.json`에 없으면 로마자 슬러그를 추가 (한 번 정하면 안 바꿈).
5. `python3 site/build.py` — 종료 코드 1이면 푸시하지 말고 `site/build-report.json`의 errors를 보고.
6. `git add site && git commit -m "site: 새 N · 고침 N" && git push origin HEAD:main`

## 규칙
- 공개한 공고 파일은 지우지 않는다. 취소된 공고는 `"status_override": "announced"` 등으로 둔다.
- 주소를 옮길 때만 `site/data/redirects.json`에 `["/옛주소/", "/새주소/"]`를 추가 (301).
- `state.json`은 빌드가 관리 (첫 공개일·내용 지문). 손대지 않는다.
- 디자인·표기 규칙: '줍줍알람 사이트 디자인 방향' 문서. 날짜는 11.2(월), 다른 해는 2027.2.16(화), 월만 2029.10.
