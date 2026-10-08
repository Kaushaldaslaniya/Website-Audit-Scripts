"""
23 - Forms checker (lead / contact / newsletter / search forms)
  HTML (every page, every form):
    lead forms ask for a name and an email, fields have a name or id, labels that show "*" match the field's
    required / aria-required state (and required fields show it in the label), email fields use type=email and
    phone fields type=tel, autocomplete on name / email / phone, a submit button with text, form action over
    https and not GET for personal data, a thank-you redirect (_next / redirect field) that works, spam
    protection (reCAPTCHA / hCaptcha / Turnstile / honeypot), a privacy link near lead forms, the disclaimer
    checkbox on legal sites (qa_config.json legal_site), no lead forms on legal / utility pages
  browser (every unique form once - the same form component on 300 pages is tested on the first page that shows it,
  plus the forms that only exist after JavaScript on the main pages):
    submitting the EMPTY form must not send anything and must show error messages, an invalid email must be
    rejected, focus moves to the first invalid field, site search (if any) returns results.
    Every POST / PUT request is blocked during the test, so nothing is ever submitted.

  python "py files/23_forms_checker.py" [--base URL] [--no-browser]
"""
import re
from threading import Lock
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, OPTIMIZATION, Audit, describe, fetch, load_site, parse_args, qa_config,
                        run_browser_pages, run_parallel, sample_pages, select_pages, text_of)

args = parse_args("Forms checker", lambda ap: ap.add_argument("--no-browser", action="store_true",
                                                             help="HTML checks only (no Chrome)"))
site, urls = load_site(args)
pages = select_pages(urls, args)
cfg = qa_config()
audit = Audit("23_forms", "Forms Report", "Forms", site)
lock = Lock()

FIELD_SKIP = {"hidden", "submit", "button", "reset", "image"}
UTILITY = re.compile(r"/(privacy|terms|cookie|refund|disclaimer|accessibility|thank-?you|404|legal)", re.I)
SPAM = re.compile(r"recaptcha|hcaptcha|turnstile|cf-turnstile|g-recaptcha|honeypot|_gotcha|friendlycaptcha", re.I)
ANALYTICS = re.compile(r"google-analytics|googletagmanager|analytics|doubleclick|facebook\.com/tr|hotjar|clarity|"
                       r"vercel-insights|_vercel/insights|sentry|segment", re.I)
forms_seen = {}            # signature -> {"pages": set, "first": url, "kind": str, "fields": str}


def field_label(form, el, soup):
    """Visible label text of a field: <label for>, wrapping <label>, aria-label, aria-labelledby."""
    if el.get("id"):
        lab = soup.find("label", attrs={"for": el["id"]})
        if lab:
            return text_of(lab)
    wrap = el.find_parent("label")
    if wrap:
        return text_of(wrap)
    if el.get("aria-label"):
        return el["aria-label"].strip()
    if el.get("aria-labelledby"):
        return " ".join(text_of(soup.find(id=i)) for i in el["aria-labelledby"].split() if soup.find(id=i))
    return ""


def purpose(el, label):
    words = " ".join(filter(None, [el.get("type"), el.get("name"), el.get("id"), el.get("autocomplete"),
                                   el.get("placeholder"), label])).lower()
    if el.get("type") == "search" or re.search(r"\b(search|query)\b|^q$|^s$", el.get("name") or ""):
        return "search"
    if "mail" in words:
        return "email"
    if re.search(r"phone|\btel\b|mobile|cell", words):
        return "phone"
    if re.search(r"\bname\b|full.?name|first.?name|last.?name|fname|lname", words):
        return "name"
    if el.name == "textarea" or re.search(r"message|details|comment|enquiry|inquiry", words):
        return "message"
    if el.get("type") == "checkbox":
        return "checkbox"
    return "other"


def signature(fields):
    return "|".join(sorted(f"{f.name}:{f.get('type', '')}:{f.get('name') or f.get('id') or ''}" for f in fields))


