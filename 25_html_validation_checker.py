"""
25 - HTML validation checker (W3C Nu HTML Checker - the engine behind validator.w3.org)
  Every page's server HTML is validated with the official Nu checker (vnu.jar), run locally: free, no rate limit,
  nothing leaves the machine. Errors (invalid nesting such as <div> inside <button>, <button> inside <a>, bad
  attribute values, IDs with spaces, duplicate IDs ...) are Important, warnings are Optimization; the plain
  "info" notes (e.g. trailing slashes on void elements, which React always writes) are left out.
  Messages that differ only in a quoted value are grouped into one issue type ("Bad value “…” for attribute id").

  Needs Java (java -version) - vnu.jar is downloaded once with npm into ~/.cache/website-audit-tools.
  Without Java it falls back to the public validator.w3.org service, one request per second, for the main pages
  only (--public-limit N) so the free service isn't abused.

  python "py files/25_html_validation_checker.py" [--base URL] [--no-warnings] [--public-limit 40]
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

from seo_common import (IMPORTANT, OPTIMIZATION, TOOLS_DIR, Audit, int_arg, load_site, parse_args, run_parallel,
                        sample_pages, select_pages)


def extra(ap):
    ap.add_argument("--no-warnings", action="store_true", help="report errors only")
    ap.add_argument("--public-limit", type=int_arg(1), default=40,
                    help="pages sent to validator.w3.org when Java isn't available (default %(default)s)")


args = parse_args("HTML validation checker (W3C Nu)", extra)
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("25_html_validation", "HTML Validation Report", "HTML validation", site)
VNU = TOOLS_DIR / "node_modules" / "vnu-jar" / "build" / "dist" / "vnu.jar"


def have_java():
    try:
        return subprocess.run(["java", "-version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_vnu():
    if VNU.exists():
        return True
    if not shutil.which("npm"):
        return False
    print("Downloading the W3C Nu validator (vnu-jar, once) ...")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["npm", "install", "--prefix", str(TOOLS_DIR), "--no-audit", "--no-fund", "--silent", "vnu-jar"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(r.stderr[-500:])
    return VNU.exists()


def group_message(msg):
    """Same message with different quoted values -> one issue type."""
    return re.sub(r"“[^”]*”", "“…”", msg, count=1) if re.match(r"(Bad value|Duplicate ID)", msg) else msg


def record(loc, m):
    kind = m.get("type")
    sub = m.get("subType", "")
    if kind == "error" or kind == "non-document-error":
        sev = IMPORTANT
    elif kind == "info" and sub == "warning" and not args.no_warnings:
        sev = OPTIMIZATION
    else:
        return None
    msg = m.get("message", "").strip()
    name = "W3C: " + group_message(msg)[:160]
    line = m.get("lastLine") or m.get("firstLine") or ""
    audit.add(loc, sev, "HTML validation", name, current=msg[:300], element=(m.get("extract") or "").strip()[:200],
              detail=f"line {line}" if line else "",
              expected="no W3C validation errors" if sev == IMPORTANT else "no W3C warnings",
              fix="Fix the markup shown in Element (line in Details). In React: don't nest interactive elements "
                  "(<button> in <a>, <a> in <a>), use only phrasing content inside <button>/<p>, and make id "
                  "values unique and without spaces.",
              description="The W3C Nu HTML checker (validator.w3.org) reports this as invalid HTML. Invalid markup "
                          "is repaired differently by each browser and assistive technology.")
    return sev, name, loc


for loc in pages:
    audit.checked(loc)
results = []
engine = ""
if have_java() and ensure_vnu():
    engine = "vnu.jar (local)"
    work = Path(tempfile.mkdtemp(prefix="w3c-"))
    import threading
    index = {}   # temp file name (p00001.html) -> page URL
    index_lock = threading.Lock()

    def save(item):
        i, loc = item
        res, _ = site.page(loc)
        if res["status"] == 200 and res["content"]:
            path = work / f"p{i:05d}.html"
            path.write_bytes(res["content"])
            with index_lock:
                index[path.name] = loc
    print(f"Downloading {len(pages)} pages ...")
    run_parallel(save, list(enumerate(pages)), args.workers)
    files = [str(work / name) for name in sorted(index)]
    unmatched = 0
    print(f"Validating {len(files)} pages with the W3C Nu checker ...")
    for start in range(0, len(files), 200):   # batches keep the command line short
        batch = files[start:start + 200]
        r = subprocess.run(["java", "-Xss8m", "-jar", str(VNU), "--format", "json", "--exit-zero-always", *batch],
                           capture_output=True, text=True, timeout=1800)
        try:
            messages = json.loads(r.stderr or r.stdout).get("messages", [])
        except ValueError:
            audit.not_checked("HTML validation", f"pages {start + 1}-{start + len(batch)}",
                              (r.stderr or r.stdout)[:200], "Run vnu.jar by hand to see the error.")
            continue
        for m in messages:
            # by file name: the reported file: URL can differ from the path given (/private/var, C:/..., %20)
            loc = index.get(Path(unquote(urlparse(m.get("url", "")).path)).name)
            if loc:
                results.append(record(loc, m))
            elif m.get("type") in ("error", "non-document-error") or m.get("subType") == "warning":
                unmatched += 1
        print(f"  {min(start + 200, len(files))}/{len(files)} pages validated")
    shutil.rmtree(work, ignore_errors=True)
    if unmatched:   # never a silent PASS: messages that could not be tied to a page
        audit.not_checked("HTML validation", f"{unmatched} validator message(s) that could not be matched to a page",
                          "the validator reported files the script did not recognise")
else:
    engine = "validator.w3.org (public, main pages only)"
    subset = sample_pages(pages, per_section=0)[: args.public_limit]
    audit.not_checked("HTML validation", f"{len(pages) - len(subset)} pages (only the main pages were sent to the "
                      "public validator)", "Java / vnu.jar not available",
                      "Install Java (e.g. brew install openjdk) so every page is validated locally.")
    print(f"Java not found - sending {len(subset)} main pages to validator.w3.org (1 per second) ...")
    import requests
    for loc in subset:
        res, _ = site.page(loc)
        try:
            r = requests.post("https://validator.w3.org/nu/?out=json", data=res["content"], timeout=60,
                              headers={"Content-Type": "text/html; charset=utf-8",
                                       "User-Agent": "WebsiteAudit/1.0 (+QA scripts)"})
            for m in r.json().get("messages", []):
                results.append(record(loc, m))
        except Exception as e:
            audit.add(loc, OPTIMIZATION, "HTML validation", "Not checked: page could not be validated", current=str(e)[:150])
        time.sleep(1)

results = [r for r in results if r]
distinct = defaultdict(lambda: {"sev": "", "pages": set(), "count": 0})
for sev, name, loc in results:
    d = distinct[name]
    d["sev"], d["count"] = sev, d["count"] + 1
    d["pages"].add(loc)
per_page = Counter(loc for _, _, loc in results)
audit.note("Validator", engine)
audit.note("Distinct messages", len(distinct))
audit.sheet("Distinct messages", ["Severity", "Message", "Occurrences", "Pages", "Example page"],
            sorted(((d["sev"], n, d["count"], len(d["pages"]), sorted(d["pages"])[0]) for n, d in distinct.items()),
                   key=lambda r: (r[0] != IMPORTANT, -r[3])), (13, 100, 12, 8, 60), severity_col=1)
audit.sheet("Pages", ["URL", "Errors + warnings"], sorted(((p, per_page.get(p, 0)) for p in pages), key=lambda r: -r[1]),
            (70, 16))
audit.save("HTML_Validation_Report")
