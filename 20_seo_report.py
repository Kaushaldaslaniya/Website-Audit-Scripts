"""
20 - SEO report (all-in-one)
  A single workbook covering the most important SEO points of 01-09 for every discovered page:

  Critical      missing title / meta description / H1, noindex on an indexable page,
                missing or wrong canonical, duplicate titles / descriptions, broken pages,
                missing or invalid sitemap, robots.txt blocking the site
  Important     title / description length, multiple H1s, Open Graph + Twitter tags,
                broken or wrong-size OG image, image alt text, broken internal links,
                missing structured data for the page type, missing lang / viewport
  Optimization  title/H1/description topic relevance, heading hierarchy, image width/height
                and file size, internal linking, orphan pages, breadcrumbs, hreflang,
                response time / HTML size, thin or duplicate content, SEO-friendly slugs,
                meta keywords (obsolete: reported when present, not when missing)

  python "py files/20_seo_report.py" [--base URL] [--external] [--hreflang] [--psi-key KEY]

  --external   also check third-party links (slower; 401/403/429 answers are "unverified").
  --hreflang   also request every hreflang alternate URL.
  --psi-key    Google PageSpeed Insights API key: adds mobile performance for --psi-limit pages (public sites only).
"""
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, load_site, meta, norm, parse_args,
                        run_parallel, select_pages, text_of)

try:
    from PIL import Image  # optional: OG image dimensions
except ImportError:
    Image = None

TITLE_MIN, TITLE_MAX = 30, 60          # 50-60 ideal
DESC_MIN, DESC_MAX = 70, 160           # 150-160 ideal
H1_MIN_CHARS = 10
OG_SIZE = (1200, 630)
IMAGE_MAX_BYTES = 500 * 1024
THIN_CONTENT_WORDS = 300
SLOW_RESPONSE_MS = 1500
HEAVY_HTML_BYTES = 500 * 1024
MIN_INTERNAL_LINKS = 3
LANGUAGES = ["en", "it", "de", "fr", "es"]
GENERIC_ALTS = {"image", "img", "photo", "picture", "pic", "logo", "banner", "icon", "graphic", "thumbnail", "untitled"}
GENERIC_ANCHORS = {"click here", "here", "read more", "more", "learn more", "link", "this", "view", "details", "go"}
STOPWORDS = set("a an and are as at be by for from how in into is it of on or our the to we with your you & | - – —".split())

SCHEMA_RULES = [  # expected JSON-LD @type per page type (any one of the set satisfies the check)
    (r"^/$", {"Organization", "WebSite"}, "Home"),
    (r"^/about-us$", {"Organization", "AboutPage"}, "About"),
    (r"^/contact-us$", {"ContactPage"}, "Contact"),
    (r"^/blog$", {"CollectionPage", "Blog"}, "Blog listing"),
    (r"^/blog/[^/]+$", {"Article", "BlogPosting", "NewsArticle", "TechArticle"}, "Blog article"),
    (r"^/portfolio/[^/]+$", {"CreativeWork", "SoftwareApplication", "WebSite", "WebApplication", "MobileApplication"},
     "Portfolio project"),
    (r"^/portfolio$", {"CollectionPage"}, "Portfolio listing"),
    (r"^/(software-services|digital-services|intelligent-data-services)/[^/]+$", {"Service"}, "Service"),
    (r"^/(services|software-services|digital-services|intelligent-data-services)$", {"Service", "CollectionPage", "ItemList"},
     "Service hub"),
    (r"^/technologies/[^/]+$", {"Service"}, "Technology service"),
    (r"^/industries/[^/]+$", {"Service", "WebPage"}, "Industry"),
    (r"^/careers$", {"JobPosting", "CollectionPage", "WebPage"}, "Careers"),
    (r"^/reviews$", {"Review", "AggregateRating", "Organization", "WebPage"}, "Reviews"),
]

args = parse_args("SEO report (all-in-one)", lambda ap: (
    ap.add_argument("--external", action="store_true", help="check third-party links too"),
    ap.add_argument("--hreflang", action="store_true", help="request every hreflang alternate URL"),
    ap.add_argument("--psi-key", default="", help="PageSpeed Insights API key (public sites only)"),
    ap.add_argument("--psi-limit", type=int, default=10)))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("20_seo_report", "SEO Report (all-in-one)", "On-Page SEO", site)
site_rows, page_rows, image_rows, link_rows = [], [], [], []
canonical_hosts = set()


