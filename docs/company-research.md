# 회사 조사 파이프라인

회사명 하나로 "회사 문서 묶음"을 만드는 과정이다. 계약은 `docs/contract.md` 3.5, 3.6, 6장이 기준이다.

## 쓰는 법

Claude Code에서 `company-research` 스킬에 회사명(한글·영문)을 주고, 원하면 직무를 덧붙인다 (기본 Product Designer). 예: `예시회사 조사해줘`, `샘플페이 UX Designer`. `apply <회사명>`을 쓰면 이 단계가 맨 앞에서 자동으로 돈다. 공고 한 건만 넣으려면 `jd-intake`에 URL이나 텍스트를 준다.

## 흐름

1. slug와 tier를 정한다 (소문자 ASCII).
2. 에이전트 4종을 병렬로 호출한다. 각자 `companies/<slug>/parts/`에 조각을 쓴다.
   - `company-careers`: 채용 사이트, ATS 판별, 열린 디자인 공고와 JD 원문
   - `company-design-blog`: 디자인·기술 블로그, 발표·인터뷰, 회사가 쓰는 용어
   - `company-business`: 개요, 제품, 최근 18개월 이슈, AI 전략, 인재상
   - `company-hiring-process`: 전형, 서류 형식·용량, 자기소개서, 과제·면접, AI 심사 공개 여부
3. 조각을 `templates/dossier.md` 틀로 합쳐 `dossier.md`를 쓰고, `vocab.yaml`, `sources.md`, `meta.yaml`, `jd/<tier>/<slug>__*.md`를 만든다.
4. "이 지원자와의 접점"에서 회사 요구를 `profile/facts.yaml`의 fact id와 연결한다. 근거 없는 항목은 공백으로 둔다.
5. JD마다 `python -m harness jd <파일> --json`(저장 직후, 종료 코드 0 필수)과 `gaps`를 돌린다.

## 지키는 것

- 공개 웹 읽기만 한다. 로그인, 지원, 제출, 연락은 하지 않는다.
- 검색어와 에이전트 입력에 지원자 이름·문서·경력을 넣지 않는다.
- 사실 주장에는 `[확인]`/`[보도]`/`[추정]`과 URL을 붙이고, 못 찾으면 못 찾았다고 쓴다.
- 이메일 주소와 전화번호는 어떤 파일에도 쓰지 않는다 (회사·채용·홍보 연락처 포함).
- 연봉, 비공개 정보는 쓰지 않는다. 인용은 한 문장 이하.
- 접점 섹션은 사실 은행에 있는 것만 연결한다. 이 결과는 합격 가능성이 아니라 근거 정리다.

## 한계

웹 검색 결과에 의존하므로 빠진 글이 있을 수 있고, 채용 페이지가 동적 렌더링이면 공고 본문을 못 읽을 수 있다 (그 경우 dossier에 "읽지 못함"으로 표시한다). 영상 발표는 텍스트 설명만 근거로 쓴다.

## 품질 체크리스트

`company-research` 스킬의 "품질 체크리스트"에 명령이 있다. 커밋 전에 모두 통과해야 한다: PII grep(이메일·전화번호)이 아무것도 출력하지 않음, `sources.md`의 URL 8개 이상, dossier 9개 섹션이 모두 있고 비어 있지 않음, `vocab.yaml`의 concept id가 `taxonomy/skills.yaml`·`taxonomy/job_families.yaml`에 존재, 모든 JD가 `python -m harness jd <파일> --json`에서 종료 코드 0. 그 밖에 1차 채용 출처 1개 이상, 모든 출처에 접근일, dossier의 모든 숫자가 `sources.md` 출처 페이지에 실제로 적혀 있음.
