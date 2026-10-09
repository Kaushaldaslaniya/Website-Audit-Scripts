"""
Run every audit script one after another and build the Website Health master report.

  python "py files/run_all.py"                                   # audits NEXT_PUBLIC_REPORT_URL from .env.local
  python "py files/run_all.py" --base http://127.0.0.1:4000      # another server
  python "py files/run_all.py" --pages sample                    # quick run: main pages + 2 per section
  python "py files/run_all.py" --only 02,05,12a                  # just some scripts (21 + 30 always run last)
  python "py files/run_all.py" --live https://www.example.com    # also compare with the current live site (29)
  python "py files/run_all.py" --skip 12b --browser-workers 2     # skip Lighthouse / fewer parallel Chromes
  python "py files/run_all.py" --no-browser                      # no Chrome at all (fast, HTML checks only)
  python "py files/run_all.py" --sitemap-only                    # old behaviour: sitemap URLs only, no crawling
  npm run seo:audit                                              # same as the first line

The server comes from --base, else $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL (environment, .env.local, .env),
else http://localhost:3000. The whole site is crawled once (every internal URL that can be discovered, not only
sitemap.xml - links that only appear after opening menus / tabs are found in Chrome) and every script audits every
one of those pages, including the Chrome-based ones (--pages sample for a quick run).

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
MASTERS = ["21_website_health_report.py", "30_qa_checklist_report.py"]   # always run last, in this order
MASTER = MASTERS[0]
NUMBERED = sorted(p.name for p in HERE.glob("[0-9][0-9]*_*.py") if p.name not in MASTERS)  # 01 ... 31 (incl. 12a)
BROWSER_SCRIPTS = {"10_accessibility_checker.py": ["--no-browser"], "13_nextjs_checker.py": ["--no-browser"],
                   "16_third_party_checker.py": ["--no-browser"], "23_forms_checker.py": ["--no-browser"],
                   "27_assets_checker.py": ["--no-browser"], "31_english_grammar_checker.py": ["--no-browser"],
                   "12_performance_checker.py": None, "12a_core_web_vitals_checker.py": None,
                   "12b_lighthouse_checker.py": None, "15_mobile_checker.py": None, "24_navigation_checker.py": None}


def main():
    missing = [m for m in ("requests", "bs4", "lxml", "openpyxl") if importlib.util.find_spec(m) is None]
    if missing:
        sys.exit(f"Missing Python packages: {', '.join(missing)}\nRun:  pip install -r \"py files/requirements.txt\"")
    sys.path.insert(0, str(HERE))
    import seo_common

    ap = argparse.ArgumentParser(description="Run all website audit scripts")
    ap.add_argument("--base", type=seo_common.base_arg, default=seo_common.default_base(),
                    help="server to audit (default: $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL from .env.local; "
                         "now %(default)s)")
    ap.add_argument("--pages", choices=("all", "sample"), help="override every script's page selection")
    ap.add_argument("--only", default="", help="comma list of script prefixes, e.g. 01,02,12a")
    ap.add_argument("--skip", default="", help="comma list of script prefixes to skip")
    ap.add_argument("--no-browser", action="store_true", help="skip Chrome-based checks (no Playwright needed)")
    ap.add_argument("--workers", type=seo_common.int_arg(1), default=8)
    ap.add_argument("--browser-workers", type=seo_common.int_arg(1), default=seo_common.default_browser_workers(),
                    help="Chrome / Lighthouse runs in parallel in the browser scripts (default %(default)s)")
    ap.add_argument("--no-js-discovery", action="store_true",
                    help="don't open menus / tabs in Chrome during the crawl to find JavaScript-only links")
    ap.add_argument("--max-pages", type=seo_common.int_arg(1), default=5000, help="crawl at most this many URLs")
    ap.add_argument("--sitemap-only", action="store_true", help="audit only sitemap.xml URLs (no crawling)")
    ap.add_argument("--ignore-robots", action="store_true", help="also crawl URLs that robots.txt disallows")
    ap.add_argument("--live", default="", help="current live site for 29 (default: qa_config.json live_url)")
    ap.add_argument("--visual", action="store_true", help="29: screenshot live vs dev and compare")
    ap.add_argument("--repo-build", action="store_true",
                    help="28: also run npm run build (stop `next start` first - the build rewrites .next)")
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
               SEO_BROWSER_WORKERS=str(args.browser_workers),
               PYTHONUNBUFFERED="1")
    if args.pages:
        env["SEO_PAGES"] = args.pages
    if args.sitemap_only:
        env["SEO_SITEMAP_ONLY"] = "1"
    if args.ignore_robots:
        env["SEO_IGNORE_ROBOTS"] = "1"
    if args.no_js_discovery or args.no_browser:
        env["SEO_NO_JS_DISCOVERY"] = "1"
    if args.live:
        env["QA_LIVE_URL"] = args.live
    if args.repo_build:
        env["SEO_REPO_BUILD"] = "1"
    report_dir = seo_common.ensure_report_root() / env["SEO_RUN_DATE"]   # py files/report, created if missing

    def prefix(name):
        return name.split("_", 1)[0]

    only = {p.strip().zfill(2) if p.strip().isdigit() else p.strip() for p in args.only.split(",") if p.strip()}
    skip = {p.strip().zfill(2) if p.strip().isdigit() else p.strip() for p in args.skip.split(",") if p.strip()}
    known = {prefix(s) for s in NUMBERED} | {prefix(m) for m in MASTERS}
    unknown = sorted((only | skip) - known)
    if unknown:
        ap.error(f"unknown script prefix(es): {', '.join(unknown)} (choose from {', '.join(sorted(known))})")
    scripts = [s for s in NUMBERED if (not only or prefix(s) in only) and prefix(s) not in skip]
    if only and not scripts and not only & {prefix(m) for m in MASTERS}:
        ap.error("--only / --skip leave no script to run")
    plan, results = [], []
    for s in scripts:
        extra = []
        if args.no_browser and s in BROWSER_SCRIPTS:
            if BROWSER_SCRIPTS[s] is None:
                results.append((s, "SKIPPED (--no-browser)", 0))
                continue
            extra = BROWSER_SCRIPTS[s]
        if s.startswith("29_") and args.visual and not args.no_browser:
            extra = extra + ["--visual"]
        plan.append((s, extra))
    if scripts and not plan:
        ap.error(f"--no-browser skips every chosen script ({', '.join(prefix(s) for s in scripts)} need Chrome)")
    plan += [(m, []) for m in MASTERS]

    if not only and not skip:   # full run: start from an empty py files/report
        seo_common.clear_reports()
        print("Removed all previous reports (full run)")
    # with --only / --skip each script still replaces its own previous report files
    print(f"Auditing {args.base} - {len(plan)} scripts - reports in {report_dir.relative_to(HERE.parent)}\n")
    try:
        run_plan(args, env, plan, results)
    except KeyboardInterrupt:
        if not results or results[-1][1] != "INTERRUPTED":
            results.append(("(stopped with Ctrl+C)", "INTERRUPTED", 0))
    summarize(results, report_dir)


def run_plan(args, env, plan, results):
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
        try:
            for line in proc.stdout:
                print(line, end="")
            code = proc.wait()
        except KeyboardInterrupt:
            proc.wait()   # the script got the same Ctrl+C; let it stop
            results.append((script, "INTERRUPTED", int(time.time() - start)))
            raise
        took = int(time.time() - start)
        results.append((script, "OK" if code == 0 else f"FAILED ({code})", took))


def summarize(results, report_dir):
    stopped = any(r[1] == "INTERRUPTED" for r in results)
    title = "RUN STOPPED WITH Ctrl+C - SUMMARY" if stopped else "ALL AUDITS COMPLETE - RUN SUMMARY"
    summary = "\n" + "=" * 70 + f"\n{title}\n" + "=" * 70 + "\n" + "\n".join(
        f"  {status:<22} {took:>5}s  {script}" for script, status, took in results)
    print(summary)
    print("=" * 70)
    failed = [r for r in results if r[1] != "OK" and not r[1].startswith("SKIPPED")]
    passed = [r for r in results if r[1] == "OK"]
    if failed:
        print(f"⚠ Finished with {len(passed)} passed and {len(failed)} failed script(s): {', '.join(s for s, _, _ in failed)}")
    else:
        print("✓ All reports generated and audit suite completed successfully!")
    print(f"  All generated reports saved to: {report_dir.relative_to(HERE.parent)}/")
    print(f"    • Excel:    {report_dir.relative_to(HERE.parent)}/excel/")
    print(f"    • JSON:     {report_dir.relative_to(HERE.parent)}/json/")
    print(f"    • CSV:      {report_dir.relative_to(HERE.parent)}/csv/")
    if (report_dir / "html").exists():
        print(f"    • HTML:     {report_dir.relative_to(HERE.parent)}/html/")
    if (report_dir / "markdown").exists():
        print(f"    • Markdown: {report_dir.relative_to(HERE.parent)}/markdown/")
    print("=" * 70 + "\n")
    sys.exit(1 if failed else 0)


CRAWL_SNIPPET = """
import sys
sys.argv = ["crawl"]
from seo_common import parse_args, load_site
load_site(parse_args("crawl"), need_sitemap=False)
"""

if __name__ == "__main__":
    main()