def glob_check(check, severity, ok, detail="", **kw):
    """A site-wide pass/fail check: listed on the Site-wide sheet, an issue when it fails."""
    site_rows.append((check, severity, "OK" if ok else "FAIL", detail))
    if not ok:
        audit.site(severity, "Site-wide", check, detail, **kw)


def topic(text, brand):
    words = re.findall(r"[a-z0-9.+#]+", (text or "").lower())
    brand_words = set(re.findall(r"[a-z0-9]+", brand.lower()))
    return {w for w in words if len(w) > 2 and w not in STOPWORDS and w not in brand_words}


def image_size(content):
    if not Image or not content:
        return None
    try:
        with Image.open(io.BytesIO(content)) as im:
            return im.size
    except Exception:
        return None


# ------------------------------------------------------------------ site-wide
if not site.sitemap_urls:
    glob_check("sitemap.xml reachable and valid", CRITICAL, False, site.sitemap_error or "no URLs")
else:
    glob_check("sitemap.xml reachable and valid", CRITICAL, True, f"{len(site.sitemap_urls)} URLs")
    hosts = Counter(urlparse(u).netloc for u in site.sitemap_urls)
    glob_check("Sitemap URLs use one host", IMPORTANT, len(hosts) == 1, ", ".join(f"{h} ({n})" for h, n in hosts.items()))
    glob_check("Sitemap URLs use HTTPS", CRITICAL, all(u.startswith("https://") for u in site.sitemap_urls),
               f"{site.site_scheme}://{site.site_host}")
    glob_check("Sitemap / canonical host is the public domain", CRITICAL, site.is_public, site.site_host,
               expected="the live https domain (NEXT_PUBLIC_SITE_URL)")
    dupes = [u for u, n in Counter(site.sitemap_urls).items() if n > 1]
    glob_check("No duplicate sitemap URLs", IMPORTANT, not dupes, ", ".join(dupes[:10]))
    lastmods = sum(1 for l in site.sitemap_root.iter() if l.tag.endswith("lastmod")) if site.sitemap_root is not None else 0
    glob_check("Sitemap entries have <lastmod>", OPTIMIZATION, lastmods >= len(site.sitemap_urls),
               f"{lastmods}/{len(site.sitemap_urls)}")

robots = fetch(f"{site.base}/robots.txt")
if robots["status"] != 200:
    glob_check("robots.txt reachable", CRITICAL, False, f"HTTP {robots['status']}")
else:
    body = robots["content"].decode("utf-8", "replace")
    glob_check("robots.txt reachable", CRITICAL, True)
    blocks_all, agent = False, None
    for line in body.splitlines():
        line = line.split("#")[0].strip()
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
        elif line.lower().startswith("disallow:") and agent == "*" and line.split(":", 1)[1].strip() == "/":
            blocks_all = True
    glob_check("robots.txt does not block the whole site", CRITICAL, not blocks_all,
               "User-agent: * / Disallow: /" if blocks_all else "")
    sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", body)
    glob_check("robots.txt declares the sitemap", IMPORTANT, bool(sitemaps), ", ".join(sitemaps) or "no Sitemap: line")
    for sm in sitemaps:
        glob_check("robots.txt sitemap uses the canonical host", IMPORTANT, urlparse(sm).netloc == site.site_host,
                   sm, expected=f"a sitemap URL on {site.site_host}")

home_res, home_soup = site.page(site.public("/"))
brand = (meta(home_soup, prop="og:site_name") or "") if home_soup else ""
icon = home_soup.find("link", rel=lambda r: r and "icon" in " ".join(r).lower()) if home_soup else None
fav = fetch(f"{site.base}/favicon.ico", "HEAD")
glob_check("Favicon", OPTIMIZATION, bool(icon) or fav["status"] == 200,
           icon.get("href") if icon else f"/favicon.ico HTTP {fav['status']}")
manifest = home_soup.find("link", rel=lambda r: r and "manifest" in r) if home_soup else None
found, detail = manifest is not None, manifest.get("href") if manifest else ""
if not found:
    for p in ("/manifest.webmanifest", "/manifest.json", "/site.webmanifest"):
        if fetch(f"{site.base}{p}", "HEAD")["status"] == 200:
            found, detail = True, p + " (not linked from <head>)"
            break
glob_check("Web app manifest", OPTIMIZATION, found, detail or "no <link rel=manifest>")
missing = fetch(f"{site.base}/this-page-does-not-exist-seo-audit")
glob_check("Unknown URLs return HTTP 404 (no soft 404)", IMPORTANT, missing["status"] == 404, f"HTTP {missing['status']}",
           expected="HTTP 404")
