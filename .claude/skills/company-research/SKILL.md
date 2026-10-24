---
name: company-research
description: "회사명(한글·영문, 선택: 직무) 하나로 채용 페이지·공고·기술/디자인/브랜드 블로그·사업·채용 절차를 조사해 companies/<slug>/ 조사 파일과 jd/ 공고 파일을 만든다. \"회사 조사\", \"예시회사 조사해줘\", apply 1단계에서 사용한다."
---

# company-research

회사명 하나를 받아 공개 웹만 읽어 회사 문서 묶음을 만든다. 합격을 보장하지 않으며, 사용자의 개인 정보는 검색어와 에이전트 입력에 넣지 않는다.

## 입력

- 회사명 (예: `예시회사`, `Example Co`, `샘플페이`)
- 선택: 직무 (예: `Backend Engineer`, `Data Analyst`, `Product Manager`, `Product Designer`, `Performance Marketer`). 없으면 `profile/facts.yaml`의 `target_titles` 첫 항목을 쓰고, 그것도 없으면 사용자에게 묻는다.

## 1. slug와 티어 정하기

- slug는 소문자 ASCII다: 예시회사 → `example-co`, 샘플페이 → `samplepay`, 가나다상사 → `ganada-trading`. 공식 영문 서비스명을 우선하고, 공백은 `-`로 바꾼다.
- 이미 `companies/<slug>/`가 있으면 사용자에게 덮어쓸지 갱신할지 묻는다. 기존 `meta.yaml`의 `researched` 날짜를 알려 준다. `researched`가 30일보다 오래됐으면 비대화형 실행은 기본으로 다시 조사하고, 대화형 실행은 다시 조사할지 묻는다.
- tier: `kr_conglomerate | kr_unicorn_it | global_bigtech | other`.
- `companies/<slug>/parts/`를 만든다.

## 2. 팬아웃 (병렬)

한 메시지에서 네 에이전트를 동시에 호출한다. 각자 입력은 회사명(한글·영문), slug, 직무, 오늘 날짜, tier뿐이다. 이 스킬이 에이전트로 호출되지 않는 환경이면 `general-purpose` 서브에이전트에 해당 에이전트 파일 내용을 프롬프트로 준다.

| 에이전트                 | 쓰는 파일                                     |
| ------------------------ | --------------------------------------------- |
| `company-careers`        | `companies/<slug>/parts/company-careers.md`        |
| `company-team-blog` (직무에 맞는 기술·디자인·브랜드 블로그) | `companies/<slug>/parts/company-team-blog.md`    |
| `company-business`       | `companies/<slug>/parts/company-business.md`       |
| `company-hiring-process` | `companies/<slug>/parts/company-hiring-process.md` |

에이전트가 실패하거나 빈 파일을 쓰면 그 부분만 한 번 다시 호출하고, 그래도 비면 dossier에 "조사 못함"으로 표시한다.

## 3. 병합

`templates/dossier.md`를 틀로 `companies/<slug>/dossier.md`를 쓴다. 섹션은 contract 3.6 순서를 그대로 유지한다 (제목은 그대로 쓰고, 내용은 사용자의 직무 조직 기준으로 쓴다): 회사 개요 / 제품·서비스 / 디자인 조직과 일하는 방식 / 채용 절차·ATS·서류 형식·용량 제한 / 인재상·가치 키워드 / 최근 이슈 / 이 지원자와의 접점 / 리스크·주의 / 출처.

- 파트 파일의 태그(`[확인]` `[보도]` `[추정]`)와 URL을 지우지 않는다. 파트끼리 모순되면 1차 출처를 따르고 모순을 "리스크·주의"에 적는다.
- dossier의 모든 숫자(투자액, 매출, 인원 등)는 `sources.md`에 올린 출처 중 그 페이지에 해당 숫자가 적힌 것을 인용해야 한다. 뒷받침하는 출처가 없으면 숫자를 빼거나 `[미확인]`으로 표시한다.
- 같은 출처가 여러 파트에 나오면 한 번만 `sources.md`에 올린다.
- 못 찾은 항목은 "찾지 못함 (확인한 곳: ...)"으로 둔다.

## 4. 부속 파일

- `vocab.yaml`: `terms: [{term, concept, evidence_url, note?}]`. 회사가 실제로 쓰는 용어만 넣는다. `concept`은 `taxonomy/skills.yaml`의 id에 정확히 맞을 때만 쓰고 아니면 `null`이다. 증거 URL이 없으면 넣지 않는다.
- `sources.md`: `| URL | 접근일 | 구분(1차/2차) | 용도 |` 표. 모든 행에 접근일(YYYY-MM-DD).
- `meta.yaml`: `{company, slug, aliases, tier, careers_url, ats, researched, jd_files}`.
- JD 파일: `company-careers` 파트의 `## JD 원문 블록`마다 `저장 경로:` 줄의 경로로, `---`로 시작하는 블록을 한 글자도 바꾸지 않고 저장한다 (contract 3.5 front matter 전체 키 + Responsibilities/Requirements/Preferred). role-slug는 소문자 ASCII 하이픈. 이미 있으면 덮어쓰기 전에 알린다. 저장할 때마다 `bin/harness jd <파일> --json`을 돌려 종료 코드 0을 확인한 뒤 다음으로 넘어간다. 실패하면 파일을 고치고 다시 돌린다. 공고 본문은 개인 키워드 분석용이므로 `jd/`를 외부에 공유하지 않는다.

