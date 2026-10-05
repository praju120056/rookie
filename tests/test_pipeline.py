"""Pipeline test: run all personas with the scripted agent. `python -m tests.test_pipeline`"""
import yaml
from pathlib import Path

from rookie import personas as P
from rookie.__main__ import serve_demo
from rookie.loop import run_persona
from rookie.store import RunStore
from tests.scripted_agent import ScriptedAgent

cfg = yaml.safe_load(Path("config.yaml").read_text())
serve_demo(cfg["demo_folder"], cfg["demo_port"])
url = f"http://127.0.0.1:{cfg['demo_port']}/index.html"
keys = ["arjun", "kamala", "ravi"]
store = RunStore(meta={"goal": cfg["goal"], "personas": keys, "model": "scripted (pipeline test)", "url": url})
for k in keys:
    s = run_persona(P.load(k), cfg["goal"], url, ScriptedAgent(), store, max_steps=cfg["max_steps"], success_text=cfg["success_text"])
    print(k, s["outcome"], s["steps"])
