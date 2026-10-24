// 원본 프레임(또는 페이지 전체)을 새 페이지로 복제하고 원본 id → 사본 id 지도를 돌려준다.
// 원본은 건드리지 않는다. 같은 이름의 페이지가 이미 있으면 멈춘다.
// 실행: Claude in Chrome javascript_tool (로그인된 Figma 파일 탭)
const ARGS = {
  newPageName: "예시회사 지원본 (2026-01-01)", // "<회사명> 지원본 (YYYY-MM-DD)" 또는 "<회사명> 포폴 (YYYY-MM-DD)"
  // 둘 중 하나: 프레임 id 목록(figma_map.yaml의 resume.frames 또는 portfolio.frames), 또는 sourcePageId(페이지의 최상위 노드를 모두 복제)
  frameIds: ["0:0"], // 예시 값. figma_map.yaml의 resume.frames 또는 portfolio.frames 값을 넣는다
  sourcePageId: null, // 예: figma_map.yaml의 portfolio.page
};

// 두 노드 트리를 같은 순서로 걸어 id 지도를 만든다 (복제본은 자식 순서가 같다).
function mapIds(orig, copy, out) {
  out[orig.id] = copy.id;
  if (!("children" in orig) || !("children" in copy)) return;
  if (orig.children.length !== copy.children.length) {
    throw new Error("복제본 구조가 원본과 다릅니다: " + orig.id);
  }
  orig.children.forEach((child, i) => mapIds(child, copy.children[i], out));
}

await figma.loadAllPagesAsync();
if (figma.root.children.some((p) => p.name === ARGS.newPageName)) {
  throw new Error("같은 이름의 페이지가 이미 있습니다: " + ARGS.newPageName);
}

let sources;
if (ARGS.sourcePageId) {
  const page = await figma.getNodeByIdAsync(ARGS.sourcePageId);
  if (!page || page.type !== "PAGE") throw new Error("페이지가 아닙니다: " + ARGS.sourcePageId);
  await page.loadAsync();
  sources = [...page.children];
} else {
  sources = await Promise.all(ARGS.frameIds.map((id) => figma.getNodeByIdAsync(id)));
}
if (sources.length === 0 || sources.some((n) => !n)) throw new Error("복제할 노드를 찾지 못했습니다.");

const newPage = figma.createPage();
newPage.name = ARGS.newPageName;

const idMap = {};
const cloneFrames = [];
for (const src of sources) {
  const copy = src.clone(); // 같은 부모(원본 페이지)에 생긴다
  const { x, y } = src;
  newPage.appendChild(copy); // 새 페이지로 옮긴다
  copy.x = x;
  copy.y = y;
  mapIds(src, copy, idMap);
  cloneFrames.push(copy.id);
}

JSON.stringify({ pageId: newPage.id, pageName: newPage.name, cloneFrames, nodeCount: Object.keys(idMap).length, idMap });