if site.is_public and site.site_scheme == "https":
    plain = fetch(f"http://{site.site_host}/", allow_redirects=False)
    glob_check("HTTP redirects to HTTPS", CRITICAL, plain["location"].startswith("https://"),
               f"HTTP {plain['status']} -> {plain['location']}")


# ------------------------------------------------------------------ per page
def expected_schema(path):
    for pattern, types, label in SCHEMA_RULES:
        if re.match(pattern, path):
            return types, label
    return None, None


def collect_types(node, out):
    if isinstance(node, list):
        for n in node:
            collect_types(n, out)
    elif isinstance(node, dict):
        t = node.get("@type")
        out.update(t if isinstance(t, list) else [t] if t else [])
        for v in node.values():
            if isinstance(v, (dict, list)):
                collect_types(v, out)


def check_slug(url, path):
    problems = []
    if path != path.lower():
        problems.append("uppercase letters")
    if "_" in path:
        problems.append("underscores (use hyphens)")
    if re.search(r"%[0-9A-Fa-f]{2}|\s", path):
        problems.append("encoded / space characters")
    if len(path) > 75:
        problems.append(f"long path ({len(path)} chars)")
    if path.count("/") > 4:
        problems.append(f"deep path ({path.count('/')} levels)")
    if re.search(r"\.(html?|php|aspx?)$", path):
        problems.append("file extension")
    if re.search(r"--|-$", path):
        problems.append("double / trailing hyphen")
    if urlparse(url).query:
        problems.append("query string")
    for p in problems:
        audit.add(url, OPTIMIZATION, "URL", "SEO-friendly slug", current=f"{p}: {path}")


def check_og_image(url, og):
    image_url = og["image"]
    if not image_url.startswith("http"):
        audit.add(url, IMPORTANT, "Open Graph", "og:image is not an absolute URL", current=image_url,
                  expected=urljoin(site.public("/"), image_url))
        image_url = urljoin(site.public("/"), image_url)
    res = fetch(site.to_fetch(image_url) if site.is_internal(image_url) else image_url)
    ctype = res["headers"].get("Content-Type", "")
    if res["status"] != 200 or not ctype.startswith("image/"):
        audit.add(url, IMPORTANT, "Open Graph", "Broken og:image", current=f"HTTP {res['status']} {ctype}".strip(),
                  element=og["image"])
        return
    size = image_size(res["content"])
    if size:
        w, h = size
        if w < 600 or abs(w / h - OG_SIZE[0] / OG_SIZE[1]) > 0.15:
            audit.add(url, IMPORTANT, "Open Graph", "og:image size", current=f"{w}x{h} px",
                      expected=f"{OG_SIZE[0]}x{OG_SIZE[1]} px", element=og["image"])
    if not (og["image:width"] and og["image:height"]):
        audit.add(url, OPTIMIZATION, "Open Graph", "Missing og:image:width / og:image:height", current="(missing)",
                  expected=f"{size[0]} / {size[1]} (real size)" if size else "the real pixel size")


