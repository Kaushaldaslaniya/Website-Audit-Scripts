"""
24 - Navigation & visual checker (real Chrome, real mouse / touch - not JavaScript clicks)
  desktop menu (1440 px, once per distinct header): every dropdown opens on hover or click, its links stay on the
      screen, every menu link responds 200, the expected top-level items from qa_config.json nav_expected exist,
      a phone number is visible in the header when the site has one
  mobile menu (390 px and 360 px): the menu button exists, lies inside the screen and can really be tapped (not
      covered / off-screen - a JavaScript click would hide that), the menu opens, its links are not cut off, its
      sub-menus open, it closes again, it contains every link of the desktop menu (same set of pages), tap-to-call
      in the mobile header
  zoom (every page): 120 % and 200 % browser zoom (1440 px window) without horizontal scrolling (WCAG 1.4.4 / 1.4.10)
  screenshots: desktop + phone (+ menu open, dropdown open) of the main pages for the visual review, in
      py files/report/<date>/screenshots/Navigation_Report_<time>/ (--screenshots all|main|none)
  other browsers: the main pages in Firefox and WebKit (Safari's engine) if Playwright has them installed
      (playwright install firefox webkit): page errors and horizontal scrolling, plus screenshots

  python "py files/24_navigation_checker.py" [--base URL] [--screenshots main] [--no-zoom] [--engines firefox,webkit]
"""
import hashlib
import re
from collections import defaultdict
from urllib.parse import urlparse

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, Audit, fetch, load_site, parse_args, qa_config,
                        run_browser_pages, sample_pages, screenshot_dir, select_pages)


def extra(ap):
    ap.add_argument("--screenshots", choices=("all", "main", "none"), default="main",
                    help="screenshots of every page, the main pages (default) or none")
    ap.add_argument("--no-zoom", action="store_true", help="skip the 120 %% / 200 %% zoom test")
    ap.add_argument("--engines", default="firefox,webkit", help="other browser engines to try ('' = none)")


args = parse_args("Navigation & visual checker", extra)
site, urls = load_site(args)
pages = select_pages(urls, args)
cfg = qa_config()
audit = Audit("24_navigation", "Navigation Report", "Navigation", site)
shots = screenshot_dir("Navigation_Report") if args.screenshots != "none" else None
main_pages = sample_pages(pages, per_section=0) or pages[:1]

