"""
04 - Image SEO checker
  per <img>: alt (missing / empty / generic / duplicate on the page / keyword-stuffed), URL, HTTP status,
  file size, real format (WebP / AVIF / JPEG / PNG / SVG / GIF), width/height attributes, natural size vs
  displayed size (oversized pixels), lazy loading, srcset/sizes (responsive), next/image usage,
  file-name quality. Image requests send a browser Accept header so next/image serves AVIF/WebP.

  python "py files/04_image_seo_checker.py" [--base URL]
"""
import io
import re
from collections import Counter
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, load_site, parse_args, run_parallel,
                        select_pages)

try:
    from PIL import Image
except ImportError:
    Image = None

MAX_BYTES = 300 * 1024          # above this an image is "oversized"
GENERIC = {"image", "img", "photo", "picture", "pic", "logo", "banner", "icon", "graphic", "thumbnail", "untitled",
           "placeholder", "default", "hero", "background"}
ACCEPT = {"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}

args = parse_args("Image SEO checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("04_images", "Image SEO Report", "Images", site)


def real_name(src):
    """File name behind /_next/image?url=... or a normal URL."""
    p = urlparse(src)
    if p.path.startswith("/_next/image"):
        inner = parse_qs(p.query).get("url", [""])[0]
        return unquote(urlparse(inner).path.rsplit("/", 1)[-1]), unquote(inner)
    return unquote(p.path.rsplit("/", 1)[-1]), src


def sniff(content, ctype):
    head = content[:16]
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return "AVIF"
    if head[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "WebP"
    if head[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if b"<svg" in content[:512].lower() or "svg" in ctype:
        return "SVG"
    return ctype.split("/")[-1].upper() if ctype else "?"


def probe(src):
    res = fetch(src, headers=ACCEPT)
    info = {"status": res["status"], "bytes": len(res["content"]), "format": "", "natural": None}
    if res["status"] == 200:
        info["format"] = sniff(res["content"], res["headers"].get("Content-Type", ""))
        if Image and info["format"] not in ("SVG", "?"):
            try:
                with Image.open(io.BytesIO(res["content"])) as im:
                    info["natural"] = im.size
            except Exception:
                pass
    return info


rows, all_imgs = [], []


def collect(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    imgs = [i for i in soup.find_all("img") if (i.get("src") or "") and not i.get("src", "").startswith("data:")]
    alts = Counter((i.get("alt") or "").strip().lower() for i in imgs if (i.get("alt") or "").strip())
    for index, img in enumerate(imgs):
        src = urljoin(site.to_fetch(loc), img["src"])
        all_imgs.append((loc, index, img, src, alts))


print(f"Reading {len(pages)} pages ...")
run_parallel(collect, pages, args.workers)
page_order = {p: n for n, p in enumerate(pages)}
all_imgs.sort(key=lambda t: (page_order.get(t[0], len(pages)), t[1]))   # same row order on every run
unique = sorted({src for *_, src, _ in all_imgs})
print(f"Checking {len(unique)} unique images ...")
info = dict(zip(unique, run_parallel(lambda s: probe(site.to_fetch(s) if site.is_internal(s) else s), unique,
                                     args.workers, "images")))

for loc, index, img, src, alts in all_imgs:
    alt = img.get("alt")
    decorative = img.get("aria-hidden") == "true" or img.get("role") in ("presentation", "none")
    name, original = real_name(src)
    i = info.get(src) or {}   # {} when the image check itself failed (recorded as "Not checked")
    issues = []

    def flag(sev, msg, current="", expected=None):
        issues.append((sev, msg))
        audit.add(loc, sev, "Images", msg, current=current, expected=expected, element=original[:200],
                  detail=f"image #{index + 1} on the page; alt={alt!r}"[:200])

    # alt text
    if alt is None:
        flag(IMPORTANT, "Missing alt attribute", "(no alt attribute)")
    elif not alt.strip():
        if not decorative:
            flag(OPTIMIZATION, "Empty alt (only correct for decorative images)", 'alt=""')
    else:
        a = alt.strip().lower()
        if a in GENERIC or re.fullmatch(r"(img|image|photo|dsc|screenshot|pic)[-_ ]?\d*(\.\w+)?", a):
            flag(IMPORTANT, "Generic alt text", f'alt="{alt}"')
        elif len(a) < 5:
            flag(OPTIMIZATION, "Very short alt text", f'alt="{alt}" ({len(a)} chars)')
        if re.search(r"\.(jpe?g|png|webp|gif|svg|avif)$", a):
            flag(IMPORTANT, "Alt text is a file name", f'alt="{alt}"')
        if alts.get(a, 0) > 1:
            flag(OPTIMIZATION, "Duplicate alt text on page", f'alt="{alt}" used {alts[a]} times')
        words = re.findall(r"[a-z0-9.]+", a)
        if len(words) >= 4 and max(Counter(words).values()) >= 3:
            flag(OPTIMIZATION, "Keyword-stuffed alt text", f'alt="{alt}"')
        if len(alt) > 125:
            flag(OPTIMIZATION, "Alt text longer than 125 chars", f"{len(alt)} chars")

    # delivery
    if i.get("status") != 200:
        flag(IMPORTANT, "Broken image", f"HTTP {i.get('status')}")
    else:
        if i["bytes"] > MAX_BYTES:
            flag(OPTIMIZATION, "Oversized image file", f"{i['bytes'] // 1024} KB ({i['format']})",
                 f"under {MAX_BYTES // 1024} KB")
        if i["format"] in ("JPEG", "PNG", "GIF") and i["bytes"] > 50 * 1024:
            flag(OPTIMIZATION, f"Served as {i['format']} - use WebP/AVIF", f"{i['format']}, {i['bytes'] // 1024} KB")

    # dimensions & layout
    fill = img.get("data-nimg") == "fill"
    w, h = img.get("width"), img.get("height")
    if not fill and not (w and h):
        flag(OPTIMIZATION, "Missing width/height (causes layout shift)", f"width={w!r} height={h!r}")
    nat = i.get("natural")
    try:
        if nat and w and int(float(w)) and nat[0] > 2.5 * int(float(w)) and not img.get("srcset"):
            flag(OPTIMIZATION, "Image pixels much larger than displayed", f"{nat[0]}x{nat[1]} px file for width={w}",
                 f"about {int(float(w)) * 2} px wide (2x display size)")
    except (ValueError, OverflowError):   # width="100%", "auto", "NaN", "Infinity" ...
        pass

    # loading & responsive
    loading = img.get("loading") or ("eager" if img.get("fetchpriority") == "high" else "")
    if index >= 2 and loading != "lazy":
        flag(OPTIMIZATION, "Below-the-fold image not lazy-loaded", f"loading={loading or '(default eager)'}",
             'loading="lazy"')
    if index == 0 and loading == "lazy" and not fill:
        flag(OPTIMIZATION, "First (likely LCP) image is lazy-loaded", 'loading="lazy"', "eager + fetchpriority=high")
    if not img.get("srcset") and i.get("format") not in ("SVG",) and (i.get("bytes") or 0) > 30 * 1024:
        flag(OPTIMIZATION, "No srcset (not responsive)", "no srcset")
    is_next = bool(img.get("data-nimg")) or "/_next/image" in src

    # file name quality
    stem = re.sub(r"\.\w+$", "", name)
    if re.fullmatch(r"(img|image|dsc|photo|screenshot|untitled|pxl)?[-_ ]?\d+|[a-f0-9-]{16,}", stem, re.I):
        flag(OPTIMIZATION, "Non-descriptive file name", name)
    elif re.search(r"[A-Z ]|_", stem):
        flag(OPTIMIZATION, "File name not lowercase-hyphenated", name)

    rows.append((loc, original[:200], alt if alt is not None else "(missing)", i.get("status"), i.get("bytes"),
                 i.get("format"), f"{w}x{h}" if w and h else ("fill" if fill else ""),
                 f"{nat[0]}x{nat[1]}" if nat else "", loading or "(default eager)", "yes" if img.get("srcset") else "no",
                 "yes" if is_next else "no", name,
                 min((s for s, _ in issues), key=lambda s: [CRITICAL, IMPORTANT, OPTIMIZATION].index(s)) if issues else "OK",
                 "; ".join(m for _, m in issues)))

per_page = Counter(r[0] for r in rows)
audit.note("Images checked", len(rows))
audit.note("Unique image files", len(unique))
audit.note("Formats", ", ".join(f"{k}: {v}" for k, v in Counter(i["format"] for i in info.values() if i["format"]).items()))
audit.sheet("Images", ["Page", "Image URL", "Alt", "HTTP", "Bytes", "Format", "width x height attr", "Natural size",
                       "loading", "srcset", "next/image", "File name", "Severity", "Issues"], rows,
            (45, 55, 35, 6, 9, 7, 12, 12, 14, 7, 9, 30, 13, 70), severity_col=13)
audit.sheet("Images per page", ["Page", "<img> count"], sorted(per_page.items(), key=lambda kv: -kv[1]), (60, 12))
audit.save("Image_SEO_Report")
