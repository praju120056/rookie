"""Phone-sized Chrome driven by Playwright: look at the screen and act on it."""
import io
import os
import time

from PIL import Image
from playwright.sync_api import sync_playwright

# Collect what a person could see on screen. Each element gets a number the AI uses to act.
COLLECT_JS = r"""
() => {
  const sel = 'a, button, input, select, textarea, label, [role=button], h1, h2, h3, p, span, b, li, div';
  const out = [];
  let n = 0;
  document.querySelectorAll('[data-rookie-id]').forEach(e => e.removeAttribute('data-rookie-id'));
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') continue;
    const clickable = el.matches('a, button, input, select, textarea, label, [role=button]');
    // Text-only elements nested inside a clickable one are covered by their parent.
    if (!clickable && el.closest('a, button, label, [role=button]')) continue;
    if (!clickable && el.querySelector(sel)) continue;
    const text = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ');
    const aria = el.getAttribute('aria-label') || '';
    if (!text && !aria && !clickable) continue;
    if (el.matches('label') && el.querySelector('input')) { /* keep: radio/checkbox rows */ }
    n += 1;
    el.setAttribute('data-rookie-id', String(n));
    out.push({
      id: n,
      kind: clickable ? (el.tagName === 'INPUT' ? 'input:' + (el.type || 'text') : 'button') : 'text',
      text: text.slice(0, 120),
      aria: aria,
      icon_only: clickable && !text && !!(aria || el.querySelector('svg, img')),
      font_px: parseFloat(st.fontSize) || 16,
      box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      in_view: r.bottom > 0 && r.top < window.innerHeight,
      checked: !!(el.checked || (el.querySelector && el.querySelector('input:checked'))),
    });
  }
  return out;
}
"""


class Phone:
    def __init__(self, device="Pixel 7", headless=True, slow_network=False):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless, executable_path=os.environ.get("ROOKIE_CHROMIUM") or None)
        self.context = self._browser.new_context(**self._pw.devices[device])
        self.page = self.context.new_page()
        self.page.on("dialog", lambda d: d.dismiss())
        if slow_network:
            cdp = self.context.new_cdp_session(self.page)
            cdp.send("Network.enable")
            # Roughly 2G: high latency, ~20 KB/s
            cdp.send("Network.emulateNetworkConditions", {
                "offline": False, "latency": 1500,
                "downloadThroughput": 20 * 1024, "uploadThroughput": 10 * 1024,
            })

    def open(self, url):
        self.page.goto(url, wait_until="load", timeout=60000)

    def look(self):
        """Return (screenshot as PIL image, list of element dicts, url)."""
        self.page.wait_for_load_state("load", timeout=60000)
        elements = self.page.evaluate(COLLECT_JS)
        png = self.page.screenshot()
        return Image.open(io.BytesIO(png)).convert("RGB"), elements, self.page.url

    def act(self, action, element=None, text=None):
        loc = self.page.locator(f'[data-rookie-id="{element}"]') if element else None
        if action == "tap":
            loc.click(timeout=5000)
        elif action == "type":
            loc.fill(text or "", timeout=5000)
        elif action == "back":
            self.page.go_back(timeout=60000)
        elif action == "scroll":
            self.page.mouse.wheel(0, 600)
        elif action == "wait":
            time.sleep(2)
        time.sleep(0.6)

    def close(self):
        self.context.close()
        self._browser.close()
        self._pw.stop()
