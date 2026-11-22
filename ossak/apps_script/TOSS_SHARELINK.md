# 클로드 코드 작업 지시서 — 토스 쉐어링크 연동 (맥북)

작성 2026-11-22 · 대상: 정대장 님 맥북의 Claude Code · 관련: `HOTDEAL_CAPTURE.md`, `KAKAO_OVERRIDES.md`
근거 문서: https://sharelink-docs.toss.im/developers/open-api (auth · convention · api/link · api/product-detail · glossary · precautions · disclosure)

## 0. 왜 맥에서 하나
- 토스 쉐어링크 Open API는 **등록한 출발지 IP에서만** 호출된다 (사업자당 IP·대역 10개, 등록 IP가 없으면 전부 차단).
- 구글 Apps Script는 출발지 IP가 정해져 있지 않아 쓸 수 없다. **맥(집 인터넷)에서만** 부른다.
- 맥북을 다른 와이파이(카페 등)에서 쓰면 IP가 바뀌어 `SHARELINK_OPENAPI_ACCESS_DENIED`가 난다. 그때는 조용히 건너뛰고 로그에 남긴다 (사람이 IP를 다시 등록할 때까지).

## 1. 정대장 님이 먼저 할 것
1. `sharelink.toss.im` → 연동 → **API 키 발급** → Access Key / Secret Key. 맥 `.env`에 `TOSS_ACCESS_KEY`, `TOSS_SECRET_KEY` (커밋·로그 금지).
2. 같은 어드민에서 **회원 연동 ID(publisherId, UUID)** → `.env`의 `TOSS_PUBLISHER_ID`.
3. **출발지 IP 등록**: 맥에서 `curl -s https://api.ipify.org`로 나온 집 공인 IP 하나를 등록.
4. (선택) subTag `threads01`·`kakao01` 등록 — 채널별 실적 구분용. 등록 후 바꿀 수 없다.

## 2. API 요약 (이것만 쓴다)
- 토큰: `POST https://oauth2.cert.toss.im/token` (form) `grant_type=client_credentials`, `client_id`, `client_secret`, `scope=sharelink:read sharelink:write` → `access_token`(약 1년). **파일에 저장해 재사용**, 매번 받지 않는다.
- 연결 확인: `GET https://sharelink.toss.im/openapi/health`
- 링크 발급: `POST https://sharelink.toss.im/openapi/links` (JSON) `{"publisherId": "...", "tacaId": 9876, "subTagId": "kakao01"}` → `success.shortUrl`(`https://toss.im/_m/…`), `success.originUrl`.
  - 같은 조합으로 다시 부르면 기존 링크를 돌려준다(한도 차감 없음). 링크 캐시는 7일.
- 응답은 HTTP 200이어도 `resultType: "FAIL"`이면 실패. `ACCESS_DENIED`(키·IP), `QUOTA_EXCEEDED`, `PARTNER_NOT_AUTHORIZED`는 재시도하지 않는다. 429면 `Retry-After`만큼 쉰다.
- **상품 상세·목록 API는 쓰지 않는다** — 토스쇼핑 인증(거래액이 생긴 뒤 메일 신청)이 있어야 한다. 인증이 나오면 그때 추가한다.

## 3. 남의 토스 링크 → 내 쉐어링크
- 토스는 "남의 토스 링크를 내 링크로 바꾸는 기능"을 주지 않는다. 대신 **상품 번호(tacaId)로 내 링크를 새로 발급**한다.
- 수집 글의 토스 링크(`toss.im/_m/…`, `toss.shopping/…`)는 쿠팡 단축 링크처럼 **이동 주소(Location)만 읽어** `toss.shopping/t/{숫자}`를 얻는다. 그 숫자가 `tacaId`다 (glossary 확인). 남의 링크를 브라우저로 열지 않는다. 꼬리(`k=…`, `referrer=…`)는 버린다.
- `tacaId`로 발급하면 토스가 그 상품의 **대표 옵션**으로 링크를 만든다. 옵션이 여러 개인 상품은 글의 옵션과 다를 수 있다 → 메시지에 옵션을 단정하지 않는다.
- `tacaId`를 못 얻으면 → 스킵 (`스킵: 토스 상품 번호 없음`). 남의 링크를 그대로 보내지 않는다.

## 4. 시트 — 새 열 V '토스링크'
- 수집기가 토스 링크도 G열에 넣거나(쿠팡과 줄바꿈으로 섞여도 됨), 본문(K열)에 있는 토스 링크를 읽는다. 수집기 수정이 필요하면 최소로: 토스 링크도 G열에 줄바꿈으로 덧붙이고 '쇼핑몰'에 `토스`를 쓴다.
- 발급 결과를 **V열**에 `toss.shopping/t/{tacaId} → https://toss.im/_m/…` 형식으로 적는다. 실패면 `없음: 사유`. (W열 이후는 비워 둔다.)
- V1 헤더 `토스링크`.

## 5. 어디에 보내나 — 처음엔 카톡방만
- **토스 딜은 카톡방에만** 보낸다 (KAKAO_SCOPE=all 규칙대로, 일반 딜 템플릿).
- **스레드에는 올리지 않는다.** 이유: 토스는 모든 게시물 첫머리에 '수수료를 받는다'는 문구를 요구하고(없으면 수익 지급 보류·계약 해지), 지금 스레드 본문은 광고 문구를 빼기로 했다. 스레드에도 올리려면 본문 첫 줄에 짧은 문구를 넣는 결정이 먼저 필요하다 — 정대장 님 결정 사항.
- **수량 역전 판단·캡처는 하지 않는다.** 토스는 '가격 크롤링'을 막고 이미지 크롭·편집을 금지한다. 토스 상품 페이지를 ego lite로 열지 않는다. 가격·상품명은 수집 글(C·D·K열) 숫자만 쓴다.

## 6. 카톡 메시지 — 토스 문구 (쿠팡 문구와 다르다)
- **맨 위**에 토스 권장 문구를 그대로:
  `이 콘텐츠는 토스쇼핑 쉐어링크 활동의 일환으로, 링크를 통한 구매가 발생하면 일정 수수료를 지급받습니다.`
- 쿠팡 문구("이 포스팅은 쿠팡 파트너스 활동의 일환으로…")를 토스 딜에 쓰지 않는다. 한 메시지에 두 쇼핑몰을 섞지 않는다.
- 순서: 수수료 문구 → 상품 소개 → 내 쉐어링크 (토스 가이드 순서).
- 상품 이미지를 직접 붙이지 않는다 (카톡 링크 미리보기 카드는 괜찮다).
- 금지: 클릭 보상("누르면 포인트"), 과장·허위, 의료기기·건강식품 효능 문구.

## 7. 완료 기준
1. `--dry-run`에서 토스 링크가 있는 행의 `tacaId`, 발급된 `shortUrl`, 메시지 전문이 나온다.
2. 실제 1건: V열 기록 → 카톡방에 토스 문구가 맨 위인 메시지 → S열 처리.
3. 남의 토스 링크를 브라우저로 연 기록이 없다 (Location만 읽음).
4. IP가 다른 와이파이에서 돌리면 `ACCESS_DENIED`로 건너뛰고 로그에 남는다 (죽지 않음).
5. 토큰을 실행마다 새로 받지 않는다 (파일 캐시).
6. 키·토큰이 커밋·로그·시트에 없다.
