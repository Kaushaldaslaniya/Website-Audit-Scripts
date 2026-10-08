"""
06 - Open Graph / social meta checker
  og:title, og:description, og:image, og:image:alt, og:image:width, og:image:height, og:url, og:type,
  og:site_name, og:locale; og:url == canonical; og:image absolute, reachable, an image, 1200x630;
  twitter:card (summary_large_image), twitter:title, twitter:description, twitter:image (+ broken image);
  duplicate og:title across pages; a page-specific share image vs one image for the whole site.

  python "py files/06_social_meta_checker.py" [--base URL]
"""
import io
from collections import Counter, defaultdict
from urllib.parse import urljoin

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, has_rel, load_site, meta, norm, parse_args,
                        run_parallel, select_pages)

try:
    from PIL import Image
except ImportError:
    Image = None

OG_REQUIRED = [("title", IMPORTANT), ("description", IMPORTANT), ("image", IMPORTANT), ("url", IMPORTANT),
               ("type", OPTIMIZATION), ("site_name", OPTIMIZATION), ("locale", OPTIMIZATION),
               ("image:alt", OPTIMIZATION), ("image:width", OPTIMIZATION), ("image:height", OPTIMIZATION)]
TW_REQUIRED = [("card", IMPORTANT), ("title", OPTIMIZATION), ("description", OPTIMIZATION), ("image", OPTIMIZATION)]

