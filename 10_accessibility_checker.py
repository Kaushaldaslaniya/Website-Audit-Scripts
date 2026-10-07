"""
10 - Accessibility checker
  static (every page): image alt, empty alt, form/input labels, button + link accessible names, heading
      hierarchy, landmarks (main / header / nav / footer), <html lang>, duplicate IDs, broken aria-labelledby /
      aria-describedby references, invalid ARIA attributes and roles, aria-hidden on focusable elements,
      positive tabindex, skip-navigation link, iframe title, video captions, form error announcements
  browser (every page, real Chrome, --browser-workers in parallel): axe-core rules incl. colour contrast + ARIA, keyboard navigation
      (Tab order reaches the page), focus visibility, clickable elements not reachable by keyboard,
      touch target size on a phone viewport

  python "py files/10_accessibility_checker.py" [--base URL] [--no-browser]
  Browser checks need:  pip install playwright axe-playwright-python   (uses your installed Chrome)
"""
import re
from collections import Counter

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, describe, load_site, parse_args, run_browser_pages,
                        run_parallel, sample_pages, select_pages, text_of)

ARIA_ATTRS = set("""activedescendant atomic autocomplete braillelabel brailleroledescription busy checked colcount colindex
colindextext colspan controls current describedby description details disabled dropeffect errormessage expanded flowto grabbed
haspopup hidden invalid keyshortcuts label labelledby level live modal multiline multiselectable orientation owns placeholder
posinset pressed readonly relevant required roledescription rowcount rowindex rowindextext rowspan selected setsize sort valuemax
valuemin valuenow valuetext""".split())
ROLES = set("""alert alertdialog application article banner blockquote button caption cell checkbox code columnheader combobox
complementary contentinfo definition deletion dialog directory document emphasis feed figure form generic grid gridcell group
heading img insertion link list listbox listitem log main mark marquee math menu menubar menuitem menuitemcheckbox menuitemradio
meter navigation none note option paragraph presentation progressbar radio radiogroup region row rowgroup rowheader scrollbar
search searchbox separator slider spinbutton status strong subscript superscript switch tab table tablist tabpanel term textbox
time timer toolbar tooltip tree treegrid treeitem""".split())
FOCUSABLE = "a[href], button, input, select, textarea, [tabindex], summary, iframe"
AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
AXE_IMPACT = {"critical": CRITICAL, "serious": IMPORTANT, "moderate": OPTIMIZATION, "minor": OPTIMIZATION}

args = parse_args("Accessibility checker", lambda ap: (
    ap.add_argument("--no-browser", action="store_true", help="static checks only"),
    ap.add_argument("--browser-pages", choices=("sample", "all"), default=None,
                    help="pages for the Chrome checks (default: same as --pages)")))
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("10_accessibility", "Accessibility Report", "Accessibility", site)


def accessible_name(el, soup):
    if el.get("aria-label", "").strip() or el.get("title", "").strip():
        return True
    ids = el.get("aria-labelledby", "").split()
    if ids and any(soup.find(id=i) and text_of(soup.find(id=i)) for i in ids):
        return True
    if text_of(el):
        return True
    img = el.find(["img", "svg"])
    if img is not None and (img.get("alt", "").strip() or img.get("aria-label") or (img.find("title") and text_of(img.find("title")))):
        return True
    return False


