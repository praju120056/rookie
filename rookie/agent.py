"""The brain: a local vision model (via Ollama) that plays the persona and picks the next action."""
import base64
import io
import json
from typing import Literal, Optional

from pydantic import BaseModel, ValidationError


class Action(BaseModel):
    thought: str                     # first person, in the persona's voice
    action: Literal["tap", "type", "back", "scroll", "wait", "done", "give_up"]
    element: Optional[int] = None    # element number for tap / type
    text: Optional[str] = None       # text for type


SYSTEM = """You are role-playing a real person using a phone app. Stay fully in character.

WHO YOU ARE
{about}

RULES
- You only know what is in the ELEMENTS list and the screenshot. Do not use knowledge this person doesn't have.
- Anything shown as [text in a language I can't read], [too small to read] or [unlabeled icon] is something you cannot understand.
- Allowed actions: {actions}.
- "tap" and "type" need an element number from the list.
- Say "done" only when the screen shows your goal is complete.
- Say "give_up" when this person would realistically give up: lost, confused, or afraid of doing something wrong.
- "thought" is one short sentence, first person, in plain English, saying what you notice and why you act.

Reply with JSON only: {{"thought": "...", "action": "...", "element": <number or null>, "text": <string or null>}}"""

USER = """GOAL: {goal}

ELEMENTS ON SCREEN:
{elements}

YOUR LAST STEPS:
{history}

What do you do next?"""


def format_elements(elements):
    lines = []
    for e in elements:
        if not e["text"]:
            continue
        tag = "button" if e["kind"] == "button" else e["kind"]
        where = "" if e["in_view"] else " (below, need to scroll)"
        lines.append(f'[{e["id"]}] {tag}: {e["text"]}{where}')
    return "\n".join(lines) or "(nothing readable)"


def format_history(history):
    if not history:
        return "(none yet)"
    return "\n".join(
        f'{h["n"]}. {h["action"]}{" [" + str(h["element"]) + "]" if h.get("element") else ""}'
        f'{"" if h.get("changed", True) else " (nothing happened)"} - "{h["thought"]}"'
        for h in history[-5:]
    )


class OllamaAgent:
    def __init__(self, model="gemma3:4b", host=None, temperature=0.2):
        import ollama
        self.client = ollama.Client(host=host) if host else ollama.Client()
        self.model = model
        self.temperature = temperature

    def decide(self, persona, goal, elements, image, history) -> Action:
        buf = io.BytesIO()
        image.resize((image.width // 2, image.height // 2)).save(buf, format="PNG")
        messages = [
            {"role": "system", "content": SYSTEM.format(about=persona.about.strip(), actions=", ".join(persona.actions))},
            {"role": "user", "content": USER.format(goal=goal, elements=format_elements(elements), history=format_history(history)),
             "images": [base64.b64encode(buf.getvalue()).decode()]},
        ]
        last_err = None
        for _ in range(2):  # one retry on bad output
            resp = self.client.chat(model=self.model, messages=messages, format=Action.model_json_schema(),
                                    options={"temperature": self.temperature})
            try:
                act = Action.model_validate(json.loads(resp["message"]["content"]))
                if act.action not in persona.actions:
                    raise ValueError(f"action {act.action} not allowed for {persona.name}")
                if act.action in ("tap", "type") and act.element not in {e["id"] for e in elements}:
                    raise ValueError(f"element {act.element} not on screen")
                return act
            except (ValidationError, ValueError, json.JSONDecodeError) as err:
                last_err = err
                messages.append({"role": "user", "content": f"That reply was invalid ({err}). Reply with valid JSON using an element number from the list."})
        return Action(thought=f"(model error: {last_err})", action="wait")
