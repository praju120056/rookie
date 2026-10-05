"""A scripted stand-in for the AI, used only to test the pipeline without Ollama.

It reads the persona's *filtered* element list and taps the first thing that matches
the next step of the goal. If nothing readable matches, it gives up. It is not the
product: real runs use OllamaAgent.
"""
from rookie.agent import Action

PLAN = [
    (["Order placed", "ऑर्डर हो गया"], "done", "I can see my order is placed."),
    (["Margherita", "मार्गेरिटा"], "tap", "I'll pick the Margherita pizza."),
    (["Add to cart", "कार्ट में डालें"], "tap", "I'll add it to my cart."),
    (["Cart / कार्ट", "कार्ट"], "tap", "Now I need to open my cart."),
    (["Proceed to payment", "भुगतान करें"], "tap", "Time to pay."),
    (["Cash on delivery"], "tap", "I'll pay cash when it arrives."),
    (["Place order"], "tap", "Placing the order."),
]


class ScriptedAgent:
    def decide(self, persona, goal, elements, image, history):
        done = {h["element_label"] for h in history if h["action"] == "tap" and h["changed"]}
        for keys, action, thought in PLAN:
            for e in elements:
                if action == "tap" and e["kind"] == "text":
                    continue
                txt = e["text"] or ""
                if (txt in keys if keys == ["Cart / कार्ट", "कार्ट"] else any(k.lower() in txt.lower() for k in keys)) and (txt not in done or action == "done"):
                    if action == "done":
                        return Action(thought=thought, action="done")
                    if keys == ["Add to cart", "कार्ट में डालें"] and any(h["element_label"] == txt for h in history):
                        continue
                    return Action(thought=thought, action="tap", element=e["id"])
        unreadable = [e for e in elements if e["text"].startswith("[")]
        why = "I can't read these buttons, so I won't risk it." if unreadable else "I don't see where to go next."
        return Action(thought=why, action="give_up")