def audit_page(loc):
    audit.checked(loc)
    path, url = site.path(loc), loc
    res = fetch(site.to_fetch(loc))
    page = {"url": loc, "path": path, "status": res["status"], "ms": res["ms"], "bytes": len(res["content"])}
    if res["status"] != 200:
        audit.add(url, CRITICAL, "Status", "Broken page", current=f"HTTP {res['status']} {res['error']}".strip())
        return page, [], []
    if res["history"]:
        audit.add(url, IMPORTANT, "Status", "URL redirects", current=f"ends at {res['url']}",
                  expected="link / list the final URL")

    soup = BeautifulSoup(res["content"], "lxml")
    head = soup.head or soup
    check_slug(url, path)

    titles = head.find_all("title")
    title = text_of(titles[0]) if titles else ""
    page["title"] = title
    if not title:
        audit.add(url, CRITICAL, "Title", "Missing title", current="(none)")
    else:
        if not TITLE_MIN <= len(title) <= TITLE_MAX:
            audit.add(url, IMPORTANT, "Title", "Title length", current=f"{len(title)} chars: {title}",
                      expected=f"{TITLE_MIN}-{TITLE_MAX} characters (ideal 50-60)")
        if len(titles) > 1:
            audit.add(url, IMPORTANT, "Title", "Multiple <title> tags", current=f"{len(titles)} tags", expected="1")

    desc = meta(head, name="description")
    page["description"] = desc or ""
    if not desc:
        audit.add(url, CRITICAL, "Description", "Missing meta description", current="(none)")
    elif not DESC_MIN <= len(desc) <= DESC_MAX:
        audit.add(url, IMPORTANT, "Description", "Description length", current=f"{len(desc)} chars: {desc}",
                  expected=f"{DESC_MIN}-{DESC_MAX} characters (ideal 150-160)")

    kw = meta(head, name="keywords")
    page["keywords"] = "present (remove)" if kw else "absent (good)"
    if kw:
        audit.add(url, OPTIMIZATION, "Meta keywords", "Meta keywords present", current=kw[:200])

    canon_tags = head.find_all("link", rel=lambda r: r and "canonical" in r)
    canonical = canon_tags[0].get("href", "").strip() if canon_tags else ""
    page["canonical"] = canonical
    if not canonical:
        audit.add(url, CRITICAL, "Canonical", "Missing canonical", current="(none)", expected=loc)
    else:
        if not canonical.startswith("http"):
            audit.add(url, CRITICAL, "Canonical", "Canonical is not absolute", current=canonical, expected=loc)
        elif norm(canonical) != norm(loc):
            if site.path(canonical) == site.path(loc):   # same page, other host: one site-wide finding
                canonical_hosts.add(f"canonical host {urlparse(canonical).netloc} vs sitemap host {urlparse(loc).netloc}")
            else:
                audit.add(url, CRITICAL, "Canonical", "Canonical points to another URL", current=canonical, expected=loc)
        if len(canon_tags) > 1:
            audit.add(url, CRITICAL, "Canonical", "Multiple canonical tags", current=f"{len(canon_tags)} tags", expected="1")
        if canonical.startswith("http") and site.is_internal(canonical):
            target = fetch(site.to_fetch(canonical), allow_redirects=False)
            if target["status"] != 200:
                audit.add(url, CRITICAL, "Canonical", "Broken canonical", current=f"{canonical} -> HTTP {target['status']}")

    robots_meta = (meta(head, name="robots") or "").lower()
    x_robots = res["headers"].get("X-Robots-Tag", "").lower()
    page["robots"] = robots_meta or "(default: index, follow)"
    in_sitemap = site.record(loc).get("in_sitemap", True)
    if "noindex" in robots_meta or "noindex" in x_robots:
        audit.add(url, CRITICAL if in_sitemap else IMPORTANT, "Robots",
                  "noindex on a sitemap page" if in_sitemap else "noindex via meta robots",
                  current=robots_meta or f"X-Robots-Tag: {x_robots}", expected="index")
    if "nofollow" in robots_meta:
        audit.add(url, IMPORTANT, "Robots", "nofollow on page", current=robots_meta, expected="follow")

    html = soup.find("html")
    page["lang"] = html.get("lang", "") if html else ""
    if not page["lang"]:
        audit.add(url, IMPORTANT, "Language", "Missing <html lang>", current="(none)")
    viewport = meta(head, name="viewport")
    if not viewport or "width=device-width" not in viewport:
        audit.add(url, IMPORTANT, "Mobile", "Missing responsive viewport meta", current=viewport or "(none)")

    alternates = {l.get("hreflang"): l.get("href") for l in head.find_all("link", rel=lambda r: r and "alternate" in r)
                  if l.get("hreflang")}
    page["hreflang"] = ", ".join(sorted(alternates))
    page["hreflang_urls"] = [h for h in alternates.values() if h]
    for lang in [l for l in LANGUAGES if l not in alternates] + ([] if "x-default" in alternates else ["x-default"]):
        audit.add(url, OPTIMIZATION, "hreflang", "hreflang alternates missing", current=f"no '{lang}'",
                  expected=f'<link rel="alternate" hreflang="{lang}" href="...">')

    headings = [(int(h.name[1]), text_of(h)) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    h1s = [t for lvl, t in headings if lvl == 1]
    page["h1"] = h1s[0] if h1s else ""
    page["h1_count"] = len(h1s)
    if not h1s:
        audit.add(url, CRITICAL, "Headings", "Missing H1", current="0 H1 tags", expected="1 H1")
    elif len(h1s) > 1:
        for t in h1s[1:]:
            audit.add(url, IMPORTANT, "Headings", "Multiple H1", current=f"{len(h1s)} H1 tags", expected="1 H1",
                      element=f"<h1> {t[:80]}")
    if h1s and len(h1s[0]) < H1_MIN_CHARS:
        audit.add(url, IMPORTANT, "Headings", "H1 not meaningful", current=f"'{h1s[0]}' ({len(h1s[0])} chars)",
                  expected=f"{H1_MIN_CHARS}+ characters")
    if headings and headings[0][0] != 1:
        audit.add(url, OPTIMIZATION, "Headings", "First heading is not H1", current=f"H{headings[0][0]}", expected="H1",
                  element=f"<h{headings[0][0]}> {headings[0][1][:60]}")
    prev = 0
    for lvl, t in headings:
        if prev and lvl > prev + 1:
            audit.add(url, OPTIMIZATION, "Headings", "Skipped heading level", current=f"H{prev} -> H{lvl}",
                      expected=f"H{prev} -> H{prev + 1}", element=f"<h{lvl}> {t[:60]}")
        prev = lvl
    for lvl, t in headings:
        if not t:
            audit.add(url, IMPORTANT, "Headings", "Empty headings", current=f"empty <h{lvl}>")

    if title and h1s:
        t_words = topic(title, brand)
        if t_words and not t_words & topic(h1s[0], brand):
            audit.add(url, OPTIMIZATION, "Relevance", "Title and H1 share no topic words", current=f"H1: {h1s[0]}",
                      expected=f"H1 shares a topic word with the title ({title})")
        if desc and t_words and not t_words & topic(desc, brand):
            audit.add(url, OPTIMIZATION, "Relevance", "Description doesn't mention the title topic", current=desc,
                      expected=f"mentions one of: {', '.join(sorted(t_words)[:8])}")

    og = {k: meta(head, prop=f"og:{k}") for k in ("title", "description", "image", "image:width", "image:height", "url",
                                                  "type", "site_name")}
    page["og_image"] = og["image"] or ""
    for key, sev in (("title", IMPORTANT), ("description", IMPORTANT), ("image", IMPORTANT), ("url", IMPORTANT),
                     ("type", OPTIMIZATION), ("site_name", OPTIMIZATION)):
        if not og[key]:
            audit.add(url, sev, "Open Graph", f"Missing og:{key}", current="(missing)")
    if og["url"] and canonical and norm(og["url"]) != norm(canonical):
        audit.add(url, IMPORTANT, "Open Graph", "og:url differs from canonical", current=og["url"], expected=canonical)
    if og["image"]:
        check_og_image(url, og)

    tw = {k: meta(head, name=f"twitter:{k}") for k in ("card", "title", "description", "image")}
    page["twitter_card"] = tw["card"] or ""
    if not tw["card"]:
        audit.add(url, IMPORTANT, "Twitter/X", "Missing twitter:card", current="(missing)", expected="summary_large_image")
    elif tw["card"] != "summary_large_image":
        audit.add(url, OPTIMIZATION, "Twitter/X", "twitter:card is not summary_large_image", current=tw["card"])
    for key in ("title", "description", "image"):
        if not tw[key]:
            audit.add(url, OPTIMIZATION, "Twitter/X", f"Missing twitter:{key}", current="(missing)")

    types, invalid = set(), 0
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            collect_types(json.loads(s.string or s.get_text() or ""), types)
        except (json.JSONDecodeError, TypeError):
            invalid += 1
    page["schema"] = ", ".join(sorted(types))
    if invalid:
        audit.add(url, IMPORTANT, "Structured data", "Invalid JSON-LD", current=f"{invalid} block(s) fail to parse")
    expected, label = expected_schema(path)
    if expected and not types & expected:
        audit.add(url, IMPORTANT, "Structured data", f"Missing {label} schema",
                  current=f"types found: {', '.join(sorted(types)) or 'none'}", expected=f"one of: {', '.join(sorted(expected))}")
    elif not types:
        audit.add(url, OPTIMIZATION, "Structured data", "No JSON-LD on page", current="0 JSON-LD blocks")
    has_breadcrumb_ui = soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)}) is not None
    if (has_breadcrumb_ui or path.count("/") >= 2) and "BreadcrumbList" not in types:
        audit.add(url, OPTIMIZATION, "Structured data", "Missing BreadcrumbList schema",
                  current="page shows breadcrumbs" if has_breadcrumb_ui else "nested page without BreadcrumbList")
    if any(re.search(r"\bFAQ|frequently asked", t, re.I) for _, t in headings) and "FAQPage" not in types:
        audit.add(url, OPTIMIZATION, "Structured data", "FAQ section without FAQPage schema", current="no FAQPage")

    page_images = []
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        alt = img.get("alt")
        decorative = img.get("aria-hidden") == "true" or img.get("role") in ("presentation", "none")
        row = {"page": url, "src": src, "alt": alt if alt is not None else "(missing)", "issue": []}
        if alt is None:
            row["issue"].append((IMPORTANT, "Missing alt", "(no alt attribute)"))
        elif not alt.strip() and not decorative:
            row["issue"].append((OPTIMIZATION, "Empty alt (only OK for decorative images)", 'alt=""'))
        elif alt.strip():
            a = alt.strip().lower()
            if len(a) < 5:
                row["issue"].append((OPTIMIZATION, "Very short alt", f'alt="{alt}"'))
            if a in GENERIC_ALTS or re.fullmatch(r"(img|image|photo|dsc|screenshot)[-_ ]?\d*(\.\w+)?", a):
                row["issue"].append((OPTIMIZATION, "Generic alt text", f'alt="{alt}"'))
            words = re.findall(r"[a-z0-9.]+", a)
            if len(words) >= 4 and max(Counter(words).values()) >= 3:
                row["issue"].append((OPTIMIZATION, "Keyword-stuffed alt", f'alt="{alt}"'))
        if img.get("data-nimg") != "fill" and not (img.get("width") and img.get("height")):
            row["issue"].append((OPTIMIZATION, "Missing width/height (layout shift)",
                                 f"width={img.get('width')!r} height={img.get('height')!r}"))
        page_images.append(row)
    page["images"] = len(page_images)
    page["images_no_alt"] = sum(1 for r in page_images if any(m == "Missing alt" for _, m, _ in r["issue"]))

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "sms:")):
            continue
        absolute = urljoin(site.to_fetch(loc), href).split("#")[0]
        label_ = text_of(a) or (a.get("aria-label") or "").strip() or (a.get("title") or "").strip()
        if not label_:
            img = a.find("img", alt=True)
            label_ = img["alt"].strip() if img else ""
        links.append((absolute, label_, site.is_internal(absolute)))
        if not label_:
            audit.add(url, IMPORTANT, "Links", "Link without accessible text", current="(no text)", element=href[:200])
        elif label_.lower().strip(" .→›»") in GENERIC_ANCHORS:
            audit.add(url, OPTIMIZATION, "Links", "Non-descriptive anchor text", current=f"'{label_}'", element=href[:200])
    internal_targets = {site.path(l) for l, _, internal in links if internal} - {path}
    page["internal_links"] = len(internal_targets)
    page["external_links"] = len({l for l, _, internal in links if not internal})
    if len(internal_targets) < MIN_INTERNAL_LINKS:
        audit.add(url, OPTIMIZATION, "Links", "Few internal links", current=f"{len(internal_targets)} unique internal links",
                  expected=f"{MIN_INTERNAL_LINKS}+")

    main = soup.find("main") or soup.body or soup
    for t in main.find_all(["script", "style", "noscript", "svg"]):
        t.decompose()
    body_text = text_of(main)
    page["words"] = len(body_text.split())
    if page["words"] < THIN_CONTENT_WORDS:
        audit.add(url, OPTIMIZATION, "Content", "Thin content", current=f"{page['words']} words in <main>",
                  expected=f"{THIN_CONTENT_WORDS}+ words")
    page["content_hash"] = hashlib.md5(body_text.lower().encode()).hexdigest() if body_text else ""
    if res["ms"] > SLOW_RESPONSE_MS:
        audit.add(url, OPTIMIZATION, "Performance", "Slow server response", current=f"{res['ms']} ms",
                  expected=f"< {SLOW_RESPONSE_MS} ms")
    if page["bytes"] > HEAVY_HTML_BYTES:
        audit.add(url, OPTIMIZATION, "Performance", "Heavy HTML document", current=f"{page['bytes'] // 1024} KB",
                  expected=f"< {HEAVY_HTML_BYTES // 1024} KB")
    return page, page_images, links


