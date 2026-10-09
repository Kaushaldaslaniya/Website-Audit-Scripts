"""
09 - Technical SEO + HTML health checker
  status:     HTTP status codes, 404 page (real 404, helpful content), 5xx errors, redirects, redirect chains, loops
  https:      HTTPS URLs, HTTP -> HTTPS redirect (public sites)
  canonical:  missing, duplicate (more than one tag), self-referencing, absolute, points to a 200 page
  indexing:   noindex / nofollow (meta robots), X-Robots-Tag header
  urls:       URL structure, duplicate URLs (letter case, trailing slash, parameters), parameter handling,
              trailing-slash consistency, uppercase/lowercase consistency
  html:       <html>/<head>/<body>, charset, viewport, multiple <title>/description, duplicate IDs, empty links,
              empty buttons, deprecated tags, nested links, invalid attributes, broken nesting

  python "py files/09_technical_seo_checker.py" [--base URL]
"""
import re
from collections import Counter
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, describe, fetch, follow_redirects, has_rel, load_site,
                        meta, norm, parse_args, run_parallel, select_pages, text_of)

DEPRECATED = ["center", "font", "marquee", "blink", "frame", "frameset", "big", "strike", "tt", "acronym", "applet"]


def leaked_jsx(soup):
    """React prop names that reached the HTML as attributes (className, htmlFor, onClick="{...}"). Only real
    attributes count: a page that shows code samples ("<span className=...>") has the same words in its text."""
    found = set()
    for el in soup.find_all(True):
        for attr, val in el.attrs.items():
            text = " ".join(val) if isinstance(val, list) else str(val)
            if attr in ("classname", "htmlfor") or (attr in ("onclick", "tabindex") and text.startswith("{")):
                found.add(attr if attr in ("classname", "htmlfor") else f'{attr}="{{...}}"')
    return found

