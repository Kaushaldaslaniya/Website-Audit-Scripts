"""
12 - Performance checker (real Chrome, desktop)
  timing:     page load, DNS, connection, TTFB, DOMContentLoaded, load, FCP, LCP (+ element), CLS, TBT, INP (lab)
  weight:     HTML / JavaScript / CSS / image / font size, number of requests, third-party requests, DOM size & depth
  blocking:   render-blocking CSS / JavaScript, unused JavaScript and CSS (Chrome coverage)
  delivery:   gzip / brotli compression, Cache-Control on static assets, CDN, HTTP/1.1 vs HTTP/2 / HTTP/3,
              preload / preconnect / dns-prefetch hints
  optional:   --lighthouse runs Google Lighthouse (npx) for Speed Index and Lighthouse's performance score

  python "py files/12_performance_checker.py" [--base URL] [--pages all] [--lighthouse]
  needs:  pip install playwright   (uses your installed Google Chrome)
"""
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from urllib.parse import urlparse

from seo_common import (COLLECT_METRICS_JS, CRITICAL, IMPORTANT, OPTIMIZATION, PERF_INIT_SCRIPT, Audit, Browser,
                        load_site, parse_args, rate, scroll_page, select_pages, simulate_interactions)

BUDGET = {"js": 400 * 1024, "css": 100 * 1024, "img": 1500 * 1024, "font": 200 * 1024, "total": 2500 * 1024,
          "requests": 80, "third_party": 15, "dom": 1500}
CDN_HEADERS = {"cf-ray": "Cloudflare", "x-vercel-id": "Vercel", "x-nf-request-id": "Netlify", "x-amz-cf-id": "CloudFront",
               "x-served-by": "Fastly", "x-akamai-transformed": "Akamai", "x-azure-ref": "Azure Front Door"}

args = parse_args("Performance checker", lambda ap: ap.add_argument("--lighthouse", action="store_true",
                                                                    help="also run Lighthouse (npx) for Speed Index"),
                  default_pages="sample")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("12_performance", "Performance Report", "Performance", site)
rows, resource_rows = [], []


def kind(res):
    url = res["url"].split("?")[0].lower()
    t = res["type"]
    if t == "script" or url.endswith(".js"):
        return "js"
    if t == "css" or url.endswith(".css") or (t == "link" and ".css" in url):
        return "css"
    if t == "img" or "/_next/image" in url or url.endswith((".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg")):
        return "img"
    if url.endswith((".woff", ".woff2", ".ttf", ".otf")):
        return "font"
    return "other"


def coverage_start(cdp):
    cdp.send("Profiler.enable")
    cdp.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    cdp.send("CSS.startRuleUsageTracking")


def coverage_stop(cdp, sheets):
    js_total = js_unused = 0
    try:
        for script in cdp.send("Profiler.takePreciseCoverage")["result"]:
            url = script["url"]
            if not url or not url.startswith("http"):
                continue
            ranges = [r for f in script["functions"] for r in f["ranges"]]
            if not ranges:
                continue
            length = max(r["endOffset"] for r in ranges)
            unused = sorted((r["startOffset"], r["endOffset"]) for r in ranges if r["count"] == 0)
            merged, total = [], 0
            for s, e in unused:
                if merged and s <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], e)
                else:
                    merged.append([s, e])
            total = sum(e - s for s, e in merged)
            js_total += length
            js_unused += min(total, length)
    except Exception:
        pass
    css_total = css_used = 0
    try:
        usage = cdp.send("CSS.stopRuleUsageTracking")["ruleUsage"]
        used = defaultdict(list)
        for u in usage:
            if u["used"]:
                used[u["styleSheetId"]].append((u["startOffset"], u["endOffset"]))
        for sid, length in sheets.items():
            css_total += length
            spans = sorted(used.get(sid, []))
            covered, last = 0, -1
            for s, e in spans:
                if e > last:
                    covered += e - max(s, last)
                    last = e
            css_used += covered
    except Exception:
        pass
    return js_total, js_unused, css_total, css_total - css_used


