---
name: career-status
description: records/의 지원 기록, 제안(leads), 미결 사항을 읽어 현황을 요약하고 다음 행동을 제안한다. 읽기 전용이다. "지원 현황", "어디까지 했지", "뭐 해야 해"에 쓴다.
---

# career-status

`records/`만 읽어 지금 상태를 짧게 보여 준다. 파일을 고치지 않는다.

## 절차

1. **읽기.** `records/applications.yaml`, `records/leads.yaml`, `records/open_items.md`. 없는 파일은 "기록 없음"으로 적는다. 오늘 날짜는 시스템 날짜로 구한다.
2. **지원 현황.** 상태별(pending, interview, offer, rejected, withdrawn, unknown)로 나눠 회사, 직무, 지원일, 지원 후 경과 일수(`오늘 - applied`)를 표로 보여 준다. `applied`가 없으면 경과일은 "미상"으로 둔다.
3. **답을 기다리는 제안.** `leads.yaml`에서 `status`가 `awaiting_reply`인 건을 받은 날 기준 경과 일수와 함께 보여 준다.
4. **미결 사항.** `open_items.md`의 완료되지 않은 항목을 그대로 옮긴다.
5. **다음 행동 제안.** 규칙으로 뽑는다.
   - pending이고 지원 후 약 3주(21일) 넘게 답이 없으면 → 후속 확인(공식 채널로 상태 확인) 또는 `unknown` 정리를 제안.
   - 면접(interview) 상태 → 준비할 것(`companies/<slug>/` 조사 파일을 다시 열기).
   - 답을 기다리는 제안이 있으면 → 답장 여부를 사용자에게 묻기.
   - 미결 사항이 오래됐으면 → 먼저 처리.
   - 지원 기록이 적으면 → `targets`로 새 후보 찾기.
6. **마무리.** 다음 행동은 제안일 뿐이며 이 스킬이 대신 연락하거나 지원하지 않는다고 한 줄로 밝힌다. 현황 갱신이 필요하면 `log-application`을 안내한다.

## 안전

- 읽기 전용이다. 연락처가 기록에 있더라도 출력하지 않는다.
- 합격 확률이나 예상 결과를 말하지 않는다. 기록된 상태와 경과일만 보여 준다.
