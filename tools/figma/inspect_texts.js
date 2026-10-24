// 읽기 전용. 페이지 또는 프레임 안의 텍스트 노드를 나열한다.
// 실행: Claude in Chrome javascript_tool (로그인된 Figma 파일 탭, window.figma, top-level await)
const ARGS = {
  rootId: "0:0", // 페이지 또는 프레임 node id (예시 값. figma_map.yaml의 page·frames 값을 넣는다)
  maxChars: 120, // characters 미리보기 길이
};

const MAX_FONT_NAMES = 6;

const root = await figma.getNodeByIdAsync(ARGS.rootId);
if (!root) throw new Error("노드를 찾을 수 없습니다: " + ARGS.rootId);
if (root.type === "PAGE") await root.loadAsync();

const texts = root.findAllWithCriteria({ types: ["TEXT"] });
const rows = texts.map((node) => {
  const len = node.characters.length;
  const fonts = len > 0 ? node.getRangeAllFontNames(0, len).map((f) => f.family + " " + f.style) : [];
  const box = node.absoluteBoundingBox;
  return {
    id: node.id,
    name: node.name,
    characters: node.characters.slice(0, ARGS.maxChars).replace(/\u2028/g, "⏎"),
    length: len,
    fonts: fonts.slice(0, MAX_FONT_NAMES),
    fontSize: node.fontSize === figma.mixed ? "mixed" : node.fontSize,
    textAutoResize: node.textAutoResize,
    box: box && { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) },
  };
});

JSON.stringify({ root: root.name, count: rows.length, rows });
