"""Screenshots of every demo mode at 1440x900 and 1920x1080 + automatic overlap / console-error checks.

  python scripts/ui_shots.py --url http://localhost:5173/ --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OVERLAP_JS = """
() => {
  const sel = ['.zl', '.chip', '.top .seg', '.top .right', '.brand', '.readout', '.legend', '.foot-right', '.now', '.decisions', '.daychart'];
  const clip = (e, r) => { const p = e.closest('.panel'); if (!p) return r; const q = p.getBoundingClientRect();
    const l = Math.max(r.left, q.left), t = Math.max(r.top, q.top), rr = Math.min(r.right, q.right), b = Math.min(r.bottom, q.bottom);
    return {left: l, top: t, right: rr, bottom: b, width: Math.max(0, rr - l), height: Math.max(0, b - t)}; };
  const els = sel.flatMap(s => [...document.querySelectorAll(s)].map(e => ({s, r: clip(e, e.getBoundingClientRect()), t: (e.textContent||'').slice(0,30)})))
    .filter(x => x.r.width > 0 && x.r.height > 0);
  const out = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i].r, b = els[j].r;
    if (els[i].s === els[j].s && els[i].s !== '.zl' && els[i].s !== '.chip') continue;
    const ov = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    if (ov > 4) out.push(`${els[i].s} "${els[i].t}" x ${els[j].s} "${els[j].t}"`);
  }
  const clipped = [...document.querySelectorAll('.top *, footer *, .readout *')].filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow === 'hidden' && !e.classList.contains('qlabel')).map(e => e.className);
  return {overlaps: out, clipped};
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5173/")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rep = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for w, h in ((1440, 900), (1920, 1080)):
            pg = b.new_page(viewport={"width": w, "height": h})
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(a.url, wait_until="networkidle"); pg.wait_for_selector(".top", timeout=30000); pg.wait_for_timeout(2500)
            pg.get_by_role("button", name="Pause").click()
            shots = {}
            for i in range(6):
                pg.locator(".steps button").nth(i).click(); pg.wait_for_timeout(2600 if i in (2, 3) else 1800)
                if i == 0:
                    pg.locator(".track input").fill("75")
                    pg.wait_for_timeout(1200)
                f = out / f"{w}_story{i + 1}.png"; pg.screenshot(path=str(f)); shots[f"story{i + 1}"] = pg.evaluate(OVERLAP_JS)
            pg.get_by_role("tab", name="Explore").click(); pg.wait_for_timeout(1500)
            pg.locator(".track input").fill("52"); pg.wait_for_timeout(1500)
            f = out / f"{w}_explore.png"; pg.screenshot(path=str(f)); shots["explore"] = pg.evaluate(OVERLAP_JS)
            if pg.locator(".zl").count():
                pg.locator(".zl").first.click(); pg.wait_for_timeout(1500)
                f = out / f"{w}_explore_selected.png"; pg.screenshot(path=str(f)); shots["explore_selected"] = pg.evaluate(OVERLAP_JS)
            pg.get_by_role("tab", name="Judge").click(); pg.wait_for_timeout(1200)
            f = out / f"{w}_judge.png"; pg.screenshot(path=str(f)); shots["judge"] = pg.evaluate(OVERLAP_JS)
            pg.get_by_role("tab", name="What-if").click(); pg.wait_for_timeout(800)
            pg.locator(".sandbox > button").click(); pg.wait_for_timeout(800)
            f = out / f"{w}_whatif.png"; pg.screenshot(path=str(f)); shots["whatif"] = pg.evaluate(OVERLAP_JS)
            pg.locator(".databadge > button").click(); pg.wait_for_timeout(400)
            f = out / f"{w}_databadge.png"; pg.screenshot(path=str(f))
            rep[f"{w}x{h}"] = {"console_errors": errs, "checks": shots}
            pg.close()
        b.close()
    (out / "shots_report.json").write_text(json.dumps(rep, indent=1))
    for size, r in rep.items():
        bad = {k: v for k, v in r["checks"].items() if v["overlaps"] or v["clipped"]}
        print(size, "console errors:", len(r["console_errors"]), "| views with overlaps/clipping:", {k: (len(v["overlaps"]), v["clipped"][:3]) for k, v in bad.items()})
        for k, v in bad.items():
            for o in v["overlaps"][:4]:
                print("   ", k, o)
        for e in r["console_errors"][:5]:
            print("   ERR", e[:200])


if __name__ == "__main__":
    main()
