"""
12b - Lighthouse audit (Google Lighthouse - free, runs locally through npx; the engine behind PageSpeed Insights and
      Chrome DevTools)
  every page: Lighthouse Performance, Accessibility, Best Practices and SEO scores, the lab metrics (FCP, LCP, TBT,
      CLS, Speed Index, TTI) and every failed Lighthouse audit as its own issue (with Lighthouse's description,
      the failing elements / resources and the "Learn more" link)
  profile:   Lighthouse mobile (Moto G Power, slow 4G, 4x CPU - simulated) or --desktop
  score:     the average of the four Lighthouse category scores over all pages

  Every discovered page is audited (--pages sample for a quick run), --browser-workers Lighthouse runs in parallel
  (about 15-20 s per page each).

  python "py files/12b_lighthouse_checker.py" [--base URL] [--desktop] [--pages sample] [--browser-workers 3]
  needs:  Node.js (npx) and Google Chrome. The first run downloads Lighthouse (npx --yes lighthouse).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, parse_args, run_parallel, select_pages)

CATEGORIES = [("performance", "Performance"), ("accessibility", "Accessibility"), ("best-practices", "Best Practices"),
              ("seo", "SEO")]
METRICS = [("first-contentful-paint", "FCP ms"), ("largest-contentful-paint", "LCP ms"), ("total-blocking-time", "TBT ms"),
           ("cumulative-layout-shift", "CLS"), ("speed-index", "Speed Index ms"), ("interactive", "TTI ms")]
BLOCKS_INDEXING = {"is-crawlable", "http-status-code", "robots-txt", "canonical"}
SCORED = ("binary", "numeric", "metricSavings")
PASS = 0.9   # Lighthouse shows an audit green from 0.9

args = parse_args("Lighthouse audit", lambda ap: (
    ap.add_argument("--desktop", action="store_true", help="Lighthouse desktop preset instead of mobile"),
    ap.add_argument("--timeout", type=int, default=240, help="seconds per page")))

npx = shutil.which("npx")
if not npx:
    sys.exit("Lighthouse needs Node.js (npx was not found) - install Node.js, or skip this script (--skip 12b).")


def chrome_path():
    """Lighthouse finds an installed Google Chrome itself; otherwise use Playwright's Chromium."""
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome",
              "/usr/bin/chromium", "C:/Program Files/Google/Chrome/Application/chrome.exe"):
        if Path(p).exists():
            return None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            return pw.chromium.executable_path
    except Exception:
        return None


env = dict(os.environ)
if chrome_path():
    env["CHROME_PATH"] = chrome_path()
version = subprocess.run([npx, "--yes", "lighthouse", "--version"], capture_output=True, text=True, env=env, timeout=600)
if version.returncode != 0:
    sys.exit(f"Could not start Lighthouse through npx: {(version.stderr or version.stdout).strip()[:300]}")
version = version.stdout.strip()

site, urls = load_site(args)
pages = select_pages(urls, args)
profile = "desktop" if args.desktop else "mobile (Moto G Power, slow 4G, 4x CPU - simulated)"
audit = Audit("12b_lighthouse", "Lighthouse Report", "Performance", site)
audit.note("Lighthouse version", version)
audit.note("Profile", profile)
rows, failed_rows = [], []


