"""Refresh the README screenshots and metrics from the latest run.

    python -m rookie run                 # a real run with your local model
    python tools/readme_assets.py        # updates docs/*.png and the metrics table in README.md

Needs the report running:  streamlit run report/app.py --server.port 8501
"""
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPORT_URL = os.environ.get("ROOKIE_REPORT_URL", "http://localhost:8501")


def latest_run():
    runs = sorted(d for d in (ROOT / "runs").glob("*") if (d / "run.json").exists())
    if not runs:
        sys.exit("No runs yet. Run `python -m rookie run` first.")
    return runs[-1]


def side_by_side(paths, out, labels_h=0):
    ims = [Image.open(p).convert("RGB") for p in paths]
    h = min(min(i.height for i in ims), int(ims[0].width * 0.9))
    ims = [i.crop((0, 0, i.width, h)) for i in ims]
    w = sum(i.width for i in ims) + 24 * (len(ims) - 1)
    canvas = Image.new("RGB", (w, h), (13, 13, 15))
    x = 0
    for i in ims:
        canvas.paste(i, (x, 0))
        x += i.width + 24
    canvas.thumbnail((1600, 1600))
    canvas.save(out)


def metrics_table(run):
    meta = json.loads((run / "run.json").read_text())
    rows = ["| Persona | Outcome | Steps | Stopped on | Wasted taps | Time | Avg think / step |",
            "|---|---|---|---|---|---|---|"]
    done = 0
    for k in meta["personas"]:
        f = run / k / "summary.json"
        if not f.exists():
            continue
        s = json.loads(f.read_text(encoding="utf-8"))
        done += s["outcome"] == "finished"
        rows.append(f'| {s["label"]} | {s["outcome"].replace("_", " ")} | {s["steps"]} | {s["stuck_on"] or "—"} | '
                    f'{s["wasted_actions"]} | {s["seconds"]}s | {s["avg_think_s"]}s |')
    head = (f'Run `{meta["run_id"]}` · model `{meta.get("model")}` · goal "{meta["goal"]}" · '
            f'**{done} of {len(meta["personas"])} personas finished**\n\n')
    return head + "\n".join(rows)


def main():
    run = latest_run()
    DOCS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("ROOKIE_CHROMIUM") or None)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(REPORT_URL, wait_until="networkidle")
        pg.wait_for_timeout(3000)
        pg.screenshot(path=str(DOCS / "report.png"), full_page=True)
        b.close()
    # What each persona saw vs the real screen, at the step where they stopped
    for k in ("kamala", "ravi"):
        steps = sorted((run / k).glob("step_*_seen.png")) if (run / k).exists() else []
        if steps:
            last = steps[-1]
            side_by_side([str(last).replace("_seen", "_raw"), last], DOCS / f"{k}_view.png")
    arjun = sorted((run / "arjun").glob("step_*_raw.png")) if (run / "arjun").exists() else []
    if arjun:
        side_by_side(arjun[:6], DOCS / "arjun_journey.png")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"<!-- metrics:start -->.*<!-- metrics:end -->",
                  "<!-- metrics:start -->\n" + metrics_table(run) + "\n<!-- metrics:end -->", text, flags=re.S)
    readme.write_text(text, encoding="utf-8")
    print(f"Updated docs/ and README metrics from run {run.name}")


if __name__ == "__main__":
    main()
