# 학식 크롤링 장애 원인 및 복구

## 확인된 원인

기존 Selenium 크롤러가 의존하던 포털 DOM이 개편됐고, GitHub Actions의
브라우저 실행에서는 STCLab `Access Denied (Code 71)` 페이지로 이동했다.
DOM 선택자와 User-Agent 수정만으로는 운영 크롤링이 복구되지 않았다.
그 이전 크롤러는 빈 결과를 성공으로 취급해 Firestore 문서를 `{}`로
덮어쓸 수 있었고, 앱은 이를 읽어도 표시할 메뉴가 없었다.

- [DOM 수정 후 실패 실행](https://github.com/HipstuCAU/nyam_nyam_crawler/actions/runs/34134433591)
- [페이지 진단 추가 후 실패 실행](https://github.com/HipstuCAU/nyam_nyam_crawler/actions/runs/34134627394)

## API 요청 계약

[포털의 p005.js](https://mportal2.cau.ac.kr/common/js/system/portlet/p005/p005.js)의
`p005List`는 `$http.post('/portlet/p005/p005.ajax', params)`로 식단을 조회한다.
폼 인코딩 요청은 HTTP 200이라도 오류 HTML을 반환했고, 동일 필드를
`Content-Type: application/json`으로 보내면 실제 식단 JSON을 반환했다.

```http
POST https://mportal2.cau.ac.kr/portlet/p005/p005.ajax
Content-Type: application/json

{"tabs":"1","tabs2":"20","daily":0}
```

`tabs=1/2`는 서울/다빈치, `tabs2=10/20/40`은 조식/중식/석식이며
`daily`는 한국 날짜 기준 일수 차이다. 주말 미등록 메뉴의
`menuDetail: null`은 정상 응답으로 확인돼 해당 메뉴만 제외한다.
재시도는 일시적인 HTTP 오류에 한정하며 인증이나 브라우저 챌린지를 우회하지 않는다.

## 반영된 수정

### 9월 8일 재실행에서 확인된 미등록 응답

[운영 재실행 34135962684](https://github.com/HipstuCAU/nyam_nyam_crawler/actions/runs/34135962684)은
9월 8일 00:00 KST 이후 조회 범위에 9월 14일이 포함되면서 실패했다.
`tabs=1,tabs2=10,daily=6` 응답은 `isEmpty: "Y"`지만 `list`가 비어 있지 않고,
식당명과 날짜만 있는 행(`menuDetail`, `camp`, `course` 등은 null)을 포함했다.
`isEmpty=Y`이면 리스트가 무조건 비어야 한다는 검증이 실제 API 계약과 달랐다.

이번 전체 수정 PR은 날짜와 식당 메타데이터를 검사한 다음 null 메뉴 행을 건너뛴다.
메뉴가 있는 행의 캠퍼스·식사시간 검증은 유지한다. Y 표시와 실제 메뉴 내용이
충돌하면 계속 실패하며 전체 결과가 비었을 때 게시하지 않는 방어도 유지한다.
독립 리뷰에서 발견한 `--days 1` 실행의 불완전한 운영 문서 덮어쓰기 위험은
7일 미만 수집 시 `--no-upload`를 요구하도록 수정했다.

### API 전환 및 develop 직접 반영 원복

[ce87002](https://github.com/HipstuCAU/nyam_nyam_crawler/commit/ce8700201db52dc96c25097de13ff5e0f784b6f4)
수정이 먼저 `develop`에 직접 반영되어 기존 PR #21에는 일부 보완만 보였다.
이를 바로잡기 위해 `25a9690`, `3932b48`, `ce87002`, 자동 데이터 커밋
`7083a51`을 역순으로 원복한
[fd0a3a4](https://github.com/HipstuCAU/nyam_nyam_crawler/commit/fd0a3a4)를
`develop`에 반영했다. 원복 직후 tracked tree는 수정 전 `d2d1eed`와 동일하다.
force push나 과거 기록 삭제는 하지 않았다. 사용자 작업 중인 원본 checkout과
Firestore의 마지막 정상 운영 데이터는 변경하지 않았다.

새 `fix/cau-menu-api-crawler` 브랜치는 원복 커밋에서 시작한다. 아래 API 전환,
미등록 응답 처리, 회귀 테스트, DTO 결과, 운영/PR 워크플로를 모두 PR diff에 담는다.

- Chrome/Selenium을 제거하고 JSON API를 호출한다.
- HTTP 200 오류 HTML, 필수 필드 누락, 요청과 응답의 캠퍼스/날짜/식사시간
  불일치, 중복 코스 충돌을 실패 처리한다.
- 42개 요청을 모두 마친 뒤 DTO를 저장한다. 전체 빈 결과는 게시하지 않는다.
- 앱 계약 `캠퍼스 → 날짜 → 식사시간 → 식당 → 코스 → {time, price, menu}`를 유지한다.
- `(다빈치)` 식당명을 유지해 기존 Swift enum 매핑과 맞춘다.
- Firestore에 저장한 DTO를 다시 읽어 동일함을 확인한다.
- 모든 성공 실행의 결과 JSON을 `CAUMealData-DTO` 아티팩트로 남긴다.

## 검증 근거

2026-09-08 KST 재검증 스냅샷은 서울 77개, 다빈치 57개, 총 134개 메뉴다.
조회 범위는 9/8~9/14이며 미등록인 9/14는 제외되어 캠퍼스별 6일 데이터가 있다.
단위 테스트는 17개다. 실시간 메뉴 수는 학교의 등록 상태와 실행 날짜에 따라 달라진다.

### 최초 운영 복구의 과거 검증 기록

2026-09-07 기준 서울 95개, 다빈치 69개, 총 164개 메뉴(9/7~9/13)를 확인했다.
이 숫자는 해당 실행의 스냅샷이며 이후 날짜의 실행 결과는 달라질 수 있다.

- [수정 브랜치 API 검증 성공](https://github.com/HipstuCAU/nyam_nyam_crawler/actions/runs/34135635530)
- [운영 수집·Firestore 재조회·데이터 커밋 성공](https://github.com/HipstuCAU/nyam_nyam_crawler/actions/runs/34135763260)
- 로컬/러너 DTO의 바이트 일치 확인.
- 실제 iOS `DataManager.swift` 및 모델 소스와 `SwiftDTOCheck.swift`를
  컴파일해 164개 메뉴 파싱, 미인식 식당 0개, 캠퍼스별 7일 화면 데이터 구성 확인.
  실제 iPhone 화면 렌더링을 실행한 검증은 아니다.

## 실행 및 운영

```bash
python -m unittest discover -s Crawler -v
python Crawler/main.py --no-upload --output Crawler/Doc/CAUMealData.api.json
```

`ValidateCrawler.yml`의 PR 실행은 읽기 전용 권한으로 테스트·실시간 수집·DTO
아티팩트 생성만 수행한다. Firebase secret을 참조하지 않으며 Firestore와
`develop`에는 쓰지 않는다. PR 검증 대기열과 워크플로를 운영과 분리했다.

**원복 기간에는 `RunCrawler.yml`을 GitHub 설정에서 일시 중지했다.** 예전 코드의
push/예약 실행이 빈 DTO를 운영에 게시할 수 있기 때문이다. 이 PR은 자동 병합하지
않으며 운영을 재개하지 않는다. 병합 전에는 운영 데이터가 자동 갱신되지 않는다.

리뷰와 PR 검증을 완료하고 **이 PR이 develop에 병합된 뒤에만** 운영을 재개한다:

```bash
gh workflow enable RunCrawler.yml
gh workflow run RunCrawler.yml --ref develop -f publish=true
```

첫 운영 실행에서 DTO 아티팩트, `Firestore verified` 로그, 데이터 커밋 성공을 확인한다.
수동 실행은 기본적으로 게시하지 않으며 `develop`에서 `publish=true`일 때만 게시한다.
예약 실행과 `develop` push 실행은 수집·검증에 성공하면 게시한다.

장애로 코드를 다시 원복해야 할 때도 운영 워크플로를 먼저 중지하고 마지막 정상
Firestore 문서를 유지한다. Git의 빈 과거 DTO를 Firestore로 복원하면 안 된다.
