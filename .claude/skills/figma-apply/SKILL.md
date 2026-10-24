---
name: figma-apply
description: (선택, Figma 이력서가 있는 사람만) 맞춤 Figma 문구(figma_text.yaml)를 Figma 파일의 새 페이지(AI 최적화 사본을 복제한 것)에 반영하고 PDF로 내보낸다. 원본 페이지는 건드리지 않는다. "Figma에 반영해 줘", "Figma 이력서도 이 회사용으로"에 쓴다.
---

# figma-apply: Figma 새 페이지에 텍스트 반영

**선택 단계다.** 디자이너처럼 Figma로 만든 이력서·포트폴리오가 있는 사람만 쓴다. `profile/figma_map.yaml`이 없으면 이 스킬은 쓰지 않고 `apply`는 이 단계를 건너뛴다.

Figma 파일 (키는 `profile/figma_map.yaml`의 `file_key`). **쓰기는 Claude in Chrome `javascript_tool`로 사용자의 열린 Figma 탭의 `window.figma`에서 한다.** Figma MCP `use_figma`는 쓰지 않는다 (로컬 폰트 Pretendard가 없어 `MISSING_FONT`로 실패한다). 읽기와 스크린샷은 Figma MCP(`create_session`, `get_metadata`, `get_screenshot`)를 쓴다. 스크립트와 실행법은 `tools/figma/README.md`.

## 입력

- `out/<slug>/figma_text.yaml` (필수), `profile/figma_map.yaml`, 선택: `out/<slug>/resume_<lang>.yaml` (`yaml_path`가 있는 슬롯만)
- 회사 표시명 (예: `예시회사`)과 오늘 날짜 `YYYY-MM-DD`

## 출력

Figma 새 페이지 `<회사명> 지원본 (YYYY-MM-DD)` (포트폴리오 슬롯이 바뀌면 `<회사명> 포폴 (YYYY-MM-DD)`도), `out/<slug>/figma_log.md` (슬롯별 적용 결과), `out/<slug>/resume_<lang>_figma.pdf`, `out/<slug>/figma_audit/`.

## 절대 규칙

- 원본 페이지(`figma_map.yaml`의 `resume.page`, `portfolio.page`. 하드코딩하지 않고 매번 파일에서 읽는다)와 기존 프레임에는 쓰지 않는다. 새 페이지의 사본에만 쓴다.
- 편집 전에 복원 지점을 남긴다. 복원 지점이 저장됐다는 응답을 확인하기 전에는 아무것도 복제하지 않는다.
- 슬롯의 `max_chars`·`lines`를 넘는 텍스트는 적용하지 않는다. 넘침이 나면 되돌린다.
- 텍스트는 `.characters` 통째 교체 금지. `apply_text.js`의 구간 편집을 쓴다. 줄바꿈은 `\n`으로 넘기고, `apply_text.js`가 노드의 원래 방식(문단 `\n` 또는 U+2028)에 맞춘다.
- 개인정보 (이메일·전화)는 Figma에 새로 넣지 않는다. 연락처 슬롯은 건드리지 않는다.
- 로그인, 코멘트, 공유 설정 변경은 하지 않는다.

## 절차

1. **슬롯 확인.** `profile/figma_map.yaml`의 `slots`가 비어 있으면 "figma_map.yaml에 슬롯이 없어 Figma 적용을 할 수 없다. 오케스트레이터가 Figma를 읽어 슬롯을 채워야 한다"고 말하고 **멈춘다.**
2. **문구 검증.** Figma를 건드리기 전에 실행한다. 글자 수, 줄 수, 하이픈 줄 끝을 손으로 세지 않는다.

   ```bash
   bin/harness figma-check out/<slug>/figma_text.yaml
   ```

   종료 코드 1(위반)이면 멈추고 `tailor`로 돌아가 문구를 고친다. 2(입력 오류)면 파일을 고친다. 0이어야 다음으로 간다.
