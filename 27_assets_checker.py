"""
27 - Assets checker (files the pages point at: fonts, logos, icons, JSON-LD URLs, feeds, PDFs)
  referenced files: every URL inside JSON-LD (image, logo, url, sameAs ...), <link rel=icon / apple-touch-icon /
      manifest / preload / alternate> on every page responds 200 (e.g. a schema image that was never uploaded)
  JSON-LD values (jsonschema): dates are ISO 8601 and dateModified >= datePublished, url / image / logo are
      absolute http(s) URLs, headline <= 110 characters, name / headline are text
  fonts: @font-face files in the site CSS are WOFF2 / WOFF (not TTF / OTF / EOT), font-display is set, the fonts
      the page uses are preloaded (next/font does this)
  icons (Pillow): favicon.ico contains 32x32 (and 16 / 48), apple-touch-icon is a 180x180 PNG, the manifest icons
      have the sizes they declare (192 and 512 present)
  logo (Chrome, 2x screen): header / footer logos are sharp on retina screens (bitmap at least 2x its displayed
      size, or SVG)
  feed: an RSS / Atom feed that is linked or exists (/feed.xml, /rss.xml ...) parses and has entries on this host
  PDFs (PyMuPDF, optional): linked PDFs respond, are not huge, have a title and real text (not a scanned image)

  python "py files/27_assets_checker.py" [--base URL] [--no-browser]
"""
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from threading import Lock
from urllib.parse import urljoin, urlparse

from seo_common import (IMPORTANT, INFO, OPTIMIZATION, Audit, Browser, fetch, load_site, parse_args,
                        run_parallel, select_pages)

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import jsonschema
except ImportError:
    jsonschema = None
try:
    import fitz   # PyMuPDF
except ImportError:
    fitz = None

args = parse_args("Assets checker", lambda ap: ap.add_argument("--no-browser", action="store_true"))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("27_assets", "Assets Report", "Assets", site)
lock = Lock()

refs = defaultdict(lambda: {"pages": set(), "how": set()})   # absolute URL -> where it is referenced
css_files, pdfs, feeds = set(), defaultdict(set), set()
preloaded_fonts = set()

URL_KEYS = {"url", "image", "logo", "contentUrl", "thumbnailUrl", "sameAs", "item", "@id", "mainEntityOfPage", "embedUrl"}
ABS_URL = {"type": "string", "pattern": r"^https?://"}
URLISH = {"anyOf": [ABS_URL, {"type": "object"}, {"type": "array"}]}
NODE_SCHEMA = {   # the value formats Google's rich results need (presence of properties is checked by 07)
    "type": "object",
    "properties": {
        "url": URLISH, "logo": URLISH, "image": URLISH,
        "headline": {"type": "string", "maxLength": 110},
        "name": {"type": "string", "minLength": 1},
        "datePublished": {"type": "string"}, "dateModified": {"type": "string"},
    },
}


