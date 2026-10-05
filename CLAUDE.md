# Rookie: MVP build guide

Rookie is a hackathon project (iQOO Hackathon 2026, Developer Tools track, Team OGs). AI "rookie" users, each with a persona, use a real Android app on a phone or emulator, try to complete a goal, and report where they got stuck.

This file tells Claude Code how to build the **MVP**: a small, working proof of work that can be demoed live and recorded for the submission video. Keep it simple and working over clever and half-built.

## Current state (read this first)

The MVP is **already built**, with one change from the plan below: to fit a one-hour deadline, the phone is a **phone-sized Chrome window driven by Playwright** (`rookie/browser.py`, Pixel 7 emulation) instead of an Android emulator over ADB. The loop, personas, filters, report and output format are as described below; wherever this file says ADB or uiautomator, the code uses Playwright and a DOM scan instead. The ADB backend is the next step: add `rookie/adb_phone.py` with the same `open / look / act / close` interface as `browser.Phone`.

- Run: `python -m rookie run`, then `streamlit run report/app.py`
- Test the pipeline without a model: `python -m tests.test_pipeline` (scripted stand-in agent)
- Refresh README screenshots and metrics: `python tools/readme_assets.py` (with the report running)

## What the MVP must do

One command runs three personas against one goal on an Android emulator and produces a friction report:

```
python -m rookie run --goal "Order a pizza" --personas arjun,kamala,ravi
streamlit run report/app.py
```

Expected demo outcome on the bundled demo shop (see **Demo app**):
- **Arjun** (baseline) finishes the order.
- **Kamala** (new to smartphones) gets stuck because the cart is an unlabeled icon.
- **Ravi** (reads only Hindi) gives up on the English-only payment page.

Definition of done:
- [ ] The loop runs end to end on the emulator with no manual help.
- [ ] Each persona's run is saved to disk (screenshots, actions, thoughts, outcome).
- [ ] The Streamlit report shows the overview, the journey and each stuck moment, in the Rookie UI style.
- [ ] Everything runs locally: no cloud APIs, works with Wi-Fi off once models are pulled.
- [ ] README with setup steps that a teammate can follow from scratch.

Out of scope for the MVP: running the model on the phone, real-device farms, CI integration, user accounts, more than one goal per run.

## Tech stack

| Part | Choice | Notes |
|---|---|---|
| Phone | Android Studio emulator (AVD, Pixel, API 34) | A real phone over USB also works, but the slow-network persona needs the emulator |
| Control | ADB | Called through `subprocess`; no Android code anywhere |
| Language | Python 3.11 | |
| AI model | Gemma 3 4B via Ollama (`ollama pull gemma3:4b`) | Vision-capable and runs locally. Make the model name a config value |
| Python libs | `ollama`, `pillow`, `pydantic`, `streamlit`, `pyyaml` | Keep the dependency list this short |
| Report | Streamlit | Styled to match the deck, see **UI** |

## Repo layout

```
rookie/
  CLAUDE.md
  README.md
  requirements.txt
  config.yaml              # model name, max steps, patience, emulator serial
  rookie/
    __main__.py            # CLI: `run` and `list-personas`
    adb.py                 # thin wrapper over adb commands
    screen.py              # screenshot + UI tree → Screen object with numbered elements
    personas.py            # persona definitions + their filters
    agent.py               # builds the prompt, calls Ollama, parses the action
    loop.py                # look → think → act → log, until done / gave up / max steps
    store.py               # writes runs/<run_id>/<persona>/...
  personas/
    arjun.yaml  kamala.yaml  ravi.yaml  meena.yaml
  report/
    app.py                 # Streamlit friction report
    style.css              # Rookie UI tokens
  demo_app/                # static demo shop with planted friction (HTML/CSS/JS only)
  runs/                    # output, git-ignored
```

## How the loop works

Each step:

