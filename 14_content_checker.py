"""
14 - Content quality checker (text inside <main>)
  thin content (< 300 words), empty pages (< 50), very short pages (< 150)
  duplicate content (identical text), near-duplicate content (>= 90% shingle similarity)
  duplicate paragraphs repeated across many pages
  placeholder text: lorem ipsum, "coming soon", "test", TODO, TBD, dummy, sample text, example.com, [insert ...]
  AI / filler phrase patterns ("in today's fast-paced", "unlock the power", "delve" ...)
  articles (/blog/...): author, publication date, updated date
  readability: Flesch Reading Ease, average sentence length

  python "py files/14_content_checker.py" [--base URL]
"""
import hashlib
import random
import re
from collections import Counter, defaultdict

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, meta, parse_args, run_parallel,
                        select_pages, text_of)

THIN, SHORT, EMPTY = 300, 150, 50
PLACEHOLDER = re.compile(r"lorem ipsum|\blorem\b|coming soon|\bTBD\b|\bTODO\b|\bdummy (text|content)\b|sample text|"
                         r"placeholder|example\.com|\[insert[^\]]*\]|\btest (page|content|text|post)\b|^test$|"
                         r"your (company|business) name here|xxx+", re.I | re.M)
AI_PHRASES = ["in today's fast-paced", "in today's digital", "unlock the power", "unlock the full potential", "delve into",
              "in the ever-evolving", "ever-changing landscape", "game-changer", "seamlessly integrate", "elevate your",
              "harness the power", "look no further", "a testament to", "navigating the complexities", "it's important to note",
              "in conclusion", "cutting-edge solutions", "revolutionize", "embark on a journey", "tapestry"]
SHINGLE, HASHES = 5, 96

args = parse_args("Content quality checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("14_content", "Content Quality Report", "Content", site)
docs = {}
paragraphs = defaultdict(set)
random.seed(7)
SEEDS = [random.getrandbits(32) for _ in range(HASHES)]


def syllables(word):
    w = word.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def flesch(text):
    sentences = max(1, len(re.findall(r"[.!?]+(\s|$)", text)))
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 50:
        return None, None
    syl = sum(syllables(w) for w in words)
    return round(206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syl / len(words)), 1), round(len(words) / sentences, 1)


def minhash(words):
    sh = {hash(" ".join(words[i:i + SHINGLE])) & 0xFFFFFFFF for i in range(max(1, len(words) - SHINGLE + 1))}
    return [min((h ^ s) for h in sh) for s in SEEDS] if sh else None


