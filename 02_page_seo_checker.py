"""
02 - Page (on-page) SEO checker
  title: missing / too short / too long / duplicate / multiple <title>
  meta description: missing / too short / too long / duplicate / multiple
  meta keywords (obsolete - reported only when present)
  H1: missing / multiple / empty / too short; H2-H6 counts
  topic presence: page topic (URL slug) in title and H1; title topic in description
  SEO-friendly URL (lowercase, hyphens, short, no parameters)

  python "py files/02_page_seo_checker.py" [--base URL]
"""
import re
from collections import defaultdict

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, meta, metas, parse_args, run_parallel,
                        select_pages, slug_words, text_of, topic_words)

TITLE_MIN, TITLE_MAX = 30, 60       # ideal 50-60
DESC_MIN, DESC_MAX = 70, 160        # ideal 150-160

args = parse_args("Page SEO checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("02_page_seo", "Page SEO Report", "On-Page SEO", site)
brand = ""


def check(loc):
    global brand
    audit.checked(loc)
    path = site.path(loc)
    res, soup = site.page(loc)
    row = {"url": loc, "status": res["status"]}
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']} {res['error']}")
        return row
    head = soup.head or soup
    brand = brand or meta(head, prop="og:site_name") or ""

    titles = head.find_all("title")
    title = text_of(titles[0]) if titles else ""
    row["title"] = title
    if not title:
        audit.add(loc, CRITICAL, "Title", "Title missing")
    elif len(title) < TITLE_MIN:
        audit.add(loc, IMPORTANT, "Title", "Title too short", current=f"{len(title)} chars: {title}",
                  expected=f"{TITLE_MIN}-{TITLE_MAX} characters (ideal 50-60)")
    elif len(title) > TITLE_MAX:
        audit.add(loc, IMPORTANT, "Title", "Title too long", current=f"{len(title)} chars: {title}",
                  expected=f"{TITLE_MIN}-{TITLE_MAX} characters (ideal 50-60)")
    if len(titles) > 1:
        audit.add(loc, IMPORTANT, "Title", "Multiple <title> tags", current=f"{len(titles)} <title> tags: "
                  + " | ".join(text_of(t)[:60] for t in titles[:4]), expected="1 <title>")

    descs = metas(head, name="description")
    desc = (descs[0].get("content") or "").strip() if descs else ""
    row["description"] = desc
    if not desc:
        audit.add(loc, CRITICAL, "Description", "Meta description missing")
    elif len(desc) < DESC_MIN:
        audit.add(loc, IMPORTANT, "Description", "Description too short", current=f"{len(desc)} chars: {desc}",
                  expected=f"{DESC_MIN}-{DESC_MAX} characters (ideal 150-160)")
    elif len(desc) > DESC_MAX:
        audit.add(loc, IMPORTANT, "Description", "Description too long", current=f"{len(desc)} chars: {desc}",
                  expected=f"{DESC_MIN}-{DESC_MAX} characters (ideal 150-160)")
    if len(descs) > 1:
        audit.add(loc, IMPORTANT, "Description", "Multiple meta descriptions", current=f"{len(descs)} tags",
                  expected="1 meta description")

    kw = meta(head, name="keywords")
    row["keywords"] = kw or ""
    if kw:
        audit.add(loc, OPTIMIZATION, "Meta keywords", "Meta keywords present (ignored by Google)", current=kw[:200])

    counts = {f"n_h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 7)}
    row.update(counts)
    h1s = [text_of(h) for h in soup.find_all("h1")]
    row["h1"] = " | ".join(h1s)
    if not h1s:
        audit.add(loc, CRITICAL, "H1", "Missing H1")
    else:
        if len(h1s) > 1:
            for extra in h1s[1:]:
                audit.add(loc, IMPORTANT, "H1", "Multiple H1", current=f"{len(h1s)} H1 tags", element=f"<h1> {extra[:100]}",
                          expected="1 H1", detail=f"first H1: {h1s[0][:100]}")
        if not h1s[0]:
            audit.add(loc, CRITICAL, "H1", "Empty H1")
        elif len(h1s[0]) < 10:
            audit.add(loc, IMPORTANT, "H1", "H1 too short to be meaningful", current=f"'{h1s[0]}' ({len(h1s[0])} chars)",
                      expected="a descriptive H1 of 10+ characters")
        if h1s[0] and title and h1s[0].strip().lower() == title.strip().lower():
            audit.add(loc, OPTIMIZATION, "H1", "H1 identical to title", current=h1s[0])
    if not counts["n_h2"]:
        audit.add(loc, OPTIMIZATION, "H2", "No H2 sub-headings", "structure longer pages with H2 sections")

    # topic presence: words from the URL slug are the page's topic
    topic = slug_words(path.rsplit("/", 1)[-1]) if path != "/" else set()
    row["topic"] = ", ".join(sorted(topic))
    if topic and title and not topic & topic_words(title, brand):
        audit.add(loc, OPTIMIZATION, "Topic", "Page topic not in title", current=title,
                  expected=f"title mentions one of: {', '.join(sorted(topic))}")
    if topic and h1s and h1s[0] and not topic & topic_words(" ".join(h1s), brand):
        audit.add(loc, OPTIMIZATION, "Topic", "Page topic not in H1", current=h1s[0],
                  expected=f"H1 mentions one of: {', '.join(sorted(topic))}")
    tw = topic_words(title, brand)
    if desc and tw and not tw & topic_words(desc, brand):
        audit.add(loc, OPTIMIZATION, "Topic", "Description doesn't mention the title topic", current=desc,
                  expected=f"description mentions one of: {', '.join(sorted(tw)[:8])}", detail=f"title: {title}")

    # SEO-friendly URL
    problems = []
    if path != path.lower():
        problems.append("uppercase")
    if "_" in path:
        problems.append("underscores")
    if re.search(r"%[0-9a-f]{2}|\s", path, re.I):
        problems.append("encoded characters")
    if len(path) > 75:
        problems.append(f"long ({len(path)} chars)")
    if path.count("/") > 3:
        problems.append(f"deep ({path.count('/')} levels)")
    if re.search(r"\d{5,}|[a-f0-9]{12,}", path):
        problems.append("IDs/hashes instead of words")
    if "?" in loc:
        problems.append("query parameters")
    for p in problems:
        audit.add(loc, OPTIMIZATION, "URL", "URL not SEO-friendly", current=f"{p}: {path}" + (f"?{loc.split('?', 1)[1]}" if "?" in loc else ""))
    row["url_ok"] = "yes" if not problems else ", ".join(problems)
    return row


print(f"Checking {len(pages)} pages ...")
rows = run_parallel(check, pages, args.workers)

for field, check_name in (("title", "Duplicate title"), ("description", "Duplicate description")):
    groups = defaultdict(list)
    for r in rows:
        if r.get(field):
            groups[r[field].strip().lower()].append(r["url"])
    for value, group in groups.items():
        if len(group) > 1:
            for u in group:
                others = [g for g in group if g != u]
                original = next(r[field] for r in rows if r["url"] == u)
                audit.add(u, CRITICAL, field.capitalize(), check_name, current=original[:160],
                          expected=f"a {field} unique to this page",
                          detail=f"also used on {len(others)} other page(s): " + ", ".join(others[:5]))

audit.sheet("Pages", ["URL", "HTTP", "Title", "Title len", "Meta description", "Desc len", "Meta keywords", "H1 text",
                      "#H1", "#H2", "#H3", "#H4", "#H5", "#H6", "Topic (slug)", "SEO-friendly URL"],
            [(r["url"], r["status"], r.get("title", ""), len(r.get("title", "")), r.get("description", ""),
              len(r.get("description", "")), r.get("keywords", ""), r.get("h1", ""), r.get("n_h1"), r.get("n_h2"), r.get("n_h3"),
              r.get("n_h4"), r.get("n_h5"), r.get("n_h6"), r.get("topic", ""), r.get("url_ok", "")) for r in rows],
            (55, 6, 50, 8, 60, 8, 30, 45, 5, 5, 5, 5, 5, 5, 22, 20))
audit.save("Page_SEO_Report")
