---
name: submit-pack
description: 지원에 필요한 파일을 out/<slug>/pack/에 모은다. 최종 이력서 PDF, 플랫폼 용량에 맞는 포트폴리오, 사실만 쓴 자기소개서 초안, 제출 전 체크리스트. 제출은 하지 않는다. "지원 패키지 만들어 줘", "제출 준비"에 쓴다.
---

# submit-pack: 지원 패키지

## 입력

- `slug`, 공고 파일, 지원 플랫폼 id (`rules/platforms.yaml`의 id, 모르면 `default`)
- `out/<slug>/resume_<lang>.yaml`과 PDF, 선택: Figma 내보낸 PDF(`resume_<lang>_figma.pdf`), 포트폴리오: `out/<slug>/portfolio_<slug>.pdf`(figma-apply가 쪽을 바꿔 끼운 회사별 버전)가 있으면 그것, 없으면 `profile/figma_map.yaml`의 `portfolio.base_pdf`(AI 최적화본)
- 자기소개서 문항과 글자 수 제한 (공고 `## Documents` 또는 dossier에 있으면 그대로, 없으면 사용자에게 묻는다)

## 출력

`out/<slug>/pack/`: `resume_<lang>.pdf`, `portfolio.pdf` (전체 또는 lite), `cover_letter.md`, `checklist.md`, `README.md` (사용한 용량 한도와 출처).

## 절대 규칙

- **제출, 로그인, 연락을 하지 않는다.** 파일만 모은다.
- 자기소개서·커버레터는 facts.yaml의 사실만으로 쓴다. `check` fact는 쓰지 않고, 숫자는 fact의 `numbers` 값 그대로 쓴다. 공고·회사 용어는 뒷받침하는 fact가 있을 때만 쓴다.
- 공개용 PDF에는 전화번호를 넣지 않는다 (`render_resume.py`의 기본). 이메일만 `profile/contact.local.yaml`에서 들어간다. 커밋되는 파일에 연락처를 쓰지 않는다.

## 절차

1. **이력서 PDF 결정.** Figma에서 내보낸 PDF가 있으면 그것을, 없으면 렌더링한다.

   ```bash
   python tools/render_resume.py out/<slug>/resume_<lang>.yaml --out out/<slug>/pack/resume_<lang>.pdf
   ```

   Figma PDF를 쓰면 `out/<slug>/resume_<lang>_figma.pdf`를 `pack/resume_<lang>.pdf`로 복사한다.

2. **포트폴리오 선택.** 한도는 이 순서로 정한다. 먼저 `companies/<slug>/dossier.md`가 업로드 용량 제한을 적고 있으면 그 값을 `<한도>`로 쓰고 아래 `audit`(4번)과 `portfolio_subset.py`에 모두 `--max-mb <한도>`로 넘긴다. 없으면 `rules/platforms.yaml`에서 플랫폼의 `max_file_mb`를 읽고, `null`이면 `observed_ok_mb`, 그것도 없으면 `default`의 10 MB를 쓴다 (이때는 `--max-mb`를 audit에 넘기지 않는다). 어떤 한도를 썼는지(값과 출처: dossier 또는 platforms.yaml)를 `pack/README.md`에 적는다. 입력의 포트폴리오 PDF 크기를 `ls -l`/`pdfinfo`로 재서 한도 이하면 그대로 복사한다. 넘으면 lite를 만든다.

   ```bash
   python tools/portfolio_subset.py <입력 포트폴리오 PDF> --pages <공고에 맞는 쪽 범위> --out out/<slug>/pack/portfolio.pdf --max-mb <한도>
   ```

   쪽 선택은 공고 직무와 맞는 프로젝트 위주로 앞 2쪽(표지·소개)을 포함한다. 확신이 없으면 `--pages`를 생략해 기본 표본으로 만들고 어떤 쪽이 들어갔는지 체크리스트에 적는다. 한도를 넘으면 쪽을 줄여 다시 한다.

3. **자기소개서·커버레터 초안.** `cover_letter.md`에 문항별로 쓴다. 문항이 없으면 지원동기·직무 적합성·협업 방식의 짧은 3개 항목으로 쓴다. 한국어는 담백하고 구체적으로, 접속어와 미사여구를 줄이고 "열정", "귀사", "성장하는 인재" 같은 틀에 박힌 말을 피한다. 글자 수 제한이 있으면 공백 포함 글자 수를 세어 제한 이하로 쓰고 문항 옆에 `(글자 수/제한)`을 적는다. 각 문단 끝에 근거 fact id를 주석(`<!-- facts: f_... -->`)으로 남긴다. 제출 때 이 주석은 지운다고 체크리스트에 적는다.

4. **검사.**

   ```bash
   bin/harness audit out/<slug>/pack/resume_<lang>.pdf --kind resume [--platform <id>] [--max-mb <한도>] --out out/<slug>/pack/audit/
   bin/harness claims out/<slug>/pack/resume_<lang>.pdf
   bin/harness consistency out/<slug>/pack/resume_<lang>.pdf out/<slug>/pack/cover_letter.md [포트폴리오 pdf]
   ```

   자기소개서의 숫자도 `bin/harness claims out/<slug>/pack/cover_letter.md`로 확인한다.

5. **`checklist.md` 작성.** 체크박스 목록:
   - 파일: 이름, 형식, 크기(MB), 플랫폼 한도 대비 (이력서, 포트폴리오)
   - 녹아웃 항목: 최소 연차(공고 vs `years_stated`와 휴직 제외 계산), 학위(졸업 표기와 전공명 확정 여부), 근무지, 언어, 필수 스킬, 비자·기타 (공고에 있는 것만)
   - 결과: claims, consistency, audit의 high 발견 수와 내용. 포트폴리오에 R-PARSE-07 경고가 있으면 일부 PDF 리더가 그 쪽에서 단어를 끊어 읽는다고 적고, 파싱이 중요한 양식에는 ATS 이력서를 권한다. `hidden_text` reason `mockup_text`는 축소한 UI 스크린샷이므로 이미지로 평탄화를 권한다 (조작 발견 아님)
   - PII: 공개 PDF에 전화번호 없음, 이메일은 의도한 것만, 비공개 링크 없음
   - 사용자가 확인할 것: `confidence: check` 항목 중 이 서류에 영향을 주는 것, 취득 예정 자격 표기, 자기소개서 주석 제거
   - 제출 경로: 플랫폼 업로드 칸 이름과 순서 (제출은 사용자가 직접 한다)

## 중단 조건

- 이력서 YAML이 strict claims를 통과하지 못한다 → `tailor`로 돌아가라고 알린다.
- 포트폴리오를 한도 이하로 줄일 수 없다 → 이미지가 큰 쪽을 빼야 함을 알리고 사용자에게 쪽 선택을 묻는다.
