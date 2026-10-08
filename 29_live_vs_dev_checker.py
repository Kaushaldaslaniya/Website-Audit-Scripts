"""
29 - Live vs dev checker (site migration / redesign: nothing from the current live site may get lost)
  URLs:    every URL of the live site (its sitemap.xml + robots.txt sitemaps; if it has none, a crawl of up to
           --live-max pages) exists on the audited (dev) server or 301-redirects to a working page there
  new:     pages that exist only on dev, and dev pages that look like test / demo / duplicate pages
  parity:  for every page on both: title, meta description, H1, H2s, amount of text, noindex, JSON-LD types,
           phone / fax numbers - big losses are reported (e.g. content much shorter, page now noindex)
  visual:  --visual: screenshots of the main pages on live and dev and the % of pixels that differ (Pillow),
           saved in py files/report/<date>/screenshots/Live_vs_Dev_Report_<time>/

  The live URL comes from --live, else qa_config.json live_url, else $QA_LIVE_URL. Without one, every check is
  reported as "Not checked" (SKIP in the QA checklist).

  python "py files/29_live_vs_dev_checker.py" --live https://www.example.com [--base URL] [--visual]
"""
import os
import re
import xml.etree.ElementTree as ET

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, Audit, Site, discover_links, fetch, follow_redirects,
                        load_site, main_text, meta, parse_args, qa_config, run_browser_pages, run_parallel,
                        sample_pages, screenshot_dir, select_pages, text_of)


def extra(ap):
    ap.add_argument("--live", default=os.environ.get("QA_LIVE_URL") or qa_config()["live_url"],
                    help="the current live site (default: $QA_LIVE_URL, else qa_config.json live_url)")
    ap.add_argument("--live-max", type=int, default=500, help="pages to crawl on live when it has no sitemap")
    ap.add_argument("--visual", action="store_true", help="screenshot main pages on live + dev and compare")


args = parse_args("Live vs dev checker", extra)
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("29_live_vs_dev", "Live vs Dev Report", "Migration", site)
live = args.live.rstrip("/")
# a whole URL segment that is a placeholder name, or a slug ending in -copy / -old / -2 (duplicated in the CMS);
# "testing" in a real slug (/technologies/unit-testing) is a topic, not a test page
TEST_PAGE = re.compile(r"/(test|test-?page|demo|demo-?page|sample|sample-?page|lorem(-ipsum)?|untitled(-\d+)?|draft|tmp|"
                       r"temp|backup|hello-world|new-page)(/|$)|-(copy|old|backup|draft|tmp)(/|$)", re.I)
DUPLICATE = re.compile(r"^(.+)-\d+$")   # /blog/post-2 next to /blog/post
PHONE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
for loc in pages:
    audit.checked(loc)


def page_facts(content):
    soup = BeautifulSoup(content, "lxml")
    import json as _json
    types = set()
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            n = stack.pop()
            if isinstance(n, list):
                stack += n
            elif isinstance(n, dict):
                t = n.get("@type")
                types.update(t if isinstance(t, list) else [t] if t else [])
                stack += [v for v in n.values() if isinstance(v, (dict, list))]
    robots = (meta(soup, name="robots") or "").lower()
    text = main_text(soup)
    return {"title": text_of(soup.title) if soup.title else "", "desc": meta(soup, name="description") or "",
            "h1": text_of(soup.find("h1")) if soup.find("h1") else "",
            "h2": [text_of(h) for h in soup.find_all("h2") if text_of(h)], "words": len(text.split()),
            "noindex": "noindex" in robots, "types": types,
            "phones": {re.sub(r"\D", "", p)[-10:] for p in PHONE.findall(text)}, "soup": soup}


def norm_text(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


if not args.visual:
    audit.not_checked("Visual", "live vs dev screenshots", "--visual not given", "Run 29 with --visual.")
if not live:
    for what in ("live URLs exist on dev", "live vs dev content parity"):
        audit.not_checked("Migration", what, "no live URL (--live / qa_config.json live_url / $QA_LIVE_URL)",
                          "Set qa_config.json \"live_url\" to the current production site, or pass --live.")
    audit.save("Live_vs_Dev_Report")
    raise SystemExit(0)

# ------------------------------------------------------------------ live URLs
live_site = Site(live)
live_urls = live_site.load_sitemap()
source = "sitemap.xml"
robots = fetch(f"{live}/robots.txt")
if robots["status"] == 200:
    for sm in re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots["content"].decode("utf-8", "replace")):
        res = fetch(sm)
        try:
            live_urls += [e.text.strip() for e in ET.fromstring(res["content"]).iter() if e.tag.endswith("loc") and e.text
                          and not e.text.strip().endswith(".xml")]
        except ET.ParseError:
            pass
