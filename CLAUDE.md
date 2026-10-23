@AGENTS.md

# career-agent-kit (엔진 개발 폴더)

이 폴더는 지원 서류 도우미의 엔진과 스킬이다. 여기서는 엔진을 개발한다 (`harness/`, `rules/`, `taxonomy/`, `templates/`, `.claude/`, `tools/`, `tests/`).

- 실제 사람의 데이터(이력, 숫자, 서류, 연락처, 지원 기록)를 이 폴더에 두지 않는다. `profile/`, `jd/`, `companies/`, `out/`, `records/`, `research/`는 만들지 않는다. 테스트가 필요하면 가짜 인물("Sample Person", "예시회사")을 쓴다.
- 사람별 워크스페이스는 이 폴더 밖(`~/orca/projects/career-friends/<slug>/`)에 `bin/harness onboard`로 만든다.
- 엔진을 고치면 `.venv/bin/python -m unittest`와 `bin/harness --help`로 확인하고, 스키마가 바뀌면 `docs/contract.md`를 먼저 고친다.
- 커밋 전에 `grep`으로 이메일, 전화번호, 실제 이름이 들어갔는지 확인한다.
