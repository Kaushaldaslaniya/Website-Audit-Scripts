"""
16 - Third-party resources checker
  HTML (every page): external scripts, stylesheets, fonts, images, iframes / embeds and preconnect hints, grouped by
      vendor (Google Analytics, Google Tag Manager, Hotjar, Meta Pixel, LinkedIn, YouTube, Google Fonts, CDNs ...)
  browser (every page, real Chrome, --browser-workers in parallel): every third-party request with HTTP status, load time, size, type,
      failed requests, render-blocking third-party CSS/JS, external API calls (fetch/XHR), excessive third parties

  python "py files/16_third_party_checker.py" [--base URL] [--no-browser]
"""
import re
import threading
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, parse_args, run_browser_pages,
                        run_parallel, select_pages)

VENDORS = [
    (r"google-analytics\.com|analytics\.google\.com|/gtag/js", "Google Analytics"),
    (r"googletagmanager\.com", "Google Tag Manager"),
    (r"hotjar\.com|hotjar\.io", "Hotjar"),
    (r"connect\.facebook\.net|facebook\.com/tr", "Meta (Facebook) Pixel"),
    (r"snap\.licdn\.com|linkedin\.com|licdn\.com", "LinkedIn"),
    (r"youtube\.com|ytimg\.com|youtube-nocookie\.com", "YouTube"),
    (r"fonts\.googleapis\.com|fonts\.gstatic\.com", "Google Fonts"),
    (r"google\.com/recaptcha|gstatic\.com/recaptcha|recaptcha\.net", "Google reCAPTCHA"),
    (r"maps\.googleapis\.com|google\.com/maps|maps\.gstatic\.com", "Google Maps"),
    (r"doubleclick\.net|googlesyndication\.com|googleadservices\.com", "Google Ads"),
    (r"clarity\.ms", "Microsoft Clarity"),
    (r"cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com", "Public CDN"),
    (r"calendly\.com", "Calendly"),
    (r"intercom|crisp\.chat|tawk\.to|zendesk|hubspot", "Chat / CRM widget"),
    (r"vimeo\.com", "Vimeo"),
    (r"images\.unsplash\.com|pexels\.com|cloudinary\.com|imgix\.net", "Image CDN"),
    (r"stripe\.com|paypal\.com|razorpay\.com", "Payments"),
    (r"twitter\.com|x\.com|twimg\.com", "X / Twitter"),
]

args = parse_args("Third-party resources checker", lambda ap: ap.add_argument("--no-browser", action="store_true"))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("16_third_party", "Third Party Report", "Performance", site)
static_rows, request_rows = [], []
domains_lock = threading.Lock()
domains = defaultdict(lambda: {"pages": set(), "kinds": Counter(), "requests": 0, "bytes": 0, "ms": [], "failed": 0, "blocking": 0})


def vendor(url):
    for rx, name in VENDORS:
        if re.search(rx, url, re.I):
            return name
    return "Other"


