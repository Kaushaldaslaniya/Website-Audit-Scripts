"""
01 - Sitemap, robots.txt & crawl coverage checker
  sitemap.xml: reachable, valid XML, size limits, duplicates, host/HTTPS, localhost, <lastmod>
  every sitemap URL: HTTP 200 (no redirect), indexable (no noindex, self canonical), allowed by robots.txt
  robots.txt: reachable, doesn't block the site, declares the sitemap on the right host
  crawl coverage (every URL the crawler discovered, not only the sitemap): live pages missing from the sitemap,
      broken internal URLs, internal URLs that redirect, URLs blocked by robots.txt, crawl limit reached
      ("Found via" = javascript: the link only appears after clicking a menu / tab)

  python "py files/01_sitemap_checker.py" [--base URL]
"""
import re
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, Audit, fetch, has_rel, load_site, meta, norm,
                        parse_args, run_parallel, select_pages)

args = parse_args("Sitemap, robots.txt & crawl coverage checker")
site, urls = load_site(args, need_sitemap=False)
audit = Audit("01_sitemap", "Sitemap Report", "Technical SEO", site)
sitemap_urls = site.sitemap_urls

# ---------------------------------------------------------------- sitemap.xml
res = site.sitemap_response or fetch(f"{site.base}/sitemap.xml")
if not sitemap_urls:
    audit.site(CRITICAL, "Sitemap", "sitemap.xml missing or invalid", site.sitemap_error or "no <url> entries",
               expected="Valid sitemap.xml listing every indexable URL")
else:
    audit.note("Sitemap URLs", len(sitemap_urls))
    audit.note("Canonical host", site.site_host)
    if len(sitemap_urls) > 50000:
        audit.site(CRITICAL, "Sitemap", "More than 50,000 URLs in one sitemap", current=f"{len(sitemap_urls)} URLs")
    if len(res["content"]) > 50 * 1024 * 1024:
        audit.site(CRITICAL, "Sitemap", "sitemap.xml larger than 50 MB", current=f"{len(res['content']) // 1048576} MB")
    ctype = res["headers"].get("Content-Type", "")
    if "xml" not in ctype:
        audit.site(IMPORTANT, "Sitemap", "sitemap.xml not served as XML", current=ctype or "(no Content-Type)")
    if not site.is_public:
        audit.site(CRITICAL, "Sitemap", "Sitemap URLs point to a local/development host",
                   current=f"{site.site_scheme}://{site.site_host}",
                   detail="set NEXT_PUBLIC_SITE_URL to the live https domain for production builds")
    if site.site_scheme != "https":
        audit.site(CRITICAL, "Sitemap", "Sitemap URLs are not HTTPS", current=f"{site.site_scheme}://{site.site_host}")
    hosts = sorted({u.split("/")[2] for u in sitemap_urls})
    if len(hosts) > 1:
        audit.site(IMPORTANT, "Sitemap", "Sitemap mixes hosts", current=", ".join(hosts))
    raw = [l.text.strip() for l in site.sitemap_root.iter() if l.tag.endswith("loc") and l.text]
    counts = {u: raw.count(u) for u in set(raw)}
    for u in sorted(u for u, n in counts.items() if n > 1):
        audit.add(u, IMPORTANT, "Sitemap", "Duplicate URL in sitemap", current=f"listed {counts[u]} times",
                  expected="listed once")
    lower = {}
    for u in sitemap_urls:
        if u.lower() in lower and lower[u.lower()] != u:
            audit.add(u, IMPORTANT, "Sitemap", "Same URL with different letter case", current=u,
                      detail=f"also listed as {lower[u.lower()]}")
        lower[u.lower()] = u
    now = datetime.now(timezone.utc)
    for entry in site.sitemap_root:
        loc = next((c.text for c in entry if c.tag.endswith("loc")), None)
        lastmod = next((c.text for c in entry if c.tag.endswith("lastmod")), None)
        if not loc:
            continue
        if not lastmod:
            audit.add(loc.strip(), OPTIMIZATION, "Sitemap", "Missing <lastmod>", current="(none)")
            continue
        try:
            d = datetime.fromisoformat(lastmod.strip().replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d > now:
                audit.add(loc.strip(), IMPORTANT, "Sitemap", "<lastmod> in the future", current=lastmod)
        except ValueError:
            audit.add(loc.strip(), IMPORTANT, "Sitemap", "Invalid <lastmod> date", current=lastmod)

# ---------------------------------------------------------------- robots.txt
robots = fetch(f"{site.base}/robots.txt")
rp = robotparser.RobotFileParser()
robots_rows = []
if robots["status"] != 200:
    audit.site(CRITICAL, "Robots.txt", "robots.txt missing", current=f"HTTP {robots['status']}")
else:
    body = robots["content"].decode("utf-8", "replace")
    rp.parse(body.splitlines())
    robots_rows = [(i + 1, line) for i, line in enumerate(body.splitlines())]
    if not rp.can_fetch("Googlebot", site.public("/")) or not rp.can_fetch("*", site.public("/")):
        audit.site(CRITICAL, "Robots.txt", "robots.txt blocks the homepage / whole site", current="Disallow matches /")
    declared = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body)
    if not declared:
        audit.site(IMPORTANT, "Robots.txt", "robots.txt has no Sitemap: line", current="(none)")
    for sm in declared:
        if site.site_host and sm.split("/")[2] != site.site_host:
            audit.site(IMPORTANT, "Robots.txt", "robots.txt sitemap on a different host", current=sm,
                       expected=f"a sitemap URL on {site.site_host}")
        elif fetch(site.to_fetch(sm))["status"] != 200:
            audit.site(CRITICAL, "Robots.txt", "Sitemap declared in robots.txt is unreachable", current=sm)
    if not re.search(r"(?im)^\s*user-agent:", body):
        audit.site(IMPORTANT, "Robots.txt", "robots.txt has no User-agent group")

