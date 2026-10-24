# tools/figma: Figma 텍스트 적용 스크립트

`figma-apply` 스킬이 쓰는 스니펫 모음이다. **쓰기는 Claude in Chrome의 `javascript_tool`로 사용자의 Figma 탭에서 `window.figma`를 쓴다.** Figma MCP `use_figma` 런타임에는 Pretendard 같은 로컬 폰트가 없어 `MISSING_FONT`로 실패한다. 읽기와 스크린샷은 Figma MCP(`get_metadata`, `get_screenshot`)로 한다.

## 실행 방법 (공통)

1. Chrome에 Figma 파일(`profile/figma_map.yaml`의 `file_key`)이 로그인된 채로 열려 있어야 한다. `tabs_context_mcp`로 그 탭의 id를 찾는다 (새 탭을 열지 않는다).
2. 스니펫 파일을 읽고 맨 위 `const ARGS = {...}`만 이번 작업 값으로 바꾼다. 노드 id와 페이지 id는 코드에 넣어 두지 않고 `profile/figma_map.yaml`(스키마는 `docs/contract.md` 3.3)에서 읽어 `ARGS`로 넘긴다.
3. 바꾼 전체 코드를 `javascript_tool`의 `text`로 그 탭에 실행한다. 스니펫은 top-level await를 쓰고 마지막 줄이 `JSON.stringify(...)` 결과다. 응답 JSON을 읽고 `out/<slug>/figma_log.md`에 남긴다.
4. 한 번에 한 스니펫만 실행하고, 응답을 확인한 뒤 다음으로 간다.

## 스니펫

| 파일               | 하는 일                                                                                                          | 쓰기 여부                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `inspect_texts.js` | 페이지·프레임의 텍스트 노드 목록 (id, 이름, 앞 120자, 글꼴, 크기, textAutoResize, 절대 좌표 상자)                  | 읽기                       |
| `save_version.js`  | 버전 기록에 복원 지점 저장. 편집 전에 꼭 한다                                                                    | 파일 스냅샷만              |
| `clone_frames.js`  | 프레임(또는 페이지 전체)을 새 페이지로 복제하고 `원본 id → 사본 id` 지도를 반환                                    | 새 페이지 생성             |
| `apply_text.js`    | 사본 노드에 슬롯 텍스트 적용. 바뀐 구간만 `deleteCharacters`/`insertCharacters`, 넘치면 되돌리고 보고              | 새 페이지의 텍스트만       |
| `export_pdf.js`    | 프레임을 PDF로 내보내 localhost 수신 서버로 POST (막히면 브라우저 다운로드로 대체)                                  | 읽기 (내보내기)            |
| `recv_server.py`   | `127.0.0.1`에서 POST 바이트를 받아 `out/` 아래에 저장. `--merge`로 프레임별 PDF를 한 파일로 합침                   | 로컬 파일                  |
| `lib_textdiff.js`  | 접두·접미 diff 논리 (테스트 대상). `apply_text.js`에 같은 함수가 들어 있다                                         | 없음                       |
| `check_textdiff.mjs` | `node tools/figma/check_textdiff.mjs`: diff 논리와 두 파일의 함수 일치를 검사                                    | 없음                       |

## 안전 규칙

- 원본 페이지(`figma_map.yaml`의 `resume.page`, `portfolio.page`)에는 쓰지 않는다. `apply_text.js`는 `allowedPageIds`(복제로 만든 새 페이지 id) 밖의 노드를 거부하고, 이 목록이 비면 실행하지 않는다.
- `apply_text.js`는 기본이 `dryRun: true`다. 계획을 먼저 보고, 사용자에게 보여 준 뒤 `false`로 바꿔 적용한다.
- 슬롯의 `max_chars`·`lines`를 넘는 텍스트는 적용하지 않고 `skipped`로 보고한다. 적용 뒤 높이가 원래보다 커지거나 최상위 프레임 밖으로 나가면 되돌리고 `reverted`로 보고한다.
- 텍스트는 `.characters`에 통째로 넣지 않는다. 혼합 스타일(굵기, 색)이 사라진다. 줄바꿈은 `\n`으로 넘기면 `apply_text.js`가 노드가 원래 쓰던 문자(문단 `\n` 또는 U+2028)로 맞춘다.
- 전체 텍스트가 바뀌는 슬롯이라도 첫·끝 글자의 스타일을 이어받는다. 결과는 반드시 `get_screenshot`으로 눈으로 확인한다.

## 수신 서버 (PDF 내보내기)

```bash
python tools/figma/recv_server.py --dir out/<slug>          # 별도 터미널에서 실행, Ctrl+C로 종료
python tools/figma/recv_server.py --merge out/<slug>/resume_ko.pdf out/<slug>/resume_ko_p1.pdf out/<slug>/resume_ko_p2.pdf
```

Figma 탭의 CSP가 `127.0.0.1` 요청을 막으면 `export_pdf.js`가 자동으로 `~/Downloads`에 다운로드한다. 그 파일을 `out/<slug>/`로 옮긴다. 큰 PDF가 막히면 프레임 단위로 나눠 내보낸다.

## 주의

- 처음 쓰는 파일에서는 `inspect_texts.js`와 `dryRun`으로 시작한다.
- 공유 파일에서 자동화 도구가 작동하는 동안 사용자가 같은 페이지를 편집하지 않도록 한다.
