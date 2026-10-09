"""
12a - Core Web Vitals checker (real Chrome, mobile, throttled)
  Core Web Vitals:  LCP, INP, CLS
  supporting:       FCP, TTFB, TBT, Speed Index (Speed Index only with --lighthouse)

  Lab test like Lighthouse mobile: phone viewport (412x823), Slow 4G network (150 ms RTT, 1.6 Mbps) and 4x CPU
  slowdown, fresh cache per page. INP is a lab estimate from real clicks/keys (field INP needs real users -
  see Google Search Console / PageSpeed Insights "field data"). --runs N takes the median of N loads.

  Thresholds (Google):  LCP <= 2.5 s good, > 4 s poor | INP <= 200 ms, > 500 ms | CLS <= 0.1, > 0.25
                        FCP <= 1.8 s, > 3 s | TTFB <= 0.8 s, > 1.8 s | TBT <= 200 ms, > 600 ms | SI <= 3.4 s, > 5.8 s

  Every discovered page is measured (--pages sample for a quick run), half of --browser-workers in parallel.

  python "py files/12a_core_web_vitals_checker.py" [--base URL] [--runs 3] [--desktop] [--pages sample]
"""
import json
import shutil
import statistics
import subprocess

from seo_common import (COLLECT_METRICS_JS, CRITICAL, IMPORTANT, OPTIMIZATION, PERF_INIT_SCRIPT, Audit, int_arg,
                        load_site, parse_args, rate, run_browser_pages, scroll_page, select_pages, simulate_interactions)

THRESHOLDS = {  # metric: (good, poor, unit, is_core)
    "lcp": (2500, 4000, "ms", True), "inp": (200, 500, "ms", True), "cls": (0.1, 0.25, "", True),
    "fcp": (1800, 3000, "ms", False), "ttfb": (800, 1800, "ms", False), "tbt": (200, 600, "ms", False),
    "si": (3400, 5800, "ms", False),
}
NAMES = {"lcp": "LCP", "inp": "INP", "cls": "CLS", "fcp": "FCP", "ttfb": "TTFB", "tbt": "TBT", "si": "Speed Index"}

args = parse_args("Core Web Vitals checker", lambda ap: (
    ap.add_argument("--runs", type=int_arg(1), default=1, help="loads per page (median is reported)"),
    ap.add_argument("--desktop", action="store_true", help="desktop instead of throttled mobile"),
    ap.add_argument("--lighthouse", action="store_true", help="run Lighthouse (npx) for Speed Index")))
site, urls = load_site(args)
pages = select_pages(urls, args)
mode = "desktop" if args.desktop else "mobile (Slow 4G, 4x CPU)"
audit = Audit("12a_cwv", "Core Web Vitals Report", "Performance", site)
audit.note("Test profile", mode)
audit.note("Runs per page", args.runs)
# throttled CPU: fewer parallel loads than the other browser scripts so pages don't slow each other down
workers = max(1, args.browser_workers // 2)
audit.note("Pages measured in parallel", workers)
rows = []


def speed_index(url):
    npx = shutil.which("npx")
    if not npx:
        return None
    try:
        cmd = [npx, "--yes", "lighthouse", url, "--output=json", "--quiet", "--only-audits=speed-index",
               "--chrome-flags=--headless=new"] + (["--preset=desktop"] if args.desktop else [])
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        return json.loads(out.stdout)["audits"]["speed-index"]["numericValue"]
    except Exception:
        return None


def measure(browser, loc):
    if args.desktop:
        ctx = browser.context(width=1350, height=940)
    else:
        ctx = browser.context(mobile=True, width=412, height=823)
    ctx.add_init_script(PERF_INIT_SCRIPT)
    page = ctx.new_page()
    try:
        if not args.desktop:
            cdp = ctx.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150,
                                                          "downloadThroughput": 1.6 * 1024 * 1024 / 8,
                                                          "uploadThroughput": 750 * 1024 / 8})
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        page.goto(site.to_fetch(loc), wait_until="load", timeout=120000)
        page.wait_for_timeout(2500)
        scroll_page(page, step=500, pause=150)
        simulate_interactions(page)
        page.wait_for_timeout(600)
        return page.evaluate(COLLECT_METRICS_JS)
    finally:
        ctx.close()


