# Interface contract (v1)

이 문서는 하네스의 폴더, 데이터 스키마, CLI, 스킬 입출력의 기준이다. 병렬 작업자는 이 계약만 보고 서로의 결과물에 의존한다. 계약을 바꿀 때는 오케스트레이터가 먼저 이 문서를 고친다.

## 0. 하는 일 (사용자 관점)

1. **기본 서류 최적화 (GEO for hiring AI).** 이력서 내용과 포트폴리오의 텍스트 슬롯(스티키 메시지, 타이틀, 키워드 줄)을 사실 은행과 조사 근거로 다듬는다. 포트폴리오 디자인(레이아웃, 폰트, 색, 이미지)은 바꾸지 않는다.
2. **회사명 하나로 맞춤 지원.** `apply <회사명>` → 회사 조사(채용 페이지, 공고, 디자인·기술 블로그, 제품·뉴스, 채용 절차·ATS) → 공고 저장 → 맞춤 이력서(YAML → PDF) → 심사 시뮬레이션(규칙 점수 + 스크리너 에이전트 3종) → Figma 새 페이지에 이력서·포트폴리오 텍스트 반영 → 지원 패키지.

## 1. 폴더와 소유

| 경로                                                                                                                                                                                                                                         | 내용                                                                       | 소유         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------ |
| `AGENTS.md`, `CLAUDE.md`, `docs/contract.md`, `docs/rules.md`                                                                                                                                                                                | 규칙, 계약                                                                 | orchestrator |
| `profile/`                                                                                                                                                                                                                                   | `facts.yaml`, `resume_base.yaml`, `figma_map.yaml`, `contact.example.yaml` | orchestrator |
| `taxonomy/`                                                                                                                                                                                                                                  | `job_families.yaml`, `skills.yaml`                                         | orchestrator |
| `rules/`                                                                                                                                                                                                                                     | `rules.yaml`, `scoring.yaml`, `platforms.yaml`, `screener_rubrics.yaml`    | orchestrator |
| `docs/research/`                                                                                                                                                                                                                             | 조사 보고서 사본                                                           | orchestrator |
| `pyproject.toml`, `harness/`, `tests/test_harness.py`                                                                                                                                                                                        | Python 코어                                                                | W-core       |
| `.claude/skills/company-research/`, `.claude/skills/jd-intake/`, `.claude/agents/company-*.md`, `templates/dossier.md`, `companies/README.md`, `jd/README.md`, `docs/company-research.md`                                                    | 회사 조사 파이프라인                                                       | W-research   |
| `.claude/skills/{apply,tailor,screen,figma-apply,submit-pack}/`, `.claude/agents/screener-*.md`, `templates/resume_ats.html`, `templates/resume_ats.css`, `tools/render_resume.py`, `tools/portfolio_subset.py`, `tools/figma/`, `README.md` | 맞춤화·출력·Figma                                                          | W-tailor     |
| `jd/<tier>/*.md`                                                                                                                                                                                                                             | 공고 파일 (런타임에 스킬이 추가)                                           | 데이터       |
| `companies/<slug>/`                                                                                                                                                                                                                          | 회사 조사 결과 (런타임)                                                    | 데이터       |
| `out/`                                                                                                                                                                                                                                       | 산출물, git 제외                                                           | 런타임       |

작업자는 자기 소유 경로만 만들거나 고친다. 다른 경로가 필요하면 escalation으로 묻는다.

## 2. 실행 환경

