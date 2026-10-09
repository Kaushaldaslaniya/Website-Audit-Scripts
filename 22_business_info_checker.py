"""
22 - Business info checker (NAP: name, address, phone + contact links, footer, social profiles)
  phone:    every phone number written on the site, the confirmed number(s) from qa_config.json (or the most common
            header/footer number), written numbers that are not clickable tel: links, tel: links whose href doesn't
            match the number shown, invalid tel: hrefs, phone in the header, phone in JSON-LD vs on the page
  email:    mailto: href vs the address shown, invalid mailto:, addresses that are not clickable, confirmed emails
  address:  the same address on every page (and the confirmed one from qa_config.json), JSON-LD PostalAddress
  name:     business name in Organization JSON-LD, og:site_name, the title suffix and the copyright line agree
  footer:   required links (privacy, terms ... from qa_config.json; disclaimer on legal sites) present and working,
            copyright notice with the current year
  social:   links to social networks point at a real profile (not the network homepage / a share URL), respond,
            and every expected profile from qa_config.json is linked

  python "py files/22_business_info_checker.py" [--base URL]
"""
import re
from collections import Counter, defaultdict
from datetime import datetime
from threading import Lock
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, Audit, describe, fetch, load_site,
                        meta, parse_args, qa_config, run_parallel, select_pages, text_of)

try:
    import tldextract
    _extract = tldextract.TLDExtract(suffix_list_urls=())   # bundled suffix list: no network needed
except ImportError:   # fall back to the last two host labels
    tldextract = None

SOCIAL = {"facebook": "Facebook", "instagram": "Instagram", "twitter": "X / Twitter", "x": "X / Twitter",
          "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok", "pinterest": "Pinterest",
          "github": "GitHub", "behance": "Behance", "dribbble": "Dribbble", "clutch": "Clutch", "avvo": "Avvo",
          "yelp": "Yelp", "threads": "Threads", "medium": "Medium", "glassdoor": "Glassdoor", "upwork": "Upwork",
          "goodfirms": "GoodFirms", "trustpilot": "Trustpilot"}
SHARE_PATH = re.compile(r"^/(sharer|share|intent|shareArticle|pin/create|home|login|signup)\b", re.I)
PHONE = re.compile(r"(?<![\w/=.-])(\+\d{1,3}[\s.\-]?)?(\(\d{1,5}\)[\s.\-]?)?\d{2,5}(?:[\s.\-]\d{2,5}){1,4}(?![\w/-])"
                   r"|(?<![\w/=.-])\+\d{10,13}(?!\w)")
NANP = re.compile(r"^\D*(1[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\D*$")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", re.I)
YEAR = re.compile(r"\b(19|20)\d{2}\b")
LEGAL_SUFFIX = re.compile(r"[,.]?\s*\b(pvt\.?|private|ltd\.?|limited|llc|l\.l\.c\.|inc\.?|pllc|llp|plc|gmbh|"
                          r"corp\.?|co\.?)(?=\s|$)", re.I)

args = parse_args("Business info (NAP) checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
cfg = qa_config()
audit = Audit("22_business_info", "Business Info Report", "Business info", site)
lock = Lock()
THIS_YEAR = datetime.now().year

phones = defaultdict(lambda: {"shown": Counter(), "pages": set(), "zones": Counter(), "linked": 0})
emails = defaultdict(lambda: {"pages": set(), "zones": Counter(), "linked": 0})
addresses = defaultdict(set)          # normalised address -> pages
names = defaultdict(lambda: defaultdict(set))   # source -> name -> pages
schema_contacts = defaultdict(set)    # ("telephone"/"email", value) -> pages
social_links = defaultdict(set)       # url -> pages
footer_links = {}                     # page -> [(text, href)]
page_rows = []


def digits(s):
    return re.sub(r"\D", "", s or "")


def phone_key(s):
    """Comparable form of a number: the last 10 digits (ignores country code / trunk 0 / formatting)."""
    d = digits(s)
    return d[-10:] if len(d) >= 10 else d


def norm_name(s):
    s = LEGAL_SUFFIX.sub("", (s or "").replace("&amp;", "&")).strip(" ,.-|")
    return re.sub(r"\s+", " ", s).lower()


def zone(el):
    for p in [el, *el.parents]:
        if p.name == "header" or (p.name == "nav" and not p.find_parent("footer")):
            return "header"
        if p.name == "footer":
            return "footer"
    return "content"


def registered_domain(host):
    host = (host or "").lower()
    if tldextract:
        ext = _extract(host)
        return ext.domain, ext.subdomain
    parts = host.split(".")
    return (parts[-2] if len(parts) >= 2 else host), ".".join(parts[:-2])


def looks_like_phone(raw, tel_keys):
    d = digits(raw)
    if not 10 <= len(d) <= 13:
        return False
    if re.fullmatch(r"(?:(?:19|20)\d\d[\s.\-]*){2,}", raw.strip()):   # "2019 2020 2021"
        return False
    return raw.strip().startswith("+") or "(" in raw or bool(NANP.match(raw)) or phone_key(raw) in tel_keys


confirmed_phones = {phone_key(p) for p in cfg["phones"] if phone_key(p)}
confirmed_emails = {e.lower().strip() for e in cfg["emails"] if e.strip()}
tel_keys_seen = set(confirmed_phones)


def jsonld_nodes(soup):
    import json
    out = []

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            out.append(n)
            for v in n.values():
                if isinstance(v, (dict, list)):
                    walk(v)
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(s.string or s.get_text() or ""))
        except (ValueError, TypeError):
            pass
    return out


