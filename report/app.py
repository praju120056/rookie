"""Rookie friction report. Run with:  streamlit run report/app.py"""
import base64
import html
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
TAG = {"finished": ("FINISHED", "teal"), "stuck": ("STUCK", "amber"), "gave_up": ("GAVE UP", "red")}

st.set_page_config(page_title="Rookie · Friction report", layout="wide")
st.markdown(f"<style>{(ROOT / 'report' / 'style.css').read_text()}</style>", unsafe_allow_html=True)


def h(s):
    return html.escape(str(s))


def img_b64(p: Path):
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def load_run(d: Path):
    meta = json.loads((d / "run.json").read_text())
    people = []
    for k in meta["personas"]:
        pd = d / k
        if not (pd / "summary.json").exists():
            continue
        steps = [json.loads(l) for l in (pd / "steps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        people.append({**json.loads((pd / "summary.json").read_text(encoding="utf-8")), "dir": pd, "steps_list": steps})
    return meta, people


runs = sorted([d for d in RUNS.glob("*") if (d / "run.json").exists()], reverse=True) if RUNS.exists() else []
if not runs:
    st.markdown('<div class="eyebrow">FRICTION REPORT</div><h1 class="headline">No runs yet.</h1>'
                '<p class="muted">Run <code>python -m rookie run</code> first.</p>', unsafe_allow_html=True)
    st.stop()

with st.sidebar:
    st.markdown('<div class="eyebrow">ROOKIE</div><div class="side-title">Runs</div>', unsafe_allow_html=True)
    run_dir = st.radio("Run", runs, format_func=lambda d: d.name, label_visibility="collapsed")

meta, people = load_run(run_dir)
finished = [p for p in people if p["outcome"] == "finished"]
friction = [p for p in people if p["outcome"] != "finished"]
baseline = next((p for p in people if p["persona"] == "arjun"), finished[0] if finished else None)

# 1. Headline
st.markdown(
    f'<div class="eyebrow">FRICTION REPORT · RUN {h(meta["run_id"])} · MODEL {h(meta.get("model", "")).upper()}</div>'
    f'<h1 class="headline">{len(finished)} of {len(people)} personas finished the goal.</h1>'
    f'<div class="sub-italic">Goal: “{h(meta["goal"])}”</div>', unsafe_allow_html=True)

# 2. Stat cards
cards = [
    (f"{len(finished)} / {len(people)}", "Personas finished", "completed the goal", True),
    (str(len(friction)), "Friction points", " · ".join(p["stuck_on"] or "?" for p in friction) or "none", False),
    (str(baseline["steps"]) if baseline else "–", "Baseline steps", baseline["label"] if baseline else "", False),
    (str(sum(p["wasted_actions"] for p in people)), "Wasted taps", "actions that changed nothing", False),
    (f'{sum(p["avg_think_s"] for p in people) / max(len(people), 1):.1f}s', "Avg think time", "per step, local model", False),
]
st.markdown('<div class="cards">' + "".join(
    f'<div class="card{" hi" if hi else ""}"><div class="num">{h(n)}</div><div class="lab">{h(l)}</div><div class="mono-sub">{h(s)}</div></div>'
    for n, l, s, hi in cards) + "</div>", unsafe_allow_html=True)

# 3. Results table
rows = "".join(
    f'<tr><td><b>{h(p["label"])}</b></td><td class="mono">{p["steps"]}</td>'
    f'<td><span class="tag {TAG[p["outcome"]][1]}">{TAG[p["outcome"]][0]}</span></td>'
    f'<td>{h(p["stuck_on"] or "—")}</td><td class="mono">{p["seconds"]}s</td><td class="quote">“{h(p["last_thought"])}”</td></tr>'
    for p in people)
st.markdown('<div class="section-label">RESULTS</div><table class="tbl"><tr><th>PERSONA</th><th>STEPS</th><th>OUTCOME</th>'
            f'<th>STOPPED ON</th><th>TIME</th><th>LAST THOUGHT</th></tr>{rows}</table>', unsafe_allow_html=True)

# 4. One strip per persona: what the AI saw at each step, with its thought
for p in people:
    tag, color = TAG[p["outcome"]]
    shots = []
    for s in p["steps_list"]:
        last = s["n"] == len(p["steps_list"])
        cls = f" end {color}" if last and p["outcome"] != "finished" else (" end teal" if last else "")
        act = s["action"] + (f' “{s["element_label"]}”' if s.get("element_label") else "")
        src = img_b64(p["dir"] / "step_{:02d}_seen.png".format(s["n"]))
        shots.append(
            f'<div class="shot{cls}"><img src="{src}"/>'
            f'<div class="mono-sub">STEP {s["n"]:02d} · {h(act)[:60]}</div><div class="thought">“{h(s["thought"])}”</div></div>')
    st.markdown(
        f'<div class="persona-head"><span class="pname">{h(p["label"])}</span><span class="tag {color}">{tag}</span></div>'
        f'<div class="strip">{"".join(shots)}</div>', unsafe_allow_html=True)
