"""
13 - Next.js + production health + browser metadata checker
  source code (src/app): every route has metadata / generateMetadata, dynamic routes have generateMetadata and
      generateStaticParams, pages that are Client Components, metadataBase, robots / sitemap / manifest / favicon /
      icon / apple-icon / opengraph-image / twitter-image files, next/font vs external font links, raw <img> instead
      of next/image, next.config image optimisation + source maps + poweredByHeader, hard-coded localhost / dev /
      staging URLs, leftover console.log / debugger
  rendered HTML (every page): default/duplicate metadata on dynamic pages, duplicate meta tags, canonical + Open Graph
      absolute (metadataBase works), Twitter tags, next/image usage, localhost / development URLs, debug text
  browser (every page, --browser-workers in parallel): console errors, hydration errors, failed requests, missing /_next assets, failed API calls,
      content that only appears after JavaScript (client-only rendering)
  favicon / browser metadata: favicon, apple-touch-icon, web manifest (name, icons 192/512, start_url, display),
      theme-color, site name

  python "py files/13_nextjs_checker.py" [--base URL] [--no-browser]
"""
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, PROJECT_ROOT, Audit, fetch, has_rel, load_site, main_text,
                        meta, parse_args, run_browser_pages, run_parallel, select_pages, text_of)

DEV_URL = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|[\w-]+\.local|[\w.-]*ngrok[\w.-]*|"
                     r"staging\.[\w.-]+|dev\.[\w.-]+|[\w-]+\.vercel\.app|[\w-]+--[\w-]+\.netlify\.app)(:\d+)?", re.I)
DEBUG_TEXT = re.compile(r"\b(undefined|NaN|\[object Object\]|TODO|FIXME|lorem ipsum|console\.log)\b")

args = parse_args("Next.js checker", lambda ap: ap.add_argument("--no-browser", action="store_true"))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("13_nextjs", "NextJS Report", "Technical SEO", site)
route_rows, file_rows, source_rows = [], [], []

# ================================================================ source code
app_dir = next((p for p in (PROJECT_ROOT / "src" / "app", PROJECT_ROOT / "app") if p.is_dir()), None)
SRC = PROJECT_ROOT / "src" if (PROJECT_ROOT / "src").is_dir() else PROJECT_ROOT


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def has_metadata(text):
    return bool(re.search(r"export\s+(const\s+metadata\b|(async\s+)?function\s+generateMetadata\b)", text))


if app_dir:
    root_layout = next((app_dir / f"layout.{e}" for e in ("tsx", "jsx", "ts", "js") if (app_dir / f"layout.{e}").exists()), None)
    root_text = read(root_layout) if root_layout else ""
    if "metadataBase" not in root_text:
        audit.site(IMPORTANT, "Metadata", "metadataBase not set in the root layout",
                   "relative canonical / Open Graph URLs can't become absolute")
    for page_file in sorted(app_dir.rglob("page.*")):
        if page_file.suffix not in (".tsx", ".jsx", ".ts", ".js"):
            continue
        rel = page_file.parent.relative_to(app_dir)
        parts = [p for p in rel.parts if not (p.startswith("(") and p.endswith(")")) and not p.startswith("@")]
        route = "/" + "/".join(parts)
        dynamic = any(p.startswith("[") for p in parts)
        text = read(page_file)
        chain = [page_file] + [d / f"layout.{e}" for d in [page_file.parent, *page_file.parent.parents]
                               if app_dir in [d, *d.parents] for e in ("tsx", "jsx", "ts", "js") if (d / f"layout.{e}").exists()]
        own = has_metadata(text) or any(has_metadata(read(l)) for l in chain[1:] if l.parent != app_dir)
        is_client = text.lstrip().startswith(('"use client"', "'use client'"))
        redirect_only = "redirect(" in text and len(text) < 600
        gen_meta = "generateMetadata" in text or any("generateMetadata" in read(l) for l in chain[1:] if l.parent != app_dir)
        static_params = "generateStaticParams" in text or any("generateStaticParams" in read(l) for l in chain[1:])
        issues = []
        if is_client:
            issues.append("Client Component page")
            audit.add(f"route: {route}", IMPORTANT, "Routes", "Page is a Client Component ('use client')",
                      current="'use client' at the top of page file", element=str(page_file.relative_to(PROJECT_ROOT)))
        if not own and not redirect_only and route != "/":
            issues.append("no metadata")
            audit.add(f"route: {route}", IMPORTANT, "Metadata", "Route has no metadata / generateMetadata (inherits the root title)",
                      current="no metadata export", element=str(page_file.relative_to(PROJECT_ROOT)))
        if dynamic and not gen_meta and not redirect_only:
            issues.append("no generateMetadata")
            audit.add(f"route: {route}", IMPORTANT, "Metadata", "Dynamic route without generateMetadata",
                      current="no generateMetadata", element=str(page_file.relative_to(PROJECT_ROOT)))
        if dynamic and not static_params and "[[..." not in route:
            issues.append("no generateStaticParams")
            audit.add(f"route: {route}", OPTIMIZATION, "Routes", "Dynamic route without generateStaticParams (rendered on every request)",
                      current="no generateStaticParams", element=str(page_file.relative_to(PROJECT_ROOT)))
        route_rows.append((route, str(page_file.relative_to(PROJECT_ROOT)), "yes" if dynamic else "", "yes" if own else "no",
                           "yes" if gen_meta else "", "yes" if static_params else "", "client" if is_client else "server",
                           ", ".join(issues)))

    def exists(*patterns):
        found = []
        for base in (app_dir, PROJECT_ROOT / "public"):
            for pat in patterns:
                found += [str(p.relative_to(PROJECT_ROOT)) for p in base.glob(pat)]
        return found

    special = [("robots", ["robots.ts", "robots.js", "robots.txt"], CRITICAL),
               ("sitemap", ["sitemap.ts", "sitemap.js", "sitemap.xml", "sitemap.xml/route.*"], CRITICAL),
               ("manifest", ["manifest.ts", "manifest.js", "manifest.json", "manifest.webmanifest", "site.webmanifest"], OPTIMIZATION),
               ("favicon", ["favicon.ico"], IMPORTANT),
               ("icon", ["icon.*", "icon[0-9]*.*"], OPTIMIZATION),
               ("apple-icon", ["apple-icon.*", "apple-touch-icon*.png"], OPTIMIZATION),
               ("opengraph-image", ["opengraph-image.*", "**/opengraph-image.*"], OPTIMIZATION),
               ("twitter-image", ["twitter-image.*", "**/twitter-image.*"], OPTIMIZATION)]
    for name, patterns, sev in special:
        found = exists(*patterns)
        file_rows.append((name, ", ".join(found[:5]) or "missing"))
        if not found:
            audit.site(sev, "Special files", f"No {name} file", current="not found in app/ or public/",
                       expected=f"{patterns[0]} in src/app/")