1. **Look.** `adb exec-out screencap -p` for the screenshot. `adb shell uiautomator dump /sdcard/ui.xml` then `adb exec-out cat /sdcard/ui.xml` for the UI tree. Parse nodes that are clickable, editable or have text/content-desc, and number them `[1]`, `[2]`… with their label and bounds `[x1,y1][x2,y2]`.
2. **Filter.** Apply the persona's filters to the screenshot and the element list (see **Personas**). The AI only ever sees the filtered version.
3. **Think.** Send the persona prompt, the goal, the filtered element list, the filtered screenshot and the last 5 steps to Ollama. Ask for JSON only (use Ollama's `format` with the schema below, temperature 0.2).
4. **Act.** Run the action over ADB:
   - `tap` → `adb shell input tap <cx> <cy>` (centre of the element's bounds)
   - `type` → `adb shell input text "<text>"` (escape spaces as `%s`)
   - `back` → `adb shell input keyevent 4`
   - `scroll` → `adb shell input swipe 540 1600 540 600 300`
   - `wait` → sleep 2 seconds
   - `done` / `give_up` → end the run
5. **Log.** Save the raw screenshot, the filtered screenshot, the element list, the model's thought and action, and the timestamp.

Stop when the model says `done` or `give_up`, when the persona's patience runs out, or at `max_steps` (default 25).

Action schema (pydantic):

```python
class Action(BaseModel):
    thought: str          # first person, in the persona's voice: "I can't see a cart button"
    action: Literal["tap", "type", "back", "scroll", "wait", "done", "give_up"]
    element: int | None   # element number for tap/type
    text: str | None      # for type
```

If the model returns invalid JSON or an element number that doesn't exist, retry once, then log it and count it as a wasted step.

Detect "nothing happened" by comparing the UI tree before and after an action. That feeds the patience limit.

## Personas

Personas are YAML: name, age, a short backstory for the prompt, allowed actions, patience, and filters. The key idea, which is also the pitch: **we change what the AI can actually see and do, so the struggles are real, not role-played.**

| Persona | Filters (applied in code, not just described in the prompt) |
|---|---|
| **Arjun, 24**: tech-savvy, impatient. The baseline | None. All actions allowed |
| **Kamala, 65**: new to smartphones, poor eyesight | Screenshot downscaled and Gaussian-blurred (radius ~4). Elements with small text (bounds height < 40px) shown as `[too small to read]`. Icon-only elements (content-desc but no visible text) shown as `[unlabeled icon]`. No `scroll`. Gives up after 3 actions in a row that change nothing |
| **Ravi, 38**: reads only Hindi | Any element whose label is in Latin script is shown as `[text in a language I can't read]`. Devanagari, digits and ₹ stay. The screenshot is shown as is: he can see the layout, just not read English |
| **Meena, 30**: on a slow 2G network | Before the run: `adb emu network speed gsm` and `adb emu network delay gprs` (emulator only). Patience: gives up after 20 seconds total of screens that don't change. Reset the network after the run |

The persona prompt must tell the model to act as that person, say `give_up` when that person realistically would, and never use knowledge the persona doesn't have.

## Demo app

Build a tiny static shop in `demo_app/` (plain HTML, CSS and JS, no framework). Serve it with `python -m http.server 8000 --directory demo_app` and open `http://10.0.2.2:8000` in Chrome on the emulator. Chrome's web content shows up in the uiautomator dump, so no Android app needs to be written.

Pages: menu → item → cart → payment → order placed.

Planted friction, on purpose:
- The **cart** is only a small bag icon in the header, with no label. Kamala should get stuck here.
- The menu, item and cart pages show **Hindi and English** labels. The **payment page is English only**. Ravi should get stuck here.
- Arjun should be able to finish in roughly 8–10 steps.

Keep the demo shop visually plain and obviously "a sample app" so it doesn't look staged.

## Output format

```
runs/<run_id>/
  run.json                  # goal, personas, model, started_at
  <persona>/
    steps.jsonl             # one line per step: n, action, element, text, thought, changed, ts
    step_01_raw.png
    step_01_seen.png        # what the AI saw after filters
    summary.json            # outcome: finished | stuck | gave_up, steps, stuck_at_step, last_thought
```

## UI: keep the same look as the deck

The report must look like the Rookie pitch deck: dark, flat and crisp. **No rounded corners, shadows, gradients, glows or emoji.**

Design tokens (put them in `report/style.css` and in `.streamlit/config.toml`):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0D0D0F` | page background |
| `--panel` | `#141416` | cards, sidebar |
| `--panel-2` | `#1F1F23` | inner boxes, table headers |
| `--rule` | `#2A2A2F` | 1px borders and dividers |
| `--dim` | `#505058` | small labels |
| `--muted` | `#A0A0A8` | body text |
| `--text` | `#F2F2F0` | headings, key text |
| `--teal` | `#00C2A8` | the one accent: finished, highlights |
| `--teal-bg` | `#0A1F1D` | highlighted box fill |
| `--red` | `#FF8080` | gave up; fill `#1F0808`, border `#4D1515` |
| `--amber` | `#F5A623` | stuck |

Typography:
- Headlines: **Georgia**, regular weight, large. Emphasis lines in Georgia italic, teal.
- Body: Helvetica Neue, falling back to Arial.
- Labels and eyebrows: **Courier New**, small, uppercase, letter-spaced (e.g. `PERSONA 02`, `FRICTION REPORT · RUN 0412`).
- Numbers in stat cards: Georgia, large, teal.

Components:
- Boxes are sharp rectangles with a 1px `--rule` border. Highlighted boxes use a `--teal` border with `--teal-bg` fill.
- Status tags: small mono uppercase text in a bordered box (`FINISHED` teal, `STUCK` amber, `GAVE UP` red).

Report layout (one page, top to bottom):
1. Eyebrow `FRICTION REPORT`, then a Georgia headline built from the data, e.g. "1 of 3 personas finished the goal."
2. Four stat cards: personas finished, friction points, baseline steps, journey stages.
3. Results table: persona, steps, outcome tag, where they got stuck, last thought (italic).
4. One section per persona: a horizontal strip of step screenshots (the `seen` version) with the thought under each. The stuck or give-up step gets a red or amber border.
5. A run picker in the sidebar that lists folders in `runs/`.

Use `st.markdown(..., unsafe_allow_html=True)` with the CSS classes for cards, tags and tables, and hide Streamlit's default header, footer and menu.

## Build order

Get each step working before starting the next:

1. `adb.py` + `screen.py`: print the numbered element list for whatever is on the emulator screen.
2. `demo_app/` served and opened in emulator Chrome.
3. `agent.py` + `loop.py` with Arjun only: completes the order on the demo shop.
4. Persona filters for Kamala and Ravi, checked by eye in the saved `seen` screenshots.
5. `store.py` output, then the Streamlit report in the Rookie style.
6. Meena (network throttle).
7. README, and a recorded run for the demo video.

## Conventions

- No cloud calls of any kind. The pitch is "everything runs on your machine".
- Keep modules small and readable; this will be shown to judges.
- Settings go in `config.yaml`, not hard-coded: model name, max steps, patience, emulator serial, demo URL.
- Log every step to the console as `[kamala] step 04 · tap [7] · "I can't see a cart button"`.
- Never commit `runs/`, APKs or model files.
