"""
07 - Structured data (JSON-LD) checker
  JSON-LD present, JSON syntax / parse errors, @context, schema types found, the expected type for the
  page (Organization + WebSite on home, Service on service pages, BlogPosting on articles, ContactPage,
  CollectionPage ...), BreadcrumbList on nested pages, FAQPage when a FAQ section exists, LocalBusiness
  when an address is shown, required/recommended properties per type, duplicate structured data.

  python "py files/07_structured_data_checker.py" [--base URL]
"""
import json
import re
from collections import Counter

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, load_site, parse_args, run_parallel, select_pages,
                        text_of)

EXPECTED = [  # (path regex, acceptable types, label)
    (r"^/$", {"Organization", "WebSite"}, "Organization/WebSite"),
    (r"^/about-us$", {"Organization", "AboutPage"}, "Organization/AboutPage"),
    (r"^/contact-us$", {"ContactPage"}, "ContactPage"),
    (r"^/blog$", {"CollectionPage", "Blog"}, "CollectionPage/Blog"),
    (r"^/blog/[^/]+$", {"Article", "BlogPosting", "NewsArticle", "TechArticle"}, "BlogPosting/Article"),
    (r"^/portfolio$", {"CollectionPage", "ItemList"}, "CollectionPage"),
    (r"^/portfolio/[^/]+$", {"CreativeWork", "SoftwareApplication", "WebApplication", "MobileApplication", "WebSite"},
     "CreativeWork"),
    (r"^/(software-services|digital-services|intelligent-data-services|technologies|tools)/[^/]+$", {"Service", "SoftwareApplication"}, "Service"),
    (r"^/(services|software-services|digital-services|intelligent-data-services|technologies|industries|tools)$",
     {"Service", "CollectionPage", "ItemList", "OfferCatalog"}, "Service/CollectionPage"),
    (r"^/industries/[^/]+$", {"Service", "WebPage"}, "Service/WebPage"),
    (r"^/careers$", {"JobPosting", "CollectionPage", "WebPage", "Organization"}, "JobPosting/WebPage"),
]
REQUIRED = {  # type -> (required, recommended)
    "Organization": (["name", "url"], ["logo", "sameAs", "contactPoint", "address"]),
    "WebSite": (["name", "url"], ["potentialAction", "publisher"]),
    "WebPage": (["name"], ["url", "description", "breadcrumb"]),
    "Service": (["name"], ["description", "provider", "areaServed", "serviceType", "url"]),
    "Article": (["headline"], ["author", "datePublished", "dateModified", "image", "publisher", "mainEntityOfPage"]),
    "BlogPosting": (["headline"], ["author", "datePublished", "dateModified", "image", "publisher", "mainEntityOfPage"]),
    "BreadcrumbList": (["itemListElement"], []),
    "FAQPage": (["mainEntity"], []),
    "LocalBusiness": (["name", "address"], ["telephone", "openingHours", "geo", "url", "image"]),
    "ContactPage": (["name"], ["url", "mainEntity"]),
    "CollectionPage": (["name"], ["url", "mainEntity", "description"]),
    "JobPosting": (["title", "description", "datePosted", "hiringOrganization"], ["employmentType", "jobLocation", "validThrough"]),
    "CreativeWork": (["name"], ["description", "image", "author", "creator"]),
}