COMMON_JS = """
window.__nav = {
  vis: el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
               return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity !== 0
                      && (!el.checkVisibility || el.checkVisibility({ opacityProperty: true, visibilityProperty: true })); },
  // visible AND (at least partly) on the screen - a closed drawer is often only moved off-screen with a transform
  shown: el => { const r = el.getBoundingClientRect();
                 return window.__nav.vis(el) && r.right > 0 && r.left < innerWidth && r.bottom > 0 && r.top < innerHeight; },
  tagMenu: () => [...document.querySelectorAll('a[href]')].filter(a => window.__nav.vis(a) && !a.hasAttribute('data-audit-seen')
                                                                    && a.closest('header, nav, [role=dialog], [role=menu], aside'))
      .forEach(a => a.setAttribute('data-audit-menulink', '')),
  menuShown: () => [...document.querySelectorAll('[data-audit-menulink]')].filter(a => window.__nav.shown(a)).length,
  links: () => [...document.querySelectorAll('a[href]')].filter(a => window.__nav.vis(a))
      .map(a => { const r = a.getBoundingClientRect();
                  return { href: a.href, fresh: !a.hasAttribute('data-audit-seen'), inHeader: !!a.closest('header, [role=banner]'),
                           inMenu: !!a.closest('header, nav, [role=banner], [role=menu], [role=dialog], [role=navigation], '
                                               + '[data-radix-popper-content-wrapper], [popover]'), text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 60),
                           left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top),
                           clipped: a.scrollWidth > a.clientWidth + 2 && getComputedStyle(a).overflow !== 'visible' }; }),
  header: () => document.querySelector('header') || document.querySelector('[role=banner]') || document.body,
  // remember which link elements are visible now; fresh() = links that became visible since (same href or not)
  ITEMS: 'a[href], button, [role=menuitem], [role=option], [role=menuitemradio]',
  mark: () => document.querySelectorAll(window.__nav.ITEMS).forEach(a => a.toggleAttribute('data-audit-seen', window.__nav.vis(a))),
  fresh: () => window.__nav.links().filter(l => l.fresh && l.inMenu),
  // menus can open lists of buttons / options (e.g. a language switcher), not only links
  freshItems: () => [...document.querySelectorAll(window.__nav.ITEMS)]
      .filter(e => window.__nav.vis(e) && !e.hasAttribute('data-audit-seen')).length,
};
"""
TRIGGERS_JS = """
() => { const N = window.__nav, h = N.header();
  const out = [];
  const add = (el, how) => { if (out.find(o => o.el === el) || !N.vis(el)) return; out.push({ el, how }); };
  h.querySelectorAll('[aria-haspopup], [aria-expanded="false"]').forEach(e => add(e, 'aria'));
  // containers (li, div.dropdown ...) holding links that stay hidden until hover / click; innermost first
  const trigger = c => [...c.querySelectorAll(':scope > a, :scope > button, :scope > span')].find(N.vis);
  const conts = [...h.querySelectorAll('nav li, nav div, nav [class*=drop], nav [class*=menu]')].filter(c =>
      [...c.querySelectorAll('a[href]')].some(a => !N.vis(a)) && trigger(c));
  conts.filter(c => !conts.some(o => o !== c && c.contains(o))).forEach(c => {
    add(trigger(c), 'container');
  });
  return out.slice(0, 20).map((o, i) => { o.el.setAttribute('data-audit-trigger', i);
      return { i, label: (o.el.innerText || o.el.getAttribute('aria-label') || '').trim().slice(0, 40), how: o.how }; });
}
"""
MENU_BUTTON_JS = """
() => { const N = window.__nav, h = N.header();
  const text = b => [b.getAttribute('aria-label'), b.innerText, typeof b.className === 'string' ? b.className : '',
                     b.getAttribute('aria-controls'), b.id].join(' ');
  const other = /language|\\blang\\b|locale|search|theme|dark|cart|account|login|close/i;   // not the menu toggle
  const all = [...h.querySelectorAll('button, [role=button], a[aria-controls]')].filter(b => !other.test(text(b)));
  const named = all.filter(b => /menu|navigation|\\bnav\\b|hamburger|toggle/i.test(text(b)));
  const b = named.find(N.vis) || all.filter(b => b.hasAttribute('aria-expanded')).find(N.vis) || named[0];
  if (!b) return null;
  b.setAttribute('data-audit-menu', '1');
  const r = b.getBoundingClientRect();
  return { label: (b.getAttribute('aria-label') || b.innerText || b.className || '').toString().trim().slice(0, 50),
           visible: N.vis(b), left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top),
           width: Math.round(r.width), height: Math.round(r.height), vw: document.documentElement.clientWidth,
           expanded: b.getAttribute('aria-expanded') };
}
"""
SUBMENU_JS = """
() => { const N = window.__nav;
  return [...document.querySelectorAll('[aria-expanded="false"], details:not([open]) > summary')]
    .filter(e => N.vis(e) && !e.matches('[data-audit-menu], [data-audit-sub]') && !e.closest('form')
            && !e.closest('footer') && e.closest('header, nav, [role=dialog], [role=menu], aside'))   // inside the menu
    .map(e => { const i = document.querySelectorAll('[data-audit-sub]').length; e.setAttribute('data-audit-sub', i);
        return { i, label: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 40) }; });
}
"""
OVERFLOW_JS = """
() => { const vw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
  let culprit = '';
  if (sw > vw + 1) { for (const el of (document.body ? document.body.querySelectorAll('*') : [])) { const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && r.width > 0 && getComputedStyle(el).position !== 'fixed') { culprit = name(el) + ' (right ' + Math.round(r.right) + 'px)'; break; } } }
  return { vw, sw, culprit };
}
"""


def path_of(href):
    p = urlparse(href)
    return (p.path.rstrip("/") or "/") if site.is_internal(href) else href.split("#")[0]


def nav_links(links, vw=None):
    """Internal page links from a list of visible links (no tel:/mailto:/#)."""
    return {path_of(l["href"]): l for l in links if l["href"].startswith("http") and "#" not in l["href"][-1:]}


def shot(page, name, full=False):
    if shots:
        try:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=full, timeout=20000)
        except Exception:
            pass