def scan(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return
    body = soup.body or soup
    row = {"tel_header": 0, "tel_footer": 0, "tel": 0, "mailto": 0, "address": "", "copyright": ""}

    # ---- tel: / mailto: links
    tel_keys = set()
    for a in body.find_all("a", href=True):
        href = a["href"].strip()
        shown = text_of(a)
        z = zone(a)
        if href.lower().startswith("tel:"):
            num = href[4:]
            row["tel"] += 1
            row[f"tel_{z}"] = row.get(f"tel_{z}", 0) + 1
            if not re.fullmatch(r"\+?[\d\-.\s()]{7,20}", num.replace("%20", " ")):
                audit.add(loc, IMPORTANT, "Phone", "Invalid tel: link", current=href[:80], element=describe(a),
                          expected="tel:+<country code><number>, digits only")
                continue
            key = phone_key(num)
            tel_keys.add(key)
            with lock:
                tel_keys_seen.add(key)
                phones[key]["linked"] += 1
            if len(digits(shown)) >= 7 and phone_key(shown) != key:
                audit.add(loc, CRITICAL, "Phone", "tel: link doesn't match the number shown",
                          current=f"shows '{shown[:40]}', dials {num}", element=describe(a),
                          expected="the tel: href dials the number that is displayed")
        elif href.lower().startswith("mailto:"):
            row["mailto"] += 1
            addr = href[7:].split("?")[0].strip().lower()
            if not EMAIL.fullmatch(addr):
                audit.add(loc, IMPORTANT, "Email", "Invalid mailto: link", current=href[:80], element=describe(a))
                continue
            with lock:
                emails[addr]["linked"] += 1
            shown_mail = EMAIL.search(shown)
            if shown_mail and shown_mail.group(0).lower() != addr:
                audit.add(loc, CRITICAL, "Email", "mailto: link doesn't match the address shown",
                          current=f"shows {shown_mail.group(0)}, opens {addr}", element=describe(a))
        elif href:
            host = urlparse(urljoin(loc, href)).netloc
            dom, sub = registered_domain(host)
            if dom in SOCIAL and not (dom == "x" and sub not in ("", "www")):
                with lock:
                    social_links[urljoin(loc, href).split("#")[0]].add(loc)

    # ---- written phone numbers / emails (visible text only)
    for s in body.find_all(string=True):
        parent = s.parent
        if type(s).__name__ != "NavigableString":   # <!-- comments --> / CDATA are not shown to visitors
            continue
        if parent is None or parent.name in ("script", "style", "noscript", "template", "title"):
            continue
        text = str(s)
        z = zone(parent)
        anchor = parent if (parent.name == "a" and parent.get("href")) else parent.find_parent("a", href=True)
        link_href = anchor.get("href", "") if anchor else ""
        for m in PHONE.finditer(text):
            raw = m.group(0).strip()
            if not looks_like_phone(raw, tel_keys | tel_keys_seen):
                continue
            key = phone_key(raw)
            with lock:
                p = phones[key]
                p["shown"][raw] += 1
                p["pages"].add(loc)
                p["zones"][z] += 1
            if not str(link_href).lower().startswith("tel:"):
                sev = IMPORTANT if z in ("header", "footer") or "contact" in loc else OPTIMIZATION
                audit.add(loc, sev, "Phone", "Phone number is not a clickable tel: link", current=raw,
                          element=f"{z}: {describe(parent, 90)}", expected=f'<a href="tel:+{digits(raw)}">{raw}</a>')
        for m in EMAIL.finditer(text):
            addr = m.group(0).lower()
            if re.search(r"\.(png|jpe?g|webp|svg|gif)$", addr):
                continue
            with lock:
                emails[addr]["pages"].add(loc)
                emails[addr]["zones"][z] += 1
            if not str(link_href).lower().startswith("mailto:"):
                audit.add(loc, OPTIMIZATION, "Email", "Email address is not a clickable mailto: link", current=addr,
                          element=f"{z}: {describe(parent, 90)}")

    # ---- address (visible <address> or the footer's PostalAddress text) + JSON-LD
    addr_el = body.find("address") or (body.find("footer") or soup).find(attrs={"itemtype": re.compile("PostalAddress")})
    if addr_el:
        row["address"] = text_of(addr_el)[:200]
        with lock:
            addresses[re.sub(r"[^a-z0-9]+", " ", row["address"].lower()).strip()].add(loc)
    for node in jsonld_nodes(soup):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        # the site's own organisation: an Organization node that has a logo or points at the homepage
        # (authors / clients described as Organization elsewhere on a page are not the business name)
        home = isinstance(node.get("url"), str) and urlparse(node["url"]).path in ("", "/")
        if any(t in ("Organization", "LocalBusiness", "LegalService", "ProfessionalService", "Corporation", "Attorney")
               for t in types) and isinstance(node.get("name"), str) and (node.get("logo") or home):
            with lock:
                names["Organization JSON-LD"][node["name"].strip()].add(loc)
        for k in ("telephone", "email"):
            v = node.get(k)
            for item in (v if isinstance(v, list) else [v]):
                if isinstance(item, str) and item.strip():
                    with lock:
                        schema_contacts[(k, item.strip())].add(loc)

    # ---- name sources
    site_name = meta(soup, prop="og:site_name")
    if site_name:
        with lock:
            names["og:site_name"][site_name].add(loc)
    title = text_of(soup.title) if soup.title else ""
    parts = re.split(r"\s[|–—]\s", title)   # "Page | Brand" ("-" is too common inside page titles)
    if len(parts) > 1:
        with lock:
            names["title suffix"][parts[-1].strip()].add(loc)

    # ---- footer
    footer = body.find_all("footer")
    footer = footer[-1] if footer else None
    if footer is None:
        audit.add(loc, IMPORTANT, "Footer", "No <footer> on page", current="(none)")
    else:
        links = [(text_of(a).lower(), a["href"]) for a in footer.find_all("a", href=True)]
        footer_links[loc] = links
        required = list(cfg["required_footer_links"]) + (["disclaimer"] if cfg["legal_site"] else [])
        for word in required:
            if not any(word.lower() in t or word.lower() in h.lower() for t, h in links):
                audit.add(loc, IMPORTANT, "Footer", f"Footer has no '{word}' link", current="(not found)",
                          expected=f"a footer link to the {word} page")
        ftext = text_of(footer)
        m = re.search(r"(©|&copy;|\(c\)|copyright)(.{0,120})", ftext, re.I)
        if not m:
            audit.add(loc, OPTIMIZATION, "Footer", "No copyright notice in the footer", current="(none)",
                      expected=f"© {THIS_YEAR} <business name>")
        else:
            row["copyright"] = re.split(r"(?i)(?<=reserved)", m.group(1) + m.group(2))[0][:120]
            years = [int(y.group(0)) for y in YEAR.finditer(m.group(2))]
            if not years:
                audit.add(loc, OPTIMIZATION, "Footer", "Copyright notice has no year", current=row["copyright"],
                          expected=f"© {THIS_YEAR}")
            elif max(years) < THIS_YEAR:
                audit.add(loc, IMPORTANT, "Footer", "Copyright year is out of date", current=row["copyright"],
                          expected=f"{THIS_YEAR} (generate it: new Date().getFullYear())")
            holder = re.sub(r"^[\s\d\-–,.]*", "", YEAR.sub("", m.group(2))).split(".")[0].split("|")[0]
            holder = re.sub(r"(?i)all rights reserved.*", "", holder).strip(" ,.-")
            if 2 < len(holder) < 80:
                with lock:
                    names["copyright"][holder].add(loc)
    with lock:
        page_rows.append((loc, row["tel_header"], row["tel_footer"], row["tel"], row["mailto"], row["address"],
                          row["copyright"]))


print(f"Checking business info on {len(pages)} pages ...")
run_parallel(scan, pages, args.workers)

# ------------------------------------------------------------------ phone numbers, site-wide
real_phones = {k: v for k, v in phones.items() if v["pages"]}
chrome_counts = Counter({k: v["zones"]["header"] + v["zones"]["footer"] for k, v in real_phones.items()})
if confirmed_phones:
    main_numbers = confirmed_phones
    seen = set(real_phones) | {k for k in tel_keys_seen}
    for k in confirmed_phones - seen:
        audit.site(CRITICAL, "Phone", "Confirmed phone number not found on the site", current=f"...{k}",
                   expected="the confirmed number (qa_config.json phones) shown and linked in header / footer")
else:
    main_numbers = {k for k, _ in chrome_counts.most_common(1) if chrome_counts[k]}
    in_chrome = [k for k, c in chrome_counts.items() if c]
    if len(in_chrome) > 1:
        audit.site(OPTIMIZATION, "Phone", "Several phone numbers in the header / footer",
                   current=", ".join(next(iter(real_phones[k]["shown"])) for k in in_chrome),
                   expected="one number per office - confirm them in qa_config.json phones",
                   fix="Confirm the right number(s) with the client and put them in py files/qa_config.json "
                       "\"phones\"; then every other number is reported.")
for k, v in real_phones.items():
    if k in main_numbers:
        continue
    shown = v["shown"].most_common(1)[0][0]
    chrome = v["zones"]["header"] + v["zones"]["footer"]
    sev = (IMPORTANT if chrome else INFO) if confirmed_phones else INFO
    for page in sorted(v["pages"])[:50]:
        audit.add(page, sev, "Phone", "Phone number differs from the confirmed number" if confirmed_phones
                  else "Other phone number on the site", current=shown,
                  expected="the confirmed number(s): " + ", ".join(sorted(main_numbers)) if main_numbers else "",
                  detail=f"on {len(v['pages'])} page(s), zones: {dict(v['zones'])}")
if real_phones and not any(r[1] for r in page_rows):
    audit.site(OPTIMIZATION if not cfg["legal_site"] else IMPORTANT, "Phone", "No clickable phone number in the header",
               current="no tel: link inside <header> on any page",
               expected="the main phone number as a tel: link in the desktop and mobile header")
for (kind, value), on in schema_contacts.items():
    if kind == "telephone" and main_numbers and phone_key(value) not in main_numbers | set(real_phones):
        audit.site(IMPORTANT, "Structured data", "Phone in JSON-LD is not shown on the site", current=value,
                   detail=f"on {len(on)} page(s)")
    if kind == "email" and value.lower().replace("mailto:", "") not in emails and not confirmed_emails:
        audit.site(OPTIMIZATION, "Structured data", "Email in JSON-LD is not shown on the site", current=value)

# ------------------------------------------------------------------ emails
for e in confirmed_emails - set(emails):
    audit.site(IMPORTANT, "Email", "Confirmed email address not found on the site", current=e)
for addr, v in emails.items():
    if confirmed_emails and addr not in confirmed_emails and (v["zones"]["header"] or v["zones"]["footer"]):
        audit.site(IMPORTANT, "Email", "Email in header / footer differs from the confirmed address", current=addr)

# ------------------------------------------------------------------ address
if cfg["address"]:
    want = re.sub(r"[^a-z0-9]+", " ", cfg["address"].lower()).strip()
    if not any(want in a for a in addresses):
        audit.site(IMPORTANT, "Address", "Confirmed address not found on the site", current=", ".join(list(addresses)[:3])
                   or "(no <address> element)", expected=cfg["address"])
if len(addresses) > 1:
    common = max(addresses, key=lambda a: len(addresses[a]))
    for a, on in addresses.items():
        if a != common and len(on) < len(addresses[common]):
            for page in sorted(on)[:50]:
                audit.add(page, OPTIMIZATION, "Address", "Address differs from the rest of the site", current=a[:150],
                          expected=common[:150])

# ------------------------------------------------------------------ business name
# a title suffix only counts when it is the site-wide pattern (used on 30%+ of the pages)
names["title suffix"] = defaultdict(set, {n: on for n, on in names.get("title suffix", {}).items()
                                          if len(on) >= 0.3 * max(1, len(pages))})
all_names = {(src, n) for src, d in names.items() for n in d}
canon = norm_name(cfg["company"]) if cfg["company"] else ""
if not canon and names.get("Organization JSON-LD"):
    canon = norm_name(max(names["Organization JSON-LD"], key=lambda n: len(names["Organization JSON-LD"][n])))
for src, n in sorted(all_names):
    if canon and norm_name(n) and canon not in norm_name(n) and norm_name(n) not in canon:
        on = names[src][n]
        audit.site(IMPORTANT if cfg["company"] else OPTIMIZATION, "Business name",
                   "Business name written differently", current=f"{src}: '{n}'",
                   expected=cfg["company"] or f"'{canon}' (Organization JSON-LD)", detail=f"on {len(on)} page(s)")
if not names.get("Organization JSON-LD"):
    audit.site(OPTIMIZATION, "Business name", "No Organization name in JSON-LD", current="(none)",
               expected="Organization / LocalBusiness JSON-LD with name, telephone, address")

# ------------------------------------------------------------------ footer links work
checked_targets = {}
for loc, links in list(footer_links.items())[:1] + list(footer_links.items())[-1:]:   # footer is shared
    for text, href in links:
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        target = urljoin(site.to_fetch(loc), href)
        if not site.is_internal(target) or target in checked_targets:
            continue
        status = fetch(site.to_fetch(target))["status"]
        checked_targets[target] = status
        if status != 200:
            audit.site(CRITICAL, "Footer", "Footer link is broken", current=f"HTTP {status}", element=f"'{text}' -> {href}")

# ------------------------------------------------------------------ social profiles
social_rows = []
expected_social = {u.rstrip("/").lower() for u in cfg["social_profiles"]}
for url, on in sorted(social_links.items()):
    p = urlparse(url)
    network = SOCIAL.get(registered_domain(p.netloc)[0], p.netloc)
    if p.path in ("", "/") or SHARE_PATH.match(p.path):
        audit.site(IMPORTANT, "Social", "Social link points to the network homepage / a share URL, not a profile",
                   current=url, detail=f"on {len(on)} page(s)", expected="https://<network>/<your-profile>")
        social_rows.append((network, url, "", "not a profile", len(on)))
        continue
    res = fetch(url, "HEAD", timeout=20)
    st = res["status"]
    verdict = "ok" if st in (200, 301, 302, 303, 307, 308) else \
        ("unverified (network blocks bots)" if st in (0, 400, 401, 403, 429, 999) else "broken")
    if verdict == "broken":
        audit.site(IMPORTANT, "Social", "Social profile link is broken", current=f"HTTP {st}", element=url,
                   detail=f"on {len(on)} page(s)")
    social_rows.append((network, url, st, verdict, len(on)))
if not social_links:
    audit.site(OPTIMIZATION, "Social", "No social profile links on the site", current="(none found)",
               expected="links to the business's profiles (LinkedIn, Facebook ...) - or confirm it has none",
               fix="Add the profile links to the footer / contact page, or list the confirmed profiles in "
                   "qa_config.json social_profiles.")
for want in expected_social - {u.rstrip("/").lower() for u in social_links}:
    audit.site(IMPORTANT, "Social", "Expected social profile is not linked", current="(not linked)", element=want)

audit.note("Confirmed phone(s)", ", ".join(cfg["phones"]) or "(not set - most common header/footer number used)")
audit.note("Main phone number(s)", ", ".join(next(iter(real_phones[k]["shown"])) if k in real_phones else k
                                             for k in main_numbers) or "(none found)")
audit.sheet("Phone numbers", ["Number (as shown)", "Last 10 digits", "Main / confirmed", "Pages", "Header", "Footer",
                              "Content", "tel: links", "Example page"],
            sorted(((v["shown"].most_common(1)[0][0], k, "yes" if k in main_numbers else "", len(v["pages"]),
                     v["zones"]["header"], v["zones"]["footer"], v["zones"]["content"], v["linked"],
                     sorted(v["pages"])[0]) for k, v in real_phones.items()), key=lambda r: -r[3]),
            (24, 14, 12, 8, 8, 8, 9, 10, 60))
audit.sheet("Emails", ["Email", "Pages", "Header", "Footer", "Content", "mailto: links"],
            sorted(((e, len(v["pages"]), v["zones"]["header"], v["zones"]["footer"], v["zones"]["content"], v["linked"])
                    for e, v in emails.items()), key=lambda r: -r[1]), (40, 8, 8, 8, 9, 12))
audit.sheet("Business names", ["Source", "Name", "Pages"],
            sorted(((src, n, len(on)) for src, d in names.items() for n, on in d.items()), key=lambda r: -r[2]),
            (24, 60, 8))
audit.sheet("Social links", ["Network", "URL", "HTTP", "Result", "Pages"], social_rows, (16, 70, 8, 30, 8))
audit.sheet("Contact per page", ["URL", "tel: in header", "tel: in footer", "tel: links", "mailto: links", "Address",
                                 "Copyright"], sorted(page_rows), (60, 12, 12, 10, 12, 60, 40))
audit.save("Business_Info_Report")