# ---------------------------------------------------------------- every sitemap URL
pages = select_pages(sitemap_urls, args)
host_mismatch = set()


def check(loc):
    audit.checked(loc)
    r = fetch(site.to_fetch(loc), allow_redirects=False)
    row = {"url": loc, "status": r["status"], "ms": r["ms"], "indexable": "yes", "canonical": "", "robots_txt": "allowed"}
    if r["status"] in (301, 302, 303, 307, 308):
        target = urljoin(loc, r["location"])
        audit.add(loc, IMPORTANT, "Sitemap URL", "Sitemap URL redirects", current=f"HTTP {r['status']} -> {target}",
                  expected=f"list the final URL {target} instead")
        row["indexable"] = "no (redirect)"
    elif r["status"] != 200:
        audit.add(loc, CRITICAL, "Sitemap URL", "Sitemap URL is not 200", current=f"HTTP {r['status']} {r['error']}".strip(),
                  expected="HTTP 200 - or remove the URL from the sitemap")
        row["indexable"] = f"no (HTTP {r['status']})"
    if robots["status"] == 200 and not rp.can_fetch("Googlebot", loc):
        audit.add(loc, CRITICAL, "Sitemap URL", "Sitemap URL blocked by robots.txt", current="Disallowed for Googlebot")
        row["robots_txt"] = "BLOCKED"
    if r["status"] == 200:
        soup = BeautifulSoup(r["content"], "lxml")
        robots_meta = (meta(soup, name="robots") or "") + " " + r["headers"].get("X-Robots-Tag", "")
        if "noindex" in robots_meta.lower():
            audit.add(loc, CRITICAL, "Sitemap URL", "Sitemap URL is noindex", current=robots_meta.strip())
            row["indexable"] = "no (noindex)"
        canon = soup.find("link", rel=lambda v: v and has_rel(v, "canonical"))
        row["canonical"] = canon.get("href", "") if canon else ""
        canon_abs = urljoin(loc, row["canonical"]) if row["canonical"] else ""
        if canon_abs and norm(canon_abs) != norm(loc):
            if site.path(canon_abs) == site.path(loc):
                host_mismatch.add((canon_abs.split("/")[2], loc.split("/")[2]))
            else:
                audit.add(loc, IMPORTANT, "Sitemap URL", "Sitemap URL canonicalises elsewhere", current=row["canonical"],
                          expected=loc)
                row["indexable"] = "no (canonical elsewhere)"
    return row