def scan(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", current=f"HTTP {res['status']} {res['error']}".strip())
        return
    page_has_spam_guard = bool(SPAM.search(str(soup.find_all("script", src=True))))
    for n, form in enumerate(soup.find_all("form"), 1):
        # aria-hidden fields are implementation details (e.g. the native <select> behind a Radix Select)
        fields = [f for f in form.find_all(["input", "textarea", "select"])
                  if (f.get("type") or "").lower() not in FIELD_SKIP and f.get("aria-hidden") != "true"]
        if not fields:
            continue
        sig = signature(fields)
        info = [(f, field_label(form, f, soup)) for f in fields]
        kinds = {purpose(f, lab) for f, lab in info}
        kind = "search" if kinds == {"search"} else ("lead" if kinds & {"email", "phone", "message"} else "other")
        if kind == "lead" and len(fields) == 1:
            kind = "newsletter"
        where = f"form #{n} ({kind}) {describe(form, 60)}"
        with lock:
            entry = forms_seen.setdefault(sig, {"pages": set(), "first": loc, "kind": kind,
                                                "fields": ", ".join(f"{lab or f.get('name') or f.get('id') or f.name}"
                                                                    f"[{purpose(f, lab)}]" for f, lab in info)})
            entry["pages"].add(loc)
        action = (form.get("action") or "").strip()
        method = (form.get("method") or "get").lower()

        if kind == "lead":
            if "email" not in kinds:
                audit.add(loc, IMPORTANT, "Lead form", "Lead form has no email field", current=entry["fields"][:200],
                          element=where)
            if "name" not in kinds:
                audit.add(loc, OPTIMIZATION, "Lead form", "Lead form has no name field", current=entry["fields"][:200],
                          element=where)
            if UTILITY.search(site.path(loc)):
                audit.add(loc, OPTIMIZATION, "Lead form", "Lead form on a legal / utility page", current=site.path(loc),
                          element=where, expected="no contact form on privacy / terms / thank-you / 404 pages")
            near = text_of(form) + " " + " ".join(a.get("href", "") for a in form.find_all("a", href=True))
            parent = form.parent
            near += " " + (text_of(parent)[:2000] if parent else "")
            if not re.search(r"privacy|data protection|gdpr", near, re.I):
                audit.add(loc, OPTIMIZATION, "Privacy", "No privacy notice / link at the lead form",
                          current="(no 'privacy' text or link in or next to the form)", element=where)
            if cfg["legal_site"]:
                box = [f for f, lab in info if f.get("type") == "checkbox" and re.search(r"disclaimer", lab, re.I)]
                if not box:
                    audit.add(loc, CRITICAL, "Legal", "No disclaimer checkbox on a legal-site form", element=where,
                              expected='a required "I have read the disclaimer" checkbox linking to /disclaimer/')
                elif not (box[0].has_attr("required") or box[0].get("aria-required") == "true"):
                    audit.add(loc, IMPORTANT, "Legal", "Disclaimer checkbox is not required", element=where)
            if not (page_has_spam_guard or SPAM.search(str(form))):
                audit.add(loc, OPTIMIZATION, "Spam", "No spam protection on the form", element=where,
                          current="no reCAPTCHA / hCaptcha / Turnstile / honeypot field found",
                          expected="a CAPTCHA or a hidden honeypot field")
        if action:
            target = urljoin(site.to_fetch(loc), action)
            if target.startswith("http://") and not site.is_internal(target):
                audit.add(loc, CRITICAL, "Submission", "Form posts over insecure http://", current=action, element=where)
            if method == "get" and kinds & {"email", "phone", "message"}:
                audit.add(loc, IMPORTANT, "Submission", "Form sends personal data with GET (ends up in URLs / logs)",
                          current=f"method={method}", element=where, expected='method="post"')
            nxt = form.find("input", attrs={"name": re.compile(r"^(_next|_redirect|redirect|redirect_to|return_url)$")})
            if nxt and nxt.get("value"):
                dest = urljoin(site.to_fetch(loc), nxt["value"])
                st = fetch(site.to_fetch(dest) if site.is_internal(dest) else dest, "HEAD")["status"]
                if st != 200:
                    audit.add(loc, IMPORTANT, "Submission", "Thank-you redirect page is broken", current=f"HTTP {st}",
                              element=nxt["value"])

        for f, lab in info:
            p = purpose(f, lab)
            el = f"{where} > {describe(f, 60)}"
            if not f.get("name") and not f.get("id"):
                audit.add(loc, IMPORTANT, "Fields", "Form field has no name or id", element=el,
                          expected="a name attribute (it becomes the label in the submitted email)")
            elif action and not f.get("name"):
                audit.add(loc, IMPORTANT, "Fields", "Field without a name is not submitted", element=el,
                          current=f"id={f.get('id')}", expected='name="Email" / "Phone Number" ...')
            required = f.has_attr("required") or f.get("aria-required") == "true"
            star = bool(re.search(r"\*|\(required\)", lab))
            optional = bool(re.search(r"optional", lab, re.I))
            if star and not required:
                audit.add(loc, IMPORTANT, "Fields", "Field marked required (*) but not required in the HTML",
                          current=f"label '{lab[:50]}'", element=el,
                          expected='required or aria-required="true" on the field',
                          fix='Add aria-required="true" (keep noValidate for custom messages) or the required '
                              'attribute, so screen readers announce it.')
            if required and not star and not optional and lab and p != "search":
                audit.add(loc, OPTIMIZATION, "Fields", "Required field not marked in its label", element=el,
                          current=f"label '{lab[:50]}'", expected="'*' or '(required)' in the label")
            if lab and lab[0].isalpha() and lab[0].islower():
                audit.add(loc, OPTIMIZATION, "Fields", "Field label not capitalised", current=f"'{lab[:50]}'",
                          element=el, expected="'Name', 'Phone Number', 'Email'")
            t = (f.get("type") or "text").lower()
            if p == "email" and f.name == "input" and t != "email":
                audit.add(loc, IMPORTANT, "Fields", "Email field is not type=email", current=f"type={t}", element=el)
            if p == "phone" and f.name == "input" and t not in ("tel",):
                audit.add(loc, OPTIMIZATION, "Fields", "Phone field is not type=tel", current=f"type={t}", element=el,
                          expected="type=tel (shows the number keypad on phones)")
            if p in ("email", "phone", "name") and not f.get("autocomplete"):
                audit.add(loc, OPTIMIZATION, "Fields", "No autocomplete attribute", current=f"{p} field", element=el,
                          expected={"email": "email", "phone": "tel", "name": "name"}[p])
        if not form.find(["button", "input"], attrs={"type": re.compile("submit|image", re.I)}) and \
                not [b for b in form.find_all("button") if (b.get("type") or "submit").lower() == "submit"]:
            if kind != "search":
                audit.add(loc, CRITICAL, "Submission", "Form has no submit button", element=where)
        for b in form.find_all(["button", "input"]):
            if (b.get("type") or ("submit" if b.name == "button" else "text")).lower() == "submit" and not (text_of(b) or b.get("value") or b.get("aria-label")):
                audit.add(loc, IMPORTANT, "Submission", "Submit button has no text", element=f"{where} > {describe(b)}")


print(f"Checking forms on {len(pages)} pages ...")
run_parallel(scan, pages, args.workers)

# ------------------------------------------------------------------ browser: validation behaviour, once per form
FORM_JS = """
() => [...document.querySelectorAll('form')].map((f, i) => {
  const fields = [...f.querySelectorAll('input, textarea, select')].filter(e => e.getAttribute('aria-hidden') !== 'true'
      && !['hidden','submit','button','reset','image'].includes((e.type||'').toLowerCase()));
  const r = f.getBoundingClientRect();
  return { i, n: fields.length, visible: r.width > 0 && r.height > 0,
           sig: fields.map(e => `${e.tagName.toLowerCase()}:${e.getAttribute('type')||''}:${e.name||e.id||''}`).sort().join('|'),
           search: fields.length === 1 && (fields[0].type === 'search' || /^(q|s|query|search)$/i.test(fields[0].name||'')),
           text: (f.innerText || '').slice(0, 80) };
})
"""
STATE_JS = """
(i) => { const f = document.querySelectorAll('form')[i]; if (!f) return null;
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                     return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const invalid = [...f.querySelectorAll('[aria-invalid="true"], :invalid')].filter(e => e.tagName !== 'FORM' && e.tagName !== 'FIELDSET').length;
  const errors = [...f.querySelectorAll('[role=alert], [aria-live], .error, [class*=error], [id*=error]')]
      .filter(e => vis(e) && (e.innerText || '').trim()).map(e => e.innerText.trim().slice(0, 80));
  const a = document.activeElement;
  return { invalid, errors, text: f.innerText, focusInvalid: !!(a && f.contains(a) &&
           (a.matches(':invalid') || a.getAttribute('aria-invalid') === 'true')) };
}
"""
FILL_JS = """
(i) => { const f = document.querySelectorAll('form')[i];
  const set = (e, v) => { const proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, v);
      e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); };
  for (const e of f.querySelectorAll('input, textarea')) {
    const t = (e.type || 'text').toLowerCase(), k = `${e.name} ${e.id} ${e.autocomplete} ${e.placeholder}`.toLowerCase();
    if (['hidden','submit','button','reset','image','file','radio'].includes(t)) continue;
    if (t === 'checkbox') { if (!e.checked) e.click(); continue; }
    if (t === 'email' || k.includes('mail')) set(e, 'not-an-email');
    else if (t === 'tel' || /phone|tel|mobile/.test(k)) set(e, '5555555555');
    else if (t === 'url') set(e, 'https://example.org');
    else if (t === 'number') set(e, '1');
    else if (t === 'date') set(e, '2030-01-01');
    else set(e, e.tagName === 'TEXTAREA' ? 'Audit test message - not submitted' : 'Audit Test');
  }
}
"""


def submit(page, i):
    loc = page.locator("form").nth(i)
    btn = loc.locator("[type=submit], button:not([type=button]):not([type=reset])").first
    try:
        btn.scroll_into_view_if_needed(timeout=3000)
        btn.click(timeout=4000)
    except Exception:
        page.evaluate("(i) => { const f = document.querySelectorAll('form')[i]; "
                      "f.requestSubmit ? f.requestSubmit() : f.submit(); }", i)
    page.wait_for_timeout(900)


def test_page(browser, loc):
    ctx = browser.context(width=1366, height=900)
    page = ctx.new_page()
    sent = []

    def guard(route):
        req = route.request
        if req.method not in ("GET", "HEAD", "OPTIONS"):
            if not ANALYTICS.search(req.url):
                sent.append(f"{req.method} {req.url[:120]}")
            return route.abort()
        if req.is_navigation_request() and req.frame == page.main_frame and page.url not in ("about:blank", "") \
                and req.url.split("#")[0] != page.url.split("#")[0] and "?" in req.url and urlparse(req.url).path \
                == urlparse(page.url).path:
            sent.append(f"GET {req.url[:120]}")   # a GET form reloading the page with the data in the URL
        return route.continue_()

    page.route("**/*", guard)
    out = []
    try:
        page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
        page.wait_for_timeout(700)
        for f in page.evaluate(FORM_JS):
            if not f["n"] or not f["visible"]:
                continue
            with lock:
                if f["sig"] in tested:
                    continue
                tested.add(f["sig"])
            r = {"page": loc, "sig": f["sig"], "search": f["search"], "fields": f["n"], "label": f["text"][:60]}
            if f["search"]:
                page.locator("form").nth(f["i"]).locator("input:not([type=hidden])").first.fill("services")
                before = page.url
                submit(page, f["i"])
                body = page.inner_text("body")[:20000].lower()
                r["result"] = "results shown" if (page.url != before or "result" in body) and \
                    not re.search(r"no results|nothing found|0 results", body) else "no results"
                out.append(r)
                page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
                continue
            before = page.evaluate(STATE_JS, f["i"])
            sent.clear()
            submit(page, f["i"])
            empty = page.evaluate(STATE_JS, f["i"]) or {}
            r["empty_sent"] = list(sent)
            new_text = set((empty.get("text") or "").splitlines()) - set((before.get("text") or "").splitlines())
            r["empty_errors"] = empty.get("invalid", 0) + len(empty.get("errors", [])) + \
                len([t for t in new_text if re.search(r"required|invalid|please|enter|must", t, re.I)])
            r["focus_invalid"] = empty.get("focusInvalid", False)
            page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)   # fresh form for the invalid-email test
            page.wait_for_timeout(500)
            page.evaluate(FILL_JS, f["i"])
            sent.clear()
            submit(page, f["i"])
            bad = page.evaluate(STATE_JS, f["i"]) or {}
            r["bad_email_sent"] = list(sent)
            r["bad_email_errors"] = bad.get("invalid", 0) + len(bad.get("errors", []))
            out.append(r)
            page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
    finally:
        ctx.close()
    return out