print(f"Auditing {len(pages)} pages ...")
results = run_parallel(audit_page, pages, args.workers)
page_data = [p for p, _, _ in results]
all_images = [img for _, imgs, _ in results for img in imgs]
all_links = {p["url"]: links for p, _, links in results}

for m in sorted(canonical_hosts):
    glob_check("Canonical host matches the sitemap host", IMPORTANT, False, m,
               expected="sitemap.xml and canonical tags both built from NEXT_PUBLIC_SITE_URL")

# ------------------------------------------------------------------ cross-page checks
print("Checking duplicates, links, images ...")
for field, check in (("title", "Duplicate title"), ("description", "Duplicate description")):
    groups = defaultdict(list)
    for p in page_data:
        if p.get(field):
            groups[p[field].strip().lower()].append(p["url"])
    for value, group in groups.items():
        if len(group) > 1:
            for u in group:
                audit.add(u, CRITICAL, field.capitalize(), check,
                          current=next(p[field] for p in page_data if p["url"] == u)[:160],
                          detail=f"shared by {len(group)} pages: " + ", ".join(g for g in group[:5] if g != u))
groups = defaultdict(list)
for p in page_data:
    if p.get("content_hash"):
        groups[p["content_hash"]].append(p["url"])
for group in groups.values():
    if len(group) > 1:
        for u in group:
            audit.add(u, OPTIMIZATION, "Content", "Duplicate page content", current=f"identical <main> text on {len(group)} pages",
                      element=", ".join(g for g in group[:5] if g != u))

