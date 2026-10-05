"""Writes each run to runs/<run_id>/<persona>/ so the report can read it."""
import json
import time
from pathlib import Path


class RunStore:
    def __init__(self, root="runs", meta=None):
        self.run_id = time.strftime("%Y%m%d-%H%M%S")
        self.dir = Path(root) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "run.json").write_text(json.dumps({"run_id": self.run_id, "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), **(meta or {})}, indent=2))

    def persona_dir(self, persona):
        d = self.dir / persona.key
        d.mkdir(exist_ok=True)
        return d

    def save_step(self, d, step, raw, seen):
        raw.save(d / f"step_{step['n']:02d}_raw.png")
        seen.save(d / f"step_{step['n']:02d}_seen.png")
        with open(d / "steps.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(step, ensure_ascii=False) + "\n")

    def save_summary(self, d, summary):
        (d / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
