// 새 페이지의 프레임을 PDF로 내보내 localhost 수신 서버(recv_server.py)에 보낸다.
// 수신 서버가 막히면(CSP·네트워크) 브라우저 다운로드로 대체한다 (~/Downloads).
// 실행: Claude in Chrome javascript_tool (로그인된 Figma 파일 탭). 먼저 터미널에서 recv_server.py를 켠다.
const ARGS = {
  receiver: "http://127.0.0.1:8765/save",
  frames: [
    // { id: "사본 프레임 id", name: "resume_ko_p1.pdf" }  // 프레임 하나가 PDF 한 쪽 파일이 된다
  ],
};

async function sendToReceiver(name, bytes) {
  const res = await fetch(`${ARGS.receiver}?name=${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: bytes,
  });
  if (!res.ok) throw new Error("수신 서버 응답 " + res.status);
  return await res.json();
}

function downloadInBrowser(name, bytes) {
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

const results = [];
for (const frame of ARGS.frames) {
  const node = await figma.getNodeByIdAsync(frame.id);
  if (!node) {
    results.push({ name: frame.name, status: "error", reason: "노드를 찾을 수 없음" });
    continue;
  }
  const bytes = await node.exportAsync({ format: "PDF" });
  try {
    const saved = await sendToReceiver(frame.name, bytes);
    results.push({ name: frame.name, status: "sent", bytes: bytes.length, saved });
  } catch (err) {
    downloadInBrowser(frame.name, bytes);
    results.push({ name: frame.name, status: "downloaded", bytes: bytes.length, reason: String(err && err.message ? err.message : err) });
  }
}

JSON.stringify(results);