def check(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    found = []
    for tag, attr, kind in (("script", "src", "script"), ("link", "href", "link"), ("img", "src", "image"),
                            ("iframe", "src", "iframe"), ("source", "src", "media"), ("video", "src", "media"),
                            ("embed", "src", "embed"), ("object", "data", "embed")):
        for el in soup.find_all(tag):
            val = (el.get(attr) or "").strip()
            if not val or val.startswith("data:"):
                continue
            full = urljoin(loc, val)
            if site.is_internal(full) or not full.startswith("http"):
                continue
            if tag == "link":
                rel = " ".join(el.get("rel") or [])
                kind = "stylesheet" if "stylesheet" in rel else "preconnect/dns-prefetch" if re.search("preconnect|dns-prefetch", rel) \
                    else "font" if el.get("as") == "font" else rel or "link"
            blocking = tag == "script" and not (el.has_attr("async") or el.has_attr("defer") or el.get("type") == "module") \
                and el.find_parent("head") is not None
            blocking = blocking or (kind == "stylesheet" and el.get("media") not in ("print",))
            host = urlparse(full).netloc
            with domains_lock:
                d = domains[host]
                d["pages"].add(loc)
                d["kinds"][kind] += 1
            found.append((loc, vendor(full), host, kind, full[:200], "yes" if blocking else ""))
            if blocking:
                audit.add(loc, IMPORTANT if tag == "script" else OPTIMIZATION, "Blocking",
                          f"Render-blocking third-party {'script' if tag == 'script' else 'stylesheet'}",
                          current="sync <script> in <head>" if tag == "script" else "<link rel=stylesheet>",
                          expected="async/defer or next/script strategy=lazyOnload" if tag == "script"
                          else "self-hosted / non-blocking stylesheet", element=full[:200], detail=vendor(full))
            if tag == "iframe" and "youtube.com/embed" in full:
                audit.add(loc, OPTIMIZATION, "Embeds", "YouTube iframe embed (heavy) - use a click-to-load facade or youtube-nocookie",
                          current="<iframe src=youtube.com/embed>", element=full[:200])
    static_rows.extend(found)


print(f"Reading {len(pages)} pages ...")
run_parallel(check, pages, args.workers)


def browser_check(browser, loc):
    ctx = browser.context(width=1440, height=900)
    try:
        _browser_check(ctx, loc)
    finally:
        ctx.close()


def _browser_check(ctx, loc):
    page = ctx.new_page()
    reqs = []
    page.on("requestfinished", lambda r: reqs.append((r, None)))
    page.on("requestfailed", lambda r: reqs.append((r, r.failure or "failed")))
    try:
        page.goto(site.to_fetch(loc), wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
    except Exception as e:
        audit.add(loc, IMPORTANT, "Browser", "Page failed to load in Chrome", current=str(e)[:200])
        page.close()
        return
    page_host = urlparse(site.to_fetch(loc)).netloc
    third = []
    for r, failure in reqs:
        host = urlparse(r.url).netloc
        if host in (page_host, site.site_host) or not r.url.startswith("http"):
            continue
        status, size, ms = "", 0, 0
        try:
            resp = r.response()
            status = resp.status if resp else ""
            t = r.timing
            ms = round(t["responseEnd"] - t["startTime"]) if t and t.get("responseEnd", -1) > 0 else 0
            size = (r.sizes() or {}).get("responseBodySize", 0)
        except Exception:
            pass
        bad = failure or (isinstance(status, int) and status >= 400)
        with domains_lock:   # several Chrome workers update the same counters
            d = domains[host]
            d["pages"].add(loc)
            d["requests"] += 1
            d["bytes"] += size or 0
            if ms:
                d["ms"].append(ms)
            if bad:
                d["failed"] += 1
            if r.resource_type in ("fetch", "xhr"):
                d["kinds"]["api"] += 1
        if bad:
            audit.add(loc, IMPORTANT, "Requests", "Failed third-party request", current=str(failure or f"HTTP {status}"),
                      element=r.url[:200], detail=vendor(r.url))
        third.append(r)
        request_rows.append((loc, vendor(r.url), host, r.resource_type, status or failure, ms, size, r.url[:200]))
    page.close()
    total = sum(1 for _ in third)
    if total > 20:
        audit.add(loc, IMPORTANT, "Volume", "Excessive third-party requests", current=f"{total} requests",
                  expected="<= 10")
    elif total > 10:
        audit.add(loc, OPTIMIZATION, "Volume", "Many third-party requests", current=f"{total} requests",
                  expected="<= 10")


if args.no_browser:
    audit.not_checked("Requests", "third-party requests in Chrome (failures, speed, volume)", "--no-browser",
                      "Run 16_third_party_checker.py without --no-browser.")
else:
    print(f"Capturing network requests on {len(pages)} pages in Chrome ({args.browser_workers} in parallel) ...")
    run_browser_pages(browser_check, pages, args.browser_workers, "pages loaded")
    request_rows.sort(key=lambda r: r[0])
    for host, d in domains.items():
        if d["ms"] and sorted(d["ms"])[len(d["ms"]) // 2] > 1000:
            audit.site(OPTIMIZATION, "Speed", "Slow third-party domain", current=f"median {sorted(d['ms'])[len(d['ms']) // 2]} ms",
                       expected="< 1000 ms", element=host)

domain_rows = [(host, vendor("https://" + host), len(d["pages"]), d["requests"], round(d["bytes"] / 1024),
                round(sum(d["ms"]) / len(d["ms"])) if d["ms"] else "", d["failed"],
                ", ".join(f"{k}: {v}" for k, v in d["kinds"].items()))
               for host, d in sorted(domains.items(), key=lambda kv: -len(kv[1]["pages"]))]
audit.note("Third-party domains", len(domains))
audit.note("Vendors", ", ".join(sorted({vendor('https://' + h) for h in domains})) or "none")
audit.sheet("Domains", ["Domain", "Vendor", "Pages", "Requests (browser)", "KB", "Avg ms", "Failed", "Resource types"],
            domain_rows, (40, 22, 8, 16, 8, 8, 8, 60))
audit.sheet("Resources in HTML", ["Page", "Vendor", "Domain", "Type", "URL", "Render-blocking"], static_rows, (50, 22, 35, 20, 70, 14))
audit.sheet("Browser requests", ["Page", "Vendor", "Domain", "Type", "HTTP / error", "ms", "Bytes", "URL"], request_rows,
            (50, 22, 35, 10, 14, 7, 9, 70))
audit.save("Third_Party_Report")
