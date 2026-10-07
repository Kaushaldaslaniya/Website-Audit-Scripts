"""
05 - Link & site-architecture checker
  links:        internal / external counts, broken (404 / 5xx), redirecting links, redirect chains & loops,
                empty links, non-descriptive anchor text, rel nofollow / sponsored / ugc, excessive links,
                pages with no / very few internal links
  architecture: orphan pages, crawl depth from the homepage, important pages too deep, homepage -> main
                sections, hub pages -> their detail pages (services, industries, technologies, blog,
                portfolio), breadcrumbs on nested pages, header navigation & footer links,
                links that only appear after clicking a menu / tab (status checked; pages linked only that way)
                (orphans / depth use the link graph of the whole-site crawl, so they work with --pages sample too)

  python "py files/05_link_checker.py" [--base URL] [--no-external]
"""
import re
from collections import defaultdict, deque
from urllib.parse import urljoin

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, follow_redirects, load_site,
                        parse_args, run_parallel, select_pages, text_of)

GENERIC_ANCHORS = {"click here", "here", "read more", "more", "learn more", "link", "this", "view", "details", "go",
                   "view more", "see more", "continue", "click"}
MAX_LINKS = 150
MIN_INTERNAL = 3
MAX_DEPTH = 3
MAIN_SECTIONS = ["/about-us", "/services", "/technologies", "/industries", "/portfolio", "/blog", "/contact-us"]
HUBS = {"/industries": "/industries/", "/technologies": "/technologies/", "/blog": "/blog/", "/portfolio": "/portfolio/",
        "/software-services": "/software-services/", "/digital-services": "/digital-services/",
        "/intelligent-data-services": "/intelligent-data-services/", "/tools": "/tools/"}

args = parse_args("Link checker", lambda ap: ap.add_argument("--no-external", action="store_true",
                                                             help="skip third-party link checks"))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("05_links", "Link Health Report", "Links", site)

graph = {}                                      # page path -> set(internal paths)
link_rows = []                                  # (page, href, type, anchor, rel)
internal_targets = defaultdict(dict)            # fetch URL -> {source page: anchor text}
external_targets = defaultdict(dict)
nav_links, footer_links = set(), set()


def anchor_text(a):
    text = text_of(a) or (a.get("aria-label") or "").strip() or (a.get("title") or "").strip()
    if not text:
        img = a.find("img", alt=True)
        text = img["alt"].strip() if img else ""
    return text


def scan(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    path = site.path(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        graph[path] = set()
        return
    targets, count = set(), 0
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        label = anchor_text(a)
        if not href:
            audit.add(loc, IMPORTANT, "Links", "Empty link (no href)", current='href=""', element=f"<a> '{label[:60]}'")
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "sms:")):
            if href.startswith("javascript:"):
                audit.add(loc, IMPORTANT, "Links", "javascript: link", current=href[:100], element=f"<a> '{label[:60]}'")
            continue
        count += 1
        absolute = urljoin(site.to_fetch(loc), href).split("#")[0]
        internal = site.is_internal(absolute)
        rel = " ".join(a.get("rel") or [])
        if not label:
            audit.add(loc, IMPORTANT, "Anchor text", "Link without text or accessible name", current="(no text)",
                      element=f"<a href={href[:120]}>")
        elif label.lower().strip(" .→›»>") in GENERIC_ANCHORS:
            audit.add(loc, OPTIMIZATION, "Anchor text", "Non-descriptive anchor text", current=f"'{label}'",
                      element=f"<a href={href[:120]}>")
        if internal:
            p = site.path(absolute)
            targets.add(p)
            internal_targets[site.to_fetch(absolute)].setdefault(loc, label[:80])
            if "nofollow" in rel:
                audit.add(loc, IMPORTANT, "rel", "nofollow on an internal link", current=f'rel="{rel}"',
                          element=f"<a href={href[:120]}> '{label[:40]}'")
        else:
            external_targets[absolute].setdefault(loc, label[:80])
            if a.get("target") == "_blank" and "noopener" not in rel and "noreferrer" not in rel:
                audit.add(loc, OPTIMIZATION, "rel", "target=_blank without rel=noopener", current=f'rel="{rel}"',
                          element=f"<a href={href[:120]}>")
        link_rows.append((loc, absolute[:250], "internal" if internal else "external", label[:80], rel))
    graph[path] = targets - {path}
    if count > MAX_LINKS:
        audit.add(loc, OPTIMIZATION, "Links", "Excessive links on page", current=f"{count} links",
                  expected=f"under {MAX_LINKS}")
    if not graph[path]:
        audit.add(loc, IMPORTANT, "Links", "No internal links on page", current="0 internal links",
                  expected=f"{MIN_INTERNAL}+ internal links")
    elif len(graph[path]) < MIN_INTERNAL:
        audit.add(loc, OPTIMIZATION, "Links", "Very few internal links", current=f"{len(graph[path])} unique internal links",
                  expected=f"{MIN_INTERNAL}+ internal links")
    nested = path.count("/") >= 2
    if nested and not soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)}) \
            and not soup.find(class_=re.compile("breadcrumb", re.I)):
        audit.add(loc, OPTIMIZATION, "Architecture", "Nested page without breadcrumbs", current="no breadcrumb found")
    if path == "/":
        for zone, store in (("header", nav_links), ("footer", footer_links)):
            el = soup.find(zone)
            for a in (el.find_all("a", href=True) if el else []):
                h = urljoin(site.to_fetch(loc), a["href"]).split("#")[0]
                if site.is_internal(h):
                    store.add((site.path(h), anchor_text(a)))


