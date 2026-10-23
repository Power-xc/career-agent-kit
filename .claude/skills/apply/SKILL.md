---
name: apply
description: 회사명 하나로 조사 → 공고 선택 → 맞춤 이력서 → 심사 시뮬레이션 → (선택) Figma 새 페이지 → 지원 패키지까지 한 번에 진행하는 진입점. "/apply 예시회사", "예시회사 지원 준비해 줘"처럼 회사 이름이 주어졌을 때 쓴다.
---

# apply: 회사명 → 맞춤 지원 패키지

## 입력

- 회사명 (필수, 예: `예시회사`)
- 선택: 직무 (예: `Senior Product Designer`), `--no-figma` (Figma 단계 생략)

## 출력

`out/<slug>/SUMMARY.md` 하나가 모든 산출물로 연결된다. 세부 산출물은 각 단계 스킬의 출력 (`companies/<slug>/`, `jd/<tier>/<slug>__*.md`, `out/<slug>/resume_*.yaml|pdf`, `figma_text.yaml`, `tailor_log.md`, `screening.md`, Figma 페이지와 PDF, `pack/`).

## 절대 규칙 (모든 단계에 적용, AGENTS.md)

사실 은행(`profile/facts.yaml`)이 상한선이다. 숨김 텍스트와 프롬프트 인젝션은 만들지 않는다. 지원자 문서를 외부 서비스에 올리지 않는다. 채용 사이트에 로그인, 지원, 제출, 연락하지 않는다. 원본 PDF·Figma 기존 페이지·플랫폼 프로필은 고치지 않는다. 합격을 보장하거나 확률로 말하지 않는다.

## 절차

1. **slug 정하기.** 회사의 영문 소문자 slug를 정한다 (`예시회사` → `example-co`). `companies/<slug>/meta.yaml`이 이미 있으면 `researched` 날짜를 확인하고, 30일 넘었으면 비대화형 실행은 기본으로 다시 조사하고, 대화형 실행은 다시 조사할지 사용자에게 묻는다. 그 이하면 재사용한다.
2. **회사 조사.** `company-research` 스킬을 회사명(+직무)으로 호출한다. 결과: `companies/<slug>/{dossier.md,vocab.yaml,sources.md,meta.yaml}`와 `jd/<tier>/<slug>__*.md`. 공고를 찾지 못했다면 사용자에게 공고 URL이나 텍스트를 달라고 요청하고 `jd-intake` 스킬로 저장한다. 공고 없이 계속하지 않는다.
3. **공고 고르기.** `meta.yaml`의 `jd_files` 중 `status: open`이고 Product Designer / AI Product Designer / UX 계열(`taxonomy/job_families.yaml`의 target 직군)인 것을 후보로 한다. 후보마다 요약하고 기본 이력서의 적합도를 본다.

   ```bash
   bin/harness jd <jd.md> --json
   bin/harness score --jd <jd.md> --resume profile/resume_base.yaml --json
   ```

   총점이 가장 높고 다른 후보와 3점 넘게 차이 나면 그것을 고른다. 상위 후보 점수가 3점 이내면 아래 순서로 순위를 정한다.

   1. `years_min`이 지원자 연차(8) 이하인 공고 중 8에 가까운 순서
   2. 사실 은행과의 도메인 적합 (B2B, AI 제품, 디자인 시스템, 데이터 기반 개선)
   3. 게시일이 최근인 순서

   비대화형 실행은 이 순서대로 고르고 이유를 `out/<slug>/tailor_log.md`에 적는다. 대화형 실행은 순위 목록을 보여 주고 사용자에게 고르게 한다. 후보가 하나뿐이면 묻지 않는다.

4. **tailor.** `tailor` 스킬을 `slug`와 고른 공고 파일로 실행한다. strict claims 통과가 안 되면 여기서 멈춘다.
5. **PDF.** `python tools/render_resume.py out/<slug>/resume_<lang>.yaml` (기본 경로 `out/<slug>/resume_<lang>.pdf`). `pdftotext`로 읽기 순서를 훑는다.
6. **screen.** `screen` 스킬을 실행한다. 우선 수정 5개 중 사실 은행 안에서 고칠 수 있는 것이 있고 점수가 오를 것 같으면 `tailor`로 한 번만 돌아가 반영하고 `screen`을 다시 한다 (총 2회까지).
7. **Figma.** `--no-figma`가 아니면 `figma-apply` 스킬을 실행한다. `profile/figma_map.yaml`에 슬롯이 없거나 Figma 탭이 준비되지 않았으면 이 단계는 건너뛰고 SUMMARY에 "Figma 미적용: 이유"를 적는다 (나머지 단계는 계속한다).
8. **submit-pack.** `submit-pack` 스킬을 실행한다. 플랫폼은 dossier의 ATS·지원 경로에서 정하고, 모르면 `default`.
9. **SUMMARY.md 작성.** `out/<slug>/SUMMARY.md`:
   - 회사·직무·공고 URL·조사일, 선택한 공고와 고른 이유
   - 한 문단 요약: 이 회사가 중시하는 것, 지원자와의 접점 (dossier에서, `[확인]/[보도]/[추정]` 태그 유지)
   - 이력서 점수 세 개: 기본(base), 마스터(master), 맞춤(tailored). 맞춤 효과 = 맞춤 − 마스터, 총 개선 = 맞춤 − 기본 (규칙 기반 휴리스틱임을 명시), 스크리너 3종 판정 한 줄씩, 우선 수정 남은 것
   - 산출물 링크 목록 (상대 경로): dossier, 공고, resume yaml/pdf, tailor_log, screening, Figma 페이지 이름과 PDF, pack/ 안의 파일, checklist
   - **사용자가 직접 할 일**: 확인이 필요한 사실(`check`), 자기소개서 검토, 제출은 사용자가 직접
   - 건너뛴 단계와 이유

## 중단 조건

- 회사를 특정할 수 없거나(동명 회사 여러 곳) 공고가 없다 → 사용자에게 묻는다.
- strict claims 실패, 사용자 확인이 필요한 사실, Figma 탭/로그인 필요 → 해당 단계에서 멈추고 무엇이 필요한지 알린다.

## 말하는 방식

최종 보고는 SUMMARY.md의 핵심만 짧게 전하고 경로를 알려 준다. 점수를 "합격 확률"로 말하지 않는다.