args = parse_args("Technical SEO checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
LOCAL_SERVER = bool(re.match(r"(localhost|127\.|0\.0\.0\.0)", site.base_host))
audit = Audit("09_technical", "Technical SEO Report", "Technical SEO", site)

# ------------------------------------------------------------ site-wide
missing = fetch(f"{site.base}/this-page-should-not-exist-audit-404")
if missing["status"] != 404:
    audit.site(CRITICAL, "Status", "Unknown URLs don't return 404 (soft 404)", current=f"HTTP {missing['status']}",
               expected="HTTP 404", element="/this-page-should-not-exist-audit-404")
else:
    s404 = BeautifulSoup(missing["content"], "lxml")
    if len(s404.find_all("a", href=True)) < 3:
        audit.site(OPTIMIZATION, "Status", "404 page offers few links back into the site",
                   current=f"{len(s404.find_all('a', href=True))} links", expected="3+ links")
    if "noindex" not in (meta(s404, name="robots") or "noindex"):
        audit.site(OPTIMIZATION, "Status", "404 page is not noindex", current=meta(s404, name="robots") or "(no robots meta)")
if site.site_scheme != "https":
    audit.site(CRITICAL, "HTTPS", "Site URLs are not HTTPS", current=f"{site.site_scheme}://{site.site_host}",
               expected=f"https://{site.site_host}")
if site.is_public and site.site_scheme == "https":
    final, hops, loop = follow_redirects(f"http://{site.site_host}/")
    if not hops or len(hops) < 2 or not str(hops[-1][1]).startswith("https://"):
        audit.site(CRITICAL, "HTTPS", "HTTP does not redirect to HTTPS", " -> ".join(f"{s} {u}" for s, u in hops))
    elif hops[0][0] not in (301, 308):
        audit.site(IMPORTANT, "HTTPS", "HTTP -> HTTPS redirect is not permanent", hops[0][0])
    alt_host = site.site_host[4:] if site.site_host.startswith("www.") else "www." + site.site_host
    final, hops, loop = follow_redirects(f"https://{alt_host}/")
    if final == 200 and len(hops) == 1:
        audit.site(IMPORTANT, "URLs", "www and non-www both serve the site (no redirect)", alt_host)


def variants(loc, path):
    """Requests trailing-slash, uppercase and parameter variants of a URL."""
    results = []
    if path != "/":
        # Uppercase variants are only requested on remote servers: on a local macOS build the case-insensitive disk
        # lets Next.js overwrite the real page's cached HTML with the 404 page for /PATH.
        upper = path.upper() if path != path.upper() and not LOCAL_SERVER else None
        for label, variant in (("trailing slash", path + "/"), ("uppercase", upper)):
            if not variant:
                continue
            r = fetch(f"{site.base}{variant}", allow_redirects=False)
            if r["status"] == 200:
                body = BeautifulSoup(r["content"], "lxml")
                c = body.find("link", rel=lambda v: v and has_rel(v, "canonical"))
                canon = urljoin(loc, c["href"]) if c and c.get("href") else ""
                if norm(canon) != norm(loc):
                    sev = IMPORTANT
                    audit.add(loc, sev, "URLs", f"Duplicate URL: {label} variant serves 200 without canonical",
                              current=f"{variant} -> HTTP 200, canonical {canon or '(none)'}",
                              expected=f"301/308 redirect to {site.path(loc)} or canonical {loc}")
                results.append((label, variant, r["status"], canon))
            else:
                results.append((label, variant, r["status"], r["location"]))
    r = fetch(f"{site.base}{path}?utm_source=audit&ref=test", allow_redirects=False)
    if r["status"] == 200:
        body = BeautifulSoup(r["content"], "lxml")
        c = body.find("link", rel=lambda v: v and has_rel(v, "canonical"))
        canon = urljoin(loc, c["href"]) if c and c.get("href") else ""
        if canon and "?" in canon:
            audit.add(loc, IMPORTANT, "URLs", "Canonical keeps URL parameters", current=canon, expected=loc,
                      element=f"{path}?utm_source=audit&ref=test")
        results.append(("parameters", f"{path}?utm_source=audit", r["status"], canon))
    return results


variant_rows = []
host_mismatch = set()


def check(loc):
    audit.checked(loc)
    path = site.path(loc)
    final, hops, loop = follow_redirects(site.to_fetch(loc))
    row = {"url": loc, "status": final, "redirects": len(hops) - 1}
    if loop:
        audit.add(loc, CRITICAL, "Status", "Redirect loop", current=" -> ".join(str(h[1]) for h in hops))
    elif len(hops) > 2:
        audit.add(loc, IMPORTANT, "Status", "Redirect chain", current=" -> ".join(f"{h[0]} {h[1]}" for h in hops),
                  expected=f"one redirect to {hops[-1][1]}")
    elif len(hops) == 2:
        audit.add(loc, IMPORTANT, "Status", "URL redirects", current=f"HTTP {hops[0][0]} -> {hops[-1][1]}",
                  expected=f"link to {hops[-1][1]} directly")
    if isinstance(final, int) and final >= 500:
        audit.add(loc, CRITICAL, "Status", "5xx server error", current=f"HTTP {final}")
        return row
    if final == 0 or (isinstance(final, int) and final >= 400):
        audit.add(loc, CRITICAL, "Status", "Page returns an error status", current=f"HTTP {final}", expected="HTTP 200")
        return row
    if not loc.startswith("https://"):
        row["https"] = "no"
    res = fetch(site.to_fetch(loc))
    raw = res["content"].decode("utf-8", "replace")
    soup = BeautifulSoup(res["content"], "lxml")
    as_written = BeautifulSoup(raw, "html.parser")  # keeps the source nesting (lxml would repair it)
    head = soup.head or soup

    # canonical
    canons = head.find_all("link", rel=lambda v: v and has_rel(v, "canonical"))
    canonical = canons[0].get("href", "").strip() if canons else ""
    row["canonical"] = canonical
    if not canonical:
        audit.add(loc, CRITICAL, "Canonical", "Missing canonical", current="(none)", expected=loc)
    else:
        if len(canons) > 1:
            audit.add(loc, CRITICAL, "Canonical", "Duplicate canonical tags", current=f"{len(canons)} tags: "
                      + " | ".join(c.get("href", "") for c in canons[:4]), expected="1 canonical tag")
        if not canonical.startswith("http"):
            audit.add(loc, IMPORTANT, "Canonical", "Relative canonical URL", current=canonical, expected=loc)
        absolute = urljoin(loc, canonical)
        if norm(absolute) != norm(loc):
            if site.path(absolute) == site.path(loc):
                c_host = urlparse(absolute).netloc or absolute
                s_host = urlparse(loc).netloc or loc
                host_mismatch.add(f"canonical host {c_host} vs sitemap host {s_host}")
            else:
                audit.add(loc, CRITICAL, "Canonical", "Canonical is not self-referencing", current=canonical, expected=loc)
        if site.is_internal(absolute):
            c = fetch(site.to_fetch(absolute), allow_redirects=False)
            if c["status"] != 200:
                audit.add(loc, CRITICAL, "Canonical", "Canonical target is not 200", current=f"{canonical} -> HTTP {c['status']}",
                          expected="canonical URL returns HTTP 200")
    if soup.body and soup.body.find("link", rel=lambda v: v and has_rel(v, "canonical")):
        audit.add(loc, IMPORTANT, "Canonical", "Canonical tag inside <body> (ignored)", current="<link rel=canonical> in <body>")

    # robots
    robots = (meta(head, name="robots") or "").lower()
    googlebot = (meta(head, name="googlebot") or "").lower()
    xrt = res["headers"].get("X-Robots-Tag", "").lower()
    row["robots"] = robots or "(none = index, follow)"
    row["x_robots"] = xrt
    for source, value in (("meta robots", robots), ("meta googlebot", googlebot), ("X-Robots-Tag", xrt)):
        if "noindex" in value:
            audit.add(loc, CRITICAL, "Indexing", f"noindex via {source}", current=value, expected="index")
        if "nofollow" in value:
            audit.add(loc, IMPORTANT, "Indexing", f"nofollow via {source}", current=value, expected="follow")
        if "none" in [v.strip() for v in value.split(",")]:
            audit.add(loc, CRITICAL, "Indexing", f"'none' (noindex, nofollow) via {source}", current=value,
                      expected="index, follow")

    # URL structure
    if path != path.lower():
        audit.add(loc, IMPORTANT, "URLs", "Uppercase letters in URL", current=path, expected=path.lower())
    if "_" in path or " " in path:
        audit.add(loc, OPTIMIZATION, "URLs", "Underscores/spaces in URL (use hyphens)", current=path,
                  expected=re.sub(r"[_ ]+", "-", path))
    in_sitemap = site.record(loc).get("in_sitemap", True)
    if "?" in loc and in_sitemap:
        audit.add(loc, OPTIMIZATION, "URLs", "Sitemap URL has parameters", current=loc, expected=loc.split("?")[0])
    if loc.endswith("/") and path != "/" and in_sitemap:
        audit.add(loc, OPTIMIZATION, "URLs", "Trailing slash in sitemap URL (inconsistent with others)", current=loc,
                  expected=loc.rstrip("/"))
    for v in variants(loc, path):
        variant_rows.append((loc, *v))

    # HTML health
    low = raw[:5000].lower()
    if "<!doctype html" not in low:
        audit.add(loc, IMPORTANT, "HTML", "Missing <!DOCTYPE html>", current="(none)")
    for tag in ("html", "head", "body"):
        if not re.search(fr"<{tag}[\s>]", raw, re.I):
            audit.add(loc, IMPORTANT, "HTML", f"Missing <{tag}>", current="(none)")
    if not head.find("meta", charset=True) and not head.find("meta", attrs={"http-equiv": re.compile("content-type", re.I)}):
        audit.add(loc, IMPORTANT, "HTML", "Missing <meta charset>", current="(none)")
    if not meta(head, name="viewport"):
        audit.add(loc, IMPORTANT, "HTML", "Missing viewport meta", current="(none)")
    if len(soup.find_all("title")) > 1:
        audit.add(loc, IMPORTANT, "HTML", "Multiple <title> tags", current=f"{len(soup.find_all('title'))} <title> tags",
                  expected="1")
    if len(soup.find_all("meta", attrs={"name": "description"})) > 1:
        audit.add(loc, IMPORTANT, "HTML", "Multiple meta descriptions",
                  current=f"{len(soup.find_all('meta', attrs={'name': 'description'}))} tags", expected="1")
    ids = Counter(t["id"] for t in soup.find_all(id=True))
    for dup_id, n in ids.items():
        if n > 1:
            audit.add(loc, IMPORTANT, "HTML", "Duplicate IDs", current=f'id="{dup_id}" used {n} times', expected="unique id",
                      element=", ".join(describe(t, 60) for t in soup.find_all(id=dup_id)[:3]))
    for a in soup.find_all("a", href=True):   # <a name="top"> without href is a jump target, not a link
        if not text_of(a) and not a.get("aria-label") and not a.find("img", alt=True) and not a.get("title"):
            audit.add(loc, IMPORTANT, "HTML", "Empty links (no text / name)", current="(no text or accessible name)",
                      element=describe(a))
    for b in soup.find_all("button"):
        if not text_of(b) and not b.get("aria-label") and not b.get("title") and not b.get("aria-labelledby"):
            audit.add(loc, IMPORTANT, "HTML", "Empty buttons (no text / name)", current="(no text or accessible name)",
                      element=describe(b))
    for tag in DEPRECATED:
        found = soup.find_all(tag)
        if found:
            audit.add(loc, OPTIMIZATION, "HTML", f"Deprecated <{tag}> tag", current=f"{len(found)} <{tag}>",
                      element=describe(found[0]))
    for a in as_written.find_all("a"):
        inner = a.find("a")
        if inner:
            audit.add(loc, IMPORTANT, "HTML", "Link nested inside a link (invalid)", current="<a> inside <a>",
                      element=f"outer {describe(a, 80)} / inner {describe(inner, 80)}")
    for b in as_written.find_all("button"):
        inner = b.find(["a", "button"])
        if inner:
            audit.add(loc, IMPORTANT, "HTML", "Interactive element nested inside <button> (invalid)",
                      current=f"<{inner.name}> inside <button>", element=describe(b))
    for p in as_written.find_all("p"):
        inner = p.find(["div", "section", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "table"])
        if inner:
            audit.add(loc, OPTIMIZATION, "HTML", "Block element inside <p> (browser rewrites the DOM)",
                      current=f"<{inner.name}> inside <p>", element=describe(p))
    for m in sorted(leaked_jsx(soup)):
        audit.add(loc, IMPORTANT, "HTML", "Invalid attribute in HTML (JSX attribute leaked)", current=m)
    if soup.body and soup.body.find("title"):
        audit.add(loc, IMPORTANT, "HTML", "<title> inside <body>", current=text_of(soup.body.find("title"))[:100])
    row["bytes"] = len(res["content"])
    return row


print(f"Checking {len(pages)} pages ...")
rows = [r for r in run_parallel(check, pages, args.workers) if r]
for m in sorted(host_mismatch):
    audit.site(IMPORTANT, "Canonical", "Canonical URLs use a different host than the sitemap", current=m,
               detail="sitemap.xml and canonical tags must both use NEXT_PUBLIC_SITE_URL")
audit.sheet("Pages", ["URL", "Final HTTP", "Redirects", "Canonical", "Robots meta", "X-Robots-Tag", "HTML bytes"],
            [(r["url"], r["status"], r["redirects"], r.get("canonical", ""), r.get("robots", ""), r.get("x_robots", ""),
              r.get("bytes", "")) for r in rows], (55, 9, 9, 55, 25, 16, 10))
audit.sheet("URL variants", ["Page", "Variant", "Requested", "HTTP", "Canonical / redirect target"], variant_rows,
            (50, 14, 50, 6, 60))
audit.save("Technical_SEO_Report")
