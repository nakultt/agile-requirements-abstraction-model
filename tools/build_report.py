"""Render report/report.html to report/RAM_Report.pdf with headless Edge/Chrome.

Two passes: the first render finds the page on which each section starts; the second fills
the table of contents with those page numbers. Requires pypdf.

Usage: python tools/build_report.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "report" / "report.html"
TMP = ROOT / "report" / "_render.html"
OUT = ROOT / "report" / "RAM_Report.pdf"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
BROWSER = next((b for b in BROWSERS if Path(b).exists()), None)

HEADINGS = {  # toc id -> heading text as printed
    "s1": "1 Introduction", "s2": "2 Background and Related Work", "s3": "3 Research Questions and Method",
    "s4": "4 RAM Adapted for Agile Teams", "s5": "5 System Design and Implementation",
    "s6": "6 Case Study: CampusConnect", "s7": "7 Results: The Toolkit in Use", "s8": "8 Evaluation",
    "s9": "9 Discussion and Threats to Validity", "s10": "10 Conclusion and Future Work",
    "refs": "References", "appA": "Appendix A Reproducing the Results",
}


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("\u00a0", " ")).strip()


def render(html: Path, pdf: Path):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([BROWSER, "--headless=new", "--disable-gpu", f"--user-data-dir={prof}",
                        "--no-pdf-header-footer", "--virtual-time-budget=5000",
                        f"--print-to-pdf={pdf}", html.as_uri()], check=True, capture_output=True, timeout=180)


def find_pages(pdf: Path):
    pages = [norm(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    found = {}
    for key, text in HEADINGS.items():
        for i in range(3, len(pages)):          # skip title, abstract and contents pages
            if text in pages[i]:
                found[key] = i + 1
                break
    return found, len(pages)


if __name__ == "__main__":
    if not BROWSER:
        sys.exit("Edge/Chrome not found")
    src = SRC.read_text(encoding="utf-8")
    TMP.write_text(re.sub(r"\{\{pg:\w+\}\}", "0", src), encoding="utf-8")
    first = ROOT / "report" / "_pass1.pdf"
    render(TMP, first)
    found, n = find_pages(first)
    missing = set(HEADINGS) - set(found)
    if missing:
        print("WARNING: headings not found:", sorted(missing))
    TMP.write_text(re.sub(r"\{\{pg:(\w+)\}\}", lambda m: str(found.get(m.group(1), "")), src), encoding="utf-8")
    render(TMP, OUT)
    found2, n2 = find_pages(OUT)
    print(f"pages: {n2}  toc: {found2}")
    if found2 != found:
        print("NOTE: pagination moved between passes; rerun to settle the contents page")
    first.unlink(missing_ok=True)
    TMP.unlink(missing_ok=True)