def slug(loc):
    return (site.path(loc).strip("/").replace("/", "_") or "home")[:80]


def header_key(loc):
    res, soup = site.page(loc)
    h = soup.find("header") if soup else None
    raw = re.sub(r"\s(class|id|style|data-[\w-]+|aria-[\w-]+)=\"[^\"]*\"", "", str(h or ""))
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


# ------------------------------------------------------------------ desktop menu
def desktop(browser, loc):
    ctx = browser.context(width=1440, height=900)
    ctx.add_init_script(COMMON_JS)
    page = ctx.new_page()
    r = {"page": loc, "triggers": [], "links": {}, "phone": False}
    try:
        page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
        page.wait_for_timeout(800)
        base = page.evaluate("() => window.__nav.links()")
        r["links"].update({k: v for k, v in nav_links(base).items() if v["inHeader"]})   # header links
        r["phone"] = page.evaluate("() => [...window.__nav.header().querySelectorAll('a[href^=\"tel:\"]')]"
                                   ".some(a => window.__nav.vis(a))")
        if loc == main_pages[0]:
            shot(page, "desktop_home_header")
        for t in page.evaluate(TRIGGERS_JS):
            el = page.locator(f"[data-audit-trigger='{t['i']}']").first
            page.evaluate("() => window.__nav.mark()")
            opened, how = [], ""
            for action in ("hover", "click"):
                try:
                    getattr(el, action)(timeout=3000)
                except Exception:
                    continue
                page.wait_for_timeout(450)
                opened = page.evaluate("() => window.__nav.fresh()")
                items = page.evaluate("() => window.__nav.freshItems()")
                if opened or items:
                    how = action
                    break
            vw = 1440
            off = [l for l in opened if l["right"] > vw + 1 or l["left"] < -1]
            r["triggers"].append({"label": t["label"], "opened": bool(how), "how": how, "links": len(opened),
                                  "offscreen": [f"{l['text']} ({l['left']}..{l['right']}px)" for l in off][:5]})
            r["links"].update({k: v for k, v in nav_links(opened).items() if v["inHeader"] or t["how"]})
            if opened and len(r["triggers"]) == 1:
                shot(page, "desktop_dropdown_open")
            page.mouse.move(5, 880)
            page.keyboard.press("Escape")
            page.wait_for_timeout(250)
    finally:
        ctx.close()
    return r


