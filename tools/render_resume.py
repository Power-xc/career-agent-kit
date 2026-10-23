#!/usr/bin/env python3
"""이력서 변형 YAML + 사실 은행 → ATS 친화 HTML → Chrome headless PDF.

사용: python tools/render_resume.py profile/resume_base.yaml [--out out/base/resume_ko.pdf] [--with-phone]
종료 코드: 0 정상, 2 입력·환경 오류. 이메일·전화번호는 콘솔에 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml이 필요합니다: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_TIMEOUT_SEC = 60
PDF_POLL_SEC = 0.2
PDF_STABLE_SEC = 1.0  # PDF 크기가 이 시간 동안 같으면 다 쓴 것으로 본다
CHROME_EXIT_SEC = 5
DEFAULT_DOC_KIND = {"ko": "이력서", "en": "Resume"}
CURRENT = {"ko": "현재", "en": "Present"}
PLANNED = {"ko": "취득 예정", "en": "expected"}
HEADINGS = {
    "ko": {
        "summary": "요약", "experience": "경력", "projects": "프로젝트", "skills": "스킬",
        "strengths": "강점", "awards": "수상", "certifications": "자격증",
        "education": "학력", "motivation": "지원 동기",
    },
    "en": {
        "summary": "Summary", "experience": "Experience", "projects": "Projects", "skills": "Skills",
        "strengths": "Strengths", "awards": "Awards", "certifications": "Certifications",
        "education": "Education", "motivation": "Motivation",
    },
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


HYPHENATED = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")


def text_html(value: object) -> str:
    """본문 텍스트. 하이픈 단어는 줄 끝에서 끊기지 않게 묶는다 (pdftotext가 'Human-in-the-\\nLoop'를 'Human-in-theLoop'로 붙인다)."""
    return HYPHENATED.sub(lambda m: f'<span class="nobr">{m.group(0)}</span>', esc(value))


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        sys.exit(f"파일을 읽을 수 없습니다: {path} ({exc.__class__.__name__})")
    if not isinstance(data, dict):
        sys.exit(f"YAML 최상위가 매핑이 아닙니다: {path}")
    return data


def pick(obj: dict, key: str, lang: str) -> str:
    """{ko, en} 값에서 lang을 고르고, 없으면 다른 언어로 대체한다."""
    value = obj.get(key)
    if isinstance(value, dict):
        return value.get(lang) or value.get("ko") or value.get("en") or ""
    return value or ""


def index_by_id(items: list[dict] | None) -> dict[str, dict]:
    return {item["id"]: item for item in items or [] if "id" in item}


def date_range(start: str, end: str | None, lang: str) -> str:
    return f"{start} – {end or CURRENT[lang]}"


def bullets_html(bullets: list[dict] | None) -> str:
    if not bullets:
        return ""
    items = "".join(f"<li>{text_html(b['text'])}</li>" for b in bullets)
    return f"<ul>{items}</ul>"


def render_experience(resume: dict, facts: dict, lang: str) -> str:
    exps = index_by_id(facts.get("experience"))
    out = []
    for item in resume.get("experience", []):
        exp = exps.get(item["ref"])
        if exp is None:
            sys.exit(f"사실 은행에 없는 experience id: {item['ref']}")
        title = item.get("title_display") or pick(exp, "title", lang)
        # 직함을 제목 줄 맨 앞에 둔다: 파서와 리크루터가 경력의 첫 줄을 직함으로 읽는다
        head = title
        meta = " · ".join(
            part for part in (f"{pick(exp, 'company', lang)} {pick(exp, 'unit', lang)}".strip(), exp.get("rank", ""),
                              date_range(exp["start"], exp.get("end"), lang)) if part
        )
        if exp.get("kind") == "leave":
            head, meta = pick(exp, "title", lang), f"{pick(exp, 'company', lang)} · {date_range(exp['start'], exp.get('end'), lang)}"
        out.append(f'<div class="entry"><h3>{esc(head)}</h3><p class="meta">{esc(meta)}</p>'
                   f'{bullets_html(item.get("bullets"))}</div>')
    return "".join(out)


def render_projects(resume: dict, facts: dict, lang: str) -> str:
    projects = index_by_id(facts.get("projects"))
    out = []
    for item in resume.get("projects", []):
        prj = projects.get(item["ref"])
        if prj is None:
            sys.exit(f"사실 은행에 없는 project id: {item['ref']}")
        meta = " · ".join(p for p in (prj.get("period", ""), prj.get("role", "")) if p)
        out.append(f'<div class="entry"><h3>{esc(pick(prj, "name", lang))}</h3>'
                   f'<p class="meta">{esc(meta)}</p>{bullets_html(item.get("bullets"))}</div>')
    return "".join(out)


def render_skills(resume: dict) -> str:
    rows = [f'<p><span class="group">{esc(g["group"])}</span>: {text_html(", ".join(g["items"]))}</p>'
            for g in resume.get("skills", [])]
    return "".join(rows)


def render_strengths(resume: dict) -> str:
    return "".join(f'<div class="strength"><h3>{esc(s["title"])}</h3><p>{text_html(s["text"])}</p></div>'
                   for s in resume.get("strengths", []))


def render_awards(resume: dict, facts: dict) -> str:
    awards = index_by_id(facts.get("awards"))
    lines = []
    for aid in resume.get("awards", []):
        if aid not in awards:
            sys.exit(f"사실 은행에 없는 award id: {aid}")
        lines.append(f"<li>{esc(awards[aid]['name'])} ({esc(awards[aid]['date'])})</li>")
    return f"<ul>{''.join(lines)}</ul>" if lines else ""


def render_certs(resume: dict, facts: dict, lang: str) -> str:
    certs = index_by_id(facts.get("certifications"))
    lines = []
    for cid in resume.get("certifications", []):
        cert = certs.get(cid)
        if cert is None:
            sys.exit(f"사실 은행에 없는 certification id: {cid}")
        if cert.get("confidence") == "check":
            print(f"경고: {cid}는 confidence=check입니다. 확인 전에는 서류에 쓰지 않는 것이 규칙입니다.", file=sys.stderr)
        when = f"{cert['date']} {PLANNED[lang]}" if cert.get("status") == "planned" else cert.get("date")
        suffix = f" ({esc(when)})" if when else ""
        lines.append(f"<li>{esc(cert['name'])} · {esc(cert['issuer'])}{suffix}</li>")
    return f"<ul>{''.join(lines)}</ul>" if lines else ""


def render_education(resume: dict, facts: dict) -> str:
    edus = index_by_id(facts.get("education"))
    lines = []
    for eid in resume.get("education", []):
        edu = edus.get(eid)
        if edu is None:
            sys.exit(f"사실 은행에 없는 education id: {eid}")
        text = f"{edu['school']} {edu['major']} · {edu['degree']} ({edu['start']} – {edu['end']})"
        if edu.get("gpa"):
            text += f" · GPA {edu['gpa']}"
        lines.append(f"<li>{esc(text)}</li>")
    return f"<ul>{''.join(lines)}</ul>" if lines else ""


def render_contact(resume: dict, facts: dict, contact: dict, with_phone: bool) -> str:
    links = index_by_id(facts.get("person", {}).get("links"))
    parts = []
    header = resume["header"]
    if header.get("location"):
        parts.append(esc(header["location"]))
    if contact.get("email"):
        parts.append(esc(contact["email"]))
    if with_phone and contact.get("phone"):
        parts.append(esc(contact["phone"]))
    for lid in header.get("links", []):
        link = links.get(lid)
        if link is None:
            sys.exit(f"사실 은행에 없는 link id: {lid}")
        if not link.get("public"):
            print(f"경고: 비공개 링크 {lid}는 건너뜁니다.", file=sys.stderr)
            continue
        parts.append(f'{esc(link["label"])} <a href="{esc(link["url"])}">{esc(link["url"])}</a>')
    return "".join(f"<span>{p}</span>" for p in parts)


def section(key: str, lang: str, body: str, css_class: str = "") -> str:
    if not body:
        return ""
    return f'<section class="section {css_class}"><h2>{esc(HEADINGS[lang][key])}</h2>{body}</section>'


def build_sections(resume: dict, facts: dict, lang: str) -> str:
    summary = "".join(f"<p>{text_html(s['text'])}</p>" for s in resume.get("summary", []))
    motivation = resume.get("motivation")
    parts = [
        section("summary", lang, summary, "summary"),
        section("experience", lang, render_experience(resume, facts, lang)),
        section("projects", lang, render_projects(resume, facts, lang)),
        section("skills", lang, render_skills(resume), "skills"),
        section("strengths", lang, render_strengths(resume)),
        section("awards", lang, render_awards(resume, facts)),
        section("certifications", lang, render_certs(resume, facts, lang)),
        section("education", lang, render_education(resume, facts)),
        section("motivation", lang, f"<p>{text_html(motivation['text'])}</p>" if motivation else ""),
    ]
    return "\n".join(p for p in parts if p)


def build_html(resume: dict, facts: dict, contact: dict, with_phone: bool) -> str:
    lang = resume.get("meta", {}).get("lang", "ko")
    if lang not in HEADINGS:
        sys.exit(f"지원하지 않는 lang: {lang} (ko 또는 en)")
    header = resume["header"]
    tagline = header.get("tagline")
    tagline_html = f'<p class="tagline">{esc(tagline)}</p>' if tagline else ""
    template = (ROOT / "templates" / "resume_ats.html").read_text(encoding="utf-8")
    css = (ROOT / "templates" / "resume_ats.css").read_text(encoding="utf-8")
    values = {
        "lang": lang,
        "doc_title": f"{header['name']} {DEFAULT_DOC_KIND[lang]}",
        "css": css,
        "name": esc(header["name"]),
        "title": esc(header["title"]),
        "tagline_html": tagline_html,
        "contact_html": render_contact(resume, facts, contact, with_phone),
        "sections_html": build_sections(resume, facts, lang),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def wait_for_stable_pdf(proc: subprocess.Popen, pdf_path: Path) -> bool:
    """PDF가 생기고 크기가 PDF_STABLE_SEC 동안 변하지 않을 때까지(또는 Chrome이 끝날 때까지) 기다린다."""
    deadline = time.monotonic() + CHROME_TIMEOUT_SEC
    last_size, stable_since = -1, time.monotonic()
    while time.monotonic() < deadline:
        size = pdf_path.stat().st_size if pdf_path.exists() else 0
        now = time.monotonic()
        if size != last_size:
            last_size, stable_since = size, now
        if size > 0 and now - stable_since >= PDF_STABLE_SEC:
            return True
        if proc.poll() is not None:
            return size > 0
        time.sleep(PDF_POLL_SEC)
    return False


def stop_chrome(proc: subprocess.Popen) -> None:
    """Chrome 프로세스 그룹(렌더러 포함)을 종료한다."""
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=CHROME_EXIT_SEC)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def print_pdf(html_text: str, pdf_path: Path) -> None:
    if not Path(CHROME).exists():
        sys.exit(f"Chrome을 찾을 수 없습니다: {CHROME}")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ash-render-") as tmp:
        src = Path(tmp) / "resume.html"
        src.write_text(html_text, encoding="utf-8")
        cmd = [CHROME, "--headless=new", "--no-pdf-header-footer", "--disable-gpu",
               f"--user-data-dir={tmp}/profile", f"--print-to-pdf={pdf_path}", src.as_uri()]
        pdf_path.unlink(missing_ok=True)
        # Chrome은 PDF를 쓴 뒤에도 종료가 늦어지므로, 파일이 완성되면 직접 종료한다
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            done = wait_for_stable_pdf(proc, pdf_path)
        finally:
            stop_chrome(proc)
    if not done:
        sys.exit(f"Chrome이 {CHROME_TIMEOUT_SEC}초 안에 PDF를 만들지 못했습니다. Chrome 경로와 --html-only 출력을 확인하세요.")


def set_metadata(pdf_path: Path, resume: dict, facts: dict) -> None:
    try:
        import pymupdf as fitz
    except ImportError:
        print("안내: pymupdf가 없어 PDF 메타데이터 설정을 건너뜁니다.", file=sys.stderr)
        return
    lang = resume.get("meta", {}).get("lang", "ko")
    name = resume["header"]["name"]
    doc = fitz.open(pdf_path)
    doc.set_metadata({
        "title": f"{name} {DEFAULT_DOC_KIND[lang]}",
        "author": name,
        "subject": resume["header"]["title"],
        "keywords": "",
        "creator": "ai-screening-harness",
        "producer": "",
    })
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    tmp.replace(pdf_path)


def default_out(src: Path, resume: dict) -> Path:
    meta = resume.get("meta", {})
    return ROOT / "out" / str(meta.get("variant", "base")) / f"resume_{meta.get('lang', 'ko')}.pdf"


def main() -> int:
    ap = argparse.ArgumentParser(description="이력서 YAML을 ATS 친화 PDF로 렌더링합니다.")
    ap.add_argument("resume", type=Path, help="이력서 변형 YAML")
    ap.add_argument("--out", type=Path, help="출력 PDF (기본: out/<variant>/resume_<lang>.pdf)")
    ap.add_argument("--facts", type=Path, default=ROOT / "profile" / "facts.yaml")
    ap.add_argument("--contact", type=Path, default=ROOT / "profile" / "contact.local.yaml")
    ap.add_argument("--with-phone", action="store_true", help="전화번호를 넣는다 (공개용 PDF에는 쓰지 않는다)")
    ap.add_argument("--html-only", action="store_true", help="HTML만 출력 경로 옆에 저장한다")
    args = ap.parse_args()

    resume, facts = load_yaml(args.resume), load_yaml(args.facts)
    contact = load_yaml(args.contact) if args.contact.exists() else {}
    if not contact:
        print("안내: contact.local.yaml이 없어 이메일 없이 렌더링합니다.", file=sys.stderr)
    out = args.out or default_out(args.resume, resume)
    html_text = build_html(resume, facts, contact, args.with_phone)
    if args.html_only:
        out.with_suffix(".html").parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".html").write_text(html_text, encoding="utf-8")
        print(f"HTML 저장: {out.with_suffix('.html')}")
        return 0
    print_pdf(html_text, out)
    set_metadata(out, resume, facts)
    print(f"PDF 저장: {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
