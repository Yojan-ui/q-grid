"""Screenshots of every story step / sub-step (13 beats) at 1440x900 and 1920x1080, plus the Verify and Try tabs,
with overlap and console-error checks. Optional 60-second recording of steps 1-4.

  python scripts/ui_story.py --url http://localhost:5173/ --out <dir> [--video]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

BEATS = ['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '6', '7']
WAIT = {'1': 7500, '2': 2500, '3': 2200, '4a': 2200, '4b': 2600, '4c': 3200, '4d': 2600, '4e': 6000, '4f': 2200, '4g': 2200, '5': 5000, '6': 7500, '7': 12500}
CHECK = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 };
  const sel = ['.top .brand', '.top .tabs', '.top .right', '.kicker', '.story-text h1', '.figs', '.chart', '.nav', '.steps', '.clock', '.vlabels span', '.illus', 'footer span'];
  const els = sel.flatMap(s => [...document.querySelectorAll(s)].filter(vis).map(e => ({s, r: e.getBoundingClientRect()})));
  const scroller = document.querySelector('.scroll'); const sb = scroller ? scroller.getBoundingClientRect() : null;
  const clip = (s, r) => (sb && ['.kicker','.story-text h1','.figs','.chart'].includes(s)) ? {left: r.left, right: r.right, top: Math.max(r.top, sb.top), bottom: Math.min(r.bottom, sb.bottom)} : r;
  const out = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = clip(els[i].s, els[i].r), b = clip(els[j].s, els[j].r);
    const ov = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    if (ov > 4 && els[i].s !== els[j].s) out.push(els[i].s + ' x ' + els[j].s);
  }
  const h1 = document.querySelector('.story-text h1'); const w = h1 ? h1.getBoundingClientRect().width : 0;
  return {overlaps: out, h1_width: Math.round(w), scroll_overflow: scroller ? scroller.scrollHeight > scroller.clientHeight + 2 : false};
}"""


def run(p, url, out: Path, w: int, h: int, video_dir: Path | None = None):
    ctx = p.new_context(viewport={"width": w, "height": h}, record_video_dir=str(video_dir) if video_dir else None,
                        record_video_size={"width": w, "height": h} if video_dir else None)
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_selector(".story-text", timeout=60000)
    rep = {}
    beats = BEATS if not video_dir else BEATS[:10]
    for k, b in enumerate(beats):
        if k:
            pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(WAIT[b] if not video_dir else int(WAIT[b] * 1.8))  # video: ~60 s for steps 1-4
        if not video_dir:
            pg.screenshot(path=str(out / f"{w}_step{b}.png"))
            rep[b] = pg.evaluate(CHECK)
    if not video_dir:
        for tab in ("Verify", "Try it"):
            pg.get_by_role("button", name=tab, exact=True).click(); pg.wait_for_timeout(1200)
            pg.screenshot(path=str(out / f"{w}_{tab.split()[0].lower()}.png"))
    vid = pg.video.path() if video_dir else None
    ctx.close()
    return rep, errs, vid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5173/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--video", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        if a.video:
            vd = out / "_video"; vd.mkdir(exist_ok=True)
            _, errs, vid = run(b, a.url, out, 1440, 900, vd)
            shutil.move(vid, out / "steps1-4.webm")
            print("video:", out / "steps1-4.webm", "errors:", len(errs))
        else:
            for w, h in ((1440, 900), (1920, 1080)):
                rep, errs, _ = run(b, a.url, out, w, h)
                report[f"{w}x{h}"] = {"errors": errs, "beats": rep}
                bad = {k: v for k, v in rep.items() if v["overlaps"]}
                print(f"{w}x{h}: console errors {len(errs)}; overlaps {bad if bad else 'none'}; "
                      f"h1 widths {[v['h1_width'] for v in rep.values()]}; overflowing panels {[k for k, v in rep.items() if v['scroll_overflow']]}")
                for e in errs[:5]:
                    print("   ERR", e[:200])
        b.close()
    (out / "story_report.json").write_text(json.dumps(report, indent=1))
    if not a.video:   # README hero: the 13 beats at 1440x900, downscaled
        from PIL import Image
        imgs = [Image.open(out / f"1440_step{b}.png").convert("RGB").resize((960, 600), Image.LANCZOS) for b in BEATS]
        media = Path(__file__).resolve().parents[1] / "docs" / "media"
        imgs[0].save(media / "hero.gif", save_all=True, append_images=imgs[1:], duration=2200, loop=0, optimize=True)
        print("hero:", media / "hero.gif")


if __name__ == "__main__":
    main()