# ------------------------------------------------------------------ mobile menu
def mobile(browser, item):
    loc, w, h = item
    ctx = browser.context(mobile=True, width=w, height=h)
    ctx.add_init_script(COMMON_JS)
    page = ctx.new_page()
    r = {"page": loc, "w": w, "button": None, "tap": "", "opened": False, "links": {}, "cut": [], "subs": [],
         "closed": None, "phone": False}
    try:
        page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
        page.wait_for_timeout(800)
        r["phone"] = page.evaluate("() => [...window.__nav.header().querySelectorAll('a[href^=\"tel:\"]')]"
                                   ".some(a => window.__nav.vis(a) && a.getBoundingClientRect().top < 160)")
        if loc == main_pages[0]:
            shot(page, f"phone{w}_home_header")
        b = page.evaluate(MENU_BUTTON_JS)
        r["button"] = b
        if not b:
            return r
        r["links"].update({k: v for k, v in nav_links(page.evaluate("() => window.__nav.links()")).items()
                           if v["inHeader"]})
        page.evaluate("() => window.__nav.mark()")
        btn = page.locator("[data-audit-menu]").first
        try:
            btn.click(timeout=5000)            # a real tap: fails when off-screen / covered / not stable
            r["tap"] = "ok"
        except Exception as e:
            r["tap"] = str(e).split("\n")[0][:160]
            try:
                btn.dispatch_event("click")    # open it anyway to check the rest of the menu
            except Exception:
                return r
        page.wait_for_timeout(700)
        opened = page.evaluate("() => window.__nav.fresh()")
        page.evaluate("() => window.__nav.tagMenu()")
        r["opened"] = bool(opened)
        if not opened:
            return r
        if loc == main_pages[0]:
            shot(page, f"phone{w}_menu_open")
        vw = b["vw"]
        r["cut"] = [f"'{l['text']}' ({l['left']}..{l['right']}px)" for l in opened
                    if l["right"] > vw + 1 or l["left"] < -1 or l["clipped"]]
        r["links"].update(nav_links(opened))
        # open every sub-menu; ones revealed by another sub-menu (nested "More ..." toggles) are opened too
        pending, tried = page.evaluate(SUBMENU_JS), 0
        while pending and tried < 40:
            s = pending.pop(0)
            tried += 1
            el = page.locator(f"[data-audit-sub='{s['i']}']").first
            page.evaluate("() => window.__nav.mark()")
            try:
                el.click(timeout=3000)
            except Exception:
                r["subs"].append((s["label"], "can't be tapped"))
                continue
            page.wait_for_timeout(450)
            new = page.evaluate("() => window.__nav.fresh()")
            items = page.evaluate("() => window.__nav.freshItems()")
            r["links"].update(nav_links(new))
            r["cut"] += [f"'{l['text']}' ({l['left']}..{l['right']}px)" for l in new
                         if l["right"] > vw + 1 or l["left"] < -1]
            r["subs"].append((s["label"], f"{len(new)} links" if new else (f"{items} items" if items else "nothing opened")))
            pending += page.evaluate(SUBMENU_JS)
        # close: Escape, then the button again
        page.keyboard.press("Escape")
        page.wait_for_timeout(700)
        still = page.evaluate("() => window.__nav.menuShown()")
        if still:
            r["closed"] = "no"
            close = page.locator("button[aria-label*=lose i], [role=button][aria-label*=lose i], "
                                 "button:has-text('Close')").filter(visible=True)
            for candidate in ([close.first] if close.count() else []) + [btn]:
                try:
                    candidate.click(timeout=3000)
                except Exception:
                    continue
                page.wait_for_timeout(700)
                still = page.evaluate("() => window.__nav.menuShown()")
                if not still:
                    r["closed"] = "button"
                    break
        else:
            r["closed"] = "escape"
    finally:
        ctx.close()
    return r


# ------------------------------------------------------------------ zoom + screenshots (every page)
def zoom(browser, loc):
    out = {"page": loc}
    levels = [] if args.no_zoom else [(1.2, "120%"), (2.0, "200%")]
    for factor, label in levels:
        ctx = browser.context(width=int(1440 / factor), height=int(900 / factor), device_scale_factor=factor)
        page = ctx.new_page()
        try:
            page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
            page.wait_for_timeout(500)
            out[label] = page.evaluate(OVERFLOW_JS)
        except Exception as e:
            out[label] = {"error": str(e)[:120]}
        finally:
            ctx.close()
    if shots and (args.screenshots == "all" or loc in main_pages):
        for mobile_, w, h, tag in ((False, 1440, 900, "desktop"), (True, 390, 844, "phone390")):
            ctx = browser.context(mobile=mobile_, width=w, height=h)
            page = ctx.new_page()
            try:
                page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
                page.wait_for_timeout(900)
                shot(page, f"{tag}_{slug(loc)}", full=True)
            except Exception:
                pass
            finally:
                ctx.close()
    return out


# ------------------------------------------------------------------ run
for loc in pages:
    audit.checked(loc)
groups = defaultdict(list)
for loc in list(dict.fromkeys(main_pages + sample_pages(pages, per_section=1))):
    groups[header_key(loc)].append(loc)
nav_pages = [g[0] for g in groups.values()]
print(f"{len(groups)} distinct header(s) - testing the menus on {len(nav_pages)} page(s), zoom on {len(pages)} pages")

desk = [r for r in run_browser_pages(desktop, nav_pages, args.browser_workers, "desktop menus") if r]
mob = [r for r in run_browser_pages(mobile, [(p, w, h) for p in nav_pages for w, h in ((390, 844), (360, 740))],
                                    args.browser_workers, "mobile menus") if r]
zooms = [r for r in run_browser_pages(zoom, pages, args.browser_workers, "pages zoomed") if r]

