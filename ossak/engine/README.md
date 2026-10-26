# 오싹알람 제작 엔진 (클라우드용)

오싹알람(@ossak_alarm) 인스타툰 한 편을 콘티 → 그림 → 조판 → 발행 준비까지 만드는 도구.
매일 클라우드 예약 작업 '오싹알람 새 편 제작'이 이 문서대로 한 편을 만든다.

## 구성
- `ossak/mk.py` story.json → episode.json (컷 ID·크기·말머리 색 자동)
- `ossak/cf.py` Cloudflare Workers AI FLUX.2 klein(무료)으로 컷 생성. 키는 환경변수 `CF_ACCOUNT_ID`, `CF_API_TOKEN`
- `ossak/compose.py` 1080×1350 조판 → `slides/NN.png`
- `ossak/finish.py` 저장소 `ossak/<편>/NN.jpg` 생성, `preview.jpg`, 발행계획 행 `rows.json`
- `ossak/render.py`, `ossak/batch.py` Gemini(유료) — 사용자가 승인했을 때만
- `fonts/` 고운바탕·개구·Noto Sans KR(OFL), `refs/boogi_sheet.png` 부기 캐릭터 시트
- `episodes/<ID>-<slug>/` story.json·episode.json (그림·슬라이드 PNG는 커밋하지 않음)

## 운영시트
구글 시트 '오싹알람 운영시트' (id `1ja_unOCU24nFAGhJpm9FkAl-QmkMlKnOUvrcNFI_UPE`)
- 소재조사: ID | 말머리 | 사건명 | 연도 | 국가 | 표지 훅 | 디테일 | 리스크 | 상태(조사중→콘티→그림→완성→발행) | 출처 | 메모
- 조사노트: ID | 순번 | 사실 문장 | 등급(A/B/C) | 출처 URL | 주의
- 발행계획: 발행일 | 시각 | 채널 | 편ID | 말머리 | 제목 | 훅 | 리스크 | 상태 | 인스타 캡션 | 스레드 본문(--- 구분) | 이미지 URL(줄마다) | 장수(수식, 쓰지 않음) | 게시 ID… (N열부터는 시트 스크립트가 채움)
- 설정: B15 Cloudflare 계정 ID, B16 Cloudflare 토큰

## 하루 한 편 만들기
1. 시트 '설정' B15·B16 값을 읽어 `export CF_ACCOUNT_ID=… CF_API_TOKEN=…` (값을 출력하지 않는다).
2. 소재 고르기: '소재조사'에서 상태 '조사중' 중 '조사노트' 사실이 충분하고 훅·핵심 사실이 A/B인 것 1개.
   말머리 비중(세계기담30·새벽괴담30·미제파일20·그날의 기록15·그 후5)과 최근 발행계획의 말머리가 겹치지 않게 고른다.
   '지침로그' 최근 행의 방향을 반영한다.
3. 콘티: `episodes/<ID>-<영문slug>/story.json` 작성 (형식은 기존 편 story.json 참고, 14~17장, 최대 20).
   - 표지 훅: 평범한 설명으로 안 풀리는 디테일 1개 + 사람·숫자, 후보 3개 중 "1초 안에 평범한 답이 떠오르는가"로 걸러 선택. 2장 이후의 답·원인을 표지 글·그림에 쓰지 않는다.
   - 흐름: 발견 장면 → 장마다 사실 1 + 풀리지 않는 질문 1 → 복선 1개(나중에 panel 재사용으로 회수) → 7~10장 '이상한 점' 저장 카드(위 그림 + evidence 3칸) → 오답 목록 → 마지막 2~3장 답 한 방(텍스트 카드: 큰 문장 + → 3줄 + 확정 여부·출처) → 마지막 장에만 부기 "그때 ~했다면 어땠을까요?" + 열린 의문.
   - 문장: 설명문이 아니라 짧은 장면 묘사와 끊어 읽기, 장당 60자 안팎, 자막 2줄 이내. 사실을 지어내지 않는다. C등급은 "~라는 설도 있다"로만.
   - 그림 프롬프트(영문): 장면 하나를 구체적으로, 사람 없으면 "nop": true, 사람은 얼굴 없는 실루엣·멀리서·뒤에서. 피·시신·흉기 금지(빈 방·열린 문 같은 상징). 실존 인물 얼굴 금지. 글자 소품은 "blurred and unreadable".
   - 다루지 않음: 아동 피해, 성범죄, 자살·자해 중심, 재판 중·최근 국내 사건, 범행 수법 상세. 국내 피해자 실명·용의자 암시 금지.
   - caption(첫 줄 훅, 본문 2~3줄, "당신의 가설은? 댓글로 알려주세요.", 출처, 해시태그 2개), threads(반말, 첫 글 훅 + 3~4개 + 마지막 "풀버전은 인스타에 @ossak_alarm", 글당 500자 이내), reels_script.
   - next: 발행계획에서 이 편 바로 다음 날 캐러셀의 표지 훅 (없으면 "다음 편도 내일 밤 9시 30분에 공개됩니다").
4. `python3 ossak/mk.py episodes/<편>` → `python3 ossak/cf.py episodes/<편>` (하루 무료 한도 약 90장, 한 편 20~23장).
   429·한도 초과면 `--model schnell`로 남은 컷을 그리거나 다음 날로 미룬다.
5. 컷 검수: `panels/*.jpg`를 직접 열어 본다(축소 시트로 한 번에). 검은 띠·엉뚱한 사람·얼굴·글자·흉기·구도 불일치는 프롬프트를 고쳐 `--only <id> --force`.
6. `python3 ossak/compose.py episodes/<편>` → `python3 ossak/finish.py episodes/<편> --date <발행일>`
   - 발행일 = 발행계획의 마지막 '인스타 캐러셀' 날짜 + 1일.
   - `preview.jpg`를 열어 자막 겹침·넘침·그림-자막 불일치를 확인하고 고친다.
7. 자동 검수(하나라도 걸리면 발행계획에 넣지 않고 소재조사 상태를 '폐기' 또는 '콘티'로 두고 사유를 메모):
   훅·제목 사실 A/B / 국내 피해자 실명·특정 정보 없음 / 용의자·무죄자 실명·암시 없음 / 피·시신·흉기 직접 묘사 없음 / 실존 인물 닮은 얼굴 없음 / 출처 표기 / 피해자 조롱·가해자 미화 없음.
8. 저장소에 올리기: `git -C <repo> pull --rebase origin main` → `git add ossak/<편> ossak/engine/episodes/<편>/story.json ossak/engine/episodes/<편>/episode.json` → 커밋 → `git push origin HEAD:main`.
   올린 뒤 이미지 주소 하나를 curl로 열어 200인지 확인.
9. 시트: `rows.json` 두 행을 '발행계획' 마지막 행 다음 A:L에 쓴다(M열 이후는 비움). '소재조사' 해당 행 상태를 '완성'으로.
10. 한두 줄로 보고: 편 ID, 표지 훅, 발행일, 장수.
