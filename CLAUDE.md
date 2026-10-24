@AGENTS.md

# career-agent-kit (엔진 개발 폴더)

career-agent-kit은 지원자가 자기 지원 서류(이력서, 포트폴리오, 자기소개서)를 AI 1차 서류 심사(ATS 파싱, LLM 스크리닝, 리크루터 검색)에 맞춰 점검하고 공고별로 맞춤화하는 Claude Code 하네스다. 어떤 직군이든(개발, 데이터·AI, PM·기획, 디자인, 마케팅, 영업·BD, HR, 재무, 운영·CS, MD 등) 본인이 자기 지원을 위해 쓴다. 서류에는 지원자 본인의 사실 은행(`profile/facts.yaml`)에 있는 내용만 쓰고, 합격을 보장하지 않는다.

이 폴더는 하네스의 엔진과 스킬이다. 여기서는 엔진을 개발한다 (`harness/`, `rules/`, `taxonomy/`, `templates/`, `.claude/`, `tools/`, `tests/`).

- 사용자는 `onboard` 스킬로 자기 워크스페이스를 이 폴더 밖에 만든다 ("내 워크스페이스 만들어줘"). 워크스페이스에는 그 사람의 데이터(`profile/`, `jd/`, `companies/`, `out/`, `records/`, `research/`)가 있고, 엔진과 스킬은 링크로 쓴다. 필요하면 사람마다 워크스페이스를 따로 둘 수 있지만, 한 워크스페이스는 한 사람의 데이터만 다룬다.
- 에이전트는 사용자 본인의 서류를 본인을 위해 다루며, 사실 은행이 상한선이다: 사실을 지어내지 않고, 숨김 텍스트와 프롬프트 인젝션을 쓰지 않고, 서류를 외부 서비스에 올리지 않고, 채용 사이트에 로그인·지원·연락하지 않는다. 연락처는 `profile/contact.local.yaml`에만 둔다.
- 실제 사람의 데이터(이력, 숫자, 서류, 연락처, 지원 기록)를 이 폴더에 두지 않는다. `profile/`, `jd/`, `companies/`, `out/`, `records/`, `research/`는 만들지 않는다. 테스트가 필요하면 가짜 인물("Sample Person", "예시회사")을 쓴다.
- 엔진을 고치면 `.venv/bin/python -m unittest discover -s tests`와 `bin/harness --help`로 확인하고, 스키마가 바뀌면 `docs/contract.md`를 먼저 고친다.
- 스킬과 에이전트 문구는 특정 직군을 전제하지 않는다. 직군이 필요한 곳에는 예시를 여러 직군으로 든다.
- 커밋 전에 `grep`으로 이메일, 전화번호, 실제 이름이 들어갔는지 확인한다.