print(f"Scanning {len(pages)} pages ...")
run_parallel(scan, pages, args.workers)

# ------------------------------------------------------------ links that only appear after clicking menus / tabs
js_links = (site.crawl or {}).get("js_links", {})
in_pages = set(pages)
js_rows = []
for page_url, links in sorted(js_links.items()):
    for url, zone in sorted(links.items()):
        if page_url in in_pages:   # their status is checked below like every other internal link
            internal_targets[site.to_fetch(url)].setdefault(page_url, f"(shown after clicking a {zone} menu / tab)")
        js_rows.append((page_url, url, zone, "yes" if site.record(url).get("js_only") else ""))
        if site.path(page_url) == "/" and zone == "menu":
            nav_links.add((site.path(url), "(after opening the menu)"))
if js_links:
    total = sum(len(v) for v in js_links.values())
    menu = sorted({u for v in js_links.values() for u, z in v.items() if z == "menu"})
    audit.site(OPTIMIZATION, "Architecture", "Links rendered only after clicking a menu or tab",
               current=f"{total} links on {len(js_links)} pages are not in the server HTML"
                       + (f" ({len(menu)} in the header / navigation menus)" if menu else ""),
               element=", ".join(site.path(u) for u in menu[:8]) or None,
               detail="search engines don't click: these links pass no link signals unless the page is also linked "
                      "in the HTML elsewhere")
    audit.note("Links found only after JavaScript interaction", total)

# ------------------------------------------------------------ internal link status (+ redirect chains)
status_rows = []


def probe_internal(target):
    final, hops, loop = follow_redirects(target)
    return target, final, hops, loop


print(f"Checking {len(internal_targets)} internal link targets ...")
for target, final, hops, loop in run_parallel(probe_internal, sorted(internal_targets), args.workers, "links"):
    sources = internal_targets[target]
    path = site.path(target) + (f"?{target.split('?', 1)[1]}" if "?" in target else "")
    redirects = len(hops) - 1
    chain = " -> ".join(f"{h[0]} {site.path(str(h[1]))}" for h in hops)
    final_url = site.path(str(hops[-1][1])) if hops else path
    check = expected = None
    if loop:
        result, sev, check = "REDIRECT LOOP", CRITICAL, "Redirect loop"
    elif final == 0 or (isinstance(final, int) and final >= 400):
        result = "BROKEN"
        sev = CRITICAL if final == 0 or final >= 500 else IMPORTANT
        check, expected = "Broken internal link", "HTTP 200 - fix the link or restore / redirect the target"
    elif redirects > 1:
        result, sev, check = f"redirect chain ({redirects} hops)", IMPORTANT, "Internal link redirect chain"
        expected = f"link directly to {final_url}"
    elif redirects == 1:
        result, sev, check = "redirects", OPTIMIZATION, "Internal link redirects"
        expected = f"link directly to {final_url}"
    else:
        result, sev = "OK", None
    if sev:
        for s, label in sorted(sources.items()):
            audit.add(s, sev, "Internal links", check, current=f"{path} -> {chain}" if redirects else f"{path} -> HTTP {final}",
                      expected=expected, element=f"<a href={path}> '{label}'")
    status_rows.append((path, "internal", final, result, chain, len(sources), sorted(sources)[0]))

# ------------------------------------------------------------ external links
if not args.no_external:
    def probe_external(target):
        res = fetch(target, "HEAD", timeout=20)
        if res["status"] in (0, 404, 405) or res["status"] >= 500:   # some servers mishandle HEAD
            res = fetch(target, timeout=20)
        return target, res

    print(f"Checking {len(external_targets)} external links ...")
    for target, res in run_parallel(probe_external, sorted(external_targets), args.workers, "external links"):
        sources = external_targets[target]
        st = res["status"]
        if st in (401, 403, 429, 999):
            result = "unverified (site blocks automated checks)"
        elif st == 0 or st >= 400:
            result = "BROKEN"
            for s, label in sorted(sources.items()):
                audit.add(s, IMPORTANT, "External links", "Broken external link",
                          current=f"HTTP {st}" if st else (res["error"] or "no response"),
                          element=f"<a href={target[:150]}> '{label}'")
        elif res["history"]:
            result = f"redirects to {res['url'][:80]}"
        else:
            result = "OK"
        status_rows.append((target[:250], "external", st, result, res["error"], len(sources), sorted(sources)[0]))