def check(loc):
    audit.checked(loc)
    path = site.path(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return (loc, 0, "", "", "", "", "")
    main = soup.find("main") or soup.body or soup
    for t in main.find_all(["script", "style", "noscript", "svg", "template", "nav", "footer"]):
        t.decompose()
    text = text_of(main)
    words = text.split()
    n = len(words)
    if n < EMPTY:
        audit.add(loc, CRITICAL, "Length", "Empty page (almost no text)", current=f"{n} words in <main>",
                  expected=f"{THIN}+ words")
    elif n < SHORT:
        audit.add(loc, IMPORTANT, "Length", "Very short page", current=f"{n} words in <main>", expected=f"{THIN}+ words")
    elif n < THIN:
        audit.add(loc, OPTIMIZATION, "Length", "Thin content", current=f"{n} words in <main>", expected=f"{THIN}+ words")
    docs[loc] = (hashlib.md5(" ".join(words).lower().encode()).hexdigest(), minhash([w.lower() for w in words]))
    for p in main.find_all(["p", "li"]):
        t = text_of(p)
        if len(t) >= 80:
            paragraphs[t.lower()].add(loc)

    for hit in {m.group(0).strip().lower(): m.start() for m in PLACEHOLDER.finditer(text)}.items():
        word, pos = hit
        audit.add(loc, IMPORTANT, "Placeholder", "Placeholder / test text on page", current=word,
                  element=f"...{text[max(0, pos - 60):pos + 60]}...")
    low = text.lower()
    found = [p for p in AI_PHRASES if p in low]
    if len(found) >= 3:
        for phrase in found:
            i = low.find(phrase)
            audit.add(loc, OPTIMIZATION, "Style", "Generic AI/filler phrasing", current=f"'{phrase}'",
                      element=f"...{text[max(0, i - 50):i + len(phrase) + 50]}...",
                      detail=f"{len(found)} filler phrases on this page")

    author = date_pub = date_mod = ""
    if re.match(r"^/blog/[^/]+$", path):
        author = meta(soup, name="author") or meta(soup, prop="article:author") or ""
        date_pub = meta(soup, prop="article:published_time") or ""
        date_mod = meta(soup, prop="article:modified_time") or ""
        ld = " ".join(s.get_text() for s in soup.find_all("script", type="application/ld+json"))
        author = author or ("schema" if '"author"' in ld else "") or (text_of(soup.find(attrs={"rel": "author"})) or "")
        date_pub = date_pub or ("schema" if '"datePublished"' in ld else "") or \
            ((soup.find("time", datetime=True) or {}).get("datetime", "") if soup.find("time", datetime=True) else "")
        date_mod = date_mod or ("schema" if '"dateModified"' in ld else "")
        if not author:
            audit.add(loc, IMPORTANT, "Article", "Article without author", current="(none found)",
                      expected="meta author / article:author / JSON-LD author")
        if not date_pub:
            audit.add(loc, IMPORTANT, "Article", "Article without publication date", current="(none found)",
                      expected="article:published_time / JSON-LD datePublished / <time datetime>")
        if not date_mod:
            audit.add(loc, OPTIMIZATION, "Article", "Article without updated date (dateModified)", current="(none found)",
                      expected="article:modified_time / JSON-LD dateModified")
    score, avg_sentence = flesch(text)
    if score is not None and score < 30:
        audit.add(loc, OPTIMIZATION, "Readability", "Very difficult to read",
                  current=f"Flesch {score}, {avg_sentence} words/sentence", expected="Flesch 50+")
    elif avg_sentence and avg_sentence > 28:
        audit.add(loc, OPTIMIZATION, "Readability", "Long sentences", current=f"{avg_sentence} words per sentence",
                  expected="under 25 words per sentence")
    return (loc, n, score if score is not None else "", avg_sentence or "", author, date_pub, date_mod)


print(f"Reading {len(pages)} pages ...")
rows = run_parallel(check, pages, args.workers)

# exact duplicates
by_hash = defaultdict(list)
for loc, (h, _) in docs.items():
    by_hash[h].append(loc)
for group in by_hash.values():
    if len(group) > 1:
        for u in group:
            others = [g for g in group if g != u]
            audit.add(u, CRITICAL, "Duplicate", "Duplicate content (identical text)",
                      current=f"identical to {len(others)} other page(s)", element=", ".join(others[:5]))
# near duplicates
near_rows = []
items = [(loc, sig) for loc, (h, sig) in docs.items() if sig]
print(f"Comparing {len(items)} pages for near-duplicates ...")
exact = {u for g in by_hash.values() if len(g) > 1 for u in g}
for i in range(len(items)):
    a, sa = items[i]
    for j in range(i + 1, len(items)):
        b, sb = items[j]
        sim = sum(x == y for x, y in zip(sa, sb)) / HASHES
        if sim >= 0.9 and not (a in exact and b in exact):
            near_rows.append((a, b, round(sim * 100)))
for a, b, sim in near_rows:
    audit.add(a, IMPORTANT, "Duplicate", "Near-duplicate content", current=f"{sim}% similar", element=b,
              expected="under 90% similar")
    audit.add(b, IMPORTANT, "Duplicate", "Near-duplicate content", current=f"{sim}% similar", element=a,
              expected="under 90% similar")
# repeated paragraphs
para_rows = sorted(((len(p_urls), text[:200], sorted(p_urls)[0]) for text, p_urls in paragraphs.items() if len(p_urls) >= 5),
                   reverse=True)
for count, text, example in para_rows[:40]:
    audit.site(OPTIMIZATION, "Duplicate", "Paragraph repeated on many pages", current=f"on {count} pages",
               element=text[:200], detail=f"e.g. {example}")

audit.note("Average words per page", round(sum(r[1] for r in rows) / max(1, len(rows))))
audit.sheet("Pages", ["URL", "Words", "Flesch", "Words/sentence", "Author", "Published", "Updated"], rows, (60, 8, 8, 14, 20, 26, 26))
audit.sheet("Near duplicates", ["Page A", "Page B", "Similarity %"], sorted(near_rows, key=lambda r: -r[2]), (60, 60, 12))
audit.sheet("Repeated paragraphs", ["Pages", "Paragraph", "Example page"], para_rows, (8, 120, 55))
audit.save("Content_Quality_Report")
