// 두 문자열의 공통 접두·접미를 빼고 바뀐 가운데 구간만 돌려준다.
// Figma 텍스트 노드는 .characters 전체 교체 시 혼합 스타일이 사라지므로, 바뀐 구간만 deleteCharacters/insertCharacters로 고친다.
// 브라우저(javascript_tool)에서는 이 파일 내용을 붙여 넣어 전역 함수로 쓰고, node에서는 import로 쓴다.

function textDiff(oldText, newText) {
  const maxPrefix = Math.min(oldText.length, newText.length);
  let prefix = 0;
  while (prefix < maxPrefix && oldText[prefix] === newText[prefix]) prefix++;

  const maxSuffix = maxPrefix - prefix;
  let suffix = 0;
  while (suffix < maxSuffix && oldText[oldText.length - 1 - suffix] === newText[newText.length - 1 - suffix]) suffix++;

  return { start: prefix, deleteCount: oldText.length - prefix - suffix, insert: newText.slice(prefix, newText.length - suffix) };
}

// 줄바꿈은 노드가 원래 쓰던 문자를 따른다. 문단 줄바꿈(\n)을 쓰는 노드는 그대로 두고,
// U+2028(줄 구분자)만 쓰는 노드에서는 \n을 U+2028로 바꾼다. 문자가 바뀌면 diff가 커져 혼합 스타일이 깨진다.
const LINE_SEP = String.fromCharCode(0x2028);
function toFigmaText(text, current) {
  const t = text.replace(/\r\n/g, "\n");
  const usesLineSep = current.includes(LINE_SEP) && !current.includes("\n");
  return usesLineSep ? t.split("\n").join(LINE_SEP) : t;
}
function lineCount(text) {
  return text.split("\n").join(LINE_SEP).split(LINE_SEP).length;
}

if (typeof module !== "undefined") module.exports = { textDiff, toFigmaText, lineCount, LINE_SEP };