# whole source tree scans
raw_img, font_links, dev_urls, logs = Counter(), [], [], Counter()
for f in SRC.rglob("*"):
    if f.suffix not in (".tsx", ".jsx", ".ts", ".js", ".mjs") or "node_modules" in f.parts or ".next" in f.parts:
        continue
    text = read(f)
    rel = str(f.relative_to(PROJECT_ROOT))
    n_img = len(re.findall(r"<img\b", text))
    if n_img:
        raw_img[rel] += n_img
    if re.search(r"fonts\.googleapis\.com|use\.typekit\.net", text):
        font_links.append(rel)
    for m in DEV_URL.finditer(text):
        line = text[: m.start()].count("\n") + 1
        context = text.splitlines()[line - 1].strip()[:140]
        if "process.env" in context or "||" in context or "??" in context:
            continue  # env fallback, fine
        dev_urls.append((rel, line, context))
    logs[rel] += len(re.findall(r"\bconsole\.log\(|\bdebugger;", text))
for rel, n in raw_img.most_common():
    source_rows.append(("raw <img> (not next/image)", rel, n))
    audit.add(f"file: {rel}", OPTIMIZATION, "Images", "Raw <img> instead of next/image", current=f"{n} <img> tag(s)",
              expected="<Image> from next/image")
for rel in font_links:
    source_rows.append(("external font stylesheet", rel, ""))
    audit.add(f"file: {rel}", OPTIMIZATION, "Fonts", "External font stylesheet instead of next/font",
              current="fonts.googleapis.com / typekit link", expected="next/font")
for rel, line, ctx in dev_urls:
    source_rows.append(("hard-coded dev URL", f"{rel}:{line}", ctx))
    audit.add(f"file: {rel}", IMPORTANT, "Production health", "Hard-coded localhost / development URL in source",
              current=ctx, element=f"{rel}:{line}", expected="URL built from process.env.NEXT_PUBLIC_SITE_URL")
for rel, n in logs.items():
    if n:
        source_rows.append(("console.log / debugger", rel, n))
        audit.add(f"file: {rel}", OPTIMIZATION, "Production health", "console.log / debugger left in source",
                  current=f"{n} statement(s)", expected="0")
if not raw_img and not font_links:
    audit.note("next/image & next/font", "no raw <img> tags or external font stylesheets found")

config = next((PROJECT_ROOT / f"next.config.{e}" for e in ("ts", "mjs", "js") if (PROJECT_ROOT / f"next.config.{e}").exists()), None)
ctext = read(config) if config else ""
if re.search(r"unoptimized\s*:\s*true", ctext):
    audit.site(IMPORTANT, "Images", "next.config images.unoptimized is true (no image optimisation)")
