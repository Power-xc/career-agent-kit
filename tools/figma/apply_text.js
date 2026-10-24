// 텍스트 슬롯을 새 페이지의 사본 노드에 적용한다. 혼합 스타일을 지키기 위해 바뀐 가운데 구간만 고친다.
// 안전장치: allowedPageIds 밖의 노드는 건드리지 않고, 슬롯 한도(maxChars·lines)나 프레임을 넘으면 되돌린다.
// 실행: Claude in Chrome javascript_tool (로그인된 Figma 파일 탭)
const ARGS = {
  allowedPageIds: [], // 복제로 만든 새 페이지 id (필수. 원본 페이지 id를 넣지 않는다)
  dryRun: true, // true면 바꾸지 않고 계획만 돌려준다
  edits: [
    // { id: "사본 노드 id", slot: "resume.header.title", text: "새 텍스트(줄바꿈은 \n, 노드가 U+2028만 쓰면 자동 변환)", maxChars: 30, lines: 1 }
  ],
};

const LINE_SEP = String.fromCharCode(0x2028);
const BOX_TOLERANCE_PX = 1; // 프레임·원래 높이를 이만큼까지는 넘어도 된다

// lib_textdiff.js의 textDiff와 같다 (check_textdiff.mjs가 두 파일이 같은지 검사한다)
function textDiff(oldText, newText) {
  const maxPrefix = Math.min(oldText.length, newText.length);
  let prefix = 0;
  while (prefix < maxPrefix && oldText[prefix] === newText[prefix]) prefix++;
  const maxSuffix = maxPrefix - prefix;
  let suffix = 0;
  while (suffix < maxSuffix && oldText[oldText.length - 1 - suffix] === newText[newText.length - 1 - suffix]) suffix++;
  return { start: prefix, deleteCount: oldText.length - prefix - suffix, insert: newText.slice(prefix, newText.length - suffix) };
}

// lib_textdiff.js의 toFigmaText·lineCount와 같다
function toFigmaText(text, current) {
  const t = text.replace(/\r\n/g, "\n");
  const usesLineSep = current.includes(LINE_SEP) && !current.includes("\n");
  return usesLineSep ? t.split("\n").join(LINE_SEP) : t;
}
function lineCount(text) {
  return text.split("\n").join(LINE_SEP).split(LINE_SEP).length;
}

function pageOf(node) {
  let cur = node;
  while (cur && cur.type !== "PAGE") cur = cur.parent;
  return cur;
}

function topFrameOf(node) {
  let cur = node;
  while (cur.parent && cur.parent.type !== "PAGE") cur = cur.parent;
  return cur;
}

// 바뀐 구간만 고친다. 새 글자는 지우려는 구간 마지막 글자의 스타일을 이어받는다.
function replaceRange(node, d) {
  if (d.deleteCount > 0) {
    if (d.insert) node.insertCharacters(d.start + d.deleteCount, d.insert, "BEFORE");
    node.deleteCharacters(d.start, d.start + d.deleteCount);
  } else if (d.insert) {
    node.insertCharacters(d.start, d.insert, d.start > 0 ? "BEFORE" : "AFTER");
  }
}

async function loadFonts(node) {
  const len = node.characters.length;
  if (len === 0) throw new Error("빈 텍스트 노드는 글꼴을 알 수 없어 건드리지 않습니다");
  const fonts = node.getRangeAllFontNames(0, len);
  await Promise.all(fonts.map((f) => figma.loadFontAsync(f)));
}

// 고정 크기 상자는 높이를 재기 위해 잠시 HEIGHT 자동 크기로 바꿨다가 원래대로 돌린다.
function measureHeight(node) {
  const orig = { mode: node.textAutoResize, w: node.width, h: node.height };
  if (orig.mode === "NONE") node.textAutoResize = "HEIGHT";
  const h = node.height;
  if (orig.mode === "NONE") {
    node.textAutoResize = "NONE";
    node.resize(orig.w, orig.h);
  }
  return h;
}

function overflowReason(node, origHeight) {
  const h = measureHeight(node);
  if (h > origHeight + BOX_TOLERANCE_PX) return `높이 ${Math.round(origHeight)}→${Math.round(h)}px로 커짐`;
  const frame = topFrameOf(node).absoluteBoundingBox;
  const box = node.absoluteBoundingBox;
  if (frame && box) {
    if (box.y + h > frame.y + frame.height + BOX_TOLERANCE_PX) return "프레임 아래로 넘침";
    if (box.x + box.width > frame.x + frame.width + BOX_TOLERANCE_PX) return "프레임 오른쪽으로 넘침";
  }
  return null;
}

async function applyEdit(edit) {
  const node = await figma.getNodeByIdAsync(edit.id);
  if (!node || node.type !== "TEXT") return { slot: edit.slot, id: edit.id, status: "skipped", reason: "텍스트 노드가 아님" };
  const page = pageOf(node);
  if (!page || !ARGS.allowedPageIds.includes(page.id)) return { slot: edit.slot, id: edit.id, status: "skipped", reason: "허용된 새 페이지 밖의 노드" };

  const before = node.characters;
  const next = toFigmaText(edit.text, before);
  if (edit.maxChars && next.length > edit.maxChars) return { slot: edit.slot, id: edit.id, status: "skipped", reason: `${next.length}자 > 슬롯 상한 ${edit.maxChars}자` };
  const lines = lineCount(next);
  if (edit.lines && lines > edit.lines) return { slot: edit.slot, id: edit.id, status: "skipped", reason: `${lines}줄 > 슬롯 상한 ${edit.lines}줄` };

  const d = textDiff(before, next);
  if (d.deleteCount === 0 && !d.insert) return { slot: edit.slot, id: edit.id, status: "unchanged" };
  if (ARGS.dryRun) return { slot: edit.slot, id: edit.id, status: "planned", diff: { start: d.start, deleteCount: d.deleteCount, insert: d.insert } };

  await loadFonts(node);
  const origHeight = node.height;
  replaceRange(node, d);
  const problem = node.characters !== next ? "적용 결과가 요청 텍스트와 다름" : overflowReason(node, origHeight);
  if (problem) {
    replaceRange(node, textDiff(node.characters, before)); // 되돌린다
    return { slot: edit.slot, id: edit.id, status: "reverted", reason: problem, restored: node.characters === before };
  }
  return { slot: edit.slot, id: edit.id, status: "applied" };
}

if (ARGS.allowedPageIds.length === 0) throw new Error("allowedPageIds가 비어 있습니다. 복제한 새 페이지 id를 넣으세요.");

const results = [];
for (const edit of ARGS.edits) {
  try {
    results.push(await applyEdit(edit));
  } catch (err) {
    results.push({ slot: edit.slot, id: edit.id, status: "error", reason: String(err && err.message ? err.message : err) });
  }
}

const summary = results.reduce((acc, r) => ((acc[r.status] = (acc[r.status] || 0) + 1), acc), {});
JSON.stringify({ dryRun: ARGS.dryRun, summary, results });
