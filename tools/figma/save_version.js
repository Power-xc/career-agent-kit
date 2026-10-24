// 편집 전 복원 지점을 남긴다 (버전 기록). 쓰기 작업이 아니라 파일 스냅샷이다.
// 실행: Claude in Chrome javascript_tool (로그인된 Figma 파일 탭)
const ARGS = {
  title: "편집 전 복원 지점", // 호출할 때 회사명과 날짜를 붙인다: "예시회사 지원본 전 (2026-01-01)"
  description: "figma-apply 실행 전 상태",
};

await figma.saveVersionHistoryAsync(ARGS.title, ARGS.description);
JSON.stringify({ saved: true, title: ARGS.title });
