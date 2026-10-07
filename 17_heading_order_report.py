"""
17 - Heading order report
  The heading-order rules on their own: the first heading must be the H1, and no level may be skipped going down
  (H2 -> H4). Every violation on a page is listed as its own issue (not just the first one).
  Sheet "Heading Order": URL, H1-H6 counts, heading order, Status (Correct / Incorrect), all problems.

  python "py files/17_heading_order_report.py" [--base URL]
"""
from collections import Counter

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, parse_args, run_parallel, select_pages,
                        text_of)

args = parse_args("Heading order report")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("17_heading_order", "Heading Order Report", "On-Page SEO", site)


def analyze(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return (loc, *[""] * 6, "", "Error", f"HTTP {res['status']}")
    heads = [(int(h.name[1]), text_of(h)) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    counts = Counter(level for level, _ in heads)
    order = " → ".join(f"H{level}" for level, _ in heads)
    problems = []
    if not heads:
        problems.append("No headings found")
        audit.add(loc, CRITICAL, "Heading order", "No headings on page", current="0 headings",
                  expected="an H1 followed by H2/H3 sections")
    else:
        if heads[0][0] != 1:
            problems.append(f"First heading is H{heads[0][0]}, expected H1")
            audit.add(loc, IMPORTANT, "Heading order", "First heading is not H1", current=f"H{heads[0][0]}",
                      expected="H1", element=f"<h{heads[0][0]}> {heads[0][1][:80]}")
        previous = 0
        for n, (level, text) in enumerate(heads, 1):
            if previous and level > previous + 1:
                problems.append(f"Skipped H{previous + 1} (H{previous} → H{level})")
                audit.add(loc, OPTIMIZATION, "Heading order", "Skipped heading level", current=f"H{previous} → H{level}",
                          expected=f"H{previous} → H{previous + 1}", element=f"heading #{n}: <h{level}> {text[:80]}")
            previous = level
    status = "Correct" if not problems else "Incorrect"
    return (loc, counts[1], counts[2], counts[3], counts[4], counts[5], counts[6], order[:3000], status,
            "Hierarchy is valid" if not problems else "; ".join(problems))


print(f"Checking heading order on {len(pages)} pages ...")
rows = run_parallel(analyze, pages, args.workers)
rows.sort(key=lambda r: (r[8] == "Correct", r[0]))
audit.note("Pages with a valid heading order", f"{sum(1 for r in rows if r[8] == 'Correct')} of {len(rows)}")
audit.sheet("Heading Order", ["URL", "H1", "H2", "H3", "H4", "H5", "H6", "Heading Order", "Status", "Issues"], rows,
            (55, 5, 5, 5, 5, 5, 5, 80, 11, 90))
audit.save("Heading_Order_Report")