## 5. 사용자와의 접점

`profile/facts.yaml`과 `taxonomy/skills.yaml`을 읽는다.

1. 공고·블로그에서 회사가 요구하거나 중시하는 것(개념)을 뽑는다.
2. 각 항목에 뒷받침하는 fact id를 붙인다. facts.yaml에 있는 id만 쓴다. `confidence: check` 사실은 쓰지 않는다.
3. 근거가 없으면 "근거 없음 (실제 공백)"으로 표시한다. 억지로 연결하지 않는다.
4. 표 형식: `회사 요구/관심 | 관련 fact id | 서류에 쓸 수 있는 기준 문장 요약 | 강도(강/중/공백)`. 숫자는 facts.yaml과 같은 값만 옮긴다.
5. 합격 확률이나 점수로 말하지 않는다.

## 6. 하네스 코어 확인

`harness/`가 있으면(`bin/harness --help`가 성공) 각 JD 파일에 대해 실행하고 요약을 dossier의 접점 섹션 끝에 붙인다.

```bash
bin/harness jd jd/<tier>/<slug>__<role>.md --json
bin/harness gaps --jd jd/<tier>/<slug>__<role>.md --json
```

코어가 아직 없으면 "코어 미설치: jd/gaps 확인은 건너뜀"이라고 dossier와 최종 보고에 쓰고 계속한다. 종료 코드 2(입력 오류)는 JD 파일 형식을 고쳐 한 번 다시 시도한다.

## 품질 체크리스트 (끝내기 전에 명령으로 확인, 커밋 전에 모두 통과)

`S=<slug>`로 두고 저장소 루트에서 실행한다.

1. **PII grep.** 아무것도 출력하지 않아야 한다. 기사 URL의 긴 숫자열이 전화번호 패턴에 걸리지 않도록 URL을 먼저 지우고 검사한다.

   ```bash
   grep -rn '' companies/$S jd/*/$S__*.md | sed -E 's#https?://[^ )|>]+##g' | grep -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|0[0-9]{1,2}[- .]?[0-9]{3,4}[- .]?[0-9]{4}'
   ```

2. **출처 URL 8개 이상.** 출력이 8 이상이어야 한다.

   ```bash
   grep -oE 'https?://[^ |)>]+' companies/$S/sources.md | sort -u | wc -l
   ```

3. **dossier 섹션이 모두 있고 비어 있지 않음.** `EMPTY` 또는 `MISSING`이 나오면 채운다 (못 찾은 항목은 "찾지 못함 (확인한 곳: ...)"으로 적는다).

   ```bash
   python3 - "$S" <<'PY'
import re, sys
S = sys.argv[1]
t = open(f"companies/{S}/dossier.md").read()
names = ["회사 개요","제품·서비스","디자인 조직과 일하는 방식","채용 절차·ATS·서류 형식·용량 제한","인재상·가치 키워드","최근 이슈","이 지원자와의 접점","리스크·주의","출처"]
parts = re.split(r"^## ", t, flags=re.M)[1:]
for n in names:
    body = next((p.split("\n", 1)[1] for p in parts if p.startswith(n)), None)
    print(n, "MISSING" if body is None else "EMPTY" if not body.strip() else "ok")
PY
   ```

4. **vocab.yaml concept id가 택소노미에 있음.** `NOT FOUND`가 나오면 `concept: null`로 바꾸거나 id를 고친다.

   ```bash
   python3 - "$S" <<'PY'
import re, sys, yaml
S = sys.argv[1]
ids = set(re.findall(r"^\s*-?\s*id:\s*([\w-]+)", open("taxonomy/skills.yaml").read() + open("taxonomy/job_families.yaml").read(), flags=re.M))
for t in yaml.safe_load(open(f"companies/{S}/vocab.yaml"))["terms"]:
    if t.get("concept") and t["concept"] not in ids:
        print("NOT FOUND:", t["term"], t["concept"])
PY
   ```

5. **JD 검증.** 모든 JD가 종료 코드 0이어야 한다.

   ```bash
   for f in jd/*/$S__*.md; do bin/harness jd "$f" --json >/dev/null || echo "FAIL $f"; done
   ```

6. **손으로 확인하는 항목.** 1차 채용 출처 1개 이상, `sources.md` 모든 행에 접근일, dossier 사실 주장마다 `[확인]`/`[보도]`/`[추정]`과 URL, dossier의 모든 숫자가 `sources.md` 출처에 실제로 적혀 있음, 검색어와 에이전트 입력에 사용자 정보 없음, 연봉·비공개 정보 없음, 인용은 한 문장 이하.

## 안전

공개 페이지 읽기만 한다. 로그인, 지원, 제출, 연락을 하지 않는다. 결과는 `companies/<slug>/`와 `jd/`에만 쓴다.