internal, external = defaultdict(dict), defaultdict(dict)
for page, links in all_links.items():
    for href, label_, is_internal in links:
        (internal if is_internal else external)[href].setdefault(page, label_)
for href, res in run_parallel(lambda h: (h, fetch(site.to_fetch(h), allow_redirects=False)), list(internal), args.workers,
                              "internal links"):
    sources, status = internal[href], res["status"]
    if status >= 400 or status == 0:
        for p, label_ in sources.items():
            audit.add(p, IMPORTANT, "Links", "Broken internal link", current=f"{site.path(href)} -> HTTP {status}",
                      element=f"<a href={site.path(href)}> '{label_[:60]}'")
        link_rows.append((site.path(href), "internal", status, "BROKEN", len(sources), sorted(sources)[0]))
    elif status in (301, 302, 303, 307, 308):
        for p, label_ in sources.items():
            audit.add(p, OPTIMIZATION, "Links", "Internal link redirects", current=f"{site.path(href)} -> {res['location']}",
                      expected=f"link to {res['location']}", element=f"<a href={site.path(href)}> '{label_[:60]}'")
        link_rows.append((site.path(href), "internal", status, f"redirects to {res['location']}", len(sources),
                          sorted(sources)[0]))
if args.external:
    for href, res in run_parallel(lambda h: (h, fetch(h, "HEAD", timeout=20)), list(external), args.workers,
                                  "external links"):
        sources, status = external[href], res["status"]
        if status in (401, 403, 429, 999):
            link_rows.append((href, "external", status, "unverified (site blocks bots)", len(sources), sorted(sources)[0]))
        elif status >= 400 or status == 0:
            for p, label_ in sources.items():
                audit.add(p, IMPORTANT, "Links", "Broken external link", current=f"HTTP {status}" if status else res["error"],
                          element=f"<a href={href[:150]}> '{label_[:60]}'")
            link_rows.append((href, "external", status, "BROKEN", len(sources), sorted(sources)[0]))