def static(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    def add(sev, check, detail="", **kw):
        audit.add(loc, sev, "Static", check, detail, **kw)

    if not (soup.html and soup.html.get("lang")):
        add(IMPORTANT, "Missing <html lang>", current="(none)", expected='<html lang="en">')
    for img in soup.find_all("img"):
        if img.get("alt") is None:
            add(IMPORTANT, "Image without alt", current="(no alt attribute)", element=img.get("src", "")[:200])
    for svg in soup.find_all("svg", attrs={"role": "img"}):
        hidden = svg.get("aria-hidden") == "true" or svg.find_parent(attrs={"aria-hidden": "true"}) is not None
        if not hidden and not (svg.get("aria-label") or svg.get("aria-labelledby") or svg.find("title")):
            add(IMPORTANT, "svg role=img without a name", current="no aria-label / <title>", element=describe(svg))

    for field in soup.find_all(["input", "select", "textarea"]):
        if field.get("type") in ("hidden", "submit", "button", "reset", "image"):
            continue
        fid = field.get("id")
        labelled = (fid and soup.find("label", attrs={"for": fid})) or field.find_parent("label") \
            or field.get("aria-label") or field.get("aria-labelledby") or field.get("title")
        if not labelled:
            add(IMPORTANT, "Form field without a label",
                current="no <label>" + (f" (only placeholder '{field.get('placeholder')}')" if field.get("placeholder") else ""),
                element=describe(field))
    for b in soup.find_all(["button"]) + soup.find_all(attrs={"role": "button"}):
        if not accessible_name(b, soup):
            add(IMPORTANT, "Button without accessible name", current="(no name)", element=describe(b) or str(b)[:120])
    for a in soup.find_all("a", href=True):
        if not accessible_name(a, soup):
            add(IMPORTANT, "Link without accessible name", current="(no name)", element=describe(a))

    prev = 0
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        lvl = int(h.name[1])
        if prev and lvl > prev + 1:
            add(OPTIMIZATION, "Skipped heading level", current=f"H{prev} -> H{lvl}", expected=f"H{prev} -> H{prev + 1}",
                element=f"<h{lvl}> {text_of(h)[:80]}")
        prev = lvl

    mains = soup.find_all("main") + soup.find_all(attrs={"role": "main"})
    if not mains:
        add(IMPORTANT, "No <main> landmark", current="(none)", expected="1 <main>")
    elif len(mains) > 1:
        add(OPTIMIZATION, "More than one main landmark", current=f"{len(mains)} main landmarks", expected="1")
    for tag, role in (("header", "banner"), ("nav", "navigation"), ("footer", "contentinfo")):
        if not soup.find(tag) and not soup.find(attrs={"role": role}):
            add(OPTIMIZATION, f"No <{tag}> landmark", current="(none)", expected=f"<{tag}> or role={role}")

    ids = Counter(t["id"] for t in soup.find_all(id=True))
    for dup_id, n in ids.items():
        if n > 1:
            add(IMPORTANT, "Duplicate IDs", current=f'id="{dup_id}" used {n} times', expected="unique id",
                element=", ".join(describe(t, 60) for t in soup.find_all(id=dup_id)[:3]))
    referencing = {id(el): el for attr in ("aria-labelledby", "aria-describedby", "aria-controls")
                   for el in soup.find_all(attrs={attr: True})}
    for el in referencing.values():
        for attr in ("aria-labelledby", "aria-describedby", "aria-controls"):
            for ref in (el.get(attr) or "").split():
                if ref not in ids:
                    add(IMPORTANT, f"{attr} points to a missing id", current=f'{attr}="{ref}"', element=describe(el))
    for el in soup.find_all(True):
        for attr in el.attrs:
            if attr.startswith("aria-") and attr[5:] not in ARIA_ATTRS:
                add(IMPORTANT, "Invalid ARIA attribute", current=attr, element=describe(el))
        role = el.get("role")
        if role and not all(r in ROLES for r in role.split()):
            add(IMPORTANT, "Invalid ARIA role", current=f"role='{role}'", element=describe(el))
        if el.get("aria-hidden") == "true" and (el.name in ("a", "button", "input", "select", "textarea") and not el.get("tabindex") == "-1"):
            add(IMPORTANT, "aria-hidden on a focusable element", current='aria-hidden="true"', element=describe(el))
        ti = el.get("tabindex")
        if ti and ti.lstrip("-").isdigit() and int(ti) > 0:
            add(OPTIMIZATION, "Positive tabindex (breaks natural focus order)", current=f"tabindex={ti}",
                expected="tabindex 0 or -1", element=describe(el))

    first_links = soup.find_all("a", href=True)[:3]
    if not any(a["href"].startswith("#") and re.search(r"skip|main|content", a["href"] + text_of(a), re.I) for a in first_links):
        add(OPTIMIZATION, "No skip-navigation link", current="(none among the first links)")
    for f in soup.find_all("iframe"):
        if not f.get("title"):
            add(IMPORTANT, "iframe without title", current="(no title)", element=f.get("src", "")[:200])
    for v in soup.find_all("video"):
        if not v.find("track", kind=re.compile("captions|subtitles")) and not v.has_attr("muted"):
            add(IMPORTANT, "Video without captions track", current="(no <track kind=captions>)", element=v.get("src", "")[:200])
    if soup.find("form") and not soup.find(attrs={"aria-live": True}) and not soup.find(attrs={"role": re.compile("alert|status")}):
        add(OPTIMIZATION, "Form without aria-live / role=alert region for error messages", current="(none)",
            element=describe(soup.find("form")))


print(f"Static checks on {len(pages)} pages ...")
run_parallel(static, pages, args.workers)

# ------------------------------------------------------------------ browser checks
browser_rows = []
try:
    from axe_playwright_python.sync_playwright import Axe
    axe = Axe()
except Exception:
    axe = None


def browser_check(browser, loc):
    desktop = browser.context(width=1440, height=900)
    page = desktop.new_page()
    try:
        page.goto(site.to_fetch(loc), wait_until="networkidle", timeout=60000)
        # axe-core
        violations = []
        try:
            if axe:
                violations = axe.run(page).response.get("violations", [])
            else:
                page.add_script_tag(url=AXE_CDN)
                violations = page.evaluate("async () => (await axe.run(document)).violations")
        except Exception as e:
            audit.add(loc, OPTIMIZATION, "Browser", "axe-core could not run", current=str(e)[:150])
        for v in violations:
            sev = AXE_IMPACT.get(v.get("impact"), OPTIMIZATION)
            for node in v.get("nodes", []):
                target = " ".join(map(str, node["target"])) if isinstance(node.get("target"), list) else str(node.get("target"))
                summary = (node.get("failureSummary") or "").replace("Fix any of the following:", "").replace(
                    "Fix all of the following:", "").strip()
                audit.add(loc, sev, "axe-core", f"{v['id']}: {v['help']}", current=summary[:300] or v.get("impact", ""),
                          element=target[:200], description=v.get("description", ""),
                          fix=f"{summary[:200]} - see {v.get('helpUrl', '')}".strip(" -"),
                          expected="no axe-core violation", detail=f"impact {v.get('impact')}; html: {node.get('html', '')[:150]}")
            browser_rows.append((loc, "axe", v["id"], v.get("impact"), len(v.get("nodes", [])), v["help"], v.get("helpUrl", "")))

        # keyboard + focus visibility
        focus = page.evaluate(f"""async () => {{
            const focusable = [...document.querySelectorAll('{FOCUSABLE}')].filter(e => !e.disabled &&
                e.getAttribute('tabindex') !== '-1' && e.offsetParent !== null);
            return {{ total: focusable.length }};
        }}""")
        no_indicator, reached = [], set()
        for _ in range(min(25, focus["total"])):
            page.keyboard.press("Tab")
            info = page.evaluate("""() => {
                const e = document.activeElement; if (!e || e === document.body) return null;
                const s = getComputedStyle(e);
                const visible = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none'
                    || s.textDecorationLine.includes('underline') && !e.matches(':hover');
                return {tag: e.tagName.toLowerCase(), text: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 40),
                        visible, key: e.tagName + (e.id || '') + (e.getAttribute('href') || '') + (e.className || '')};
            }""")
            if not info:
                continue
            reached.add(info["key"])
            if not info["visible"]:
                no_indicator.append(f"<{info['tag']}> {info['text']}")
        if focus["total"] and not reached:
            audit.add(loc, CRITICAL, "Keyboard", "Tab key doesn't reach any element",
                      current=f"0 of {focus['total']} focusable elements reached")
        for el in dict.fromkeys(no_indicator):
            audit.add(loc, IMPORTANT, "Keyboard", "Focused elements without a visible focus indicator",
                      current="no outline / box-shadow on :focus", element=el)
        clickable = page.evaluate("""() => [...document.querySelectorAll('div, span, li, img, svg')].filter(e => {
                const s = getComputedStyle(e);
                return s.cursor === 'pointer' && !e.closest('a, button, label, summary, [role=button], [tabindex], input, select')
                    && e.offsetParent !== null && e.getBoundingClientRect().width > 0;
            }).slice(0, 8).map(e => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'))""")
        for el in clickable:
            audit.add(loc, IMPORTANT, "Keyboard", "Clickable elements not reachable by keyboard",
                      current="cursor:pointer on a non-focusable element", element=el)
        browser_rows.append((loc, "keyboard", "tab-stops", "", len(reached), f"{len(no_indicator)} without focus indicator", ""))
    except Exception as e:
        audit.add(loc, OPTIMIZATION, "Browser", "Page failed to load in browser", current=str(e)[:200])
    finally:
        desktop.close()

    # touch targets on a phone
    phone = browser.context(mobile=True, width=390, height=844)
    mpage = phone.new_page()
    try:
        mpage.goto(site.to_fetch(loc), wait_until="networkidle", timeout=60000)
        small = mpage.evaluate(f"""() => [...document.querySelectorAll('{FOCUSABLE}')].filter(e => e.offsetParent !== null)
            .map(e => {{ const r = e.getBoundingClientRect(); return {{w: r.width, h: r.height,
                label: (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 30),
                inline: getComputedStyle(e).display === 'inline' && e.closest('p, li') !== null}}; }})
            .filter(t => t.w > 0 && t.h > 0 && !t.inline && (t.w < 44 || t.h < 44))""")
        tiny = [t for t in small if t["w"] < 24 or t["h"] < 24]
        for t in tiny:
            audit.add(loc, IMPORTANT, "Touch targets", "Touch targets smaller than 24x24 px",
                      current=f"{int(t['w'])}x{int(t['h'])} px", expected="24x24 px minimum (44x44 recommended)",
                      element=t["label"], detail="390 px phone viewport")
        for t in small:
            if t not in tiny:
                audit.add(loc, OPTIMIZATION, "Touch targets", "Touch targets smaller than 44x44 px",
                          current=f"{int(t['w'])}x{int(t['h'])} px", expected="44x44 px", element=t["label"],
                          detail="390 px phone viewport")
        browser_rows.append((loc, "touch", "small-targets", "", len(small), f"{len(tiny)} under 24px", ""))
    except Exception as e:
        audit.add(loc, OPTIMIZATION, "Browser", "Page failed to load on phone viewport", current=str(e)[:200])
    finally:
        phone.close()


if not args.no_browser:
    targets = pages if (args.browser_pages or args.pages) == "all" else sample_pages(pages)
    print(f"Browser checks on {len(targets)} pages (axe-core: {'package' if axe else 'CDN'}, "
          f"{args.browser_workers} in parallel) ...")
    run_browser_pages(browser_check, targets, args.browser_workers, "browser pages")
    browser_rows.sort(key=lambda r: (r[0], r[1]))   # parallel workers finish in any order

audit.sheet("Browser results", ["Page", "Check", "Rule", "Impact", "Elements", "Description", "Help"], browser_rows,
            (50, 10, 28, 10, 9, 60, 50))
audit.save("Accessibility_Report")