- Python 3.11+ (이 맥은 3.14). 의존성: `pyyaml>=6`, `pymupdf>=1.24`(선택 기능: 숨김 텍스트, 링크, 폰트 정보). pymupdf가 없으면 해당 검사는 `skipped`로 보고하고 나머지는 동작한다.
- 외부 도구: poppler `pdftotext`, `pdfinfo` (`/opt/homebrew/bin`). 없으면 pymupdf 텍스트로 대체한다.
- PDF 렌더: Google Chrome headless (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new --no-pdf-header-footer --print-to-pdf=<out> <html>`). 폰트 Pretendard는 사용자 맥에 설치돼 있다.
- 네트워크: 코어(`harness/`)는 네트워크를 쓰지 않는다. 회사 조사 스킬만 공개 웹을 읽는다 (WebSearch, WebFetch).

### 2.1 엔진 루트와 워크스페이스 루트

- **엔진 루트**: `harness/` 패키지가 있는 폴더 (`Path(harness.__file__).resolve().parents[1]`). `rules/`, `taxonomy/`, `templates/` 같은 엔진 자원은 여기서 읽는다.
- **워크스페이스 루트**: 한 사람의 데이터(`profile/`, `jd/`, `companies/`, `out/`, `records/`, `research/`)가 있는 폴더. `--root`가 없으면 현재 폴더에서 위로 올라가 `profile/facts.yaml`이 있는 첫 폴더를 쓴다.
- 내 에이전트 저장소에서는 두 루트가 같은 폴더다. 사용자 워크스페이스(예: `~/career-workspaces/<slug>/`)는 엔진 루트(키트 폴더 `~/orca/projects/career-agent-kit`)와 다르고, `bin/harness`, `.claude/skills`, `.claude/agents`가 엔진의 것으로 링크된다.
- `bin/harness`는 자신의 실제 경로(심볼릭 링크를 따라간 뒤)에서 엔진 루트를 찾고, python은 `$HARNESS_PYTHON`, `$ENGINE/.venv/bin/python`, `python3` 순으로 고른다. 스킬은 워크스페이스 루트에서 `bin/harness <command>`로 부른다.

## 3. 데이터 스키마

### 3.1 `profile/facts.yaml` (사실 은행)

```yaml
version: 1
updated: "YYYY-MM-DD"
person:
  name: {ko: str, en: str}
  headline: {ko: str, en: str}
  target_titles: [str]
  years_stated: int            # 서류에 쓰는 총 경력 연수 (휴직 제외)
  location: str
  links: [{id: str, label: str, url: str, public: bool, note: str?}]
experience:                    # 최신순
  - id: str                    # exp_*, leave_*
    kind: job | leave
    company: {ko: str, en: str}
    unit: {ko: str, en: str}
    title: {ko: str, en: str}
    title_aliases: [str]       # 서류에 써도 되는 다른 표기 (사실인 것만)
    track: str
    rank: str
    start: "YYYY.MM"
    end: "YYYY.MM" | null      # null = 현재
    family: str                # taxonomy/job_families.yaml id
    note: str?
projects:
  - {id: str, name: {ko: str, en: str}, exp: str, period: str, domain: str, role: str, team: str?, public_name: bool}
facts:
  - id: str                    # f_*
    exp: str | null            # experience id
    project: str | null        # project id
    ko: str                    # 서류에 쓸 수 있는 기준 문장
    en: str
    numbers: [str]             # 이 사실이 허용하는 숫자 토큰 (예: "36%", "2분 48초", "33,094명")
    basis: str?                # 측정 맥락 (표본, 기간, 방법)
    sources: [str]             # "resume", "portfolio:p15", "remember", "linkedin", "wanted"
    concepts: [str]            # taxonomy/skills.yaml concept id
    confidence: verified | reported | check   # check = 사용자 확인 전 사용 금지
    attribution: solo | lead | team           # 성과 기여 범위
    note: str?
skills:
  - {concept: str, display: {ko: str, en: str}, aliases: [str]?, level: core | working | familiar, evidence: [fact id]}
certifications:
  - {id: str, name: str, issuer: str, date: "YYYY.MM", status: acquired | planned, seen: {source: "YYYY.MM"}, confidence: verified | check}
awards: [{id: str, name: str, date: str, note: str?, sources: [str]}]
education:
  - {id: str, school: str, school_aliases: [str], degree: str, major: str, major_seen: {source: str}, start: "YYYY.MM", end: "YYYY.MM", gpa: str, note: str?, confidence: verified | check}
canonical:                     # 문서 간 일관성 검사용
  - {field: str, value: str, variants: [str], note: str?}
```

### 3.2 이력서 변형 (`profile/resume_base.yaml`, `out/<slug>/resume_<lang>.yaml`)

```yaml
meta:
  {
    lang: ko | en,
    variant: base | <slug>,
    target: { company: str?, title: str?, jd: str? },
    created: "YYYY-MM-DD",
  }
header:
  name: str
  title: str # 헤드라인 직함 한 줄
  tagline: str # 스티키 메시지 한 줄
  location: str
  links: [link id] # person.links id. 이메일·전화는 렌더 때 contact.local.yaml에서 넣는다
summary: [{ text: str, facts: [fact id] }]
experience:
  - ref: experience id
    title_display: str? # experience.title 또는 title_aliases 중 하나여야 한다
    bullets: [{ text: str, facts: [fact id] }]
projects: [{ ref: project id, bullets: [{ text: str, facts: [fact id] }] }] # 선택
skills: [{ group: str, items: [str] }] # items는 facts.skills의 display.ko · display.en · aliases 값만
strengths: [{ title: str, text: str, facts: [fact id] }] # 선택
awards: [award id]
certifications: [certification id]
education: [education id]
motivation: { text: str, facts: [fact id] } # 선택
```

### 3.3 `profile/figma_map.yaml` (Figma 텍스트 슬롯)

```yaml
file_key: "<FIGMA_FILE_KEY>"
resume: { page: "1:2", frames: [node id], original_page: "1:1" } # page = AI 최적화 사본(복제 기준), original_page = 읽기 전용 원본
portfolio:
  page: "1:3" # 슬롯이 있는 슬라이드(1·2쪽)의 AI 최적화 사본
  frames: [node id]
  original_page: "0:1" # 50장 원본 (읽기 전용)
  base_pdf: str # 기준 전체 포트폴리오 PDF (AI 최적화본)
  replaces: { "<frame id>": int } # 사본 프레임 → 전체 PDF의 쪽 번호
slots:
  - id: str # 예: resume.header.title, resume.about.lead, portfolio.cover.role
    node: "123:456" # page의 노드 id (복제 뒤 idMap으로 사본 id를 찾는다)
    doc: resume | portfolio
    max_chars: int # 넘으면 적용하지 않는다
    lines: int? # 줄 수 상한 (\n과 U+2028을 모두 센다)
    base: str # 현재 Figma 문구. tailor가 바꿀 문구의 출발점
    yaml_path: str? # figma_text.yaml에 없을 때 이력서 변형에서 가져올 값 (예: header.title)
    note: str?
```

Figma에서 페이지를 복제하면 노드 id가 바뀐다. 복제 스크립트는 원본 id → 사본 id 매핑을 반환하고, 적용 스크립트는 그 매핑으로 슬롯을 찾는다. 적용 스크립트는 바뀐 구간만 고치고(혼합 스타일 유지), 줄바꿈 문자는 노드가 원래 쓰던 것(문단 `\n` 또는 U+2028)을 따르며, 상자 높이가 커지거나 프레임을 넘으면 되돌린다.

### 3.4 택소노미

`taxonomy/job_families.yaml`

```yaml
seniority_levels: { level: [직급어] } # intern, junior, mid, senior, lead
families:
  - id: str
    target: bool # 지원 목표 직군이면 true
    labels: { ko: str, en: str }
    group: str # 직군 묶음 (design, dev, data, planning, marketing, sales, hr, finance, ops, commerce). 없으면 id
    portfolio_expected: bool # false면 포트폴리오 감사 감점을 점수에 반영하지 않는다 (없으면 true)
    core_skills: [skill concept id] # skills.yaml 개념. 서류에 나오면 직군 신호에 가산 (scoring.yaml classification.core_skill_weight)
    decisive_evidence: [{ label: str, terms: [str] }] # 이 직군 심사에서 결정적인 근거와 서류에서 찾을 용어
    seniority_words: [str] # 이 직군 직함에서 쓰는 직급어 (공통 직급어는 최상위 seniority_levels)
    titles: [str] # 타이틀 정규화용 표기 (대소문자, 공백 무시)
    signals: [str] # 본문에서 이 직군을 암시하는 용어
    platform_labels:
      {
        wanted: str?,
        remember: str?,
        linkedin: str?,
        saramin: str?,
        jobkorea: str?,
      }
```

`taxonomy/skills.yaml`

```yaml
concepts:
  - id: str
    category: design | research | data | build | ai | domain | collab | leadership | tool | process
    terms: { ko: [str], en: [str] }
    related: [concept id] # 부분 점수용
```

매칭 규칙: 대소문자 무시. 영문은 단어 경계, 한글은 공백 유무 무시(예: "디자인 시스템" = "디자인시스템"). 2자 이하 영문 약어(UT, IA, PM)는 대문자 그대로만 매칭한다.

### 3.5 공고 파일 (`jd/<tier>/<company-slug>__<role-slug>.md`)

YAML front matter: `company, tier, title, url, accessed (YYYY-MM-DD), status (open|closed|unknown), location, seniority, ats, language (ko|en)`. tier: `kr_conglomerate | kr_unicorn_it | global_bigtech | other`. 본문 섹션: `## Responsibilities`, `## Requirements`, `## Preferred` (공고에 적힌 bullet 그대로). 선택 섹션: `## Process`, `## Documents`, `## Notes`.

### 3.6 회사 조사 결과 (`companies/<slug>/`)

- `dossier.md`: 회사 개요 / 제품·서비스 / 디자인 조직과 일하는 방식(블로그 근거) / 채용 절차·ATS·서류 형식·용량 제한 / 인재상·가치 키워드 / 최근 이슈(최근 18개월) / 이 지원자와의 접점(fact id 매핑) / 리스크·주의 / 출처. 모든 주장에 `[확인]`·`[보도]`·`[추정]`.
- `vocab.yaml`: `terms: [{term: str, concept: concept id | null, evidence_url: str, note: str?}]` 회사가 실제로 쓰는 용어.
- `sources.md`: URL, 접근일, 1차/2차.
- `meta.yaml`: `{company: str, slug: str, aliases: [str], tier: str, careers_url: str?, ats: str?, researched: "YYYY-MM-DD", jd_files: [path]}`

### 3.7 규칙 데이터 (`rules/`)

`rules.yaml`: `rules: [{id, title, type, params, severity: high|med|low, applies_to: [resume|portfolio], source, confidence: 상|중|하}]`

지원하는 `type` (코어가 구현):

| type                 | params                                                | 판정                                                         |
| -------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| `text_layer`         | `min_chars_per_page`                                  | 페이지별 추출 글자 수                                        |
| `max_file_mb`        | `platform` 또는 `mb`                                  | 파일 크기 (`platforms.yaml` 참조)                            |
| `max_pages`          | `pages`                                               | 페이지 수                                                    |
| `section_present`    | `sections: [summary, experience, ...]`                | 섹션 제목 인식                                               |
| `contact_policy`     | `email: required                                      | optional`, `phone: forbid                                    | optional`         | 연락처 존재 여부 |
| `hidden_text_none`   | `min_font_pt`, `min_contrast`                         | 숨김·초소형·페이지 밖·흰 글씨                                |
| `date_format`        | `pattern`                                             | 날짜 표기 일관성                                             |
| `title_alignment`    | `target_families`                                     | 헤드라인·최근 직함이 목표 직군으로 정규화되는지              |
| `family_balance`     | `off_target: [family id]`, `max_share`                | 비목표 직군 신호 비중                                        |
| `keyword_density`    | `max_per_1000_chars`, `max_list_terms_outside_skills` | 키워드 반복·나열                                             |
| `quantified_ratio`   | `min_ratio`                                           | 숫자가 있는 bullet 비율                                      |
| `forbidden_patterns` | `patterns: [regex]`                                   | 인젝션·지시문 패턴                                           |
| `consistency`        | `fields: [canonical field]`                           | 정본과 다른 표기                                             |
| `claims_supported`   | `mode: strict                                         | loose`                                                       | 사실 은행 밖 숫자 |
| `reading_order`      | -                                                     | 기하 순서와 추출 순서가 다른 줄                              |
| `extractor_agreement` | `min_share` (기본 0.95)                              | 쪽마다 MuPDF 단어(2자 이상) 중 `pdftotext` 기본 출력에 공백 단위 토큰으로 온전히 나온 비율. 미만이면 warn, 나쁜 쪽과 깨진 단어 예시 5개를 낸다 |
| `first_page_signals` | `must_include: [title, years, metric]`                | 첫 페이지(포트폴리오는 첫 2쪽)에 핵심 신호가 텍스트로 있는지 |

모르는 type은 경고(`unsupported rule type`)만 내고 넘어간다.

`hidden_text_none` 판정: 후보가 없으면 pass, 후보가 있으면 warn, 후보가 프롬프트 인젝션 패턴(`forbidden_patterns`)에 걸리거나 문단 길이(40자 이상)의 흰 글씨면 fail. 후보는 (쪽, 이유)별로 묶어 `items`에 낸다. 한 쪽에 초소형 글자가 20개 이상이면 이유는 `mockup_text`(축소된 화면 캡처)이고 권고는 "목업은 이미지로 평탄화하거나 화면 밖 텍스트를 지우세요"다. 숫자 주장(`claims_supported`)은 PDF에서 MuPDF 텍스트로 검사한다.
warn 결과의 감점은 같은 severity 감점에 `scoring.yaml`의 `warn_penalty_factor`(0.5)를 곱한다.

`scoring.yaml`: `weights: {parse, title, required, preferred, seniority, impact}` (합 100), `penalty_cap`, `bands: [{min, label}]`, 세부 계수, 그리고 아래 둘.

- `family_weights: {<group>: {parse, title, required, preferred, seniority, impact}}`: 직군 묶음(taxonomy `group`)별 구성 점수 배분. 적힌 항목만 `weights`를 덮어쓰고, 덮어쓴 결과의 합은 `weights`의 합(100)과 같아야 한다(다르면 입력 오류, 종료 코드 2). 정의가 없는 묶음(현재 `design`)은 `weights` 그대로다.
- `classification: {title_bonus, core_skill_weight, jd_fallback_min_score}`: 직군 신호 계산 계수. `title_bonus`는 헤드라인·최근 직함이 정규화된 직군에 더하는 점수, `core_skill_weight`는 직군 `core_skills` 개념이 서류에 하나 나올 때 더하는 점수, `jd_fallback_min_score`는 공고 제목이 직군으로 정규화되지 않을 때 본문 신호 점수가 이 이상이면 가장 높은 직군을 공고 직군(`jd.family`)으로 본다는 기준이다.
`platforms.yaml`: `platforms: [{id, name, max_file_mb, types: [pdf, docx, ...], max_files?, notes, source}]`.
`screener_rubrics.yaml`: 스크리너 3종(ats, llm, recruiter)의 관점, 체크 항목, 출력 스키마.

### 3.6 `records/` (지원 기록, 워크스페이스 데이터)

`records/applications.yaml`은 YAML 목록이다. 연락처는 적지 않는다.

```yaml
- company: str                  # 필수
  aliases: [str]                # 다른 표기. 지원 여부 비교에 같이 쓴다
  scope: company | group        # 기본 company. group = 계열사 공용 채용 포털이라 그룹 전체를 지원한 것으로 본다
  role: str
  applied: "YYYY-MM-DD"
  channel: str
  status: pending | rejected | interview | offer | withdrawn | unknown   # 기본 pending
  source: str                   # 기록 근거 종류 (예: 지원 완료 화면 캡처)
  documents: str                # 낸 서류를 복사해 둔 폴더 (서류 보관함의 회사별/<날짜>_<회사>_<직무>/)
  note: str
```

서류 보관함: 워크스페이스 `CLAUDE.md`가 정한 폴더(없으면 `documents/`)에 `최신/`(지금 내는 기본본, 날짜 없는 이름), `회사별/<YYYY-MM-DD>_<회사>_<직무>/`(낸 그대로), `보관/<YYYY-MM-DD>_<설명>/`(교체된 이전 최신본)을 둔다. PDF는 `out/`에서 만들고 보관함 파일을 직접 고치지 않는다.

`records/leads.yaml` (먼저 연락 온 제안): `company, role, via, received(YYYY-MM-DD), status(awaiting_reply|replied|declined|closed), note`. `records/open_items.md`는 미결 사항 체크리스트다.

`bin/harness targets [--resume FILE] [--out FILE] [--json] <unit.yaml>...`은 `research/targets/<unit>.yaml`의 공고 목록(`company, slug, role, url, checked, tier, location, years_min, years_max, language, domain_tags, verdict, chance, reasons, jd_file`)을 합치고, 지원한 회사를 빼고, 공고별 점수를 내 순위를 매긴다 (chance 상>중>하, verdict 적합>도전>낮음, 점수 내림차순). `jd_file`은 절대 경로, 작업 폴더 기준, 목록 파일 폴더 기준, 목록 파일의 두 단계 위 폴더 기준 순서로 찾는다.

`bin/harness onboard <dest> --name "<이름>" [--template-dir DIR]`는 `templates/workspace/`로 사용자 워크스페이스를 만든다 (`CLAUDE.workspace.md` → `CLAUDE.md`, `gitignore` → `.gitignore`, `*.example.yaml` → 실제 이름, `bin/harness`·`.claude/skills`·`.claude/agents` 링크, `git init`).

## 4. 숫자 토큰 규칙 (claims 검사)

- 숫자 토큰: `\d{1,3}(,\d{3})+` 또는 `\d+(\.\d+)?` 뒤에 선택 단위 `%p|%|명|건|분|초|주|개월|년|개|곳|회|배|단계|화면|종|인|px|min|x`.
- 무시: 날짜(`YYYY.MM`, `YYYY-MM`, `YY.MM`, `YYYY년`), 20xx 연도, 줄 앞 목록 번호(`1.`, `2)`), 버전(`v1.9`), URL 안의 숫자, 공고 인용 부분.
- 무시: 영문자와 붙은 숫자(단어 안의 숫자). 숫자 앞이 영문자이거나 숫자 뒤가 영문자(단위 목록에 없는)인 경우다. 예: `B2B`, `B2C`, `GA4`, `3D`, `S3`. 정규식 힌트: `(?<![A-Za-z])` 와 `(?![A-Za-z])`(단, `px`·`min`·`x` 같은 단위는 허용).
- 비교는 숫자 값으로 한다 (쉼표 제거, 부호 무시). 양쪽에 단위가 있는데 다르면 경고.
- strict 모드: bullet의 숫자는 그 bullet의 `facts`가 가진 `numbers` 안에 있어야 한다. loose 모드(PDF, 텍스트): 사실 은행 전체 숫자 + 경력 기간 숫자 안에 있으면 통과.

## 5. CLI (`bin/harness <command>`)

모든 명령은 `--json`이면 표준 출력에 JSON 하나를 낸다. 종료 코드: 0 정상, 1 severity high 발견(검사형 명령), 2 입력 오류. 기본 경로는 레포 루트 기준 (`--root`로 변경).

| 명령                                                             | 입력                                    | 출력                                                                    |
| ---------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------- |
| `audit <pdf> [--kind resume                                      | portfolio] [--platform ID] [--out DIR]` | PDF                                                                     | 추출 텍스트(default·layout, 가림 처리)와 `audit.json`. 섹션, 날짜 범위·총 경력 개월·공백·겹침, 연락처 존재, 링크, 숨김 텍스트, 한글 무결성, 페이지별 글자 수, 읽기 순서 의심 줄, 규칙 결과 |
| `jd <jd.md>`                                                     | 공고                                    | 직군, 최소 연차, 섹션별 개념, 언어                                      |
| `family <file>`                                                  | pdf/txt/yaml                            | 직군 신호 분포와 예측 순위, 비목표 직군 경고                            |
| `claims <file> [--strict]`                                       | pdf/txt/yaml                            | 근거 없는 숫자, 없는 fact id, `check` 사실 사용, 비공개 링크, 금지 패턴 |
| `gaps --jd <jd.md>`                                              | 공고                                    | 공고 개념별 뒷받침 fact 목록 또는 "근거 없음"                           |
| `consistency <files...>`                                         | pdf/txt/md                              | 정본과 다른 표기 (전공, 자격 날짜 등)                                   |
| `score --jd <jd.md> --resume <file> [--portfolio <pdf>]`         | 공고+이력서                             | 총점, 구성 점수, 감점, 빠진 개념, 근거 있는 보완 제안                   |
| `run --jd <jd.md> --resume <file> [--portfolio <pdf>] --out DIR` | 위 전부                                 | `report.md`, `report.json`                                              |
| `targets [--resume FILE] [--out FILE] <unit.yaml>...` | 대상 공고 목록 YAML | 병합·제외·순위. 3.6 참조 |
| `onboard <dest> --name NAME [--template-dir DIR]` | 대상 폴더, 이름 | 사용자 워크스페이스. 3.6 참조 |
| `figma-check <figma_text.yaml>`                                  | `out/<slug>/figma_text.yaml`            | 슬롯마다 점검: `figma_map.yaml`에 있는 id, 글자 수(줄바꿈 제외) ≤ `max_chars`, 줄 수(`\n`·U+2028) ≤ `lines`, 줄 끝 하이픈으로 끊긴 단어 없음, 나열한 `facts`가 사실 은행에 있고 `check`가 아님, 글의 숫자가 그 facts의 `numbers`에 있음(`claims --strict`와 같은 규칙). 종료 코드 0 통과, 1 위반(슬롯별 메시지), 2 입력 오류 |
| `corpus --jd-dir DIR --resume <file>`                            | 공고 묶음                               | 공고별 점수표, 자주 빠지는 개념                                         |

`audit`과 `run`은 `--max-mb <MB>`로 R-SIZE-01의 용량 제한을 플랫폼 값 대신 지정할 수 있다(메시지에 어떤 제한을 왜 썼는지 적는다). `platforms.yaml`에 회사를 추가하지 않고, 스킬이 회사 조사 파일의 제한을 넘긴다.
`run`은 이력서 또는 포트폴리오 감사에 high 실패가 있거나 진실성 검사가 실패하면 종료 코드 1이다. 사람이 읽는 출력(`--json` 아님)은 점수, 실패·주의 규칙 한 줄 메시지, 출력 경로만 담은 짧은 요약이고, 전체 내용은 `--out`의 `report.md`·`report.json`과 `--json`에만 있다. `--out`에는 가림 처리한 `text_default.txt`(Poppler 기본)와 `text_mupdf.txt`(MuPDF)도 항상 쓴다.

`score` JSON 최소 형태:

```json
{
  "total": 0,
  "band": "",
  "components": {
    "parse": { "score": 0, "max": 0, "notes": [] },
    "title": {},
    "required": { "covered": [], "missing": [] },
    "preferred": {},
    "seniority": {},
    "impact": {}
  },
  "penalties": [{ "rule_id": "", "points": 0, "reason": "" }],
  "gaps": [
    {
      "concept": "",
      "importance": "required|preferred",
      "evidence_facts": [],
      "suggestion": ""
    }
  ],
  "suggestions": [{ "concept": "", "fact_ids": [], "hint": "" }],
  "family": {
    "id": "",
    "group": "",
    "weights": { "parse": 0, "title": 0, "required": 0, "preferred": 0, "seniority": 0, "impact": 0 },
    "portfolio_expected": true,
    "portfolio_penalties_applied": false
  },
  "family_evidence": [{ "label": "", "found": [] }],
  "note": ""
}
```

- `family.id`: 공고 직군(`jd.family`). 공고 직군을 모르면 서류에서 예측한 직군(`classify`의 `predicted`)이고, 둘 다 없으면 `null`이다. `group`은 그 직군의 묶음, `weights`는 실제 쓰인 구성 점수 배분(`family_weights` 반영 후)이다.
- `family.portfolio_expected`는 taxonomy 값(직군을 모르면 true)이고, `portfolio_penalties_applied`는 포트폴리오를 받았고 `portfolio_expected`가 true라서 포트폴리오 감사 감점(`penalties`의 `portfolio:` 접두 `rule_id`)을 점수에 반영했는지다.
- `family_evidence`: `family.id`의 `decisive_evidence` 항목마다 `label`과, 서류 텍스트에서 실제로 찾은 용어 `found`(최대 3개, 못 찾으면 빈 목록). 점수에 넣지 않고 알리기만 한다. 직군을 모르거나 `decisive_evidence`가 없으면 빈 목록이다.

`run`이 쓰는 `report.json`의 최상위 키: `texts`, `jd`(`file, company, title, family, years_min, language, concepts`), `resume`, `portfolio`, `audit`, `portfolio_audit`, `family`, `claims`, `consistency`, `score`. 여기서 `family`는 서류 분류 결과(`family` 명령과 같은 형태)다.

```json
{
  "headline": "", "headline_family": null,
  "recent_title": "", "recent_family": null,
  "ranking": [{ "id": "", "target": true, "score": 0, "share": 0.0, "signals": {} }],
  "predicted": null,
  "warnings": []
}
```

직군 정보를 읽는 위치: 공고 직군 `jd.family`, 서류 분류 `family.predicted`·`family.ranking`, 점수에 쓰인 직군과 배분 `score.family`, 결정적 근거 `score.family_evidence`.

## 6. 스킬과 에이전트

| 스킬               | 입력                                                   | 출력                                                                                                                                    |
| ------------------ | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `targets`          | 회사 목록 또는 티어                                    | `research/targets/<unit>.{yaml,md}`, `research/targets/jd/<tier>/*.md`, `research/targets/{merged.json,report.md}`                       |
| `log-application`  | 지원 확인 캡처, 메일, 또는 한 문장                     | `records/applications.yaml`에 항목 추가 (회사+직무 중복 없음, 연락처 복사 금지)                                                         |
| `career-status`    | (없음, `records/` 읽기 전용)                           | 상태별 지원 현황, 답 기다리는 제안, 미결 사항, 다음 행동 제안                                                                           |
| `onboard`          | 사용자 이름, 이력서·포트폴리오 위치                    | 사용자 워크스페이스(예: `~/career-workspaces/<slug>/`)와 `profile/facts.yaml`, `profile/resume_master_ko.yaml`                          |
| `apply`            | 회사명, 선택: 직무, `--no-figma`                       | 아래 단계를 순서대로 실행하고 `out/<slug>/SUMMARY.md`                                                                                   |
| `company-research` | 회사명, 선택: 직무                                     | `companies/<slug>/{dossier.md,vocab.yaml,sources.md,meta.yaml}`, `jd/<tier>/<slug>__*.md`                                               |
| `jd-intake`        | 공고 URL 또는 붙여 넣은 텍스트                         | `jd/<tier>/<slug>__<role>.md` + `bin/harness jd` 요약                                                                             |
| `tailor`           | slug, 공고 파일                                        | `out/<slug>/resume_<lang>.yaml`, `out/<slug>/figma_text.yaml`, `out/<slug>/tailor_log.md` (claims strict 통과 필수, 점수 전후 비교) |
| `screen`           | 이력서 파일, 공고 파일, 선택: 포트폴리오               | `out/<slug>/screening.md` (규칙 점수 + 직군 핵심 근거 + 스크리너 3종 판정 + 우선 수정 5개)                                                               |
| `figma-apply`      | `out/<slug>/figma_text.yaml`, `profile/figma_map.yaml` | Figma 새 페이지 "<회사명> 지원본 (YYYY-MM-DD)", 내보낸 PDF(이력서, 바꾼 쪽을 끼운 포트폴리오), 슬롯별 적용 로그                         |
| `submit-pack`      | slug                                                   | `out/<slug>/pack/` (최종 PDF, 플랫폼 용량별 포트폴리오 선택, 자기소개서 초안, 체크리스트). 제출은 하지 않는다                           |

`figma_text.yaml`: `slots: [{id: figma_map slot id, text: str, facts: [fact id], reason: str}]` — 이력서·포트폴리오 모두 텍스트 슬롯만 바꾼다. 바꿀 슬롯만 적는다.

스크리너 3종은 경로 외에 공고 직군 입력(직군 id, 한글 이름, `decisive_evidence` label 목록)을 받고 그 직군의 결정적 근거로 판단한다. 포트폴리오는 `score.family.portfolio_expected`가 true이거나 PDF를 받았을 때만 넘긴다. 출력 형태는 직군과 무관하게 같다.

스크리너 판정 JSON (세 에이전트 공통):

```json
{
  "screener": "ats|llm|recruiter",
  "decision": "advance|hold|reject",
  "score": 0,
  "title_fit": "",
  "must_have": [{ "req": "", "met": true, "evidence": "" }],
  "red_flags": [],
  "top_fixes": [],
  "confidence": "high|med|low"
}
```

## 7. 수용 기준 (공통)

- 레포 루트에서 `bin/harness --help`와 `python -m unittest tests/test_harness.py`가 통과한다.
- `bin/harness claims profile/resume_base.yaml --strict`가 종료 코드 0이다.
- 커밋되는 어떤 파일에도 이메일 주소와 전화번호가 없다: `grep -rEn "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|01[016789][- .]?[0-9]{3,4}[- .]?[0-9]{4}" --exclude-dir=.git .` 결과 없음.