def check(browser, loc):
    audit.checked(loc)
    runs = []
    for _ in range(max(1, args.runs)):
        try:
            runs.append(measure(browser, loc))
        except Exception as e:
            audit.add(loc, CRITICAL, "Load", "Page failed to load", current=str(e)[:200])
            break
    if not runs:
        return
    med = lambda key: statistics.median([r[key] for r in runs if r.get(key) is not None]) \
        if any(r.get(key) is not None for r in runs) else None
    values = {"lcp": med("lcp"), "inp": med("inp"), "cls": med("cls"), "fcp": med("fcp"), "ttfb": med("ttfb"),
              "tbt": med("tbt"), "si": speed_index(site.to_fetch(loc)) if args.lighthouse else None}
    verdicts = {}
    for key, (good, poor, unit, core) in THRESHOLDS.items():
        v = values[key]
        verdicts[key] = rate(v, good, poor)
        if verdicts[key] in ("Poor", "Needs improvement"):
            sev = (CRITICAL if core else IMPORTANT) if verdicts[key] == "Poor" else (IMPORTANT if core else OPTIMIZATION)
            shown = f"{v:.3f}" if key == "cls" else f"{v / 1000:.2f} s" if unit == "ms" and v >= 1000 else f"{v:.0f} {unit}"
            good_txt = f"{good}" if key == "cls" else f"{good / 1000:g} s" if good >= 1000 else f"{good} ms"
            audit.add(loc, sev, "Core Web Vitals" if core else "Supporting metrics",
                      f"{NAMES[key]} {verdicts[key].lower()}", current=shown, expected=f"<= {good_txt}",
                      element=runs[0].get("lcpEl") if key == "lcp" else None,
                      detail=f"{mode}, median of {len(runs)} run(s)")
    core_pass = all(verdicts[k] == "Good" for k in ("lcp", "cls")) and verdicts["inp"] in ("Good", "n/a")
    fmt = lambda v, d=0: "" if v is None else round(v, d) if d else round(v)
    rows.append((loc, "PASS" if core_pass else "FAIL", fmt(values["lcp"]), verdicts["lcp"], runs[0].get("lcpEl", ""),
                 fmt(values["inp"]), verdicts["inp"], fmt(values["cls"], 3), verdicts["cls"], fmt(values["fcp"]),
                 verdicts["fcp"], fmt(values["ttfb"]), verdicts["ttfb"], fmt(values["tbt"]), verdicts["tbt"],
                 fmt(values["si"]), verdicts["si"]))
    print(f"  {'PASS' if core_pass else 'FAIL'}  LCP {fmt(values['lcp'])}ms  INP {fmt(values['inp'])}  "
          f"CLS {fmt(values['cls'], 3)}  {loc}")


print(f"Measuring {len(pages)} pages ({mode}, {args.runs} run(s) each, {workers} in parallel) ...")
run_browser_pages(check, pages, workers, "pages measured")
rows.sort(key=lambda r: r[0])   # parallel workers finish in any order

passed = sum(1 for r in rows if r[1] == "PASS")
audit.note("Pages passing Core Web Vitals", f"{passed} of {len(rows)}")
audit.sheet("Core Web Vitals", ["URL", "CWV", "LCP ms", "LCP", "LCP element", "INP ms (lab)", "INP", "CLS", "CLS rating",
                                "FCP ms", "FCP", "TTFB ms", "TTFB", "TBT ms", "TBT", "Speed Index ms", "SI"], rows,
            (55, 7, 8, 16, 40, 11, 16, 7, 16, 8, 16, 8, 16, 8, 16, 13, 16))
audit.save("Core_Web_Vitals_Report")