live_urls = list(dict.fromkeys(live_urls))
home = fetch(f"{live}/")
if not live_urls:
    if home["status"] != 200:
        reason = f"live site answered HTTP {home['status']} {home['error']}".strip()
        audit.not_checked("Migration", "live URLs exist on dev", reason + " (it blocks bots?)",
                          "Export the live URL list another way (Search Console, a crawl from your browser) and "
                          "check it, or allow-list the audit user agent.")
        audit.not_checked("Migration", "live vs dev content parity", reason)
        audit.save("Live_vs_Dev_Report")
        raise SystemExit(0)
    source = f"crawl of {live} (no sitemap: {live_site.sitemap_error or 'empty'})"
    print(f"No live sitemap - crawling up to {args.live_max} live pages ...")
    queue, seen = [f"{live}/"], {f"{live}/"}
    host = urlparse(live).netloc.lower().removeprefix("www.")
    while queue and len(live_urls) < args.live_max:
        batch, queue = queue[:20], queue[20:]
        for u, res in zip(batch, run_parallel(lambda x: fetch(x), batch, min(args.workers, 4), "live pages")):
            if res["status"] != 200 or "html" not in res["headers"].get("Content-Type", ""):
                continue
            live_urls.append(u)
            for link, how in discover_links(BeautifulSoup(res["content"], "lxml"), u):
                p = urlparse(link)
                if p.netloc.lower().removeprefix("www.") == host and link not in seen and \
                        not re.search(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|css|js|xml)$", p.path, re.I):
                    seen.add(link)
                    queue.append(link.split("#")[0])
print(f"{len(live_urls)} live URLs from {source}")


def path_key(u):
    p = urlparse(u)
    return (p.path.rstrip("/") or "/") + (f"?{p.query}" if p.query else "")


dev_paths = {path_key(u) for u in urls}


def compare(live_url):
    path = path_key(live_url)
    dev_url = site.base + path
    status, hops, loop = follow_redirects(dev_url)
    row = {"live": live_url, "path": path, "dev_status": status, "redirect": hops[-1][1] if len(hops) > 1 else "",
           "loop": loop}
    if status == 200:
        lres = fetch(live_url)
        dres = fetch(hops[-1][1] if len(hops) > 1 else dev_url)
        if lres["status"] == 200 and dres["status"] == 200 and "html" in lres["headers"].get("Content-Type", ""):
            row["live_facts"], row["dev_facts"] = page_facts(lres["content"]), page_facts(dres["content"])
        row["live_status"] = lres["status"]
    return row


print(f"Comparing {len(live_urls)} live URLs with {site.base} ...")
rows = run_parallel(compare, live_urls, min(args.workers, 6), "URLs compared")
url_rows, parity_rows = [], []
for r in rows:
    dev_page = site.base + r["path"]
    url_rows.append((r["live"], r["dev_status"] if not r["loop"] else "loop", r["redirect"]))
    if r["loop"]:
        audit.add(dev_page, CRITICAL, "Migration", "Live URL ends in a redirect loop on dev", current=r["live"])
        continue
    if r["dev_status"] != 200:
        audit.add(dev_page, CRITICAL, "Migration", "Live page missing on the new site (no redirect)",
                  current=f"HTTP {r['dev_status']}", element=r["live"], expected="HTTP 200 or a 301 to the new page",
                  fix="Rebuild the page or add a permanent redirect for this path (next.config redirects / vercel.json).")
        continue
    if r["redirect"] and len(r.get("redirect", "")) and path_key(r["redirect"]) == "/" and r["path"] != "/":
        audit.add(dev_page, IMPORTANT, "Migration", "Live page redirects to the homepage", current=r["live"],
                  expected="a redirect to the most relevant page (homepage redirects are treated as soft 404s)")
    lf, df = r.get("live_facts"), r.get("dev_facts")
    if not (lf and df):
        continue
    target = r["redirect"] or dev_page
    parity_rows.append((r["path"], lf["title"], df["title"], lf["h1"], df["h1"], lf["words"], df["words"],
                        "yes" if df["noindex"] and not lf["noindex"] else ""))
    if df["noindex"] and not lf["noindex"]:
        audit.add(target, CRITICAL, "Parity", "Page is noindex on the new site but indexed on live", current="noindex")
    if lf["words"] >= 150 and df["words"] < 0.7 * lf["words"]:
        audit.add(target, IMPORTANT, "Parity", "Much less text than on the live page",
                  current=f"{df['words']} words (live: {lf['words']})", expected=">= 70% of the live text",
                  fix="Check that no content sections were lost in the transfer (compare the pages side by side).")
    if norm_text(lf["h1"]) and norm_text(lf["h1"]) != norm_text(df["h1"]):
        audit.add(target, OPTIMIZATION, "Parity", "H1 changed from the live site", current=df["h1"][:120] or "(none)",
                  expected=f"live: {lf['h1'][:120]} - or an SEO sign-off for the new H1")
    if norm_text(lf["title"]) and norm_text(lf["title"]) != norm_text(df["title"]):
        audit.add(target, OPTIMIZATION, "Parity", "Title changed from the live site", current=df["title"][:120],
                  expected=f"live: {lf['title'][:120]} - or an SEO sign-off")
    if norm_text(lf["desc"]) and not norm_text(df["desc"]):
        audit.add(target, IMPORTANT, "Parity", "Meta description lost (live page has one)", current="(none)",
                  expected=lf["desc"][:160])
    lost_h2 = [h for h in lf["h2"] if norm_text(h) not in {norm_text(x) for x in df["h2"]}]
    if len(lost_h2) >= 3 and len(lost_h2) > len(lf["h2"]) / 2:
        audit.add(target, OPTIMIZATION, "Parity", "Most live H2 sections are missing on the new page",
                  current=f"{len(lost_h2)} of {len(lf['h2'])} H2s not found", element="; ".join(lost_h2[:5])[:300])
    lost_types = lf["types"] - df["types"] - {None}
    if lost_types:
        audit.add(target, OPTIMIZATION, "Parity", "Structured data types lost", current=", ".join(sorted(lost_types)),
                  expected="the same schema types as live (or better)")
    lost_phones = lf["phones"] - df["phones"]
    if lost_phones:
        audit.add(target, OPTIMIZATION, "Parity", "Phone / fax number on the live page is not on the new page",
                  current=", ".join(sorted(lost_phones)), fix="Confirm with the client whether the number (e.g. a fax) "
                  "should be on the new site.")