# ------------------------------------------------------------ architecture (whole-site link graph from the crawl)
if site.crawl:
    crawl_graph = defaultdict(set)
    for src, targets in site.crawl["edges"].items():
        crawl_graph[site.path(src)] |= {site.path(t) for t in targets} - {site.path(src)}
    for p, t in graph.items():   # include links seen in this run
        crawl_graph[p] |= t
    full = {site.path(u) for u in urls}
    complete = True
else:
    crawl_graph, full = graph, {site.path(u) for u in pages}
    complete = args.pages == "all" and not args.only and not args.limit
in_scope = {site.path(u) for u in pages}
incoming = defaultdict(set)
for src, targets in crawl_graph.items():
    for t in targets:
        incoming[t].add(src)
if complete:
    for p in sorted(in_scope - {"/"}):
        if not incoming.get(p):
            rec = site.record(site.public(p))
            if rec.get("js_only"):
                audit.add(site.public(p), IMPORTANT, "Architecture", "Page linked only from JavaScript menus / tabs",
                          current="0 links in server HTML; only shown after clicking a menu / tab",
                          expected="at least one plain <a href> link in the server-rendered HTML",
                          detail="found via " + ("sitemap.xml + " if rec.get("in_sitemap") else "") + "JavaScript menu")
                continue
            audit.add(site.public(p), IMPORTANT, "Architecture", "Orphan page", current="0 pages link here",
                      detail="only reachable through sitemap.xml" if rec.get("in_sitemap") else "")

depth = {"/": 0}
queue = deque(["/"])
while queue:
    cur = queue.popleft()
    for t in crawl_graph.get(cur, ()):
        if t not in depth:
            depth[t] = depth[cur] + 1
            queue.append(t)
depth_rows = []
for p in sorted(in_scope):
    d = depth.get(p)
    if d is None:
        if complete and incoming.get(p):
            audit.add(site.public(p), IMPORTANT, "Architecture", "Not reachable from homepage by links",
                      current="no link path from /", detail=f"linked only from: {', '.join(sorted(incoming[p])[:5])}")
    elif d > MAX_DEPTH:
        audit.add(site.public(p), OPTIMIZATION, "Architecture", "Page too deep", current=f"{d} clicks from the homepage",
                  expected=f"{MAX_DEPTH} clicks or fewer")
    depth_rows.append((p, d if d is not None else "unreachable", len(incoming.get(p, ())), len(crawl_graph.get(p, ()))))

home_links = crawl_graph.get("/", set())
for section in MAIN_SECTIONS:
    if section in full and section not in home_links:
        audit.add(site.public("/"), IMPORTANT, "Architecture", "Homepage doesn't link to main section", current=section,
                  expected=f"a link to {section} on the homepage")
hub_rows = []
for hub, prefix in HUBS.items():
    if hub not in crawl_graph:
        continue
    details = {p for p in full if p.startswith(prefix)}
    if not details:
        continue
    linked = {p for p in crawl_graph[hub] if p.startswith(prefix)}
    missing = sorted(details - linked)
    hub_rows.append((hub, len(details), len(linked & details), len(missing), ", ".join(missing[:15])))
    if missing and complete:
        audit.add(site.public(hub), OPTIMIZATION, "Architecture", "Hub page doesn't link to all its detail pages",
                  current=f"{len(missing)} of {len(details)} detail pages not linked",
                  detail="e.g. " + ", ".join(missing[:10]))

audit.note("Internal link targets", len(internal_targets))
audit.note("External link targets", len(external_targets))
audit.note("Max crawl depth", max((d for d in depth.values()), default=0))
audit.sheet("Link status", ["Link", "Type", "HTTP", "Result", "Redirect path / error", "Pages linking", "Example page"],
            sorted(status_rows, key=lambda r: (r[3] == "OK", r[1], r[0])), (60, 9, 6, 32, 50, 12, 55))
audit.sheet("Crawl depth", ["Path", "Clicks from home", "Incoming links", "Outgoing internal links"], depth_rows, (60, 16, 15, 22))
audit.sheet("Hub coverage", ["Hub", "Detail pages", "Linked from hub", "Missing", "Missing examples"], hub_rows, (28, 13, 15, 9, 100))
audit.sheet("Header & footer", ["Zone", "Path", "Anchor"],
            [("header", p, t) for p, t in sorted(nav_links)] + [("footer", p, t) for p, t in sorted(footer_links)], (10, 45, 40))
audit.sheet("All links", ["Page", "Link", "Type", "Anchor text", "rel"], link_rows, (50, 60, 9, 40, 22))
audit.sheet("JavaScript-only links", ["Page", "Link (appears after a click)", "Zone", "Not linked anywhere in HTML"],
            js_rows, (50, 60, 10, 14))
audit.save("Link_Health_Report")
