"""Look → filter → think → act → log, until the persona finishes, gives up, or runs out of steps."""
import time

from . import personas as P
from .browser import Phone
from .store import RunStore


def run_persona(persona, goal, url, agent, store: RunStore, max_steps=20, success_text=None, headless=True):
    phone = Phone(headless=headless, slow_network=persona.slow_network)
    out = store.persona_dir(persona)
    history, wasted, outcome = [], 0, "stuck"   # stuck = ran out of steps
    started = time.time()
    try:
        phone.open(url)
        for n in range(1, max_steps + 1):
            raw, elements, page_url = phone.look()
            seen_elements = P.filter_elements(persona, elements)
            seen_img = P.filter_image(persona, raw)

            t0 = time.time()
            act = agent.decide(persona, goal, seen_elements, seen_img, history)
            think_s = time.time() - t0

            changed = False
            if act.action not in ("done", "give_up"):
                try:
                    phone.act(act.action, act.element, act.text)
                except Exception as err:  # element vanished, timeout, etc.
                    act.thought += f" (couldn't do it: {type(err).__name__})"
                _, after, after_url = phone.look()
                sig = lambda els: [(e["text"], e["checked"]) for e in els]
                changed = (page_url, sig(elements)) != (after_url, sig(after))

            label = next((e["text"] for e in seen_elements if e["id"] == act.element), None)
            step = {"n": n, "action": act.action, "element": act.element, "element_label": label, "text": act.text,
                    "thought": act.thought, "changed": changed, "page": page_url.split("/")[-1].split("?")[0],
                    "think_s": round(think_s, 2)}
            history.append(step)
            store.save_step(out, step, raw, seen_img)
            print(f'[{persona.key}] step {n:02d} · {act.action}{f" [{act.element}]" if act.element else ""} · "{act.thought}"')

            if act.action == "done":
                outcome = "finished"
                break
            if act.action == "give_up":
                outcome = "gave_up"
                break
            wasted = 0 if changed else wasted + 1
            if wasted >= persona.patience:
                history[-1]["thought"] += " (out of patience)"
                outcome = "gave_up"
                break

        # Trust the screen over the model: did the goal actually complete?
        if success_text:
            reached = success_text.lower() in " ".join(e["text"] for e in phone.look()[1]).lower()
            if outcome == "finished" and not reached:
                outcome = "stuck"
            elif reached:
                outcome = "finished"
    finally:
        phone.close()

    summary = {
        "persona": persona.key, "label": persona.label, "color": persona.color, "outcome": outcome,
        "steps": len(history), "seconds": round(time.time() - started, 1),
        "stuck_at_step": None if outcome == "finished" else len(history),
        "stuck_on": None if outcome == "finished" or not history else history[-1]["page"],
        "last_thought": history[-1]["thought"] if history else "",
        "wasted_actions": sum(1 for h in history if not h["changed"] and h["action"] not in ("done", "give_up")),
        "avg_think_s": round(sum(h["think_s"] for h in history) / max(len(history), 1), 2),
    }
    store.save_summary(out, summary)
    return summary