tested = set()
browser_rows = []
if args.no_browser:
    audit.not_checked("Browser", "form validation in the browser", "--no-browser",
                      "Run 23_forms_checker.py without --no-browser.")
else:
    # pages that show each form first + the main pages (forms rendered only by JavaScript, e.g. in modals)
    targets = list(dict.fromkeys([v["first"] for v in forms_seen.values()] + sample_pages(pages, per_section=0)))
    print(f"Testing form validation in Chrome on {len(targets)} pages (every POST is blocked - nothing is sent) ...")
    for res in run_browser_pages(test_page, targets, args.browser_workers, "pages tested"):
        for r in res or []:
            browser_rows.append(r)
            loc, where = r["page"], f"form '{r['label'][:40]}' ({r['fields']} fields)"
            if r["search"]:
                if r["result"] == "no results":
                    audit.add(loc, IMPORTANT, "Search", "Site search returns no results", current="query 'services'",
                              element=where, expected="matching pages listed")
                continue
            if r["empty_sent"]:
                audit.add(loc, CRITICAL, "Validation", "Empty form is submitted (no validation)",
                          current="; ".join(r["empty_sent"])[:300], element=where,
                          expected="the form blocks submission and shows what is missing")
            elif not r["empty_errors"]:
                audit.add(loc, IMPORTANT, "Validation", "No error message when submitting an empty form",
                          current="nothing marked invalid, no error text", element=where)
            elif not r["focus_invalid"]:
                audit.add(loc, OPTIMIZATION, "Validation", "Focus doesn't move to the first invalid field",
                          current="after submitting the empty form", element=where)
            if r["bad_email_sent"]:
                audit.add(loc, IMPORTANT, "Validation", "Invalid email address is accepted",
                          current="'not-an-email' -> " + "; ".join(r["bad_email_sent"])[:250], element=where)
    found_sigs = {r["sig"] for r in browser_rows}
    for sig, v in forms_seen.items():
        if sig not in found_sigs and v["kind"] != "search":
            # the server HTML form wasn't visible in Chrome (hidden tab / modal) - not tested, say so
            audit.add(v["first"], OPTIMIZATION, "Browser", "Form not visible in Chrome - validation not tested",
                      current=v["fields"][:200], expected="form visible on page load")

audit.note("Unique forms", len(forms_seen))
audit.sheet("Forms", ["Kind", "Fields (label[purpose])", "Pages with this form", "First page"],
            sorted(((v["kind"], v["fields"], len(v["pages"]), v["first"]) for v in forms_seen.values()),
                   key=lambda r: -r[2]), (12, 90, 10, 60))
audit.sheet("Browser tests", ["Page", "Form", "Fields", "Search result", "Empty submit sent", "Errors shown (empty)",
                              "Focus on invalid", "Invalid email sent", "Errors shown (bad email)"],
            [(r["page"], r["label"], r["fields"], r.get("result", ""), "; ".join(r.get("empty_sent", [])) or "no",
              r.get("empty_errors", ""), r.get("focus_invalid", ""), "; ".join(r.get("bad_email_sent", [])) or "no",
              r.get("bad_email_errors", "")) for r in browser_rows], (55, 40, 8, 14, 30, 12, 12, 30, 12))
audit.save("Forms_Report")
