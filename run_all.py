"""
Run every audit script one after another and build the Website Health master report.

  python "py files/run_all.py"                                   # audits NEXT_PUBLIC_REPORT_URL from .env.local
  python "py files/run_all.py" --base http://127.0.0.1:4000      # another server
  python "py files/run_all.py" --pages all                       # browser checks on every page (slow)
  python "py files/run_all.py" --only 02,05,12a                  # just some scripts (21 always runs last)
  python "py files/run_all.py" --skip 12,12a --no-browser        # skip scripts / all Chrome-based checks
  python "py files/run_all.py" --sitemap-only                    # old behaviour: sitemap URLs only, no crawling
  npm run seo:audit                                              # same as the first line

The server comes from --base, else $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL (environment, .env.local, .env),
else http://localhost:3000. The whole site is crawled once (every internal URL that can be discovered, not only
sitemap.xml) and every script audits those pages.

All reports of one run share a date folder and a time stamp, one folder per format (nothing else is written):
  py files/report/<YYYY-MM-DD>/excel/<Report_Name>_<HH-MM-SS>.xlsx
  py files/report/<YYYY-MM-DD>/json/<Report_Name>_<HH-MM-SS>.json
  py files/report/<YYYY-MM-DD>/csv/<Report_Name>_<HH-MM-SS>.csv     (py files/report is created if missing)
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASTER = "21_website_health_report.py"
NUMBERED = sorted(p.name for p in HERE.glob("[0-9][0-9]*_*.py") if p.name != MASTER)  # 01 ... 20 (incl. 12a)
BROWSER_SCRIPTS = {"10_accessibility_checker.py": ["--no-browser"], "13_nextjs_checker.py": ["--no-browser"],
                   "16_third_party_checker.py": ["--no-browser"],
                   "12_performance_checker.py": None, "12a_core_web_vitals_checker.py": None, "15_mobile_checker.py": None}


def main():
    missing = [m for m in ("requests", "bs4", "lxml", "openpyxl") if importlib.util.find_spec(m) is None]
    if missing:
        sys.exit(f"Missing Python packages: {', '.join(missing)}\nRun:  pip install -r \"py files/requirements.txt\"")
    sys.path.insert(0, str(HERE))
    import seo_common

    ap = argparse.ArgumentParser(description="Run all website audit scripts")
    ap.add_argument("--base", default=seo_common.default_base(),
                    help="server to audit (default: $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL from .env.local; "
                         "now %(default)s)")
    ap.add_argument("--pages", choices=("all", "sample"), help="override every script's page selection")
    ap.add_argument("--only", default="", help="comma list of script prefixes, e.g. 01,02,12a")
    ap.add_argument("--skip", default="", help="comma list of script prefixes to skip")
    ap.add_argument("--no-browser", action="store_true", help="skip Chrome-based checks (no Playwright needed)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-pages", type=int, default=5000, help="crawl at most this many URLs")
    ap.add_argument("--sitemap-only", action="store_true", help="audit only sitemap.xml URLs (no crawling)")
    ap.add_argument("--ignore-robots", action="store_true", help="also crawl URLs that robots.txt disallows")
    args = ap.parse_args()
    args.base = args.base.rstrip("/")

    if not args.no_browser and importlib.util.find_spec("playwright") is None:
        print("Playwright is not installed - Chrome-based checks will be skipped. Install with:  pip install playwright\n")
        args.no_browser = True

    import requests
    try:
        requests.get(args.base + "/", timeout=30).raise_for_status()
    except Exception as e:
        sys.exit(f"Can't reach {args.base}/ ({e}).\nStart the site first (npm run build && npm run start, "
                 f"or npm run dev), or set NEXT_PUBLIC_REPORT_URL in .env.local / pass --base.")

    now = datetime.now()
    env = dict(os.environ, SEO_RUN_DATE=now.strftime("%Y-%m-%d"), SEO_RUN_TIME=now.strftime("%H-%M-%S"),
               SITE_BASE_URL=args.base, SEO_WORKERS=str(args.workers), SEO_MAX_PAGES=str(args.max_pages),
               PYTHONUNBUFFERED="1")
    if args.pages:
        env["SEO_PAGES"] = args.pages
    if args.sitemap_only:
        env["SEO_SITEMAP_ONLY"] = "1"
    if args.ignore_robots:
        env["SEO_IGNORE_ROBOTS"] = "1"
    report_dir = seo_common.ensure_report_root() / env["SEO_RUN_DATE"]   # py files/report, created if missing

    def prefix(name):
        return name.split("_", 1)[0]

    only = {p.strip() for p in args.only.split(",") if p.strip()}
    skip = {p.strip() for p in args.skip.split(",") if p.strip()}
    scripts = [s for s in NUMBERED if (not only or prefix(s) in only) and prefix(s) not in skip]
    plan = []
    for s in scripts:
        extra = []
        if args.no_browser and s in BROWSER_SCRIPTS:
            if BROWSER_SCRIPTS[s] is None:
                continue
            extra = BROWSER_SCRIPTS[s]
        plan.append((s, extra))
    plan.append((MASTER, []))

    if not only and not skip:   # full run: start from an empty py files/report
        seo_common.clear_reports()
        print("Removed all previous reports (full run)")
    # with --only / --skip each script still replaces its own previous report files
    print(f"Auditing {args.base} - {len(plan)} scripts - reports in {report_dir.relative_to(HERE.parent)}\n")
    results = []
    if not args.sitemap_only:   # crawl once; every script reuses it (cached in the system temp folder)
        header = f"\n{'=' * 70}\n[crawl] discovering every URL of {args.base}\n{'=' * 70}"
        print(header)
        start = time.time()
        proc = subprocess.Popen([sys.executable, "-c", CRAWL_SNIPPET], cwd=HERE, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(line, end="")
        code = proc.wait()
        results.append(("site crawl", "OK" if code == 0 else f"FAILED ({code})", int(time.time() - start)))
        if code != 0:
            print("Crawl failed - each script will crawl on its own.")

    for i, (script, extra) in enumerate(plan, 1):
        header = f"\n{'=' * 70}\n[{i}/{len(plan)}] {script} {' '.join(extra)}\n{'=' * 70}"
        print(header)
        start = time.time()
        proc = subprocess.Popen([sys.executable, str(HERE / script), *extra], cwd=HERE, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(line, end="")
        code = proc.wait()
        took = int(time.time() - start)
        results.append((script, "OK" if code == 0 else f"FAILED ({code})", took))

    summary = "\n" + "=" * 70 + "\nRUN SUMMARY\n" + "=" * 70 + "\n" + "\n".join(
        f"  {status:<12} {took:>5}s  {script}" for script, status, took in results)
    print(summary)
    print(f"\nReports: {report_dir}/excel, /json and /csv")
    failed = [r for r in results if r[1] != "OK"]
    sys.exit(1 if failed else 0)


CRAWL_SNIPPET = """
import sys
sys.argv = ["crawl"]
from seo_common import parse_args, load_site
load_site(parse_args("crawl"), need_sitemap=False)
"""

if __name__ == "__main__":
    main()
