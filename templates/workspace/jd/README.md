# jd/

지원할 공고를 `jd/<tier>/<company-slug>__<role-slug>.md`로 둔다 (tier는 회사 묶음 이름, 예: `favorites`).

- 가장 쉬운 방법: Claude에게 공고 URL이나 붙여 넣은 텍스트를 주고 `jd-intake` 스킬을 쓴다.
- 직접 쓸 때는 front matter에 `company, tier, title, url, accessed, status, location, seniority, ats, language`를 큰따옴표 문자열로 쓰고, 본문에 `## Responsibilities`, `## Requirements`, `## Preferred`를 공고 문구 그대로 둔다. 모르는 값은 `"unknown"`.
- 저장 뒤 `bin/harness jd <파일> --json`이 종료 코드 0이면 형식이 맞다.
