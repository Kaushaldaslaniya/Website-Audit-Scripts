"""
19 - Third-party URL report
  Every third-party URL used by every page (links, images, scripts, stylesheets, iframes, media, forms, embeds,
  srcset candidates) is requested once: Working / Redirect / Error / Timeout / SSL Error / Unverified (the site blocks
  automated checks). Each failing or redirecting URL is reported on every page that uses it.
  Sheets: "Third Party Summary" (page x URL with HTTP status, final URL, redirect chain, error) and
  "Third Party Domains" (domain, occurrences, pages, example URLs).

  python "py files/19_third_party_url_report.py" [--base URL] [--timeout 20]
"""
from collections import defaultdict
from datetime import datetime
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, load_site, parse_args, run_parallel,
                        select_pages)

TAGS = {  # tag -> (attributes holding a URL, label)
    "a": (("href",), "Link"), "img": (("src", "srcset"), "Image"), "script": (("src",), "Script"),
    "link": (("href",), "Stylesheet / Link"), "iframe": (("src",), "Iframe"), "video": (("src", "poster"), "Video"),
    "audio": (("src",), "Audio"), "source": (("src", "srcset"), "Media Source"), "form": (("action",), "Form"),
    "object": (("data",), "Object"), "embed": (("src",), "Embed"), "track": (("src",), "Track"),
}
SKIP = ("#", "mailto:", "tel:", "javascript:", "data:", "blob:", "sms:", "about:")
BLOCKED = (401, 403, 429, 999)

args = parse_args("Third-party URL report", lambda ap: ap.add_argument("--timeout", type=int, default=20))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("19_third_party_urls", "Third Party URL Report", "Link Health", site)
used = defaultdict(list)   # third-party URL -> [(page, type, rel)]


def collect(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return
    seen = set()
    for tag, (attrs, label) in TAGS.items():
        for el in soup.find_all(tag):
            for attr in attrs:
                value = (el.get(attr) or "").strip()
                if not value:
                    continue
                candidates = [c.strip().split(" ")[0] for c in value.split(",")] if attr == "srcset" else [value]
                for raw in candidates:
                    if not raw or raw.lower().startswith(SKIP):
                        continue
                    full = urljoin(loc, raw).split("#")[0]
                    if urlparse(full).scheme not in ("http", "https") or site.is_internal(full):
                        continue
                    kind = label
                    if tag == "link":
                        rel = " ".join(el.get("rel") or [])
                        kind = "Stylesheet" if "stylesheet" in rel else f"Link ({rel or 'no rel'})"
                    if (full, kind) not in seen:
                        seen.add((full, kind))
                        used[full].append((loc, kind))


def check(url):
    res = fetch(url, "HEAD", timeout=args.timeout)
    if res["status"] in (0, 400, 404, 405) or res["status"] >= 500:   # some servers mishandle HEAD
        res = fetch(url, timeout=args.timeout)
    err = res["error"]
    if res["status"] == 0:
        status = "Timeout" if "Timeout" in err else "SSL Error" if "SSL" in err else "Error"
    elif res["status"] in BLOCKED:
        status = "Unverified"
    elif res["status"] >= 400:
        status = "Error"
    elif res["history"]:
        status = "Redirect"
    else:
        status = "Working"
    chain = " -> ".join(f"{code}: {u}" for code, u, _ in res["history"])
    return url, {"code": res["status"] or "", "status": status, "final": res["url"] if res["status"] else "",
                 "chain": chain, "hops": len(res["history"]), "error": err}


print(f"Collecting third-party URLs from {len(pages)} pages ...")
run_parallel(collect, pages, args.workers)
print(f"Checking {len(used)} unique third-party URLs ...")
results = dict(run_parallel(check, sorted(used), args.workers, "third-party URLs"))
checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

summary_rows = []
domains = defaultdict(lambda: {"count": 0, "pages": set(), "urls": set(), "failing": 0})
for url, uses in sorted(used.items()):
    r = results[url]
    host = urlparse(url).netloc.lower()
    d = domains[host]
    for page, kind in uses:
        d["count"] += 1
        d["pages"].add(page)
        d["urls"].add(url)
        summary_rows.append((page, url, kind, r["code"], r["status"], r["final"], "Yes" if r["hops"] else "No", r["hops"],
                             r["chain"], r["error"], checked_at))
        critical_kind = kind in ("Script", "Stylesheet", "Iframe")
        if r["status"] in ("Error", "Timeout", "SSL Error"):
            d["failing"] += 1
            name = {"Error": "Third-party URL broken", "Timeout": "Third-party URL timeout",
                    "SSL Error": "Third-party URL SSL error"}[r["status"]]
            audit.add(page, CRITICAL if critical_kind and r["status"] != "Timeout" else IMPORTANT, kind, name,
                      current=f"HTTP {r['code']}" if r["code"] else (r["error"] or r["status"])[:200],
                      expected="HTTP 200", element=url[:250], detail=f"{kind} on {host}")
        elif r["status"] == "Redirect":
            audit.add(page, OPTIMIZATION, kind, "Third-party URL redirects", current=f"{r['hops']} redirect(s)",
                      expected=r["final"][:250], element=url[:250], detail=r["chain"][:400])
        if url.startswith("http://") and page.startswith("https://"):
            audit.add(page, IMPORTANT if kind != "Link" else OPTIMIZATION, kind, "Third-party URL over http:// (insecure)",
                      current=url[:250], expected="https://" + url[7:250])

domain_rows = [(host, d["count"], len(d["pages"]), d["failing"], "\n".join(sorted(d["pages"])[:20]),
                "\n".join(sorted(d["urls"])[:20])) for host, d in sorted(domains.items())]
statuses = defaultdict(int)
for r in results.values():
    statuses[r["status"]] += 1
audit.note("Third-party URLs (unique)", len(used))
audit.note("Third-party domains", len(domains))
audit.note("URL status", ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())) or "none")
audit.sheet("Third Party Summary", ["Page URL", "Third Party URL", "Type", "HTTP Status", "Status", "Final URL", "Redirected",
                                    "Redirect Count", "Redirect Chain", "Error", "Checked At"],
            sorted(summary_rows, key=lambda r: ({"Error": 0, "SSL Error": 0, "Timeout": 1, "Redirect": 2,
                                                  "Unverified": 3}.get(r[4], 4), r[0])),
            (50, 70, 18, 11, 11, 60, 10, 13, 70, 50, 19))
audit.sheet("Third Party Domains", ["Third Party Domain", "Occurrences", "Pages", "Failing uses", "Pages Found On (first 20)",
                                    "URL Examples (first 20)"], domain_rows, (40, 12, 8, 12, 80, 80))
audit.save("Third_Party_URL_Report")