args = parse_args("Structured data checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("07_schema", "Structured Data Report", "Structured Data", site)
entity_rows = []


def walk(node, out):
    if isinstance(node, list):
        for n in node:
            walk(n, out)
    elif isinstance(node, dict):
        if "@graph" in node:
            walk(node["@graph"], out)
        if node.get("@type"):
            out.append(node)
        for k, v in node.items():
            if k != "@graph" and isinstance(v, (dict, list)):
                walk(v, out)


def types_of(entity):
    """The entity's @type values that are text (an object or number there is invalid JSON-LD - ignored, not a crash)."""
    t = entity.get("@type")
    return [x for x in (t if isinstance(t, list) else [t]) if isinstance(x, str) and x]


def check(loc):
    audit.checked(loc)
    path = site.path(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return (loc, 0, "", "")
    blocks = soup.find_all("script", type="application/ld+json")
    entities, raw_blocks, tops = [], [], []
    for b in blocks:
        raw = (b.string or b.get_text() or "").strip()
        raw_blocks.append(raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            audit.add(loc, CRITICAL, "Syntax", "JSON-LD parse error", current=f"{e.msg} at line {e.lineno}",
                      element=raw[:150])
            continue
        top = data if isinstance(data, list) else [data]
        for t in top:
            if isinstance(t, dict) and "schema.org" not in str(t.get("@context", "")) and "@graph" not in t:
                audit.add(loc, IMPORTANT, "Syntax", "Missing or wrong @context", current=str(t.get("@context"))[:60],
                          element=f"@type {t.get('@type')}")
        walk(data, entities)
        for t in top:
            if isinstance(t, dict):
                tops.extend(x for x in (t.get("@graph") if isinstance(t.get("@graph"), list) else [t]) if isinstance(x, dict))
    types = Counter(t for e in entities for t in types_of(e) if t)
    if not blocks:
        audit.add(loc, IMPORTANT, "Presence", "No JSON-LD on page", current="0 JSON-LD blocks")
    for raw, n in Counter(raw_blocks).items():
        if n > 1:
            audit.add(loc, IMPORTANT, "Duplicates", "Identical JSON-LD block repeated", current=f"{n} copies",
                      expected="1 copy", element=raw[:150])
    ids = Counter(e["@id"] for e in entities if isinstance(e.get("@id"), str) and e["@id"] and len(e) > 2)
    for i, n in ids.items():
        if n > 1:
            audit.add(loc, OPTIMIZATION, "Duplicates", "Same @id defined more than once", current=f"{i} defined {n} times")
    for t in ("Organization", "WebSite", "BreadcrumbList", "FAQPage"):
        if types[t] > 1 and t != "Organization":
            audit.add(loc, IMPORTANT, "Duplicates", f"{t} schema appears more than once", current=f"{types[t]} times",
                      expected="once per page")

    for rx, accepted, label in EXPECTED:
        if re.match(rx, path):
            if not accepted & set(types):
                audit.add(loc, IMPORTANT, "Page type", f"Missing {label} schema",
                          current=f"types found: {', '.join(sorted(types)) or 'none'}",
                          expected=f"one of: {', '.join(sorted(accepted))}")
            break
    if path.count("/") >= 2 and not types["BreadcrumbList"]:
        audit.add(loc, OPTIMIZATION, "Page type", "Missing BreadcrumbList on nested page", current="no BreadcrumbList",
                  expected="BreadcrumbList with one ListItem per path level")
    headings = " ".join(text_of(h) for h in soup.find_all(["h2", "h3"]))
    if re.search(r"\bFAQ|frequently asked", headings, re.I) and not types["FAQPage"]:
        audit.add(loc, OPTIMIZATION, "Page type", "FAQ section without FAQPage schema")
    if path in ("/contact-us", "/") and soup.find("address") and not (types["LocalBusiness"] or types["ProfessionalService"]):
        audit.add(loc, OPTIMIZATION, "Page type", "Address shown but no LocalBusiness/ProfessionalService schema")

    for e in tops:  # completeness only for top-level entities (nested ones are partial by design)
        for t in types_of(e):
            req, rec = REQUIRED.get(t, ([], []))
            if len(e) <= 2 and "@id" in e:   # a reference, not a full entity
                continue
            missing_req = [k for k in req if not e.get(k)]
            missing_rec = [k for k in rec if not e.get(k)]
            label = f"{t} '{(e.get('name') or e.get('headline') or e.get('@id') or '')}'"[:120]
            for k in missing_req:
                audit.add(loc, IMPORTANT, "Completeness", f"{t} missing required properties", current=f"no '{k}'",
                          expected=f"'{k}' property on {t}", element=label)
            for k in missing_rec:
                audit.add(loc, OPTIMIZATION, "Completeness", f"{t} missing recommended properties", current=f"no '{k}'",
                          expected=f"'{k}' property on {t}", element=label)
            if t == "BreadcrumbList":
                items = e.get("itemListElement") or []
                items = items if isinstance(items, list) else [items]   # a single ListItem object counts as one
                if len(items) < 2:
                    audit.add(loc, OPTIMIZATION, "Completeness", "BreadcrumbList has fewer than 2 items",
                              current=f"{len(items)} item(s)", expected="2+ items")
                for it in items:
                    if isinstance(it, dict) and not (it.get("position") and it.get("name") and (it.get("item") or it is items[-1])):
                        missing = [k for k in ("position", "name", "item") if not it.get(k)]
                        audit.add(loc, IMPORTANT, "Completeness", "Breadcrumb item missing position/name/item",
                                  current=f"missing {', '.join(missing)}", element=str(it)[:150])
            if t == "FAQPage":
                questions = e.get("mainEntity") or []
                for q in (questions if isinstance(questions, list) else [questions]):   # one Question is fine too
                    acc = q.get("acceptedAnswer") if (isinstance(q, dict) and isinstance(q.get("acceptedAnswer"), dict)) else {}
                    if not (isinstance(q, dict) and q.get("name") and acc.get("text")):
                        audit.add(loc, IMPORTANT, "Completeness", "FAQ question without name/acceptedAnswer.text",
                                  current="name or acceptedAnswer.text empty", element=str(q)[:150])
            entity_rows.append((loc, t, str(e.get("@id", "")), str(e.get("name") or e.get("headline") or ""),
                                ", ".join(k for k in e if not k.startswith("@"))[:300]))
    return (loc, len(blocks), ", ".join(f"{t}" + (f" x{n}" if n > 1 else "") for t, n in sorted(types.items())),
            "yes" if blocks else "no")


print(f"Checking {len(pages)} pages ...")
rows = [r for r in run_parallel(check, pages, args.workers) if r]
all_types = Counter()
for r in rows:
    for t in (r[2] or "").split(", "):
        if t:
            all_types[t.split(" x")[0]] += 1
audit.note("Schema types used", ", ".join(f"{t} ({n})" for t, n in all_types.most_common()))
audit.sheet("Pages", ["URL", "JSON-LD blocks", "Types", "Has JSON-LD"], rows, (60, 14, 80, 12))
audit.sheet("Entities", ["URL", "@type", "@id", "name / headline", "Properties"], entity_rows, (55, 18, 40, 45, 90))
audit.save("Structured_Data_Report")