def iso_date(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def nodes(data):
    if isinstance(data, list):
        for x in data:
            yield from nodes(x)
    elif isinstance(data, dict):
        yield data
        for v in data.values():
            if isinstance(v, (dict, list)):
                yield from nodes(v)


def add_ref(url, loc, how):
    if not url or url.startswith(("data:", "mailto:", "tel:", "#", "javascript:")):
        return
    with lock:
        refs[url]["pages"].add(loc)
        refs[url]["how"].add(how)


def scan(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, IMPORTANT, "Status", "Page not reachable", current=f"HTTP {res['status']}")
        return
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        href = urljoin(loc, link["href"])
        if "stylesheet" in rel:
            with lock:
                css_files.add(href)
        elif "icon" in rel or "manifest" in rel:
            add_ref(href, loc, rel)
        elif "preload" in rel:
            add_ref(href, loc, f"preload {link.get('as', '')}")
            if link.get("as") == "font":
                with lock:
                    preloaded_fonts.add(urlparse(href).path)
        elif "alternate" in rel and re.search(r"rss|atom", link.get("type", "")):
            with lock:
                feeds.add(href)
    for a in soup.find_all("a", href=True):
        if re.search(r"\.pdf($|\?)", a["href"], re.I):
            with lock:
                pdfs[urljoin(loc, a["href"])].add(loc)
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue   # parse errors are reported by 07
        for n in nodes(data):
            t = n.get("@type", "?")
            t = t[0] if isinstance(t, list) and t else t
            for k, v in n.items():
                if k in URL_KEYS:
                    for item in (v if isinstance(v, list) else [v]):
                        if isinstance(item, str) and item.startswith(("http", "/")):
                            add_ref(urljoin(loc, item), loc, f"JSON-LD {t}.{k}")
            if jsonschema:
                for err in jsonschema.Draft7Validator(NODE_SCHEMA).iter_errors(n):
                    field = ".".join(str(x) for x in err.path) or "?"
                    audit.add(loc, IMPORTANT if field in ("url", "logo", "image") else OPTIMIZATION, "JSON-LD values",
                              f"JSON-LD {t}.{field} has the wrong format", current=str(err.instance)[:150],
                              expected={"headline": "at most 110 characters", "url": "an absolute https:// URL",
                                        "logo": "an absolute https:// URL", "image": "an absolute https:// URL"}
                              .get(field, err.message[:120]))
            pub, mod = n.get("datePublished"), n.get("dateModified")
            for k in ("datePublished", "dateModified", "uploadDate", "startDate", "validThrough"):
                if n.get(k) and not iso_date(n[k]):
                    audit.add(loc, IMPORTANT, "JSON-LD values", f"JSON-LD {t}.{k} is not an ISO 8601 date",
                              current=str(n[k])[:60], expected="e.g. 2026-10-08 or 2026-10-08T09:30:00+05:30")
            if pub and mod and iso_date(pub) and iso_date(mod):
                a, b = iso_date(pub), iso_date(mod)
                try:
                    if b < a:
                        audit.add(loc, OPTIMIZATION, "JSON-LD values", "dateModified is before datePublished",
                                  current=f"{pub} > {mod}")
                except TypeError:   # one has a timezone, the other not
                    pass


print(f"Collecting referenced files on {len(pages)} pages ...")
run_parallel(scan, pages, args.workers)

# ------------------------------------------------------------------ referenced files respond
ref_rows = []


def check_ref(url):
    target = site.to_fetch(url) if site.is_internal(url) else url
    res = fetch(target, "HEAD", timeout=30)
    return url, res["status"], res["headers"].get("Content-Type", "")


print(f"Requesting {len(refs)} referenced URLs ...")
for url, status, ctype in run_parallel(check_ref, sorted(refs), args.workers, "URLs"):
    info = refs[url]
    how = ", ".join(sorted(info["how"]))[:120]
    ref_rows.append((url, status, ctype.split(";")[0], how, len(info["pages"])))
    internal = site.is_internal(url)
    if status in (200, 301, 302, 303, 307, 308):
        continue
    if not internal and status in (0, 401, 403, 405, 429, 999):
        continue   # external site blocks bots: unverified, not broken
    sev = IMPORTANT if internal or "JSON-LD" in how and "sameAs" not in how else OPTIMIZATION
    label = "Referenced file is missing" if re.search(r"icon|manifest|preload|image|logo", how) else "Referenced URL is broken"
    for loc in sorted(info["pages"])[:50]:
        audit.add(loc, sev, "Referenced files", label, current=f"HTTP {status}", element=url,
                  detail=f"referenced as {how}", expected="HTTP 200",
                  fix="Upload the file to public/ (or fix the path in the metadata / JSON-LD that points at it).")

# ------------------------------------------------------------------ fonts in the CSS
font_rows = []
font_urls = set()
for css in sorted(css_files):
    res = fetch(site.to_fetch(css) if site.is_internal(css) else css)
    if res["status"] != 200:
        continue
    text = res["content"].decode("utf-8", "replace")
    for block in re.findall(r"@font-face\s*{([^}]*)}", text):
        family = (re.search(r"font-family\s*:\s*([^;]+)", block) or [None, "?"])[1].strip(" '\"")
        srcs = re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", block)
        if not srcs:
            continue   # local() fallback faces (next/font size-adjusted fallbacks) load nothing
        fmts = {(re.search(r"\.(\w+)(?:$|[?#])", s) or [None, "?"])[1].lower() for s in srcs}
        display = (re.search(r"font-display\s*:\s*(\w+)", block) or [None, ""])[1]
        font_rows.append((css, family, ", ".join(sorted(fmts)), display or "(not set)", len(srcs)))
        for s in srcs:
            font_urls.add(urlparse(urljoin(css, s)).path)
        bad = fmts - {"woff2", "woff"}
        if bad:
            audit.site(OPTIMIZATION, "Fonts", "Font file not in WOFF2 / WOFF format", current=f"{family}: {', '.join(bad)}",
                       element=css, expected="woff2 (smallest, supported by every current browser)",
                       fix="Convert the font to WOFF2 (or load it with next/font, which does this).")
        if not display:
            audit.site(OPTIMIZATION, "Fonts", "font-display not set (text invisible while the font loads)",
                       current=family, element=css, expected="font-display: swap (or optional)")
if font_urls and not (font_urls & preloaded_fonts):
    audit.site(OPTIMIZATION, "Fonts", "No font is preloaded", current=f"{len(font_urls)} font files, none preloaded",
               expected='<link rel="preload" as="font"> for the hero / heading font (next/font adds it)')

# ------------------------------------------------------------------ icons (Pillow)
icon_rows = []


def image_info(url):
    res = fetch(site.to_fetch(url) if site.is_internal(url) else url)
    if res["status"] != 200 or not Image:
        return res["status"], None
    try:
        img = Image.open(io.BytesIO(res["content"]))
        sizes = sorted(img.info.get("sizes", [])) if img.format == "ICO" else []
        return res["status"], (img.format, img.size, sizes)
    except Exception:
        return res["status"], ("not an image", (0, 0), [])


if not Image:
    audit.not_checked("Icons", "icon image sizes", "Pillow not installed", "pip install pillow")
else:
    st, info = image_info(f"{site.base}/favicon.ico")
    icon_rows.append(("/favicon.ico", st, *(info[:2] if info else ("", ""))))
    if st == 200 and info:
        fmt, size, sizes = info
        if fmt == "ICO" and sizes and (32, 32) not in sizes:
            audit.site(OPTIMIZATION, "Icons", "favicon.ico has no 32x32 image", current=str(sizes), expected="16, 32 and 48 px")
    icon_refs = [u for u, i in refs.items() if any("icon" in h for h in i["how"])]
    for u in icon_refs:
        st, info = image_info(u)
        if not info:
            continue
        fmt, size, _ = info
        icon_rows.append((u, st, fmt, f"{size[0]}x{size[1]}"))
        if any("apple-touch-icon" in h for h in refs[u]["how"]) and (size != (180, 180) or fmt != "PNG"):
            audit.site(OPTIMIZATION, "Icons", "apple-touch-icon is not a 180x180 PNG", current=f"{fmt} {size[0]}x{size[1]}",
                       element=u)
    for u in [u for u, i in refs.items() if any("manifest" in h for h in i["how"])][:1]:
        res = fetch(site.to_fetch(u) if site.is_internal(u) else u)
        try:
            manifest = json.loads(res["content"])
        except ValueError:
            continue
        declared = set()
        for icon in manifest.get("icons", []):
            src = urljoin(u, icon.get("src", ""))
            st, info = image_info(src)
            for want in (icon.get("sizes") or "").split():
                declared.add(want)
                if info and f"{info[1][0]}x{info[1][1]}" != want and info[0] not in ("SVG", None):
                    audit.site(IMPORTANT, "Icons", "Manifest icon size doesn't match its declared size",
                               current=f"{info[1][0]}x{info[1][1]}", expected=want, element=src)
            if st != 200:
                audit.site(IMPORTANT, "Icons", "Manifest icon is missing", current=f"HTTP {st}", element=src)
            icon_rows.append((src, st, info[0] if info else "", icon.get("sizes", "")))
        for want in ("192x192", "512x512"):
            if want not in declared:
                audit.site(OPTIMIZATION, "Icons", f"Manifest has no {want} icon", current=", ".join(sorted(declared)) or "(none)")

# ------------------------------------------------------------------ logo sharpness (Chrome, 2x screen)
LOGO_JS = """
() => [...document.querySelectorAll('header img, footer img, header svg, footer svg, [class*=logo] img, img[alt*=logo i]')]
  .filter(e => { const r = e.getBoundingClientRect(); return r.width > 20 && r.height > 8; })
  .filter(e => /logo/i.test([e.getAttribute('alt'), e.getAttribute('src'), e.className && e.className.baseVal !== undefined
      ? e.className.baseVal : e.className, e.closest('a') && e.closest('a').getAttribute('aria-label'),
      e.parentElement && e.parentElement.className].join(' ')))
  .map(e => ({ tag: e.tagName.toLowerCase(), src: e.currentSrc || e.getAttribute('src') || '(inline svg)',
               natural: e.naturalWidth || 0, shown: Math.round(e.getBoundingClientRect().width),
               where: e.closest('footer') ? 'footer' : 'header' }))
"""
logo_rows = []
if args.no_browser:
    audit.not_checked("Logo", "logo sharpness", "--no-browser")
else:
    with Browser() as b:
        for label, mobile, w, h in (("desktop", False, 1440, 900), ("phone", True, 390, 844)):
            ctx = b.context(mobile=mobile, width=w, height=h, device_scale_factor=2)
            page = ctx.new_page()
            try:
                page.goto(site.to_fetch(pages[0]), wait_until="load", timeout=60000)
                page.wait_for_timeout(800)
                for lg in page.evaluate(LOGO_JS):
                    sharp = lg["tag"] == "svg" or lg["src"].lower().split("?")[0].endswith(".svg") or \
                        lg["natural"] >= 2 * lg["shown"] * 0.95
                    logo_rows.append((label, lg["where"], lg["src"][:150], lg["natural"], lg["shown"],
                                      "sharp" if sharp else "blurry on retina"))
                    if not sharp:
                        audit.site(OPTIMIZATION, "Logo", "Logo is low resolution for retina screens",
                                   current=f"{lg['natural']}px wide shown at {lg['shown']}px ({label} {lg['where']})",
                                   expected=f">= {2 * lg['shown']}px wide, or SVG", element=lg["src"][:200])
            except Exception as e:
                audit.add(pages[0], OPTIMIZATION, "Logo", "Page failed to load in Chrome", current=str(e)[:150])
            finally:
                ctx.close()
    if not logo_rows:
        audit.site(INFO, "Logo", "No image logo in the header / footer (text logo?) - sharpness not checked",
                   current="(no <img>/<svg> with 'logo' in its alt / src / class)")

# ------------------------------------------------------------------ feed
feed_rows = []
candidates = set(feeds) | {f"{site.base}{p}" for p in ("/feed.xml", "/rss.xml", "/feed", "/atom.xml", "/blog/rss.xml")}
for f in sorted(candidates):
    res = fetch(site.to_fetch(f) if site.is_internal(f) else f)
    if res["status"] != 200 or b"<" not in res["content"][:200]:
        if f in feeds:
            audit.site(IMPORTANT, "Feed", "Linked RSS / Atom feed is broken", current=f"HTTP {res['status']}", element=f)
        continue
    try:
        root = ET.fromstring(res["content"])
    except ET.ParseError as e:
        audit.site(IMPORTANT, "Feed", "RSS / Atom feed is not valid XML", current=str(e)[:120], element=f)
        continue
    if not re.search(r"rss|feed|rdf", root.tag, re.I):
        continue
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    links = [e.text or e.get("href", "") for e in root.iter() if e.tag.split("}")[-1] == "link"]
    feed_rows.append((f, len(items), links[0] if links else ""))
    if not items:
        audit.site(IMPORTANT, "Feed", "RSS / Atom feed has no entries", current="0 items", element=f)
    dev = [l for l in links if l and re.search(r"localhost|127\.0\.0\.1|vercel\.app|staging", l)]
    if dev and site.is_public:
        audit.site(IMPORTANT, "Feed", "Feed links point to a development host", current=dev[0], element=f)
if not feed_rows and any("/blog/" in p for p in pages):
    audit.site(INFO, "Feed", "Blog has no RSS / Atom feed", current="(none found)",
               expected="optional: /feed.xml linked with <link rel=alternate type=application/rss+xml>")

# ------------------------------------------------------------------ PDFs
pdf_rows = []
for url, on in sorted(pdfs.items()):
    res = fetch(site.to_fetch(url) if site.is_internal(url) else url, timeout=90)
    size = len(res["content"])
    title, text_chars, n_pages = "", "", ""
    if res["status"] != 200:
        for loc in sorted(on)[:20]:
            audit.add(loc, IMPORTANT, "PDF", "Linked PDF is broken", current=f"HTTP {res['status']}", element=url)
    elif fitz:
        try:
            doc = fitz.open(stream=res["content"], filetype="pdf")
            title, n_pages = (doc.metadata or {}).get("title", ""), doc.page_count
            text_chars = sum(len(doc[i].get_text()) for i in range(min(3, doc.page_count)))
            if not title:
                audit.site(OPTIMIZATION, "PDF", "PDF has no title in its properties", element=url,
                           expected="a document title (shown in browser tabs and search results)")
            if text_chars < 50:
                audit.site(IMPORTANT, "PDF", "PDF has no text layer (scanned image)", element=url,
                           expected="real text (searchable, readable by screen readers) - run OCR")
        except Exception as e:
            audit.site(IMPORTANT, "PDF", "PDF can't be opened", current=str(e)[:120], element=url)
    if res["status"] == 200 and size > 10 * 1024 * 1024:
        audit.site(OPTIMIZATION, "PDF", "Large PDF (over 10 MB)", current=f"{size // 1048576} MB", element=url)
    pdf_rows.append((url, res["status"], round(size / 1024), n_pages, title, text_chars, len(on)))
if pdfs and not fitz:
    audit.not_checked("PDF", "PDF title / text layer", "PyMuPDF not installed", "pip install pymupdf")

audit.sheet("Referenced files", ["URL", "HTTP", "Content-Type", "Referenced as", "Pages"],
            sorted(ref_rows, key=lambda r: (r[1] == 200, r[0])), (70, 7, 24, 50, 8))
audit.sheet("Fonts", ["Stylesheet", "Family", "Formats", "font-display", "Files"], font_rows, (60, 30, 16, 14, 8))
audit.sheet("Icons", ["URL", "HTTP", "Format", "Size"], icon_rows, (60, 7, 10, 12))
audit.sheet("Logos", ["View", "Where", "Image", "Bitmap width", "Shown width", "Result"], logo_rows, (10, 10, 70, 12, 12, 18))
audit.sheet("Feeds", ["Feed", "Entries", "First link"], feed_rows, (60, 8, 60))
audit.sheet("PDFs", ["PDF", "HTTP", "KB", "Pages", "Title", "Text chars (3 pages)", "Linked from"], pdf_rows,
            (60, 7, 8, 7, 30, 16, 10))
audit.save("Assets_Report")
