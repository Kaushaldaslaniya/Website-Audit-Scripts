"""
03 - Heading structure checker (H1-H6)
  Same rules as heading_checker.py (first heading is H1, no skipped level going down) plus:
  exactly one H1, empty headings, very long headings, duplicate headings on a page,
  H1 that only repeats the brand, and the full outline of every page.

  python "py files/03_heading_checker.py" [--base URL]
"""
from collections import Counter

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, parse_args, run_parallel, select_pages,
                        text_of)

args = parse_args("Heading structure checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("03_headings", "Heading Structure Report", "On-Page SEO", site)
outline_rows = []


def check(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return (loc, res["status"], *[""] * 6, "", "Error", f"HTTP {res['status']}")
    heads = [(int(h.name[1]), text_of(h)) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    counts = Counter(level for level, _ in heads)
    order = " > ".join(f"H{l}" for l, _ in heads)
    problems = []

    def flag(sev, check, problem, **kw):
        problems.append(problem)
        audit.add(loc, sev, "Headings", check, **kw)

    if not heads:
        flag(CRITICAL, "No headings on page", "No headings found", current="0 headings", expected="1 H1 + H2 sections")
    else:
        if heads[0][0] != 1:
            flag(IMPORTANT, "First heading is not H1", f"First heading is H{heads[0][0]}, expected H1",
                 current=f"H{heads[0][0]}", element=f"<h{heads[0][0]}> {heads[0][1][:80]}", expected="H1")
        if counts[1] == 0:
            flag(CRITICAL, "Missing H1", "Missing H1", current="0 H1 tags", expected="1 H1")
        elif counts[1] > 1:
            h1s = [t for l, t in heads if l == 1]
            for t in h1s[1:]:
                flag(IMPORTANT, "Multiple H1", f"{counts[1]} H1 tags", current=f"{counts[1]} H1 tags",
                     element=f"<h1> {t[:80]}", expected="1 H1", detail=f"first H1: {h1s[0][:80]}")
        prev = 0
        for n, (level, text) in enumerate(heads, 1):
            if prev and level > prev + 1:
                flag(OPTIMIZATION, "Skipped heading level", f"Skipped H{prev + 1} (H{prev} -> H{level})",
                     current=f"H{prev} -> H{level}", expected=f"H{prev} -> H{prev + 1}",
                     element=f"heading #{n}: <h{level}> {text[:80]}")
            prev = level
        for n, (level, text) in enumerate(heads, 1):
            if not text:
                flag(IMPORTANT, "Empty heading", f"Empty H{level}", current="(empty)", element=f"heading #{n}: <h{level}>")
            elif len(text) > 90:
                flag(OPTIMIZATION, "Very long heading", f"Long H{level}", current=f"{len(text)} chars",
                     element=f"<h{level}> {text[:80]}...", expected="under 90 characters")
        dupes = [(t, n) for t, n in Counter(t.lower() for l, t in heads if l <= 3 and t).items() if n > 1]
        for t, n in dupes:
            flag(OPTIMIZATION, "Duplicate heading text on page", f"Duplicate heading '{t[:40]}'",
                 current=f"'{t[:100]}' used {n} times", expected="unique heading text")

    for i, (level, text) in enumerate(heads, 1):
        outline_rows.append((loc, i, f"H{level}", ("    " * (level - 1)) + text[:150]))
    status = "Correct" if not problems else "Incorrect"
    problem = "Hierarchy is valid" if not problems else "; ".join(dict.fromkeys(problems))
    return (loc, res["status"], counts[1], counts[2], counts[3], counts[4], counts[5], counts[6], order[:3000], status,
            problem)


print(f"Checking {len(pages)} pages ...")
rows = run_parallel(check, pages, args.workers)
rows.sort(key=lambda r: (r[9] == "Correct", r[0]))
audit.note("Pages with valid hierarchy", sum(1 for r in rows if r[9] == "Correct"))
audit.sheet("Heading Order", ["URL", "HTTP", "H1", "H2", "H3", "H4", "H5", "H6", "Heading Order", "Status", "Issue"], rows,
            (55, 6, 5, 5, 5, 5, 5, 5, 80, 11, 80))
page_order = {p: i for i, p in enumerate(pages)}
outline_rows.sort(key=lambda r: (page_order.get(r[0], 99999), r[1]))
audit.sheet("Outline", ["URL", "#", "Level", "Heading text (indented by level)"], outline_rows, (55, 5, 7, 110))
audit.save("Heading_Structure_Report")