# ---- desktop findings
_, home_soup = site.page(main_pages[0])
site_has_phone = bool(home_soup and home_soup.find("a", href=re.compile(r"^tel:", re.I)))
menu_rows, all_desktop = [], {}
for r in desk:
    all_desktop.update(r["links"])
    for t in r["triggers"]:
        menu_rows.append((r["page"], "desktop", t["label"], "opens on " + t["how"] if t["opened"] else "does NOT open",
                          t["links"], "; ".join(t["offscreen"])))
        if not t["opened"]:
            audit.add(r["page"], IMPORTANT, "Desktop menu", "Desktop dropdown doesn't open (hover or click)",
                      current=f"'{t['label']}'", expected="the sub-menu appears on hover / click")
        if t["offscreen"]:
            audit.add(r["page"], IMPORTANT, "Desktop menu", "Dropdown menu runs off the screen",
                      current="; ".join(t["offscreen"]), element=f"'{t['label']}'")
    if site_has_phone and not r["phone"]:
        audit.add(r["page"], IMPORTANT if cfg["legal_site"] else OPTIMIZATION, "Desktop menu",
                  "No visible phone number in the desktop header", current="(no visible tel: link in <header>)")
labels = " | ".join(v["text"].lower() for v in all_desktop.values())
for want in cfg["nav_expected"]:
    if want.lower() not in labels:
        audit.site(IMPORTANT, "Desktop menu", "Expected menu item missing", current=f"'{want}' not in the header menu",
                   expected="every item of qa_config.json nav_expected")
for p, l in sorted(all_desktop.items()):
    if p.startswith("/"):
        st = fetch(site.to_fetch(p))["status"]
        if st != 200:
            audit.site(CRITICAL, "Desktop menu", "Menu link is broken", current=f"HTTP {st}", element=f"'{l['text']}' -> {p}")

# ---- mobile findings
for r in mob:
    loc, w, b = r["page"], r["w"], r["button"]
    vp = f"{w}px phone"
    if not b:
        audit.add(loc, CRITICAL, "Mobile menu", "No mobile menu button", current="no menu / toggle button in <header>",
                  detail=vp)
        menu_rows.append((loc, vp, "-", "no menu button", 0, ""))
        continue
    if not b["visible"]:
        audit.add(loc, CRITICAL, "Mobile menu", "Mobile menu button is hidden", element=b["label"], detail=vp)
    elif b["right"] > b["vw"] + 1 or b["left"] < -1:
        audit.add(loc, CRITICAL, "Mobile menu", "Mobile menu button is outside the screen",
                  current=f"button at {b['left']}..{b['right']}px, screen {b['vw']}px", element=b["label"], detail=vp)
    if r["tap"] and r["tap"] != "ok":
        audit.add(loc, CRITICAL, "Mobile menu", "Mobile menu button can't be tapped", current=r["tap"],
                  element=b["label"], detail=vp, expected="a normal tap opens the menu",
                  fix="Make sure the button is inside the viewport and not covered (z-index / overlapping header "
                      "elements); check with Chrome DevTools device mode at this width.")
    if not r["opened"]:
        audit.add(loc, CRITICAL, "Mobile menu", "Mobile menu doesn't open", element=b["label"], detail=vp,
                  current="no new links visible after tapping the button")
    if r["cut"]:
        audit.add(loc, IMPORTANT, "Mobile menu", "Mobile menu links are cut off / off-screen",
                  current="; ".join(r["cut"][:8]), element=b["label"], detail=f"{vp}, {len(r['cut'])} link(s)")
    for label, result in r["subs"]:
        if result in ("nothing opened", "can't be tapped"):
            audit.add(loc, IMPORTANT, "Mobile menu", "Mobile sub-menu doesn't open", current=f"'{label}': {result}",
                      detail=vp)
    if r["opened"] and r["closed"] == "no":
        audit.add(loc, IMPORTANT, "Mobile menu", "Mobile menu can't be closed", current="Escape and the button fail",
                  detail=vp)
    elif r["closed"] == "button":
        audit.add(loc, OPTIMIZATION, "Mobile menu", "Mobile menu doesn't close with Escape", detail=vp,
                  current="closes only with the button")
    if site_has_phone and not r["phone"]:
        audit.add(loc, OPTIMIZATION if not cfg["legal_site"] else IMPORTANT, "Mobile menu",
                  "No tap-to-call phone in the mobile header", current="(no visible tel: link at the top)", detail=vp)
    menu_rows.append((loc, vp, b["label"], ("opens" if r["opened"] else "does NOT open") +
                      ("" if r["tap"] == "ok" else " (tap failed)"), len(r["links"]), "; ".join(r["cut"][:5])))
    # parity: every page linked in the desktop menu must be in the mobile menu
    if r["opened"] and w == 390:
        desk_for_page = next((d["links"] for d in desk if d["page"] == loc), all_desktop)
        missing = [(p, l) for p, l in desk_for_page.items() if p.startswith("/") and p not in r["links"]]
        for p, l in missing[:40]:
            audit.add(loc, IMPORTANT, "Menu parity", "Desktop menu link missing from the mobile menu",
                      current=f"'{l['text']}' -> {p}", expected="the mobile menu offers the same pages as the desktop menu")
        extra_mobile = [p for p in r["links"] if p.startswith("/") and p != "/" and p not in desk_for_page]
        if extra_mobile:
            audit.add(loc, INFO, "Menu parity", "Mobile menu has links the desktop menu doesn't",
                      current=", ".join(extra_mobile[:15]))

