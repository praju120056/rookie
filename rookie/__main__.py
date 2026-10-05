"""Rookie CLI.

    python -m rookie run --personas arjun,kamala,ravi
    python -m rookie list-personas
"""
import argparse
import functools
import http.server
import threading
from pathlib import Path

import yaml

from . import personas as P
from .loop import run_persona
from .store import RunStore


def serve_demo(folder, port):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(Quiet, directory=folder)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    cfg = yaml.safe_load(Path("config.yaml").read_text())
    ap = argparse.ArgumentParser(prog="rookie")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run personas against a goal")
    r.add_argument("--goal", default=cfg["goal"])
    r.add_argument("--personas", default=",".join(cfg["personas"]))
    r.add_argument("--url", default=None, help="app URL (default: the bundled demo shop)")
    r.add_argument("--model", default=cfg["model"])
    r.add_argument("--show", action="store_true", help="show the browser window")
    sub.add_parser("list-personas")
    args = ap.parse_args()

    if args.cmd == "list-personas":
        for k in P.available():
            p = P.load(k)
            print(f"{k:8} {p.label:12} {p.about.strip()[:70]}…")
        return

    url = args.url
    if not url:
        serve_demo(cfg["demo_folder"], cfg["demo_port"])
        url = f"http://127.0.0.1:{cfg['demo_port']}/index.html"

    from .agent import OllamaAgent
    agent = OllamaAgent(model=args.model, host=cfg.get("ollama_host"))
    keys = [k.strip() for k in args.personas.split(",") if k.strip()]
    store = RunStore(meta={"goal": args.goal, "personas": keys, "model": args.model, "url": url})
    print(f"Rookie run {store.run_id} · goal: {args.goal} · model: {args.model}")
    for k in keys:
        s = run_persona(P.load(k), args.goal, url, agent, store, max_steps=cfg["max_steps"],
                        success_text=cfg.get("success_text"), headless=not args.show)
        print(f"  → {s['label']}: {s['outcome'].upper()} in {s['steps']} steps")
    print(f"\nDone. See the report:  streamlit run report/app.py")


if __name__ == "__main__":
    main()
