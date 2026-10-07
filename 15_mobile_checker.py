"""
15 - Mobile checker (real Chrome, phone + tablet viewports)
  viewport meta, horizontal overflow (+ the elements causing it), page width, images / tables / modals overflowing,
  mobile navigation (menu button opens a usable menu), touch target size, buttons with clipped text,
  font readability (< 12 px text), form inputs (font < 16 px zooms on iPhone, too wide), mobile CLS,
  mobile LCP (unthrottled - use 12a for throttled Core Web Vitals)

  python "py files/15_mobile_checker.py" [--base URL] [--viewports 360x740,390x844,768x1024]
  needs:  pip install playwright   (uses your installed Google Chrome)
"""
from seo_common import (COLLECT_METRICS_JS, CRITICAL, IMPORTANT, OPTIMIZATION, PERF_INIT_SCRIPT, Audit, Browser,
                        load_site, parse_args, scroll_page, select_pages)

LAYOUT_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const clipped = el => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX; if (o === 'hidden' || o === 'clip' || o === 'auto' || o === 'scroll') return true; }
      return false; };
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 3).join('.') : '');
  const visible = el => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
      return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0; };
  const all = [...document.body.querySelectorAll('*')];
  const overflowing = all.filter(el => { const r = el.getBoundingClientRect();
      return visible(el) && (r.right > vw + 1 || r.left < -1) && !clipped(el) && getComputedStyle(el).position !== 'fixed'; });
  const roots = overflowing.filter(el => !overflowing.includes(el.parentElement)).slice(0, 6)
      .map(el => name(el) + ' (' + Math.round(el.getBoundingClientRect().right) + 'px)');
  const imgs = [...document.images].filter(i => visible(i) && i.getBoundingClientRect().right > vw + 1 && !clipped(i)).map(i => i.src.split('/').pop().slice(0, 50));
  const tables = [...document.querySelectorAll('table')].filter(t => t.getBoundingClientRect().width > vw + 1 && !clipped(t)).length;
  const fixedWide = all.filter(el => getComputedStyle(el).position === 'fixed' && visible(el) && el.getBoundingClientRect().width > vw + 1).map(name).slice(0, 3);
  let small = 0, smallSample = '';
  const smallText = [];
  for (const el of all) {
    if (!visible(el) || !el.childNodes.length) continue;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
    if (own.length < 20) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) { small++; smallSample = smallSample || own.slice(0, 40);
      if (smallText.length < 30) smallText.push({ el: name(el), size: fs, text: own.slice(0, 50) }); }
  }
  const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')].filter(visible);
  const smallInputList = inputs.filter(i => parseFloat(getComputedStyle(i).fontSize) < 16)
      .map(i => ({ el: name(i) + (i.name ? '[name=' + i.name + ']' : ''), size: parseFloat(getComputedStyle(i).fontSize) }));
  const smallInputs = smallInputList.length;
  const wideInputList = inputs.filter(i => i.getBoundingClientRect().right > vw + 1).map(i => name(i));
  const wideInputs = wideInputList.length;
  const targetList = [...document.querySelectorAll('a[href], button, input, select, textarea, [role=button]')].filter(visible)
      .map(e => { const r = e.getBoundingClientRect(); return { w: r.width, h: r.height,
        label: name(e) + ' "' + (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30) + '"',
        inline: getComputedStyle(e).display === 'inline' && e.closest('p, li') !== null }; })
      .filter(t => !t.inline && (t.w < 44 || t.h < 44));
  const targets = targetList;
  const clippedButtons = [...document.querySelectorAll('button, a[class*=btn], a[class*=button]')].filter(b => visible(b) &&
      (b.scrollWidth > b.clientWidth + 2) && getComputedStyle(b).overflow !== 'visible').map(b => (b.innerText || '').trim().slice(0, 30)).slice(0, 4);
  return { vw, scrollWidth: document.documentElement.scrollWidth, roots, imgs, tables, fixedWide, small, smallSample,
           smallInputs, wideInputs, smallTargets: targets.length, tinyTargets: targets.filter(r => r.w < 24 || r.h < 24).length,
           targetList: targetList.slice(0, 60), smallText, smallInputList, wideInputList,
           clippedButtons, viewportMeta: (document.querySelector('meta[name=viewport]') || {}).content || '' };
}
"""

MENU_JS = """
async () => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > 0 && r.top < innerHeight; };
  const header = document.querySelector('header') || document.body;
  const btn = [...header.querySelectorAll('button, [role=button]')].find(b => visible(b) &&
      /menu|navigation|nav|toggle/i.test((b.getAttribute('aria-label') || '') + ' ' + (b.innerText || '') + ' ' + (b.getAttribute('aria-controls') || '')))
      || [...header.querySelectorAll('button[aria-expanded]')].find(visible);
  if (!btn) return { found: false };
  const before = [...document.querySelectorAll('nav a, [role=dialog] a, [role=menu] a')].filter(visible).length;
  btn.click();
  await new Promise(r => setTimeout(r, 700));
  const links = [...document.querySelectorAll('nav a, [role=dialog] a, [role=menu] a, aside a')].filter(visible);
  const expanded = btn.getAttribute('aria-expanded');
  const vw = document.documentElement.clientWidth;
  const overflow = links.filter(a => a.getBoundingClientRect().right > vw + 1).length;
  btn.click();
  await new Promise(r => setTimeout(r, 300));
  return { found: true, label: btn.getAttribute('aria-label') || btn.innerText.trim(), linksBefore: before,
           linksAfter: links.length, expanded, overflow };
}
"""

args = parse_args("Mobile checker", lambda ap: ap.add_argument("--viewports", default="360x740,390x844,768x1024"),
                  default_pages="sample")
site, urls = load_site(args)
pages = select_pages(urls, args)
viewports = [tuple(int(x) for x in v.split("x")) for v in args.viewports.split(",")]
audit = Audit("15_mobile", "Mobile Report", "Mobile", site)
rows = []

print(f"Checking {len(pages)} pages at {', '.join(f'{w}px' for w, _ in viewports)} ...")
with Browser() as browser:
    for w, h in viewports:
        ctx = browser.context(mobile=w < 700, width=w, height=h, **({} if w < 700 else {"has_touch": True}))
        ctx.add_init_script(PERF_INIT_SCRIPT)
        label = f"{w}px"
        for loc in pages:
            audit.checked(loc)
            page = ctx.new_page()
            try:
                page.goto(site.to_fetch(loc), wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(800)
                scroll_page(page)
                lay = page.evaluate(LAYOUT_JS)
                perf = page.evaluate(COLLECT_METRICS_JS)
                menu = page.evaluate(MENU_JS) if w < 1024 else {"found": None}
            except Exception as e:
                audit.add(loc, IMPORTANT, "Load", "Page failed to load", current=str(e)[:200],
                          detail=f"{label} viewport")
                page.close()
                continue
            page.close()
            def add(sev, check, **kw):
                audit.add(loc, sev, "Mobile", check, detail=f"{label} viewport ({w}x{h})", **kw)

            if "width=device-width" not in lay["viewportMeta"]:
                add(CRITICAL, "Viewport meta missing width=device-width", current=lay["viewportMeta"] or "(none)",
                    expected="width=device-width, initial-scale=1")
            if lay["scrollWidth"] > lay["vw"] + 1:
                add(CRITICAL if w < 700 else IMPORTANT, "Horizontal scroll (page wider than screen)",
                    current=f"page {lay['scrollWidth']}px wide on a {lay['vw']}px screen", expected=f"<= {lay['vw']}px")
                for el in lay["roots"]:
                    add(IMPORTANT, "Element wider than the screen", current=el.rsplit(" (", 1)[-1].rstrip(")") + " right edge",
                        expected=f"<= {lay['vw']}px", element=el.rsplit(" (", 1)[0])
            else:
                for el in lay["roots"][:3]:
                    add(OPTIMIZATION, "Elements wider than the screen (hidden by overflow)",
                        current=el.rsplit(" (", 1)[-1].rstrip(")") + " right edge", element=el.rsplit(" (", 1)[0])
            for img in lay["imgs"]:
                add(IMPORTANT, "Images overflow the screen", current="wider than the viewport", element=img)
            if lay["tables"]:
                add(IMPORTANT, "Tables overflow (wrap them in a horizontal scroll container)",
                    current=f"{lay['tables']} table(s) wider than the screen")
            for el in lay["fixedWide"]:
                add(IMPORTANT, "Fixed/modal element wider than the screen", current="position: fixed, wider than viewport",
                    element=el)
            for t in lay["smallText"]:
                add(IMPORTANT if lay["small"] > 10 else OPTIMIZATION, "Text smaller than 12px",
                    current=f"{t['size']:g}px", expected=">= 12px (16px for body text)", element=f"{t['el']} '{t['text']}'")
            for i in lay["smallInputList"]:
                add(OPTIMIZATION, "Form fields with font-size < 16px (iPhone zooms in on focus)",
                    current=f"{i['size']:g}px", expected="16px", element=i["el"])
            for el in lay["wideInputList"]:
                add(IMPORTANT, "Form fields wider than the screen", current="wider than viewport", element=el)
            for t in lay["targetList"]:
                tiny = t["w"] < 24 or t["h"] < 24
                if tiny or lay["smallTargets"] > 5:
                    add(IMPORTANT if tiny else OPTIMIZATION,
                        "Touch targets smaller than 24x24px" if tiny else "Touch targets smaller than 44x44px",
                        current=f"{int(t['w'])}x{int(t['h'])}px", expected="24x24px minimum" if tiny else "44x44px",
                        element=t["label"])
            for b in lay["clippedButtons"]:
                add(IMPORTANT, "Button text is cut off", current="text overflows the button", element=b)
            if perf["cls"] > 0.1:
                add(IMPORTANT if perf["cls"] > 0.25 else OPTIMIZATION, "Mobile layout shift (CLS)",
                    current=f"{perf['cls']:.3f}", expected="<= 0.1")
            if menu.get("found") is False and w < 1024:
                add(IMPORTANT, "No mobile menu button found in header", current="no menu/toggle button in <header>")
            elif menu.get("found"):
                if menu["linksAfter"] <= menu["linksBefore"]:
                    add(IMPORTANT, "Mobile menu button doesn't reveal navigation links",
                        current=f"{menu['linksBefore']} visible links before, {menu['linksAfter']} after click",
                        element=menu["label"])
                if menu["expanded"] is None:
                    add(OPTIMIZATION, "Menu button has no aria-expanded", current="(no aria-expanded)",
                        expected='aria-expanded="true|false"', element=menu["label"])
                if menu["overflow"]:
                    add(IMPORTANT, "Mobile menu links overflow the screen", current=f"{menu['overflow']} link(s)",
                        element=menu["label"])
            rows.append((loc, label, lay["vw"], lay["scrollWidth"], "yes" if lay["scrollWidth"] > lay["vw"] + 1 else "no",
                         ", ".join(lay["roots"][:3]), len(lay["imgs"]), lay["tables"], lay["small"], lay["smallTargets"],
                         lay["tinyTargets"], lay["smallInputs"], round(perf["cls"], 3), round(perf["lcp"]),
                         "" if menu.get("found") is None else ("ok" if menu.get("found") and menu["linksAfter"] > menu["linksBefore"]
                                                               else "problem")))
        ctx.close()
        print(f"  {label} done")

audit.sheet("Mobile results", ["URL", "Viewport", "Screen px", "Page px", "Horizontal scroll", "Overflow caused by",
                               "Imgs overflow", "Tables overflow", "Text < 12px", "Targets < 44px", "Targets < 24px",
                               "Inputs < 16px", "CLS", "LCP ms", "Mobile menu"], rows,
            (55, 9, 9, 8, 10, 60, 10, 11, 10, 12, 12, 11, 7, 8, 11))
audit.save("Mobile_Report")