# ---- zoom findings
zoom_rows = []
for r in zooms:
    row = [r["page"]]
    for label in ("120%", "200%"):
        z = r.get(label)
        if not z:
            row.append("")
            continue
        if z.get("error"):
            row.append("error")
            continue
        over = z["sw"] - z["vw"]
        row.append(f"+{over}px" if over > 1 else "ok")
        if over > 1:
            audit.add(r["page"], IMPORTANT if label == "120%" else OPTIMIZATION, "Zoom",
                      f"Horizontal scrolling at {label} zoom", current=f"page {z['sw']}px wide in a {z['vw']}px window",
                      element=z["culprit"], expected="no horizontal scrollbar (content reflows)")
    zoom_rows.append(tuple(row))
if args.no_zoom:
    audit.not_checked("Zoom", "120 % / 200 % zoom", "--no-zoom")

# ---- other engines (Firefox, WebKit)
engine_rows = []
engines = [e.strip() for e in args.engines.split(",") if e.strip()]
if engines:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        for name in engines:
            try:
                br = getattr(pw, name).launch()
            except Exception as e:
                audit.not_checked("Browsers", f"{name} rendering", str(e).split("\n")[0][:150],
                                  f"Install the engine once:  playwright install {name}")
                continue
            print(f"Checking {len(main_pages)} main pages in {name} ...")
            for loc in main_pages:
                ctx = br.new_context(viewport={"width": 1440, "height": 900})
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e, errors=errors: errors.append(str(e)[:150]))
                try:
                    page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
                    page.wait_for_timeout(800)
                    o = page.evaluate(OVERFLOW_JS)
                    shot(page, f"{name}_{slug(loc)}", full=True)
                    engine_rows.append((loc, name, len(errors), "; ".join(errors[:3]),
                                        f"+{o['sw'] - o['vw']}px" if o["sw"] > o["vw"] + 1 else "ok"))
                    for err in errors[:5]:
                        audit.add(loc, IMPORTANT, "Browsers", f"JavaScript error in {name}", current=err)
                    if o["sw"] > o["vw"] + 1:
                        audit.add(loc, IMPORTANT, "Browsers", f"Horizontal scrolling in {name}",
                                  current=f"page {o['sw']}px in {o['vw']}px", element=o["culprit"])
                except Exception as e:
                    audit.add(loc, IMPORTANT, "Browsers", f"Page failed to load in {name}", current=str(e)[:150])
                finally:
                    ctx.close()
            br.close()
else:
    audit.not_checked("Browsers", "Firefox / WebKit rendering", "--engines ''")

if shots:
    audit.note("Screenshots", str(shots))
audit.note("Distinct headers tested", len(groups))
audit.sheet("Menus", ["Page", "Viewport", "Menu item / button", "Result", "Links", "Cut off / off-screen"], menu_rows,
            (55, 14, 30, 24, 8, 70))
audit.sheet("Desktop menu links", ["Path", "Text"], sorted((p, l["text"]) for p, l in all_desktop.items()), (60, 40))
audit.sheet("Zoom", ["Page", "120% zoom", "200% zoom"], zoom_rows, (70, 12, 12))
audit.sheet("Other browsers", ["Page", "Engine", "JS errors", "Errors", "Horizontal scroll"], engine_rows,
            (60, 10, 10, 70, 16))
audit.save("Navigation_Report")
