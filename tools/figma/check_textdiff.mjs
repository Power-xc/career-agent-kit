// node tools/figma/check_textdiff.mjs : textDiff의 접두/접미 diff 논리를 검사한다.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const { textDiff, toFigmaText, lineCount, LINE_SEP } = createRequire(import.meta.url)("./lib_textdiff.js");

// 적용 결과가 항상 새 문자열과 같아야 한다.
function apply(oldText, newText) {
  const d = textDiff(oldText, newText);
  return oldText.slice(0, d.start) + d.insert + oldText.slice(d.start + d.deleteCount);
}

const cases = [
  ["", ""],
  ["abc", "abc"],
  ["abc", ""],
  ["", "abc"],
  ["AI Product Designer", "Senior Product Designer"],
  ["이탈률 36%→6%", "이탈률 36%→6% 달성"],
  ["가나다라마", "가나XX마"],
  ["aaaa", "aaa"],
  ["aaa", "aaaa"],
  ["abcabc", "abc"],
  ["한 줄", "한 줄\n두 줄"],
];
for (const [a, b] of cases) assert.equal(apply(a, b), b, `${JSON.stringify(a)} → ${JSON.stringify(b)}`);

// 변경이 없으면 아무것도 지우거나 넣지 않는다.
assert.deepEqual(textDiff("같음", "같음"), { start: 2, deleteCount: 0, insert: "" });
// 공통 접두·접미는 건드리지 않는다.
assert.deepEqual(textDiff("Senior Product Designer", "Senior UX Designer"), {
  start: 7,
  deleteCount: 7,
  insert: "UX",
});
// 접두와 접미가 겹치는 경우(aaa → aaaa)에도 길이가 어긋나지 않는다.
assert.deepEqual(textDiff("aaa", "aaaa"), { start: 3, deleteCount: 0, insert: "a" });
// 줄바꿈은 노드의 원래 문자를 따른다: 문단(\n) 노드는 그대로, U+2028만 쓰는 노드는 U+2028로.
assert.equal(toFigmaText("a\nb", "x\ny"), "a\nb");
assert.equal(toFigmaText("a\nb", "x" + LINE_SEP + "y"), "a" + LINE_SEP + "b");
assert.equal(toFigmaText("a\r\nb", "한 줄"), "a\nb");
assert.equal(lineCount("a\nb" + LINE_SEP + "c"), 3);
assert.equal(LINE_SEP.charCodeAt(0), 0x2028);

console.log("textdiff ok");

// apply_text.js 안의 복사본이 lib_textdiff.js와 같은지 확인한다.
import { readFileSync } from "node:fs";
const fnSource = (file) => {
  const s = readFileSync(new URL(file, import.meta.url), "utf8");
  const m = s.match(/function textDiff[\s\S]*?\n}\n/);
  assert.ok(m, `${file}에서 textDiff를 찾지 못했습니다`);
  return m[0].replace(/\s+/g, " ").trim();
};
// 두 파일의 서식 차이는 무시하고 토큰 순서만 비교한다.
const squash = (s) => s.replace(/\s+/g, "");
assert.equal(squash(fnSource("apply_text.js")), squash(fnSource("lib_textdiff.js")), "apply_text.js의 textDiff가 lib_textdiff.js와 다릅니다");
const helperSource = (file, name) => {
  const s = readFileSync(new URL(file, import.meta.url), "utf8");
  const m = s.match(new RegExp(`function ${name}[\\s\\S]*?\\n}\\n`));
  assert.ok(m, `${file}에서 ${name}을 찾지 못했습니다`);
  return squash(m[0]);
};
for (const name of ["toFigmaText", "lineCount"]) {
  assert.equal(helperSource("apply_text.js", name), helperSource("lib_textdiff.js", name), `apply_text.js의 ${name}이 lib_textdiff.js와 다릅니다`);
}
console.log("apply_text.js copy ok");