print(f"Checking {len(pages)} sitemap URLs ...")
rows = run_parallel(check, pages, args.workers)
for canon_host, sm_host in sorted(host_mismatch):
    audit.site(IMPORTANT, "Sitemap", "Sitemap host differs from the canonical host",
               current=f"canonical host {canon_host}, sitemap host {sm_host}",
               detail="both must be built from NEXT_PUBLIC_SITE_URL")

# ---------------------------------------------------------------- crawl coverage (all discovered URLs)
crawl_rows = []
if site.crawl:
    recs = site.crawl["records"]
    stats = site.crawl["stats"]
    if stats.get("truncated"):
        audit.site(IMPORTANT, "Crawl", "Crawl limit reached - some URLs were not crawled",
                   current=f"{stats['crawled']} URLs (limit {stats['max_pages']})", expected="all URLs crawled")
    for url in site.crawl["order"]:
        r = recs[url]
        found_on = r.get("found_on") or ("sitemap.xml" if r["in_sitemap"] else "")
        if r["robots_blocked"]:
            if r.get("found_on"):
                audit.add(url, OPTIMIZATION, "Crawl", "Internal URL blocked by robots.txt", current="Disallowed",
                          element=f"linked from {r['found_on']}")
        elif r["status"] in (301, 302, 303, 307, 308) and not r["in_sitemap"]:
            audit.add(url, OPTIMIZATION, "Crawl", "Internal URL redirects",
                      current=f"HTTP {r['status']} -> {r['redirect_to']}", expected=f"link directly to {r['final_url']}",
                      element=f"linked from {found_on}", detail=f"{r['sources']} page(s) link here")
        elif r["status"] is not None and r["status"] != 200 and r["status"] not in (301, 302, 303, 307, 308) \
                and not r["in_sitemap"]:
            audit.add(url, CRITICAL if (r["status"] or 0) >= 500 or r["status"] == 0 else IMPORTANT, "Crawl",
                      "Broken internal URL", current=f"HTTP {r['status']} {r['error']}".strip(),
                      element=f"linked from {found_on}", detail=f"found via {r['via']}; {r['sources']} page(s) link here")
        elif r["is_html"] and r["status"] == 200 and not r["in_sitemap"] and not r["noindex"]:
            canon = r.get("canonical") or ""
            if not canon or norm(canon) == norm(url):
                audit.add(url, IMPORTANT, "Coverage", "Live page missing from sitemap",
                          current="not in sitemap.xml", expected="listed in sitemap.xml",
                          element=f"linked from {found_on}", detail=f"found via {r['via']}")
        elif r["status"] == 200 and r["content_type"] and not r["is_html"] and r["via"] == "link":
            audit.add(url, OPTIMIZATION, "Crawl", "Internal link to a non-HTML page", current=r["content_type"],
                      element=f"linked from {found_on}")
        crawl_rows.append((url, r["status"], r["content_type"], "yes" if r["in_sitemap"] else "no", r["via"],
                           found_on, "" if r["depth"] is None else r["depth"], r.get("inlinks", 0),
                           r["redirect_to"], "BLOCKED" if r["robots_blocked"] else "", "yes" if r["noindex"] else "",
                           r["canonical"], r["title"], r["ms"], r["error"]))
    audit.note("URLs discovered by crawling", stats["crawled"])
    audit.note("HTML pages found only by crawling (not in sitemap)",
               sum(1 for r in recs.values() if r["is_html"] and not r["in_sitemap"]))

audit.sheet("Sitemap URLs", ["URL", "HTTP", "Response ms", "Indexable", "Canonical", "robots.txt"],
            [(r["url"], r["status"], r["ms"], r["indexable"], r["canonical"], r["robots_txt"]) for r in rows],
            (60, 7, 11, 24, 60, 12))
audit.sheet("Crawled URLs", ["URL", "HTTP", "Content-Type", "In sitemap", "Found via", "Found on", "Clicks from home",
                             "Incoming links", "Redirects to", "robots.txt", "noindex", "Canonical", "Title", "ms", "Error"],
            crawl_rows, (60, 7, 14, 10, 12, 50, 9, 9, 50, 10, 8, 50, 50, 7, 30))
audit.sheet("robots.txt", ["Line", "Content"], robots_rows, (6, 100))
audit.save("Sitemap_Report")
