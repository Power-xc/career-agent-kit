# career-agent-kit

지원 서류가 **AI 1차 서류 심사**(ATS 파싱, LLM 스크리닝, 리크루터 검색)에서 정확히 읽히도록, 사실만 써서 점검하고 회사별로 맞춤화하는 도우미입니다. Claude Code에서 스킬로 씁니다. 합격을 보장하지 않으며 점수는 휴리스틱입니다.

이 폴더는 엔진과 스킬만 있습니다. 사람의 데이터는 없고, 사람마다 이 폴더 밖에 워크스페이스를 하나씩 만듭니다.

## 설치

```bash
cd career-agent-kit
python3 -m venv .venv && .venv/bin/pip install -e .
bin/harness --help
```

PDF 텍스트 추출에 poppler(`pdftotext`)가 있으면 더 정확합니다 (macOS: `brew install poppler`). 이력서 PDF 렌더에는 Google Chrome을 씁니다.

## 친구 한 명 시작하기

Claude Code를 이 폴더에서 열고 `onboard` 스킬을 씁니다 ("친구 워크스페이스 만들어줘"). 이름, 이력서와 포트폴리오 위치를 알려 주면 다음을 합니다.

```bash
bin/harness onboard ~/orca/projects/career-friends/<slug> --name "<이름>"
```

워크스페이스에는 `CLAUDE.md`, `profile/`, `records/`, `jd/`, `out/`, `research/targets/`가 생기고 `bin/harness`, `.claude/skills`, `.claude/agents`는 이 키트로 링크됩니다. 이후 작업은 **그 워크스페이스 폴더에서** Claude Code를 열어 합니다. 사실 은행(`profile/facts.yaml`)은 그 사람의 서류에 있는 내용만으로 만들고, 확인이 필요한 항목은 `confidence: check`로 둡니다.

## 스킬

| 스킬               | 하는 일                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `onboard`          | 새 워크스페이스를 만들고 서류에서 사실 은행을 세운다                                        |
| `apply`            | 회사명 하나로 조사 → 공고 → 맞춤 이력서 → 심사 시뮬레이션 → (선택) Figma → 지원 패키지      |
| `company-research` | 회사의 채용 페이지, 공고, 디자인 블로그, 사업, 채용 절차를 공개 자료로 조사                 |
| `jd-intake`        | 공고 URL이나 텍스트를 JD 파일로 저장                                                        |
| `tailor`           | 사실 안에서 회사·공고별 맞춤 이력서 만들기                                                  |
| `screen`           | ATS, LLM, 리크루터 관점의 심사 시뮬레이션                                                   |
| `submit-pack`      | 최종 PDF와 체크리스트 모으기 (제출은 하지 않는다)                                           |
| `figma-apply`      | 새 Figma 페이지에 맞춤 문구 반영 (Figma 파일이 있는 사람만)                                 |
| `targets`          | 지원할 만한 회사와 공고를 찾아 적합도 순위 보고서 만들기                                    |
| `log-application`  | 낸 지원을 `records/`에 기록                                                                 |
| `career-status`    | `records/` 기준 현황과 다음 행동                                                            |

## 친구 데이터 개인정보 규칙

- 한 워크스페이스는 한 사람의 것입니다. 그 사람의 데이터를 다른 사람의 워크스페이스, 이 키트 폴더, 도우미를 쓰는 사람의 기록이나 메모리에 복사하지 않습니다.
- 이메일과 전화번호는 `profile/contact.local.yaml`(git 제외)에만 둡니다. 주민등록번호와 연봉은 어디에도 적지 않습니다.
- 서류를 온라인 ATS 검사기, 이력서 파서, 서드파티 LLM API 같은 외부 서비스에 올리지 않습니다. 채용 사이트에 로그인, 지원, 연락하지 않습니다.
- 사용 전에 그 사람의 동의를 받고, 삭제를 요청하면 워크스페이스 폴더를 지웁니다. 산출물은 `out/`에만 있습니다.
- 숨김 텍스트, 프롬프트 인젝션, 지어낸 경력이나 숫자를 쓰지 않습니다. 사실 은행에 없는 내용은 서류에 들어가지 않습니다.

## 한계

- 직군 분류(`taxonomy/`)는 Product Designer, UX, 서비스 디자인 등 **프로덕트 디자이너 중심**입니다. 다른 직군은 `taxonomy/job_families.yaml`과 `taxonomy/skills.yaml`을 확장해야 분류와 점수가 제대로 나옵니다.
- 점수는 규칙과 시뮬레이션에 기반한 휴리스틱이며 합격 확률이 아닙니다.
- 한국어 서류와 한국·글로벌 채용 사이트 기준으로 만들었습니다.

## 엔진 개발

엔진을 고칠 때는 `CLAUDE.md`와 `AGENTS.md`의 규칙을 따르고, `.venv/bin/python -m unittest`로 확인합니다. 규칙과 스키마의 기준은 `docs/contract.md`입니다.