live_paths = {path_key(u) for u in live_urls}
new_rows = []
for u in urls:
    p = path_key(u)
    if p not in live_paths:
        new_rows.append((u,))
        dup = DUPLICATE.match(p)
        if TEST_PAGE.search(p) or (dup and dup.group(1) in dev_paths):
            audit.add(u, OPTIMIZATION, "New pages", "Page looks like a test / demo / duplicate page", current=p,
                      element=f"duplicate of {dup.group(1)}" if dup and dup.group(1) in dev_paths else "",
                      expected="only real pages in the sitemap", fix="Delete it, noindex it, or merge / redirect it.")
audit.note("Live site", live)
audit.note("Live URLs", f"{len(live_urls)} from {source}")
audit.note("Missing on dev", sum(1 for r in rows if r["dev_status"] != 200))

# ------------------------------------------------------------------ visual comparison (optional)
vis_rows = []
if args.visual:
    try:
        from PIL import Image, ImageChops
    except ImportError:
        Image = None
    if not Image:
        audit.not_checked("Visual", "live vs dev screenshots", "Pillow not installed", "pip install pillow")
    else:
        shots = screenshot_dir("Live_vs_Dev_Report")
        both = [r for r in rows if r.get("dev_facts")]
        main = [r for r in both if r["path"] in {path_key(u) for u in sample_pages([r["live"] for r in both], 0)}][:30]

        def snap(browser, r):
            name = (r["path"].strip("/").replace("/", "_") or "home")[:60]
            out = {}
            for tag, url in (("live", r["live"]), ("dev", r["redirect"] or site.base + r["path"])):
                ctx = browser.context(width=1440, height=900)
                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(1200)
                    out[tag] = shots / f"{name}_{tag}.png"
                    page.screenshot(path=str(out[tag]))
                except Exception:
                    pass
                finally:
                    ctx.close()
            if len(out) == 2:
                a, b = Image.open(out["live"]).convert("L"), Image.open(out["dev"]).convert("L")
                b = b.resize(a.size)
                diff = ImageChops.difference(a, b).point(lambda v: 255 if v > 40 else 0)
                pct = round(100 * sum(diff.histogram()[255:]) / (a.size[0] * a.size[1]), 1)
                diff.save(shots / f"{name}_diff.png")
                return r["path"], pct
            return r["path"], None
        print(f"Screenshotting {len(main)} main pages on live and dev ...")
        for res in run_browser_pages(snap, main, args.browser_workers, "pages compared"):
            if res:
                vis_rows.append(res)
                if res[1] is not None:
                    audit.add(site.base + res[0], INFO, "Visual", "Visual difference from the live page",
                              current=f"{res[1]}% of the first screen differs", element=str(shots))
        audit.note("Screenshots", str(shots))

audit.sheet("Live URLs", ["Live URL", "Dev HTTP (after redirects)", "Dev redirect target"], url_rows, (70, 12, 60))
audit.sheet("Content parity", ["Path", "Live title", "Dev title", "Live H1", "Dev H1", "Live words", "Dev words",
                               "Now noindex"], parity_rows, (40, 40, 40, 30, 30, 10, 10, 10))
audit.sheet("Only on dev", ["Dev URL"], new_rows, (80,))
audit.sheet("Visual diff", ["Path", "% of pixels different (first screen)"], vis_rows, (60, 18))
audit.save("Live_vs_Dev_Report")
