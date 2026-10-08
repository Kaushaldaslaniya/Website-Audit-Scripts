"""
18 - Image alt report
  Alt attribute of every <img> on every page: missing alt (Error), empty alt on an image that isn't marked decorative
  (Warning). Every image with a problem is its own issue row.
  Sheets: "Image Alt Summary" (per page: images, with alt, missing, empty, status) and "Image Issues" (per image).

  python "py files/18_image_alt_report.py" [--base URL]
"""
from urllib.parse import urljoin

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, describe, load_site, parse_args, run_parallel,
                        select_pages)

args = parse_args("Image alt report")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("18_image_alt", "Image Alt Report", "Image", site)
issue_rows = []


def analyze(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return (loc, "", "", "", "", "Error", f"HTTP {res['status']}")
    images = soup.find_all("img")
    with_alt = missing = empty = 0
    for n, img in enumerate(images, 1):
        src = img.get("src") or img.get("data-src") or ""
        image_url = urljoin(loc, src) if src and not src.startswith("data:") else (src[:40] + "..." if src else "(no src)")
        decorative = img.get("aria-hidden") == "true" or img.get("role") in ("presentation", "none")
        if not img.has_attr("alt"):
            missing += 1
            audit.add(loc, IMPORTANT, "Image alt", "Missing alt attribute", current="(no alt attribute)",
                      element=image_url[:200], detail=f"image #{n} of {len(images)}: {describe(img, 100)}")
            issue_rows.append((loc, n, image_url[:250], "Error", "Missing alt attribute"))
        elif not img["alt"].strip():
            if decorative:   # alt="" + aria-hidden / role=presentation is the correct markup for decoration
                with_alt += 1
            else:
                empty += 1
                audit.add(loc, OPTIMIZATION, "Image alt", "Empty alt (only correct for decorative images)",
                          current='alt=""', element=image_url[:200],
                          detail=f"image #{n} of {len(images)}; if decorative also add aria-hidden=\"true\"")
                issue_rows.append((loc, n, image_url[:250], "Warning", "Empty alt attribute"))
        else:
            with_alt += 1
    if missing:
        status, text = "Error", f"{missing} image(s) missing alt attribute"
    elif empty:
        status, text = "Warning", f"{empty} image(s) have empty alt attribute"
    else:
        status, text = "Correct", "All images have alt attributes"
    return (loc, len(images), with_alt, missing, empty, status, text)


print(f"Checking image alt text on {len(pages)} pages ...")
rows = run_parallel(analyze, pages, args.workers)
rows.sort(key=lambda r: ({"Error": 0, "Warning": 1}.get(r[5], 2), r[0]))
issue_rows.sort(key=lambda r: (r[0], r[1]))
audit.note("Images checked", sum(r[1] for r in rows if isinstance(r[1], int)))
audit.note("Pages with every image described", f"{sum(1 for r in rows if r[5] == 'Correct')} of {len(rows)}")
audit.sheet("Image Alt Summary", ["URL", "Total Images", "Images With Alt", "Missing Alt", "Empty Alt", "Status", "Issue"],
            rows, (60, 12, 15, 11, 10, 10, 45))
audit.sheet("Image Issues", ["Page URL", "Image Number", "Image URL", "Status", "Issue"], issue_rows, (60, 13, 80, 10, 30))
audit.save("Image_Alt_Report")