if not args.only and not args.limit and args.pages == "all":
    linked = defaultdict(set)
    for href, sources in internal.items():
        for p in sources:
            if site.path(p) != site.path(href):
                linked[site.path(href)].add(p)
    if site.crawl:   # pages not audited in this run still link to others
        for src, targets in site.crawl["edges"].items():
            for t in targets:
                if site.path(t) != site.path(src):
                    linked[site.path(t)].add(src)
    for loc in pages:
        if site.path(loc) != "/" and not linked.get(site.path(loc)):
            audit.add(loc, OPTIMIZATION, "Links", "Orphan page", current="0 pages link here")

unique = defaultdict(list)
for row in all_images:
    unique[urljoin(site.to_fetch(row["page"]), row["src"])].append(row)
for src, res in run_parallel(lambda s: (s, fetch(site.to_fetch(s) if site.is_internal(s) else s)), list(unique),
                             args.workers, "images"):
    for row in unique[src]:
        if res["status"] != 200:
            row["issue"].append((IMPORTANT, "Broken image", f"HTTP {res['status']}"))
        elif len(res["content"]) > IMAGE_MAX_BYTES:
            row["issue"].append((OPTIMIZATION, "Oversized image file", f"{len(res['content']) // 1024} KB"))
        row["bytes"] = len(res["content"])
order = {CRITICAL: 0, IMPORTANT: 1, OPTIMIZATION: 2}
for row in all_images:
    for sev, msg, current in row["issue"]:
        audit.add(row["page"], sev, "Images", msg, current=current, element=row["src"][:200])
    if row["issue"]:
        worst = min(order[s] for s, _, _ in row["issue"])
        image_rows.append((row["page"], row["src"][:200], row["alt"], row.get("bytes", ""), [CRITICAL, IMPORTANT, OPTIMIZATION][worst],
                           "; ".join(m for _, m, _ in row["issue"])))