args = parse_args("Open Graph / social meta checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("06_social", "Social Meta Report", "On-Page SEO", site)
import threading
image_cache = {}
image_cache_lock = threading.Lock()


def check_image(url_value, loc, label):
    if not url_value.startswith("http"):
        audit.add(loc, IMPORTANT, label, f"{label} image is not an absolute URL", current=url_value,
                  expected=urljoin(site.public("/"), url_value))
        url_value = urljoin(site.public("/"), url_value)
    with image_cache_lock:
        in_cache = url_value in image_cache
    if not in_cache:
        res = fetch(site.to_fetch(url_value) if site.is_internal(url_value) else url_value)
        size = None
        ctype = res["headers"].get("Content-Type", "")
        if res["status"] == 200 and Image and ctype.startswith("image/") and "svg" not in ctype:
            try:
                with Image.open(io.BytesIO(res["content"])) as im:
                    size = im.size
            except Exception:
                pass
        with image_cache_lock:
            image_cache[url_value] = (res["status"], ctype, size, len(res["content"]))
    with image_cache_lock:
        status, ctype, size, nbytes = image_cache[url_value]
    if status != 200 or not ctype.startswith("image/"):
        audit.add(loc, IMPORTANT, label, f"Broken {label} image", current=f"HTTP {status} {ctype}".strip(),
                  element=url_value)
    elif "svg" in ctype:
        audit.add(loc, IMPORTANT, label, f"{label} image is SVG (not supported by social networks)", current=ctype,
                  element=url_value)
    elif size:
        w, h = size
        if w < 600 or h == 0 or (h > 0 and abs(w / h - 1200 / 630) > 0.15):
            audit.add(loc, IMPORTANT, label, f"{label} image not 1200x630", current=f"{w}x{h} px",
                      expected="1200x630 px", element=url_value)
        if nbytes > 5 * 1024 * 1024:
            audit.add(loc, OPTIMIZATION, label, f"{label} image larger than 5 MB", current=f"{nbytes // 1048576} MB",
                      element=url_value)
    return status, size


def check(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return {"url": loc}
    head = soup.head or soup
    og = {k: meta(head, prop=f"og:{k}") for k, _ in OG_REQUIRED}
    tw = {k: meta(head, name=f"twitter:{k}") for k, _ in TW_REQUIRED}
    for k, sev in OG_REQUIRED:
        if not og[k]:
            audit.add(loc, sev, "Open Graph", f"Missing og:{k}", current="(missing)",
                      expected=f'<meta property="og:{k}" content="...">')
    for k, sev in TW_REQUIRED:
        if not tw[k]:
            audit.add(loc, sev, "Twitter/X", f"Missing twitter:{k}", current="(missing)",
                      expected=f'<meta name="twitter:{k}" content="...">')
    if tw["card"] and tw["card"] != "summary_large_image":
        audit.add(loc, OPTIMIZATION, "Twitter/X", "twitter:card is not summary_large_image", current=tw["card"])
    canon = soup.find("link", rel=lambda v: v and has_rel(v, "canonical"))
    canonical = urljoin(loc, canon["href"]) if canon and canon.get("href") else ""
    if og["url"]:
        if not og["url"].startswith("http"):
            audit.add(loc, IMPORTANT, "Open Graph", "og:url is not absolute", current=og["url"], expected=canonical or loc)
        elif canonical and norm(og["url"]) != norm(canonical):
            audit.add(loc, IMPORTANT, "Open Graph", "og:url differs from canonical", current=og["url"], expected=canonical)
    title = (soup.title.string or "").strip() if soup.title else ""
    if og["title"] and title and og["title"].strip() != title and len(og["title"]) < 15:
        audit.add(loc, OPTIMIZATION, "Open Graph", "og:title much shorter than page title", current=og["title"],
                  expected=title)
    og_status = og_size = tw_status = None
    if og["image"]:
        og_status, og_size = check_image(og["image"], loc, "og:image")
        if og_size and og["image:width"] and og["image:height"]:
            if (str(og_size[0]), str(og_size[1])) != (og["image:width"], og["image:height"]):
                audit.add(loc, OPTIMIZATION, "Open Graph", "og:image:width/height don't match the real image",
                          current=f"tags say {og['image:width']}x{og['image:height']}",
                          expected=f"{og_size[0]}x{og_size[1]} (real size)", element=og["image"])
    if tw["image"]:
        tw_status, _ = check_image(tw["image"], loc, "twitter:image")
    return {"url": loc, **{f"og:{k}": v or "" for k, v in og.items()}, **{f"twitter:{k}": v or "" for k, v in tw.items()},
            "og_status": og_status, "og_size": f"{og_size[0]}x{og_size[1]}" if og_size else "", "tw_status": tw_status}


print(f"Checking {len(pages)} pages ...")
rows = run_parallel(check, pages, args.workers)

titles = defaultdict(list)
for r in rows:
    if r.get("og:title"):
        titles[r["og:title"].lower()].append(r["url"])
for t, group in titles.items():
    if len(group) > 1:
        for u in group:
            audit.add(u, IMPORTANT, "Open Graph", "Duplicate og:title",
                      current=next(r["og:title"] for r in rows if r["url"] == u)[:150],
                      detail=f"shared by {len(group)} pages: " + ", ".join(g for g in group[:5] if g != u))
images = Counter(r.get("og:image") for r in rows if r.get("og:image"))
if images and len(rows) > 5:
    top, n = images.most_common(1)[0]
    if n / len(rows) > 0.5:
        audit.site(OPTIMIZATION, "Open Graph", "Same share image on most pages", current=f"{n} of {len(rows)} pages",
                   element=top)

cols = ["og:title", "og:description", "og:image", "og:image:alt", "og:image:width", "og:image:height", "og:url", "og:type",
        "og:site_name", "og:locale", "twitter:card", "twitter:title", "twitter:description", "twitter:image"]
audit.sheet("Social tags", ["URL", *cols, "og:image HTTP", "og:image real size", "twitter:image HTTP"],
            [(r["url"], *[r.get(c, "") for c in cols], r.get("og_status"), r.get("og_size"), r.get("tw_status")) for r in rows],
            (50, 40, 50, 45, 30, 8, 8, 45, 9, 14, 9, 18, 40, 50, 45, 9, 11, 9))
audit.sheet("Share images", ["Image", "HTTP", "Content-Type", "Size", "Bytes", "Pages using it"],
            [(u, s, c, f"{z[0]}x{z[1]}" if z else "", b, images.get(u, "")) for u, (s, c, z, b) in image_cache.items()],
            (70, 7, 18, 12, 10, 13))
audit.save("Social_Meta_Report")
