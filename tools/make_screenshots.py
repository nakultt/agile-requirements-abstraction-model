"""Capture screenshots of each web-app view with headless Edge/Chrome, and terminal-style
renderings of CLI output, into docs/screenshots/.

Usage: python tools/make_screenshots.py
"""
import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            shutil.which("chromium") or "", shutil.which("google-chrome") or ""]
BROWSER = next((b for b in BROWSERS if b and Path(b).exists()), None)

VIEWS = {  # route -> (file name, window height)
    "model": ("01-model", 840), "workup": ("02-workup", 780), "validate": ("03-validation", 820),
    "trace": ("04-traceability", 640), "plan": ("05-planning", 600), "metrics": ("06-metrics", 560),
}


def shoot(url: str, dest: Path, w: int, h: int):
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([BROWSER, "--headless=new", "--disable-gpu", f"--user-data-dir={prof}",
                        "--hide-scrollbars", f"--window-size={w},{h}", "--virtual-time-budget=3000",
                        f"--screenshot={dest}", url], check=True, capture_output=True, timeout=90)


def terminal_png(title: str, cmd: str, dest: Path):
    out = subprocess.run([sys.executable, "-m", "ram", *cmd.split("|")], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout.rstrip()
    lines = out.count("\n") + 1
    page = f"""<html><body style="margin:0;background:#0f1117"><div style="font:14px/1.45 Consolas,monospace;color:#d6deeb;padding:0">
    <div style="background:#1f2430;padding:8px 14px;color:#9aa5b8;font-size:12px">{html.escape(title)}</div>
    <pre style="margin:0;padding:14px 18px;white-space:pre-wrap"><span style="color:#7fdbca">$ python -m ram {html.escape(cmd.replace('|', ' '))}</span>
{html.escape(out)}</pre></div></body></html>"""
    tmp = Path(tempfile.gettempdir()) / f"term_{dest.stem}.html"
    tmp.write_text(page, encoding="utf-8")
    shoot(tmp.as_uri(), dest, 1000, 60 + 21 * (lines + 2))


if __name__ == "__main__":
    if not BROWSER:
        sys.exit("No Edge/Chrome found")
    idx = (ROOT / "webapp" / "index.html").as_uri()
    for route, (name, h) in VIEWS.items():
        shoot(f"{idx}#{route}", OUT / f"{name}.png", 1040, h)
        print("wrote", name)
    terminal_png("Terminal - abstraction tree", "tree", OUT / "07-cli-tree.png")
    terminal_png("Terminal - validation", "validate", OUT / "08-cli-validate.png")
    terminal_png("Terminal - sprint plan and work-up", "plan", OUT / "09-cli-plan.png")
    terminal_png("Terminal - classifier", 'classify|The API shall return JSON in under 200 ms using an indexed database table.', OUT / "10-cli-classify.png")
    print("done")