if args.hreflang:
    targets = defaultdict(set)
    for p in page_data:
        for href in p.get("hreflang_urls", []):
            targets[href].add(p["url"])
    for href, res in run_parallel(lambda h: (h, fetch(site.to_fetch(h), "HEAD")), list(targets), args.workers, "hreflang"):
        if res["status"] != 200:
            for p in targets[href]:
                audit.add(p, IMPORTANT, "hreflang", "Broken hreflang alternate", current=f"HTTP {res['status']}", element=href)

if args.psi_key:
    print(f"Running PageSpeed Insights for {args.psi_limit} pages ...")
    for p in page_data[: args.psi_limit]:
        try:
            data = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                                params={"url": p["url"], "strategy": "mobile", "key": args.psi_key}, timeout=120).json()
            lh = data["lighthouseResult"]
            score = round(lh["categories"]["performance"]["score"] * 100)
            a = lh["audits"]
            p["psi"] = (f"perf {score} | LCP {a['largest-contentful-paint']['displayValue']} | "
                        f"CLS {a['cumulative-layout-shift']['displayValue']}")
            if score < 90:
                audit.add(p["url"], IMPORTANT if score < 50 else OPTIMIZATION, "Performance",
                          "Poor mobile performance score" if score < 50 else "Mobile performance could improve",
                          current=p["psi"], expected="performance 90+")
        except Exception as e:
            p["psi"] = f"error: {e}"[:120]

# ------------------------------------------------------------------ sheets
by_url = defaultdict(Counter)
for i in audit.issues:
    by_url[i["url"]][i["severity"]] += 1
for p in page_data:
    p["score"] = audit.page_score(p["url"])
    c = by_url[p["url"]]
    page_rows.append((p["url"], p["status"], p["score"], c[CRITICAL], c[IMPORTANT], c[OPTIMIZATION], p.get("title", ""),
                      len(p.get("title", "")), p.get("description", ""), len(p.get("description", "")), p.get("keywords", ""),
                      p.get("h1", ""), p.get("h1_count", ""), p.get("canonical", ""), p.get("robots", ""),
                      p.get("og_image", ""), p.get("twitter_card", ""), p.get("schema", ""), p.get("hreflang", ""),
                      p.get("lang", ""), p.get("images", ""), p.get("images_no_alt", ""), p.get("internal_links", ""),
                      p.get("words", ""), p.get("ms", ""), p.get("psi", "")))
page_rows.sort(key=lambda r: r[2])
audit.note("Pages with zero Critical/Important issues",
           sum(1 for p in page_data if not by_url[p["url"]][CRITICAL] and not by_url[p["url"]][IMPORTANT]))
audit.sheet("Site-wide", ["Check", "Severity", "Status", "Detail"], site_rows, (52, 14, 10, 100))
audit.sheet("Pages", ["URL", "HTTP", "Score", "Critical", "Important", "Optimization", "Title", "Title len", "Meta description",
                      "Desc len", "Meta keywords", "H1", "H1 count", "Canonical", "Robots", "OG image", "Twitter card",
                      "JSON-LD types", "hreflang", "lang", "Images", "Images w/o alt", "Internal links", "Words",
                      "Response ms", "PageSpeed (mobile)"], page_rows,
            (48, 6, 7, 8, 9, 11, 45, 8, 50, 8, 15, 40, 8, 45, 22, 40, 20, 35, 18, 6, 7, 9, 9, 7, 9, 40))
audit.sheet("Images", ["Page", "Image src", "Alt", "Bytes", "Severity", "Issues"], image_rows, (45, 60, 35, 10, 14, 60),
            severity_col=5)
audit.sheet("Links", ["Link", "Type", "HTTP", "Result", "Pages linking", "Example page"], link_rows, (60, 10, 7, 40, 13, 50))
audit.sheet("Duplicates", ["URL", "Category", "Issue", "Current value"],
            sorted(((i["url"], i["category"], i["issue"], i["current_value"]) for i in audit.issues
                    if i["issue"].startswith("Duplicate")), key=lambda r: (r[2], r[3])), (48, 14, 24, 100))
audit.save("SEO_Report")
if Image is None:
    print("Tip: pip install pillow to also check OG image dimensions.")