3. **준비 확인.** `mcp__claude-in-chrome__tabs_context_mcp`로 Figma 탭(파일 키 `<FILE_KEY>`)이 열려 있는지 본다. 없으면 사용자에게 열고 로그인해 달라고 요청하고 멈춘다. 새 탭으로 로그인 시도를 하지 않는다.
4. **적용 목록 만들기.** `figma_text.yaml`의 `slots[]`마다 `figma_map.yaml`에서 같은 id의 슬롯을 찾아 `{slot, node(원본 id), text, maxChars: max_chars, lines}`를 만든다. `figma_text.yaml`에 없고 `yaml_path`만 있는 슬롯은 `resume_<lang>.yaml`의 값을 쓴다 (`bullets.0.text`처럼 숫자는 배열 인덱스). `base`와 같은 문구는 제외한다. `figma-check`를 통과했으므로 `max_chars` 초과는 없어야 한다. 줄바꿈은 `\n`으로 넘기면 `apply_text.js`가 노드의 원래 줄바꿈 문자(문단 `\n` 또는 U+2028)에 맞춘다.
5. **복원 지점.** `tools/figma/save_version.js`의 `ARGS.title`을 `"<회사명> 지원본 전 (YYYY-MM-DD)"`로 바꿔 실행한다. 응답에 `saved: true`가 있어야 한다.
6. **복제.** `clone_frames.js`를 이력서 프레임(`figma_map.yaml`의 `resume.frames`)으로 실행해 새 페이지를 만든다. 응답의 `pageId`, `cloneFrames`, `idMap`(원본 id → 사본 id)을 저장한다. 같은 이름의 페이지가 이미 있다는 오류가 나면 이름 끝에 `-2`를 붙이거나 사용자에게 묻는다. 포트폴리오 슬롯이 하나라도 바뀔 때는 `frameIds: <figma_map.yaml의 portfolio.frames>`로 한 번 더 실행해 `<회사명> 포폴 (YYYY-MM-DD)` 페이지를 만든다 (슬롯이 있는 슬라이드만 복제한다. 50장 전체를 복제하지 않는다).
7. **dry run.** `apply_text.js`에 `allowedPageIds: [새 페이지 id들]`, 3번 목록의 `id`를 `idMap`으로 사본 id로 바꾼 `edits`, `dryRun: true`를 넣어 실행한다. `planned`/`skipped` 결과를 사용자에게 요약해 보여 주고 진행 여부를 확인한다 (이 단계는 파일 밖 시스템에 쓰기가 일어나기 직전이므로 확인한다).
8. **적용.** 같은 `edits`로 `dryRun: false`를 실행한다. 한 번에 약 20개 이하로 나눠 실행한다. `reverted`, `skipped`, `error`는 `figma_log.md`에 이유와 함께 적는다. 되돌려진 슬롯은 문구를 줄여 한 번만 다시 시도한다.
9. **눈으로 확인.** Figma MCP `get_screenshot`으로 새 페이지의 각 프레임을 본다. 줄바꿈, 넘침, 겹침, 굵기·색 혼합 스타일이 유지됐는지 확인한다. 문제가 있으면 해당 슬롯만 `apply_text.js`로 고치거나 원문으로 되돌린다.
10. **PDF 내보내기.** 다른 터미널에서 `python tools/figma/recv_server.py --dir out/<slug>`를 켜고(Bash 백그라운드), `export_pdf.js`로 사본 프레임을 `resume_<lang>_figma_p1.pdf`, `_p2.pdf`로 보낸 뒤 합친다.

   ```bash
   python tools/figma/recv_server.py --merge out/<slug>/resume_<lang>_figma.pdf out/<slug>/resume_<lang>_figma_p1.pdf out/<slug>/resume_<lang>_figma_p2.pdf
   ```

   포트폴리오 슬롯을 바꿨다면 사본 슬라이드를 `figma_map.yaml`의 `portfolio.replaces` 쪽 번호로 이름 붙여 내보내고(`portfolio_s01.pdf`, `portfolio_s02.pdf`), 기준 전체 PDF에서 그 쪽만 바꿔 끼운다.

   ```bash
   python tools/portfolio_replace.py --base <figma_map.yaml의 portfolio.base_pdf> \
       --page 1=out/<slug>/portfolio_s01.pdf --page 2=out/<slug>/portfolio_s02.pdf --out out/<slug>/portfolio_<slug>.pdf
   ```

   수신 서버가 막혀 `downloaded`로 응답하면 `~/Downloads`의 파일을 `out/<slug>/`로 옮긴다. 수신 서버는 끝나면 종료한다.

11. **감사.**

    ```bash
    bin/harness audit out/<slug>/resume_<lang>_figma.pdf --kind resume --out out/<slug>/figma_audit/
    bin/harness claims out/<slug>/resume_<lang>_figma.pdf
    ```

    텍스트 층, 읽기 순서, 숨김 텍스트, 숫자 근거를 확인한다. high 발견이 있으면 `figma_log.md`에 적고 사용자에게 알린다. 포트폴리오를 바꿨다면 같은 방식으로 `--kind portfolio` 감사도 한다. 결과 해석:

    - R-PARSE-07 경고(포트폴리오 쪽): 일부 PDF 리더가 그 쪽에서 단어를 끊어 읽는다. 사용자에게 알리고, 파싱이 중요한 양식에는 ATS 이력서(또는 개선 이력서)를 권한다. 숨김 텍스트로 "고치지" 않는다.
    - `hidden_text`의 reason이 `mockup_text`: 축소한 UI 스크린샷의 글자다. 조작 발견이 아니다. 목업을 이미지로 평탄화하라고 권한다.

## 중단 조건

- 슬롯 없음, `figma-check` 종료 코드 1, Figma 탭 없음/로그인 안 됨, 복원 지점 저장 실패, 복제 실패.
- `javascript_tool`이 2~3회 연속 실패하거나 응답이 없으면 시도를 멈추고 무엇이 막혔는지 사용자에게 알린다.
- `MISSING_FONT`가 나면 스니펫이 Figma MCP 런타임이 아니라 사용자의 탭에서 실행되고 있는지 확인한다.