def plain(markdown):
    """Lighthouse descriptions are Markdown: keep the text, drop the link targets."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown or "").replace("`", "").strip()


def learn_more(markdown):
    m = re.search(r"\[Learn [^\]]*\]\(([^)]+)\)", markdown or "")
    return m.group(1) if m else ""


def item_label(item):
    node = item.get("node") if isinstance(item.get("node"), dict) else (item if item.get("type") == "node" else None)
    if node:
        return (node.get("selector") or node.get("snippet") or node.get("nodeLabel") or "")[:150]
    for key in ("url", "source", "label", "groupLabel", "description", "entity"):
        v = item.get(key)
        if isinstance(v, dict):
            v = v.get("url") or v.get("text") or ""
        if isinstance(v, str) and v:
            return v[:150]
    return ""


def failing_items(details, limit=5):
    items = (details or {}).get("items") or []
    labels = []
    for it in items:
        if isinstance(it, dict):
            sub = (it.get("subItems") or {}).get("items") if isinstance(it.get("subItems"), dict) else None
            sub_label = item_label(sub[0]) if (isinstance(sub, list) and sub and isinstance(sub[0], dict)) else ""
            label = item_label(it) or sub_label
            if label and label not in labels:
                labels.append(label)
        if len(labels) >= limit:
            break
    return labels, len(items)


def run_lighthouse(loc):
    url = site.to_fetch(loc)
    cmd = [npx, "--yes", "lighthouse", url, "--output=json", "--output-path=stdout", "--quiet",
           "--only-categories=" + ",".join(c for c, _ in CATEGORIES), "--max-wait-for-load=60000",
           "--chrome-flags=--headless=new --no-sandbox --disable-dev-shm-usage"]
    if args.desktop:
        cmd.append("--preset=desktop")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, env=env)
        return json.loads(out.stdout), ""
    except subprocess.TimeoutExpired:
        return None, f"Lighthouse timed out after {args.timeout} s"
    except ValueError:
        return None, (out.stderr or "no JSON output").strip().splitlines()[-1][:300] if out.stderr else "no JSON output"


def check(loc):
    audit.checked(loc)
    lhr, error = run_lighthouse(loc)
    if lhr is None or lhr.get("runtimeError"):
        msg = error or lhr["runtimeError"].get("message", lhr["runtimeError"].get("code", ""))
        audit.add(loc, IMPORTANT, "Lighthouse", "Lighthouse could not audit the page", current=msg[:300])
        rows.append((loc, *[""] * (len(CATEGORIES) + len(METRICS) + 1), msg[:200]))
        return
    cats = lhr.get("categories", {})
    scores = {c: (round(cats[c]["score"] * 100) if cats.get(c, {}).get("score") is not None else None) for c, _ in CATEGORIES}
    a = lhr.get("audits", {})
    seen, n_failed = set(), 0
    for cat_id, cat_name in CATEGORIES:
        cat = cats.get(cat_id) or {}
        for ref in cat.get("auditRefs", []):
            aid = ref["id"]
            res = a.get(aid) or {}
            score = res.get("score")
            if aid in seen or score is None or score >= PASS or res.get("scoreDisplayMode") not in SCORED:
                continue
            seen.add(aid)
            n_failed += 1
            metric = ref.get("group") == "metrics"
            if aid in BLOCKS_INDEXING:
                sev = CRITICAL
            elif cat_id in ("accessibility", "seo") or (metric and score < 0.5):
                sev = IMPORTANT
            elif cat_id == "best-practices" and res.get("scoreDisplayMode") == "binary":
                sev = IMPORTANT
            else:
                sev = OPTIMIZATION
            labels, total = failing_items(res.get("details"))
            link = learn_more(res.get("description"))
            current = res.get("displayValue") or (f"score {round(score * 100)}" if res.get("scoreDisplayMode") != "binary"
                                                  else "failed")
            if total:
                current += f" ({total} item{'s' if total != 1 else ''})"
            audit.add(loc, sev, f"Lighthouse {cat_name}", f"Lighthouse: {res.get('title', aid)}",
                      current=current, expected=f"Lighthouse audit '{aid}' passes (score >= {int(PASS * 100)})",
                      element="; ".join(labels) or None, description=plain(res.get("description")),
                      fix=("Fix the elements / resources listed in Element. " +
                           (f"Lighthouse guide: {link}" if link else "")).strip(),
                      detail=f"Lighthouse {cat_name}, audit id {aid}, score {round(score * 100)}")
            failed_rows.append((loc, cat_name, aid, res.get("title", aid), round(score * 100),
                                res.get("displayValue", ""), total, "; ".join(labels)[:300]))
    for cat_id, cat_name in CATEGORIES:
        s = scores[cat_id]
        if s is not None and s < 50:
            audit.add(loc, IMPORTANT, f"Lighthouse {cat_name}", f"Lighthouse {cat_name} score poor",
                      current=f"{s} / 100", expected=">= 90 / 100", detail=profile)
        elif s is not None and s < 90:
            audit.add(loc, OPTIMIZATION, f"Lighthouse {cat_name}", f"Lighthouse {cat_name} score needs improvement",
                      current=f"{s} / 100", expected=">= 90 / 100", detail=profile)
    metric_values = []
    for mid, _ in METRICS:
        v = a.get(mid, {}).get("numericValue")
        metric_values.append("" if v is None else round(v, 3) if mid == "cumulative-layout-shift" else round(v))
    rows.append((loc, *[scores[c] if scores[c] is not None else "" for c, _ in CATEGORIES], *metric_values, n_failed, ""))
    print(f"  {loc}  " + "  ".join(f"{name} {scores[c]}" for c, name in CATEGORIES))


workers = max(1, args.browser_workers)
print(f"Running Lighthouse {version} on {len(pages)} pages ({profile}, {workers} in parallel) ...")
run_parallel(check, pages, workers, "pages audited")
rows.sort(key=lambda r: r[0])
failed_rows.sort(key=lambda r: (r[0], r[1], r[4]))

# report score = average Lighthouse category score over all pages (what Lighthouse / PageSpeed users expect)
averages = {}
for i, (cat_id, cat_name) in enumerate(CATEGORIES, 1):
    values = [r[i] for r in rows if isinstance(r[i], (int, float))]
    if values:
        averages[cat_name] = round(sum(values) / len(values), 1)
        audit.note(f"Average {cat_name} score", averages[cat_name])
if averages:
    audit.score_override = round(sum(averages.values()) / len(averages), 1)
audit.sheet("Lighthouse scores", ["URL", *[name for _, name in CATEGORIES], *[h for _, h in METRICS], "Failed audits",
                                  "Error"], rows, (55, 12, 13, 14, 8, 8, 8, 8, 7, 14, 8, 12, 40))
audit.sheet("Failed audits", ["URL", "Category", "Audit id", "Audit", "Score", "Value", "Items", "Examples"], failed_rows,
            (50, 15, 30, 55, 7, 22, 7, 80))
audit.save("Lighthouse_Report")
