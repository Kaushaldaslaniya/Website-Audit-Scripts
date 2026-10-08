"""
26 - Text quality checker (text hygiene: what visitors and search results actually read)
  odd characters:  HTML entities shown as text (&amp; &#39; &hellip; - double-encoded), mojibake (â€™ Ã© �) in the
                   title, meta description, social tags, headings and body text
  capitalisation:  title / H1 in ALL CAPS or all lowercase or with extra spaces, ALL CAPS phrases typed in the HTML
                   (use CSS text-transform so screen readers and search snippets get normal text)
  leftovers:       qa_config.json forbidden_terms (old vendor / brand / staging names) anywhere in the page HTML

  Spelling, grammar, punctuation and spacing are checked by 31_english_grammar_checker.py (LanguageTool).

  python "py files/26_text_quality_checker.py" [--base URL]
"""
import re

from seo_common import (IMPORTANT, OPTIMIZATION, Audit, describe, load_site, meta, parse_args, qa_config, run_parallel,
                        select_pages, text_blocks, text_of)

args = parse_args("Text quality checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
cfg = qa_config()
audit = Audit("26_text_quality", "Text Quality Report", "Text quality", site)

ENTITY = re.compile(r"&(amp|lt|gt|quot|apos|nbsp|hellip|mdash|ndash|rsquo|lsquo|rdquo|ldquo|copy|reg|trade|#\d{2,5}|"
                    r"#x[0-9a-f]{2,4});", re.I)
MOJIBAKE = re.compile(r"â€[™œ\x9d“”˜¦\"]|â€|Ã[©¨¢ª«¶¼½§¤±³]|Â[ ·»«©®°]|ï¿½|�")
# three or more capitalised words of 6+ letters in a row: acronyms (SEO, HTML, GDPR) are shorter and not reported
CAPS_RUN = re.compile(r"\b(?:[A-Z][A-Z'’&-]{2,}\s+){2,}[A-Z][A-Z'’&-]{2,}\b")
forbidden = [t.lower() for t in cfg["forbidden_terms"] if t.strip()]
row_data = []


def acronyms_only(words):
    """True when every all-caps token is short enough to be an acronym (SEO, HTML, GDPR, HIPAA)."""
    return all(len(w.strip("'’&-")) <= 5 for w in words)


def check_odd(loc, where, text, element=""):
    hit = ENTITY.search(text)
    if hit:
        meta_field = where in ("title", "meta description", "og:title", "og:description")
        audit.add(loc, IMPORTANT if meta_field else OPTIMIZATION, "Odd characters",
                  f"HTML entity shown as text in the {where}" if meta_field else "HTML entity shown as text on the page",
                  current=f"'{hit.group(0)}' in: {text[max(0, hit.start() - 40):hit.end() + 40]}", element=element,
                  expected="the real character (& ' …)", fix="The text is HTML-escaped twice: store plain text (not "
                  "&amp;-encoded) in the data / CMS and let React escape it once.")
    hit = MOJIBAKE.search(text)
    if hit:
        audit.add(loc, IMPORTANT, "Odd characters", f"Garbled characters (mojibake) in the {where}",
                  current=f"'{hit.group(0)}' in: {text[max(0, hit.start() - 40):hit.end() + 40]}", element=element,
                  expected="’ “ é … as intended", fix="The text was saved / imported with the wrong encoding: re-import "
                  "it as UTF-8 or replace the broken sequences.")


def check_case(loc, where, text):
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(letters) < 8:
        return
    if letters.isupper() and not acronyms_only(re.findall(r"[A-Z]{2,}", text)):
        audit.add(loc, OPTIMIZATION, "Capitalisation", f"{where} in ALL CAPS", current=text[:120],
                  expected="Title Case or Sentence case (uppercase via CSS if the design needs it)")
    elif letters.islower():
        audit.add(loc, OPTIMIZATION, "Capitalisation", f"{where} all lowercase", current=text[:120],
                  expected="Title Case or Sentence case")
    if text != text.strip() or "  " in text:
        audit.add(loc, OPTIMIZATION, "Capitalisation", f"Extra spaces in the {where}", current=repr(text[:120]),
                  expected="single spaces, no leading / trailing space")


def scan(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, IMPORTANT, "Status", "Page not reachable", current=f"HTTP {res['status']}")
        return
    raw_title = soup.title.string if soup.title and soup.title.string else (text_of(soup.title) if soup.title else "")
    fields = {"title": raw_title or "", "meta description": meta(soup, name="description") or "",
              "og:title": meta(soup, prop="og:title") or "", "og:description": meta(soup, prop="og:description") or ""}
    for where, value in fields.items():
        if value:
            check_odd(loc, where, value)
    if fields["title"]:
        check_case(loc, "Title", fields["title"])
    h1 = soup.find("h1")
    if h1 and text_of(h1):
        check_case(loc, "H1", text_of(h1))

    caps = 0
    blocks = text_blocks(soup)
    for el, text, _ in blocks:
        check_odd(loc, "text", text, describe(el, 80))
        m = CAPS_RUN.search(text)
        if m and caps < 10 and not acronyms_only(m.group(0).split()):
            caps += 1
            audit.add(loc, OPTIMIZATION, "Capitalisation", "ALL CAPS typed in the text (use CSS text-transform)",
                      current=m.group(0)[:100], element=describe(el, 80),
                      expected="normal case in the HTML + text-transform: uppercase in CSS",
                      fix="Type the words in normal case and add the Tailwind class 'uppercase' (CSS "
                          "text-transform) where the design shows capitals.")

    if forbidden:
        html = res["content"].decode("utf-8", "replace").lower()
        for term in forbidden:
            i = html.find(term)
            if i >= 0:
                blog = "/blog/" in loc
                audit.add(loc, OPTIMIZATION if blog else IMPORTANT, "Leftovers", "Forbidden / leftover term on the page",
                          current=f"'{term}' ({html.count(term)}x)", element=html[max(0, i - 80):i + 80].replace("\n", " "),
                          expected="none of qa_config.json forbidden_terms",
                          fix="Remove or replace the term (old vendor, old brand, staging name ...). Inside old blog "
                              "posts an in-text mention can be fine - review it." if blog else
                              "Remove or replace the term (old vendor, old brand, staging name ...).")
    row_data.append((loc, len(blocks), caps))


print(f"Checking text on {len(pages)} pages ...")
run_parallel(scan, pages, args.workers)
row_data.sort(key=lambda r: r[0])
audit.sheet("Pages", ["URL", "Text sections", "ALL CAPS phrases"], row_data, (70, 14, 16))
audit.save("Text_Quality_Report")
