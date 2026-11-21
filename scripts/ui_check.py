"""Browser check of every demo mode (headless Chrome via Playwright): console errors, all six story chapters,
explore, judge (provenance popover, solve-it-live, stress test, rule box), sandbox — with the backend on or off.
Saves screenshots to --out and builds docs/media/hero.gif from the story chapters.

  python scripts/ui_check.py --url http://localhost:4173 [--backend] --out <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:4173")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", action="store_true", help="expect the live backend to be running")
    ap.add_argument("--gif", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    errors, report, frames = [], {}, []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        pg.goto(a.url, wait_until="networkidle")
        pg.wait_for_selector(".top", timeout=30000)
        pg.wait_for_timeout(2500)
        report["live_badge"] = pg.locator(".pill").inner_text()
        for i in range(6):
            pg.locator(".steps button").nth(i).click()
            pg.wait_for_timeout(3200 if i in (2, 3) else 2400)
            shot = out / f"story_{i + 1}.png"
            pg.screenshot(path=str(shot))
            frames.append(shot)
            report[f"chapter_{i + 1}"] = pg.locator(".chapter h2").inner_text()
            canvases = pg.locator("canvas").count()
            report[f"chapter_{i + 1}_canvases"] = canvases
        # chapter 5 kill button
        pg.locator(".steps button").nth(4).click(); pg.wait_for_timeout(1500)
        pg.get_by_text("Take mechanical labs offline").click(); pg.wait_for_timeout(2500)
        pg.screenshot(path=str(out / "kill.png"))
        report["kill_text"] = pg.locator(".panel").inner_text()[-300:]
        # explore
        pg.get_by_role("tab", name="Explore").click(); pg.wait_for_timeout(2000)
        pg.mouse.click(500, 420); pg.wait_for_timeout(800)
        pg.screenshot(path=str(out / "explore.png"))
        # judge
        pg.get_by_role("tab", name="Judge").click(); pg.wait_for_timeout(1500)
        pg.locator("button.num").first.click(); pg.wait_for_timeout(500)
        report["provenance_modal"] = pg.locator(".modal").inner_text()[:400]
        pg.screenshot(path=str(out / "judge_provenance.png"))
        pg.locator(".modal button").click()
        btn = pg.locator(".solve button")
        report["solve_button"] = btn.inner_text()
        if a.backend:
            btn.click(); pg.wait_for_timeout(8000)
        report["solve_panel"] = pg.locator(".solve").inner_text()[:600]
        pg.screenshot(path=str(out / "judge_solve.png"))
        pg.get_by_text("BESCOM outage 3 h").click(); pg.wait_for_timeout(9000 if a.backend else 800)
        report["stress"] = pg.locator(".panel .card").last.inner_text()[:300]
        pg.locator("input[aria-label='operator rule']").fill("no DG during exams unless outage")
        pg.locator("button", has_text="parse rule").click(); pg.wait_for_timeout(6000 if a.backend else 800)
        report["rule"] = pg.locator(".panel .card").last.inner_text()[:300]
        pg.screenshot(path=str(out / "judge_rules.png"))
        # sandbox
        pg.get_by_role("tab", name="What-if").click(); pg.wait_for_timeout(800)
        pg.locator(".sandbox > button").click(); pg.wait_for_timeout(9000 if a.backend else 800)
        report["sandbox"] = pg.locator(".sandbox .card").inner_text()[:300]
        pg.screenshot(path=str(out / "sandbox.png"))
        # other scenarios load
        opts = pg.locator("header select option").all_inner_texts()
        for k in range(len(opts)):
            pg.locator("header select").select_option(index=k); pg.wait_for_timeout(1500)
        report["scenarios_loaded"] = len(opts)
        b.close()
    report["console_errors"] = errors
    (out / "ui_report.json").write_text(json.dumps(report, indent=1))
    if a.gif:
        from PIL import Image
        imgs = [Image.open(f).convert("RGB").resize((960, 600)) for f in frames]
        media = ROOT / "docs" / "media"
        media.mkdir(parents=True, exist_ok=True)
        imgs[0].save(media / "hero.gif", save_all=True, append_images=imgs[1:], duration=2200, loop=0, optimize=True)
    print(json.dumps({k: (v if k != "console_errors" else len(v)) for k, v in report.items() if not k.endswith("_text")}, indent=1)[:3000])
    if errors:
        print("CONSOLE ERRORS:", *errors[:20], sep="\n  ")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
