"""터미널 스타일 데모 프레임(HTML) 생성. 가상의 출력만 쓴다. 사용: python3 demo.py <out_dir>"""
import sys, pathlib
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
Y, M, G = "#FFD84D", "#9C968A", "#8FD694"
STEPS = [
 ("① 회사 딥리서치", "companies/예시회사/ 에 조사 파일 4개 저장", "[확인] 채용 페이지 · [보도] 기사 3건"),
 ("② 공고 저장", "jd/tier1/예시회사__backend-engineer.md", "필수 6 · 우대 4 요건 구조화"),
 ("③ 사실 안에서 맞춤", "out/예시회사/resume_ko.yaml", "사실 은행 밖 숫자 0건"),
 ("④ ATS · LLM · 리크루터 심사", "out/예시회사/screening.md", "매칭 72점 (경쟁권) · 우선 수정 5개"),
 ("⑤ 제출 패키지", "out/예시회사/pack/", "PDF · 자기소개서 초안 · 체크리스트"),
]
def frame(n_steps, typed, final):
    body = f'<div><span style="color:{Y}">❯</span> {typed}<span class="cur"></span></div>'
    if n_steps or final: body += '<div class="gap"></div>'
    for i, (t, p, d) in enumerate(STEPS[:n_steps]):
        body += f'<div class="st"><span style="color:{G}">✓</span> <b>{t}</b><div class="p">{p}</div><div class="d">{d}</div></div>'
    if final: body += f'<div class="gap"></div><div class="fin">완료 → <b style="color:{Y}">out/예시회사/SUMMARY.md</b></div>'
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#16140F;color:#F3EEE4;font-family:"SF Mono",Menlo,Pretendard,monospace;word-break:keep-all}}
.win{{width:960px;height:540px;box-sizing:border-box;padding:0;position:relative}}
.bar{{height:44px;background:#221F19;display:flex;align-items:center;gap:8px;padding:0 18px;border-bottom:1px solid #3A362C;font:500 14px Pretendard;color:{M}}}
.bar i{{width:12px;height:12px;border-radius:50%;background:#3A362C;display:block}}
.bar span{{margin-left:12px}}
.t{{padding:14px 30px;font-size:18px;line-height:1.4}}
.cur{{display:inline-block;width:10px;height:21px;background:{Y};vertical-align:-4px;margin-left:3px}}
.gap{{height:8px}}.st{{margin-bottom:5px}}.st b{{font-family:Pretendard;font-weight:700}}
.p{{color:{Y};margin-left:26px;font-size:15px}}.d{{color:{M};margin-left:26px;font-size:13.5px;font-family:Pretendard}}
.fin{{font-family:Pretendard;font-size:20px}}
</style></head><body><div class="win"><div class="bar"><i></i><i></i><i></i><span>career-agent-kit — 예시 (가상 출력)</span></div><div class="t">{body}</div></div></body></html>'''
cmd = "/apply 예시회사"
seq = [("", 0, False)] * 2 + [(cmd[:k], 0, False) for k in range(1, len(cmd) + 1)] + [(cmd, 0, False)] * 2
seq += [(cmd, n, False) for n in range(1, 6) for _ in range(3)] + [(cmd, 5, True)] * 8
# 각 프레임 = 0.5초 (fps 2). 타이핑은 빠르게 보이도록 같은 프레임 길이를 쓴다.
for i, (typed, n, fin) in enumerate(seq):
    (out / f"f{i:03d}.html").write_text(frame(n, typed, fin), encoding="utf-8")
print(len(seq))
