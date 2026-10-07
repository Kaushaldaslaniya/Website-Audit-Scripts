"""
08 - Multilingual / hreflang checker
  hreflang tags: present, valid language (ISO 639-1) and optional country (ISO 3166-1) codes, absolute URLs,
  self-reference, x-default, every expected language, alternates return 200, return links (the alternate page
  links back), duplicate hreflang codes / one URL for several languages.
  language versions: every page is requested once per language - as /it/<path> or, when the site keeps one URL and
  chooses the language by a "lang" cookie (this site), as <path> with that cookie. A 404 there means visitors using
  that language can't open the page. Also: <html lang> matches, content / title / description translated,
  "Vary: Cookie" for cookie-based languages, canonical.

  python "py files/08_hreflang_checker.py" [--base URL] [--languages en,it,de,fr,es]
"""
import hashlib
import re
from collections import Counter
from urllib.parse import urljoin

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, fetch, has_rel, load_site, main_text, meta, norm,
                        parse_args, run_parallel, select_pages)

ISO_LANG = set("aa ab af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz ee el "
               "en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it "
               "iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms "
               "mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si "
               "sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo "
               "xh yi yo za zh zu".split())

args = parse_args("hreflang checker", lambda ap: ap.add_argument("--languages", default="en,it,de,fr,es"),
                  default_pages="sample")
LANGS = [l.strip() for l in args.languages.split(",") if l.strip()]
DEFAULT_LANG = LANGS[0]
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("08_hreflang", "Hreflang Report", "Technical SEO", site)
alt_rows, route_rows = [], []


def alternates_of(soup, page_url):
    out = []
    for l in (soup.head or soup).find_all("link", rel=lambda v: v and has_rel(v, "alternate")):
        if l.get("hreflang"):
            out.append((l["hreflang"].strip(), urljoin(page_url, l.get("href", "").strip()), l.get("href", "")))
    return out


def fingerprint(soup):
    return hashlib.md5(main_text(soup).lower().encode()).hexdigest()