def lighthouse(url):
    npx = shutil.which("npx")
    if not npx:
        return None
    try:
        out = subprocess.run([npx, "--yes", "lighthouse", url, "--output=json", "--quiet", "--only-categories=performance",
                              "--chrome-flags=--headless=new"], capture_output=True, text=True, timeout=240)
        data = json.loads(out.stdout)
        a = data["audits"]
        return {"score": round(data["categories"]["performance"]["score"] * 100),
                "speed_index": a["speed-index"]["numericValue"], "tbt": a["total-blocking-time"]["numericValue"],
                "lcp": a["largest-contentful-paint"]["numericValue"], "fcp": a["first-contentful-paint"]["numericValue"],
                "cls": a["cumulative-layout-shift"]["numericValue"],
                "unused_js": a.get("unused-javascript", {}).get("details", {}).get("overallSavingsBytes", 0),
                "render_blocking_ms": a.get("render-blocking-resources", {}).get("details", {}).get("overallSavingsMs", 0)}
    except Exception:
        return None


print(f"Measuring {len(pages)} pages in Chrome ...")
with Browser() as browser:
    ctx = browser.context(width=1440, height=900)
    ctx.add_init_script(PERF_INIT_SCRIPT)
    for n, loc in enumerate(pages, 1):
        audit.checked(loc)
        page = ctx.new_page()
        responses, failed, sheets = [], [], {}
        page.on("response", lambda r: responses.append(r))
        page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
        cdp = ctx.new_cdp_session(page)
        cdp.on("CSS.styleSheetAdded", lambda e: sheets.__setitem__(e["header"]["styleSheetId"], e["header"].get("length", 0)))
        try:
            coverage_start(cdp)
            page.goto(site.to_fetch(loc), wait_until="load", timeout=90000)
            page.wait_for_timeout(1500)
            scroll_page(page)
            simulate_interactions(page)
            page.wait_for_timeout(500)
            m = page.evaluate(COLLECT_METRICS_JS)
            js_total, js_unused, css_total, css_unused = coverage_stop(cdp, sheets)
        except Exception as e:
            audit.add(loc, CRITICAL, "Load", "Page failed to load in Chrome", current=str(e)[:200])
            page.close()
            continue

        page_host = urlparse(site.to_fetch(loc)).netloc
        by_kind = Counter()
        third = [r for r in m["resources"] if urlparse(r["url"]).netloc not in (page_host, site.site_host)]
        for r in m["resources"]:
            by_kind[kind(r)] += r["size"] or r["body"] or 0
        total_bytes = sum(by_kind.values()) + (m["htmlTransfer"] or 0)
        blocking = [r["url"] for r in m["resources"] if r["blocking"] == "blocking"]

        # response headers: compression / caching / CDN / protocol
        doc_headers = {}
        uncompressed, uncached = [], []
        cdn = ""
        for r in responses:
            try:
                h = {k.lower(): v for k, v in r.headers.items()}
            except Exception:
                continue
            url = r.url
            if r.request.resource_type == "document" and not doc_headers:
                doc_headers = h
            for header, name in CDN_HEADERS.items():
                if header in h:
                    cdn = name
            if "netlify" in h.get("server", "").lower():
                cdn = cdn or "Netlify"
            internal = urlparse(url).netloc in (page_host, site.site_host)
            rtype = r.request.resource_type
            if internal and rtype in ("document", "script", "stylesheet") and r.status == 200:
                if h.get("content-encoding", "") not in ("br", "gzip", "zstd", "deflate"):
                    uncompressed.append(url.split("?")[0][-150:])
            if internal and "/_next/static/" in url and r.status == 200:
                cc = h.get("cache-control", "")
                if "max-age=31536000" not in cc and "immutable" not in cc:
                    uncached.append((url.split("?")[0][-120:], cc))
        page.close()

        def add(sev, cat, check, detail="", **kw):
            audit.add(loc, sev, cat, check, detail, **kw)

        if m["ttfb"] > 1800:
            add(IMPORTANT, "Timing", "Slow TTFB", current=f"{m['ttfb']:.0f} ms", expected="<= 800 ms")
        elif m["ttfb"] > 800:
            add(OPTIMIZATION, "Timing", "TTFB above 800 ms", current=f"{m['ttfb']:.0f} ms", expected="<= 800 ms")
        for metric, good, poor, label in (("fcp", 1800, 3000, "FCP"), ("lcp", 2500, 4000, "LCP"), ("tbt", 200, 600, "TBT")):
            verdict = rate(m[metric], good, poor)
            if verdict != "Good":
                add(IMPORTANT if verdict == "Poor" else OPTIMIZATION, "Timing", f"{label} {verdict.lower()}",
                    current=f"{m[metric]:.0f} ms", expected=f"<= {good} ms",
                    element=m["lcpEl"] if metric == "lcp" else None, detail="desktop, unthrottled")
        verdict = rate(m["cls"], 0.1, 0.25)
        if verdict != "Good":
            add(IMPORTANT if verdict == "Poor" else OPTIMIZATION, "Timing", f"CLS {verdict.lower()}",
                current=f"{m['cls']:.3f}", expected="<= 0.1")
        if m["inp"] is not None and m["inp"] > 200:
            add(IMPORTANT if m["inp"] > 500 else OPTIMIZATION, "Timing", "Slow interaction (lab INP)",
                current=f"{m['inp']:.0f} ms", expected="<= 200 ms")
        for k in ("js", "css", "img", "font"):
            if by_kind[k] > BUDGET[k]:
                add(OPTIMIZATION if k != "js" else IMPORTANT, "Weight", f"{k.upper()} over budget",
                    current=f"{by_kind[k] // 1024} KB", expected=f"<= {BUDGET[k] // 1024} KB")
        if total_bytes > BUDGET["total"]:
            add(IMPORTANT, "Weight", "Page weight over budget", current=f"{total_bytes // 1024} KB",
                expected=f"<= {BUDGET['total'] // 1024} KB")
        if len(m["resources"]) > BUDGET["requests"]:
            add(OPTIMIZATION, "Weight", "Many requests", current=f"{len(m['resources'])} requests",
                expected=f"<= {BUDGET['requests']}")
        if len(third) > BUDGET["third_party"]:
            add(OPTIMIZATION, "Third-party", "Many third-party requests", current=f"{len(third)} requests",
                expected=f"<= {BUDGET['third_party']}")
        if m["domNodes"] > BUDGET["dom"]:
            add(OPTIMIZATION if m["domNodes"] < 3000 else IMPORTANT, "DOM", "Large DOM",
                current=f"{m['domNodes']} nodes, depth {m['domDepth']}", expected=f"<= {BUDGET['dom']} nodes")
        for b in blocking:
            add(OPTIMIZATION, "Render-blocking", "Render-blocking resources", current="blocks first render",
                element=b[:200])
        if js_total and js_unused / js_total > 0.4:
            add(OPTIMIZATION, "Coverage", "Unused JavaScript", current=f"{js_unused // 1024} KB of {js_total // 1024} KB "
                f"({100 * js_unused // js_total}%) unused on load", expected="under 40% unused")
        if css_total and css_unused / css_total > 0.5:
            add(OPTIMIZATION, "Coverage", "Unused CSS", current=f"{css_unused // 1024} KB of {css_total // 1024} KB "
                f"({100 * css_unused // css_total}%) unused", expected="under 50% unused")
        for name in uncompressed:
            add(IMPORTANT, "Delivery", "Responses not compressed (gzip/brotli)", current="no Content-Encoding",
                expected="br or gzip", element=name)
        for name, cc in uncached:
            add(IMPORTANT, "Delivery", "Static assets without long-term caching", current=cc or "no Cache-Control",
                expected="public, max-age=31536000, immutable", element=name)
        if m["protocol"] in ("http/1.1", "http/1.0") and site.is_public:
            add(IMPORTANT, "Delivery", "Served over HTTP/1.1 (no HTTP/2/3)", current=m["protocol"], expected="h2 or h3")
        if site.is_public and not cdn:
            add(OPTIMIZATION, "Delivery", "No CDN detected from response headers", current="no CDN header")
        third_hosts = {urlparse(r["url"]).netloc for r in third}
        preconnected = {urlparse(u).netloc for u in m["preconnect"] + m["dnsPrefetch"]}
        missing_hints = sorted(h for h in third_hosts - preconnected
                               if sum(1 for r in third if urlparse(r["url"]).netloc == h) >= 2)
        for host in missing_hints:
            add(OPTIMIZATION, "Hints", "Third-party origins without preconnect/dns-prefetch", current="no hint",
                expected=f'<link rel="preconnect" href="https://{host}">', element=host)
        for u, e in failed:
            add(IMPORTANT, "Requests", "Failed requests", current=str(e)[:150], element=u[:200])

        lh = lighthouse(site.to_fetch(loc)) if args.lighthouse else None
        if lh and lh["speed_index"] > 3400:
            add(IMPORTANT if lh["speed_index"] > 5800 else OPTIMIZATION, "Timing", "Speed Index slow (Lighthouse)",
                current=f"{lh['speed_index']:.0f} ms", expected="<= 3400 ms")
        rows.append((loc, round(m["dns"]), round(m["connect"]), round(m["ttfb"]), round(m["domContentLoaded"]), round(m["load"]),
                     round(m["fcp"]), round(m["lcp"]), m["lcpEl"], round(m["cls"], 3), round(m["tbt"]),
                     round(m["inp"]) if m["inp"] is not None else "", round(lh["speed_index"]) if lh else "",
                     lh["score"] if lh else "", m["domNodes"], m["domDepth"], (m["htmlSize"] or 0) // 1024,
                     by_kind["js"] // 1024, by_kind["css"] // 1024, by_kind["img"] // 1024, by_kind["font"] // 1024,
                     total_bytes // 1024, len(m["resources"]), len(third), len(blocking), js_unused // 1024,
                     css_unused // 1024, m["protocol"], doc_headers.get("content-encoding", ""), cdn,
                     len(m["preconnect"]), len(m["dnsPrefetch"]), m["preload"]))
        for r in sorted(m["resources"], key=lambda r: -(r["size"] or 0))[:15]:
            resource_rows.append((loc, kind(r), r["url"][:200], (r["size"] or 0) // 1024, r["duration"], r["protocol"],
                                  r["blocking"]))
        print(f"  {n}/{len(pages)} {loc}  LCP {m['lcp']:.0f}ms  CLS {m['cls']:.3f}  TBT {m['tbt']:.0f}ms")

audit.sheet("Metrics", ["URL", "DNS ms", "Connect ms", "TTFB ms", "DOMContentLoaded ms", "Load ms", "FCP ms", "LCP ms",
                        "LCP element", "CLS", "TBT ms", "INP ms (lab)", "Speed Index (LH)", "Lighthouse score", "DOM nodes",
                        "DOM depth", "HTML KB", "JS KB", "CSS KB", "Images KB", "Fonts KB", "Total KB", "Requests",
                        "3rd-party req", "Render-blocking", "Unused JS KB", "Unused CSS KB", "Protocol", "HTML encoding",
                        "CDN", "preconnect", "dns-prefetch", "preload"], rows,
            (50, 7, 9, 8, 11, 8, 8, 8, 40, 7, 7, 9, 10, 10, 9, 8, 8, 7, 7, 9, 8, 8, 9, 10, 10, 10, 11, 9, 10, 10, 9, 10, 8))
audit.sheet("Largest resources", ["Page", "Type", "URL", "KB", "Duration ms", "Protocol", "Render-blocking"], resource_rows,
            (45, 7, 80, 7, 11, 9, 14))
audit.save("Performance_Report")
