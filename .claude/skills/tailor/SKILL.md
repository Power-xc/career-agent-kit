---
name: tailor
description: 회사 조사 결과(companies/<slug>/)와 선택한 공고로 사실만 쓴 맞춤 이력서(resume_<lang>.yaml)와 (Figma 이력서가 있는 사람만) Figma 이력서·포트폴리오 텍스트 슬롯 문구(figma_text.yaml)를 만든다. "예시회사 맞춤 이력서", "이 공고에 맞게 고쳐줘"처럼 회사·공고별 이력서가 필요할 때 쓴다.
---

# tailor: 공고에 맞춘 이력서와 포트폴리오 텍스트

## 입력

- `slug`: `companies/<slug>/`의 폴더 이름 (예: `example-co`)
- 공고 파일: `jd/<tier>/<slug>__<role>.md` (없으면 `jd-intake` 스킬을 먼저 쓴다)
- 읽는 파일: `companies/<slug>/dossier.md`, `vocab.yaml`, `profile/facts.yaml`, `profile/resume_master_<lang>.yaml`(있으면, 없으면 `profile/resume_base.yaml`), `profile/figma_map.yaml`, `taxonomy/job_families.yaml`, `rules/rules.yaml`, `rules/scoring.yaml`

## 출력

- `out/<slug>/resume_ko.yaml` (공고가 영어면 `resume_en.yaml`도, 스키마는 `docs/contract.md` 3.2)
- `out/<slug>/figma_text.yaml` (`slots: [{id, text, facts, reason}]`, `figma_map.yaml`에 슬롯이 있을 때만. 이력서·포트폴리오 슬롯 모두)
- `out/<slug>/tailor_log.md` (바꾼 곳, 이유, 전후 점수)

## 절대 규칙

1. 모든 bullet은 `facts: [fact id]`를 달고, 숫자는 그 fact의 `numbers`에 있는 값만 쓴다. 반올림, 합산, 추정으로 새 숫자를 만들지 않는다.
2. `confidence: check`인 fact, 자격, 학력 항목은 쓰지 않는다. 쓰고 싶으면 사용자에게 확인을 요청하고 멈춘다.
3. 공고·회사 용어는 그 용어를 뒷받침하는 fact가 있을 때만, 경험을 설명하는 문장 안에서만 쓴다. 용어 나열, 반복으로 밀도를 올리지 않는다 (`rules.yaml`의 `keyword_density`).
4. 직함 정규화는 `experience.title` 또는 `title_aliases`에 있는 표기만 쓴다 (`title_display`). 없는 직함을 만들지 않는다.
5. 지원 직군과 다른 직군의 신호가 되는 항목(facts.yaml의 `note`에 "기본 제외"가 적힌 자격·수상. 예: "그래픽·GUI/편집 직군 신호, 기본 제외")은 그 직군 지원 서류에 넣지 않는다.
6. 숨김 텍스트, "AI에게 지시하는" 문장, 메타데이터 키워드 채우기는 만들지 않는다.
7. 비공개 정보(`public: false` 링크, 연봉, 확정되지 않은 직책·TF)는 쓰지 않는다.

## 절차

1. **준비.** `mkdir -p out/<slug>`. 공고 요약과 격차를 본다.

   ```bash
   bin/harness jd jd/<tier>/<slug>__<role>.md --json
   bin/harness gaps --jd jd/<tier>/<slug>__<role>.md --json
   ```

2. **기준 점수.** 기본(base)과 마스터(master) 이력서를 각각 렌더링해 비교용 점수를 남긴다. master가 없으면 base만 남기고 master 칸에 "없음"이라고 쓴다.

   ```bash
   python tools/render_resume.py profile/resume_base.yaml --out out/<slug>/base_ref.pdf
   bin/harness run --jd jd/<tier>/<slug>__<role>.md --resume profile/resume_base.yaml --out out/<slug>/before/
   python tools/render_resume.py profile/resume_master_ko.yaml --out out/<slug>/master_ref.pdf
   bin/harness run --jd jd/<tier>/<slug>__<role>.md --resume profile/resume_master_ko.yaml --out out/<slug>/before_master/
   ```

   두 `report.json`의 총점을 `tailor_log.md`에 "base", "master"로 기록한다. `harness run` 종료 코드 1은 이력서나 포트폴리오에 high 발견이 있다는 뜻이다 (실패가 아니라 보고 대상).

3. **복사.** `profile/resume_master_<lang>.yaml`이 있으면 그것을, 없으면 `profile/resume_base.yaml`을 `out/<slug>/resume_<lang>.yaml`로 복사하고 `meta.variant: <slug>`, `meta.target: {company, title, jd}`, `meta.created`를 채운다. 공고 `language`가 `en`이면 `meta.lang: en`으로 하고 fact의 `en` 문장과 `display.en`을 기준으로 쓴다.