if config and "formats" not in ctext:
    audit.site(OPTIMIZATION, "Images", "next.config images.formats not set (AVIF not enabled)",
               "add images: { formats: ['image/avif', 'image/webp'] }")
if re.search(r"productionBrowserSourceMaps\s*:\s*true", ctext):
    audit.site(IMPORTANT, "Production health", "productionBrowserSourceMaps is enabled (source code public)")
if config and not re.search(r"poweredByHeader\s*:\s*false", ctext):
    audit.site(OPTIMIZATION, "Production health", "poweredByHeader not disabled (sends X-Powered-By: Next.js)")
env_local = read(PROJECT_ROOT / ".env.local")
if DEV_URL.search(re.search(r"NEXT_PUBLIC_SITE_URL\s*=\s*(\S+)", env_local).group(1) if re.search(r"NEXT_PUBLIC_SITE_URL\s*=\s*(\S+)", env_local) else ""):
    audit.note(".env.local NEXT_PUBLIC_SITE_URL", "localhost (fine for development - production builds must set the live https URL)")

# ================================================================ rendered HTML
root_title = None
html_rows = []


def check_html(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    head = soup.head or soup
    title = text_of(soup.title) if soup.title else ""
    for name in ("description", "robots", "viewport"):
        n = len(head.find_all("meta", attrs={"name": name}))
        if n > 1:
            audit.add(loc, IMPORTANT, "Metadata", f"Duplicate <meta name={name}>", current=f"{n} tags", expected="1")
    for prop in ("og:title", "og:description", "og:url", "og:type"):
        n = len(head.find_all("meta", attrs={"property": prop}))
        if n > 1:
            audit.add(loc, IMPORTANT, "Metadata", f"Duplicate {prop}", current=f"{n} tags", expected="1")
    canon = head.find("link", rel=lambda v: v and has_rel(v, "canonical"))
    if canon and not canon.get("href", "").startswith("http"):
        audit.add(loc, IMPORTANT, "Metadata", "Canonical not absolute (metadataBase)", current=canon.get("href"),
                  expected=loc)
    og_image = meta(head, prop="og:image") or ""
    if og_image and not og_image.startswith("http"):
        audit.add(loc, IMPORTANT, "Metadata", "og:image not absolute (metadataBase)", current=og_image,
                  expected=urljoin(site.public("/"), og_image))
    if not meta(head, name="twitter:card"):
        audit.add(loc, OPTIMIZATION, "Metadata", "No Twitter metadata", current="no twitter:card")
    imgs = soup.find_all("img")
    raw = [i for i in imgs if not i.get("data-nimg") and not (i.get("src") or "").startswith("data:")
           and not (i.get("src") or "").endswith(".svg")]
    for img in raw:
        audit.add(loc, OPTIMIZATION, "Images", "Images not using next/image", current="plain <img>",
                  element=(img.get("src") or "")[:200])
    html = res["content"].decode("utf-8", "replace")
    for m in set(DEV_URL.findall(html)):
        host = m[0]
        if site.site_host and host in site.site_host:
            continue  # the audited server itself (sitemap host is checked in 01)
        audit.add(loc, IMPORTANT, "Production health", "Development URL in page HTML", current=host,
                  expected="production URLs only")
    visible = main_text(soup)
    for m in set(DEBUG_TEXT.findall(visible)):
        i = visible.find(m)
        audit.add(loc, IMPORTANT, "Production health", "Debug / placeholder text visible on page", current=m,
                  element=f"...{visible[max(0, i - 50):i + 50]}...")
    html_rows.append((loc, title, len(imgs), len(imgs) - len(raw), "yes" if canon else "no"))
    return title


print(f"Checking HTML of {len(pages)} pages ...")
titles = run_parallel(check_html, pages, args.workers)
home_res, home = site.page(site.public("/"))
if home:
    root_title = text_of(home.title) if home.title else ""
    for loc, t in zip(pages, titles):
        if t and site.path(loc) != "/" and t == root_title:
            audit.add(loc, IMPORTANT, "Metadata", "Page uses the default (homepage) title - metadata not generated",
                      current=t, expected="a page-specific title")

    # favicon / browser metadata
    head = home.head or home
    icon = head.find("link", rel=lambda v: v and (has_rel(v, "icon") or has_rel(v, "shortcut")))
    if not icon and fetch(f"{site.base}/favicon.ico", "HEAD")["status"] != 200:
        audit.site(IMPORTANT, "Browser metadata", "No favicon")
    if not head.find("link", rel=lambda v: v and has_rel(v, "apple-touch-icon")):
        audit.site(OPTIMIZATION, "Browser metadata", "No apple-touch-icon")
    if not meta(head, name="theme-color"):
        audit.site(OPTIMIZATION, "Browser metadata", "No theme-color meta")
    if not (meta(head, prop="og:site_name") or meta(head, name="application-name")):
        audit.site(OPTIMIZATION, "Browser metadata", "No site name (og:site_name / application-name)")
    man_link = head.find("link", rel=lambda v: v and has_rel(v, "manifest"))
    if not man_link:
        audit.site(OPTIMIZATION, "Browser metadata", "No web app manifest linked")
    else:
        mres = fetch(urljoin(site.base + "/", man_link["href"]))
        try:
            manifest = json.loads(mres["content"])
            sizes = " ".join(i.get("sizes", "") for i in manifest.get("icons", []))
            for key in ("name", "short_name", "start_url", "display", "theme_color", "background_color"):
                if not manifest.get(key):
                    audit.site(OPTIMIZATION, "Browser metadata", f"Manifest missing {key}")
            for size in ("192x192", "512x512"):
                if size not in sizes:
                    audit.site(OPTIMIZATION, "Browser metadata", f"Manifest has no {size} icon")
        except (ValueError, TypeError):
            audit.site(IMPORTANT, "Browser metadata", "Manifest is missing or invalid JSON", f"HTTP {mres['status']}")

# ================================================================ browser
browser_rows = []


def browser_check(browser, loc):
    ctx = browser.context(width=1440, height=900)
    try:
        _browser_check(ctx, loc)
    finally:
        ctx.close()


def _browser_check(ctx, loc):
    page = ctx.new_page()
    console, errors, failed, bad_api = [], [], [], []
    page.on("console", lambda m: console.append((m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    page.on("response", lambda r: (bad_api if r.request.resource_type in ("fetch", "xhr") else failed).append(
        (r.url, r.status)) if r.status >= 400 else None)
    try:
        page.goto(site.to_fetch(loc), wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1000)
        rendered = page.evaluate("() => (document.querySelector('main') || document.body)?.innerText || ''")
    except Exception as e:
        audit.add(loc, IMPORTANT, "Browser", "Page failed to load in Chrome", current=str(e)[:200])
        page.close()
        return
    page.close()
    hydration = [t for k, t in console if re.search(r"hydrat|did not match|server rendered HTML", t, re.I)]
    errs = [t for k, t in console if k == "error" and t not in hydration]
    for t in dict.fromkeys(hydration):
        audit.add(loc, IMPORTANT, "Hydration", "Hydration error/warning", current=t[:300])
    for t in dict.fromkeys(errors):
        audit.add(loc, CRITICAL, "Runtime", "Uncaught JavaScript error", current=t[:300])
    for t in dict.fromkeys(errs):
        audit.add(loc, IMPORTANT, "Runtime", "Console errors", current=t[:300])
    for u, st in failed:
        if "/_next/" in u:
            audit.add(loc, CRITICAL, "Production health", "Missing /_next asset", current=str(st), element=u[:200])
        else:
            audit.add(loc, IMPORTANT, "Requests", "Failed requests", current=str(st), element=u[:200])
    for u, st in bad_api:
        audit.add(loc, IMPORTANT, "Requests", "Failed API calls", current=f"HTTP {st}", element=u[:200])
    res, soup = site.page(loc)
    ssr_words = len(main_text(soup).split()) if soup else 0
    csr_words = len((rendered or "").split())
    if csr_words > 150 and csr_words > 2 * max(ssr_words, 1):
        audit.add(loc, IMPORTANT, "Rendering", "Most content is rendered client-side only",
                  current=f"{ssr_words} words in server HTML, {csr_words} after JavaScript",
                  expected="most words already in the server HTML")
    browser_rows.append((loc, len(errs), len(hydration), len(errors), len(failed), len(bad_api), ssr_words, csr_words))


if not args.no_browser:
    print(f"Loading {len(pages)} pages in Chrome (console, hydration, failed requests; "
          f"{args.browser_workers} in parallel) ...")
    run_browser_pages(browser_check, pages, args.browser_workers, "pages loaded")
    browser_rows.sort(key=lambda r: r[0])

audit.sheet("Routes", ["Route", "File", "Dynamic", "Own metadata", "generateMetadata", "generateStaticParams", "Component",
                       "Issues"], route_rows, (40, 55, 8, 12, 15, 18, 10, 45))
audit.sheet("Special files", ["File", "Found"], file_rows, (18, 90))
audit.sheet("Source findings", ["Finding", "File", "Detail"], source_rows, (28, 60, 80))
audit.sheet("Rendered pages", ["URL", "Title", "<img>", "next/image", "Canonical"], html_rows, (55, 55, 7, 10, 10))
audit.sheet("Browser", ["URL", "Console errors", "Hydration", "JS exceptions", "Failed requests", "Failed API", "Words in HTML",
                        "Words after JS"], browser_rows, (55, 13, 10, 12, 14, 10, 13, 13))
audit.save("NextJS_Report")