def check(loc):
    audit.checked(loc)
    path = site.path(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    html_lang = (soup.html.get("lang", "") if soup.html else "").lower()
    if not html_lang:
        audit.add(loc, IMPORTANT, "Language", "Missing <html lang>", current="(none)", expected=f'<html lang="{DEFAULT_LANG}">')
    elif html_lang.split("-")[0] != DEFAULT_LANG:
        audit.add(loc, IMPORTANT, "Language", "Default-language page has a different <html lang>", current=html_lang,
                  expected=DEFAULT_LANG)

    alts = alternates_of(soup, loc)
    codes = Counter(c.lower() for c, _, _ in alts)
    if not alts:
        audit.add(loc, IMPORTANT, "hreflang", "No hreflang tags", current="0 hreflang links",
                  expected=f"hreflang for {', '.join(LANGS)} + x-default")
    else:
        for code, n in codes.items():
            if n > 1:
                audit.add(loc, IMPORTANT, "hreflang", "Duplicate hreflang code", current=f"{code} x{n}")
        for code, href, raw in alts:
            c = code.lower()
            m = re.fullmatch(r"([a-z]{2})(?:-([a-z]{2}))?", c)
            if c != "x-default" and (not m or m.group(1) not in ISO_LANG):
                audit.add(loc, IMPORTANT, "hreflang", "Invalid hreflang language code", current=code, element=href)
            elif m and m.group(2) and m.group(2) in ("uk", "en", "eu"):
                audit.add(loc, IMPORTANT, "hreflang", "Invalid hreflang country code", current=code, element=href,
                          expected="ISO 3166-1 code, e.g. en-GB")
            if not raw.startswith("http"):
                audit.add(loc, IMPORTANT, "hreflang", "hreflang URL is not absolute", current=raw, expected=href)
            alt_rows.append((loc, code, href))
        for lang in LANGS:
            if not any(c.lower().split("-")[0] == lang for c in codes):
                audit.add(loc, OPTIMIZATION, "hreflang", "Language missing from hreflang", current=f"no '{lang}'",
                          expected=f'<link rel="alternate" hreflang="{lang}" href="...">')
        if "x-default" not in codes:
            audit.add(loc, OPTIMIZATION, "hreflang", "Missing x-default", current="no x-default")
        if not any(norm(h) == norm(loc) for _, h, _ in alts):
            audit.add(loc, IMPORTANT, "hreflang", "No self-referencing hreflang", current="page not in its own hreflang set",
                      expected=f"hreflang link to {loc}")
        hrefs = Counter(norm(h) for c, h, _ in alts if c.lower() != "x-default")
        for h, n in hrefs.items():
            if n > 1:
                audit.add(loc, IMPORTANT, "hreflang", "Same URL used for several languages", current=f"{h} used {n} times")
        for code, href, _ in alts:
            if code.lower() == "x-default" or norm(href) == norm(loc):
                continue
            r = fetch(site.to_fetch(href) if site.is_internal(href) else href)
            if r["status"] != 200:
                audit.add(loc, IMPORTANT, "hreflang", "hreflang alternate not 200", current=f"HTTP {r['status']}",
                          element=f"{code}: {href}")
                continue
            from bs4 import BeautifulSoup
            back = alternates_of(BeautifulSoup(r["content"], "lxml"), href)
            if not any(norm(h) == norm(loc) for _, h, _ in back):
                audit.add(loc, IMPORTANT, "hreflang", "Missing return link", current=f"{href} doesn't link back",
                          element=f"hreflang {code}", expected=f"hreflang link back to {loc}")

    # ---------- localized routes (/it/<path> ...)
    en_print = fingerprint(soup)
    en_title = (soup.title.string or "").strip() if soup.title else ""
    en_desc = meta(soup, name="description") or ""
    for lang in LANGS[1:]:
        lpath = f"/{lang}" + ("" if path == "/" else path)
        prefixed = fetch(f"{site.base}{lpath}", allow_redirects=False)
        # This site keeps one URL per page and picks the language from a "lang" cookie (/it/... only redirects),
        # so the language version is what a visitor with that cookie gets at the normal URL.
        cookie_based = prefixed["status"] in (301, 302, 307, 308)
        r = fetch(site.to_fetch(loc), headers={"Cookie": f"lang={lang}"}) if cookie_based else fetch(f"{site.base}{lpath}")
        shown = f"{path} (cookie lang={lang})" if cookie_based else lpath
        target = loc if cookie_based else site.public(lpath)
        row = [path, lang, shown, r["status"], "", "", "", "", ""]
        if r["status"] != 200:
            audit.add(target, CRITICAL, "Language versions", "Page not available in a supported language",
                      current=f"{lang.upper()}: HTTP {r['status']}", expected="HTTP 200", element=shown)
        else:
            from bs4 import BeautifulSoup
            ls = BeautifulSoup(r["content"], "lxml")
            llang = (ls.html.get("lang", "") if ls.html else "").lower()
            canon = ls.find("link", rel=lambda v: v and has_rel(v, "canonical"))
            canon_href = urljoin(target, canon["href"]) if canon and canon.get("href") else ""
            title = (ls.title.string or "").strip() if ls.title else ""
            desc = meta(ls, name="description") or ""
            same_text = fingerprint(ls) == en_print
            row[4:9] = [llang, canon_href, title, "identical to English" if same_text else "translated",
                        "same as English" if desc == en_desc else "localized"]
            if llang.split("-")[0] != lang:
                audit.add(target, IMPORTANT, "Language", "<html lang> doesn't match the language served",
                          current=f"lang='{llang}'", expected=f"lang='{lang}'", element=shown)
            if same_text:
                audit.add(target, IMPORTANT, "Translation", "Language version shows untranslated (English) content",
                          current=f"{lang.upper()} content identical to English", element=shown)
            if title and title == en_title:
                audit.add(target, OPTIMIZATION, "Translation", "Title not translated", current=title,
                          expected=f"{lang.upper()} title", element=shown)
            if desc and desc == en_desc:
                audit.add(target, OPTIMIZATION, "Translation", "Meta description not translated", current=desc[:160],
                          expected=f"{lang.upper()} description", element=shown)
            if cookie_based and "cookie" not in r["headers"].get("Vary", "").lower():
                audit.add(target, IMPORTANT, "Caching", "Language chosen by cookie but response has no 'Vary: Cookie'",
                          current=f"Vary: {r['headers'].get('Vary', '(none)')}", element=shown)
            if not cookie_based and canon_href and norm(canon_href) == norm(loc):
                audit.add(target, OPTIMIZATION, "Canonical", "Localized page canonicalises to English",
                          current=canon_href, expected=target)
        route_rows.append(tuple(row))


print(f"Checking {len(pages)} pages x {len(LANGS)} languages ...")
run_parallel(check, pages, args.workers)
audit.note("Languages", ", ".join(LANGS))
audit.sheet("hreflang tags", ["Page", "hreflang", "Alternate URL"], alt_rows, (60, 10, 70))
audit.sheet("Language versions", ["Path", "Lang", "Requested as", "HTTP", "<html lang> / redirect", "Canonical", "Title",
                                 "Content", "Description"], route_rows, (40, 6, 40, 6, 22, 55, 50, 20, 16))
audit.save("Hreflang_Report")