4. **헤드라인과 직함.** 공고 직군(`jd` 출력의 family, 예: 백엔드 개발, 데이터 분석, 프로덕트 매니저, 프로덕트 디자인, 마케팅)에 맞춰 `header.title`을 `taxonomy/job_families.yaml`의 `titles` 중 사실과 맞는 것으로 정한다. 최근 두 경력의 `title_display`는 `experience.title`/`title_aliases` 안에서 고른다. `header.tagline`은 한 줄, 공고 직무와 맞는 사실 기반 문장으로 쓰거나 null로 둔다.

5. **요약 3줄.** 누구인가 (연차는 `years_stated`, 직군) / 증거 (숫자는 fact의 값 그대로) / 이 회사·직무와의 접점. 각 줄에 `facts`를 단다. 길어도 두 문장이다.

6. **경력 bullet.** 공고 Requirements·Preferred와 회사 `vocab.yaml` 용어에 맞는 fact를 위쪽으로 올린다. bullet 문구는 base의 문장을 바탕으로 하고, 새 문장을 쓸 때도 fact의 `ko`/`en` 기준 문장과 `numbers` 안에서만 쓴다. 관련이 약한 bullet은 뒤로 보내거나 줄인다. 2쪽을 넘기지 않는다.

7. **스킬·자격·수상.** `skills.items`는 facts.yaml의 `display`/`aliases` 값만 쓴다. 공고와 맞는 그룹을 앞에 둔다. 자격은 `status: planned`면 "취득 예정"으로만 표시되며 렌더러가 처리한다.

8. **Figma 슬롯 (선택).** Figma 이력서가 있는 사람만 해당한다. `profile/figma_map.yaml`이 없거나 `slots`가 비어 있으면 이 단계를 건너뛰고 로그에 "슬롯 없음"이라고 적는다. 있으면 슬롯마다 `base`(현재 Figma 문구)를 이 회사·공고에 맞게 바꿀지 정하고, 바꿀 슬롯만 `figma_text.yaml`에 쓴다 (`doc: resume`과 `doc: portfolio` 모두).
   - 우선순위: `resume.header.title`, `resume.about.lead`, `resume.motivation.*`(지원 동기는 dossier의 접점으로), 경력 라벨(`*.track`), 스킬 묶음, `portfolio.cover.role`, `portfolio.competency.*`. 바꿀 이유가 없으면 그대로 둔다.
   - 각 항목에 `facts`와 `reason`을 단다. 숫자는 그 fact의 `numbers` 값만 쓴다 (원문 표기 그대로).
   - `max_chars`와 `lines`를 넘기지 않는다. 직접 세지 말고 9번의 `figma-check`로 확인한다. 줄 구성은 `base`를 따른다: 줄바꿈 위치와 첫 줄 묶음 이름(스킬)은 유지한다. 하이픈 단어(Human-in-the-Loop)는 줄 끝에 두지 않는다.
   - 디자인(레이아웃, 폰트, 색, 이미지)은 바꾸지 않는다.

9. **검증 (필수).**

   ```bash
   bin/harness claims out/<slug>/resume_ko.yaml --strict      # 종료 코드 0이어야 한다
   bin/harness figma-check out/<slug>/figma_text.yaml          # 슬롯이 있을 때만. 종료 코드 0이어야 한다
   bin/harness run --jd jd/<tier>/<slug>__<role>.md --resume out/<slug>/resume_ko.yaml --out out/<slug>/after/
   ```

   claims나 figma-check가 종료 코드 1이면 보고된 숫자·fact id·금지 항목·슬롯 id·글자 수·줄 수·줄 끝 하이픈을 고치고 다시 한다. 종료 코드 2는 입력 파일을 고친다. 통과 전에는 다음 단계로 가지 않는다.

10. **반복 (최대 3회).** 점수가 오르는 동안만 `report.md`의 `gaps`/`suggestions` 중 근거 있는 것을 반영해 9번을 반복한다. 점수가 오르지 않으면 직전 버전으로 돌아가 멈춘다. 근거 없는 요건은 채우지 않고 `tailor_log.md`에 "근거 없음"으로 남긴다.

11. **로그.** `out/<slug>/tailor_log.md`에 변경마다 `위치 | 전 → 후 | 이유(공고 항목, fact id) | 점수 전/후`를 적는다. 마지막에 점수 세 개(base, master, tailored)와 맞춤 효과(tailored − master), 총 개선(tailored − base), 남은 격차, 사용자 확인이 필요한 항목을 쓴다.

## 중단 조건

- `companies/<slug>/dossier.md`나 공고 파일이 없다 → 필요한 스킬(`company-research`, `jd-intake`)을 안내하고 멈춘다.
- strict claims가 3회 안에 통과하지 않는다 → 마지막 실패 목록과 함께 사용자에게 알린다.
- 쓰고 싶은 사실이 facts.yaml에 없거나 `check`다 → 사용자에게 사실 확인을 요청하고, 확인되면 facts.yaml에 출처와 함께 먼저 넣게 한다.

## 말하는 방식

점수는 규칙 기반 휴리스틱이다. "합격 확률"이나 "통과 보장"으로 말하지 않는다.
