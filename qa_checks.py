"""
The QA checklist: every check the launch QA needs, with the report issues that decide it.

Each check reads the JSON reports of the audit scripts and gets one status:
  FAIL   an issue of a severity in `fail` (default Critical / Important) matched the check
  WARN   only lower-severity issues matched (Optimization by default) - review them
  PASS   the source reports ran and none of their issues matched
  SKIP   a source report didn't run, or it recorded "Not checked: ..." for this check (tool missing, option off)
  HUMAN  a person must check it (type HUMAN); record the result with  qa.py mark <ID> pass|fail|warn "note"
A person can also override any automatic result with qa.py mark (e.g. an SEO sign-off for a changed H1).

  Check(id, section, title, kind, sources, fail=..., owner=..., how=...)
    kind     AUTO | AUTO+HUMAN (automatic result + a manual confirmation) | HUMAN
    sources  Src(report key, issue regex, category regex, exclude regex) - regexes are case-insensitive searches
             on the issue name / category; None = any
    owner    who fixes it: dev | seo | content | client | qa (used for the "notes for ..." blocks)
    how      what to do for a HUMAN check (or how to get the automatic part to run)
"""
import re
from dataclasses import dataclass, field

from seo_common import CRITICAL, IMPORTANT

STRICT = (CRITICAL, IMPORTANT)      # default: these FAIL, Optimization WARNs
ONLY_CRITICAL = (CRITICAL,)         # softer checks: only Critical fails, Important/Optimization warn
NEVER = ()                          # review-only checks: anything found is a WARN


@dataclass
class Src:
    report: str
    issue: str = None
    category: str = None
    exclude: str = None

    def matches(self, issue):
        name = issue.get("issue") or ""
        cat = issue.get("category") or ""
        # a page that didn't load is a crawl problem (NAV-01), not a failure of every check that reads the report
        if not self.issue and re.search(r"page not reachable|failed to load", name, re.I):
            return False
        if self.issue and not re.search(self.issue, name, re.I):
            return False
        if self.category and not re.search(self.category, cat, re.I):
            return False
        if self.exclude and re.search(self.exclude, name, re.I):
            return False
        return True


@dataclass
class Check:
    id: str
    section: str
    title: str
    kind: str = "AUTO"
    sources: list = field(default_factory=list)
    fail: tuple = STRICT
    owner: str = "dev"
    how: str = ""

    @property
    def reports(self):
        return sorted({s.report for s in self.sources})


S = Src
CHECKS = [
    # ------------------------------------------------------------------ project context (people)
    Check("CTX-01", "Project context", "Brief / scope read; every requested page and feature is built", "HUMAN",
          owner="qa", how="Compare the project brief / ticket with the site; post open questions on the ticket."),
    Check("CTX-02", "Project context", "Ticket comments and dev notes read; requested changes are done", "HUMAN",
          owner="qa", how="Read every comment on the ticket / card and check each request on the site."),
    Check("CTX-03", "Project context", "Design (Figma) comments read; the site follows the approved design", "HUMAN",
          owner="qa", how="Open the Figma file, read the comment threads, compare the main pages with the frames."),
    Check("CTX-04", "Project context", "Open questions for the client listed and sent", "HUMAN", owner="qa",
          how="Copy the 'Questions for the client' block of this report into the ticket."),

    # ------------------------------------------------------------------ business info
    Check("NAP-01", "Business info", "Phone number is the confirmed number everywhere (header, footer, content, schema)",
          "AUTO", [S("22_business_info", r"phone number (differs|not found)|confirmed phone|several phone|other phone|"
                   r"phone in json-ld")], owner="dev"),
    Check("NAP-02", "Business info", "Every written phone number is a tel: link that dials the number shown",
          "AUTO", [S("22_business_info", r"tel: link|not a clickable tel")], owner="dev"),
    Check("NAP-03", "Business info", "Phone is visible and tappable in the desktop and mobile header",
          "AUTO", [S("24_navigation", r"phone|tap-to-call"), S("22_business_info", r"phone number in the header")],
          owner="dev"),
    Check("NAP-04", "Business info", "Email addresses are correct and mailto: links match the address shown",
          "AUTO", [S("22_business_info", r"mail")], owner="dev"),
    Check("NAP-05", "Business info", "Address is the same on every page (and matches the confirmed / Google listing)",
          "AUTO+HUMAN", [S("22_business_info", r"address")], owner="client",
          how="Compare the address with the Google Business Profile."),
    Check("NAP-06", "Business info", "Business name is written the same way everywhere (schema, og:site_name, titles)",
          "AUTO", [S("22_business_info", r"business name|organization name")], owner="dev"),
    Check("NAP-07", "Business info", "Phone numbers / addresses inside images and videos match", "HUMAN", owner="qa",
          how="Watch the videos and look at banner images for old phone numbers or addresses."),

    # ------------------------------------------------------------------ navigation & links
    Check("NAV-01", "Navigation and links", "No broken internal links, pages or redirect loops",
          "AUTO", [S("05_links", r"broken internal|empty link|javascript: link|placeholder link"),
                   S("09_technical", r"error status|5xx|redirect loop|soft 404"),
                   S("01_sitemap", r"broken internal|not 200")], owner="dev"),
    Check("NAV-02", "Navigation and links", "No broken external links / third-party URLs",
          "AUTO", [S("05_links", r"broken external"), S("19_third_party_urls", r"broken|error|timeout|ssl")],
          fail=ONLY_CRITICAL, owner="content"),
    Check("NAV-03", "Navigation and links", "Desktop dropdown menus open and their links work",
          "AUTO", [S("24_navigation", None, r"desktop menu")], owner="dev"),
    Check("NAV-04", "Navigation and links", "Mobile menu: button on screen and tappable, opens, links not cut off, closes",
          "AUTO", [S("24_navigation", None, r"mobile menu", r"phone|tap-to-call"),
                   S("15_mobile", r"mobile menu|menu button")], owner="dev"),
    Check("NAV-05", "Navigation and links", "Mobile menu offers the same pages as the desktop menu",
          "AUTO", [S("24_navigation", r"missing from the mobile menu")], owner="dev"),
    Check("NAV-06", "Navigation and links", "Social links point to real, working profiles",
          "AUTO+HUMAN", [S("22_business_info", None, r"^social$")], owner="client",
          how="Confirm the profile list with the client (qa_config.json social_profiles)."),
    Check("NAV-07", "Navigation and links", "Every page is reachable by links (no orphans, not only via JS menus)",
          "AUTO", [S("05_links", r"orphan|not reachable|linked only from javascript|homepage doesn't link")],
          owner="seo"),
    Check("NAV-08", "Navigation and links", "Hub pages link their detail pages; breadcrumbs on nested pages",
          "AUTO", [S("05_links", r"hub page|breadcrumb|page too deep|in-page anchor")], owner="seo"),
    Check("NAV-09", "Navigation and links", "Links have descriptive text",
          "AUTO", [S("05_links", r"anchor text|without text"), S("12b_lighthouse", r"descriptive text")],
          fail=ONLY_CRITICAL, owner="content"),
    Check("NAV-10", "Navigation and links", "No leftover / forbidden terms (old vendor, old brand, staging names)",
          "AUTO", [S("26_text_quality", r"forbidden|leftover")], owner="content"),
    Check("NAV-11", "Navigation and links", "Internal URLs are lowercase, hyphenated and consistent",
          "AUTO", [S("09_technical", None, r"^urls$"), S("02_page_seo", r"url not seo")], owner="dev"),

    # ------------------------------------------------------------------ SEO
    Check("SEO-01", "SEO", "Every page has a unique title and meta description of the right length",
          "AUTO", [S("02_page_seo", None, r"^(title|description)$")], owner="seo"),
    Check("SEO-02", "SEO", "Titles / descriptions / social tags have no odd characters (&amp;, &#39;, mojibake)",
          "AUTO", [S("26_text_quality", r"html entity shown as text in the|garbled")], owner="content"),
    Check("SEO-03", "SEO", "Home page title, description and H1 approved by SEO", "HUMAN", owner="seo",
          how="Send the home title / description / H1 (Page SEO report) to SEO; record the sign-off with qa.py mark."),
    Check("SEO-04", "SEO", "Exactly one meaningful H1 per page; headings in order",
          "AUTO", [S("02_page_seo", None, r"^h1$"), S("17_heading_order"), S("03_headings")], owner="seo"),
    Check("SEO-05", "SEO", "Canonical tag on every page points to itself (absolute, 200)",
          "AUTO", [S("09_technical", None, r"canonical"), S("13_nextjs", r"canonical")], owner="dev"),
    Check("SEO-06", "SEO", "No page is noindex / nofollow by mistake; robots.txt allows the site",
          "AUTO", [S("09_technical", None, r"indexing"), S("01_sitemap", r"noindex|robots")], owner="seo"),
    Check("SEO-07", "SEO", "JSON-LD parses, has the expected types and valid values / URLs",
          "AUTO", [S("07_schema", None, r"syntax|duplicates|presence"),
                   S("27_assets", r"json-ld|dateModified", None), S("27_assets", r"referenced", None, r"icon")],
          owner="dev"),
    Check("SEO-08", "SEO", "Expected schema type per page (Organization, Service, BlogPosting, Breadcrumbs ...)",
          "AUTO", [S("07_schema", None, r"page type|completeness")], fail=ONLY_CRITICAL, owner="seo"),
    Check("SEO-09", "SEO", "Favicon, apple-touch-icon, manifest icons and theme-color set",
          "AUTO", [S("13_nextjs", None, r"browser metadata|special files"), S("27_assets", None, r"icons")],
          fail=ONLY_CRITICAL, owner="dev"),
    Check("SEO-10", "SEO", "Social share (Open Graph / Twitter) tags complete; share image works (1200x630)",
          "AUTO", [S("06_social")], owner="seo"),
    Check("SEO-11", "SEO", "Titles and H1s are not ALL CAPS / all lowercase / padded with spaces",
          "AUTO", [S("26_text_quality", r"^(title|h1) |extra spaces in the")], owner="content"),
    Check("SEO-12", "SEO", "Every content image has accurate alt text",
          "AUTO+HUMAN", [S("18_image_alt"), S("04_images", r"alt")], owner="content",
          how="Skim the Image alt sheet: alt texts must describe this client's images (no other company's names)."),
    Check("SEO-14", "SEO", "Language versions / hreflang correct (multi-language sites)",
          "AUTO", [S("08_hreflang")], fail=ONLY_CRITICAL, owner="seo"),

    # ------------------------------------------------------------------ sitemap & content
    Check("MAP-01", "Sitemap and content", "sitemap.xml valid, https, on the live host, every URL 200 and indexable",
          "AUTO", [S("01_sitemap", None, r"^sitemap( url)?$")], owner="dev"),
    Check("MAP-02", "Sitemap and content", "Every live page is in the sitemap; robots.txt points to it",
          "AUTO", [S("01_sitemap", None, r"coverage|robots")], owner="dev"),
    Check("MAP-03", "Sitemap and content", "Every URL of the current live site exists on the new site or redirects",
          "AUTO", [S("29_live_vs_dev", r"missing on the new site|redirect loop|redirects to the homepage|live urls")],
          owner="dev"),
    Check("MAP-04", "Sitemap and content", "Content carried over from the live site (text, H1s, schema, numbers)",
          "AUTO+HUMAN", [S("29_live_vs_dev", None, r"parity"), S("29_live_vs_dev", r"content parity")],
          fail=ONLY_CRITICAL, owner="content",
          how="Open the Content parity sheet; get an SEO sign-off for changed titles / H1s."),
    Check("MAP-05", "Sitemap and content", "No test / demo / duplicate pages published",
          "AUTO", [S("29_live_vs_dev", r"test / demo"), S("14_content", r"duplicate content")], owner="content"),
    Check("MAP-06", "Sitemap and content", "No lorem ipsum, placeholder or debug text",
          "AUTO", [S("14_content", r"placeholder"), S("13_nextjs", r"debug / placeholder")], owner="content"),
    Check("MAP-07", "Sitemap and content", "No empty / very thin pages",
          "AUTO", [S("14_content", None, r"length")], fail=ONLY_CRITICAL, owner="content"),
    Check("MAP-08", "Sitemap and content", "Articles show author and dates", "AUTO",
          [S("14_content", None, r"article")], fail=ONLY_CRITICAL, owner="content"),
    Check("MAP-09", "Sitemap and content", "Testimonials / reviews up to date (newest 5-star reviews added)", "HUMAN",
          owner="client", how="Compare the Google reviews with the reviews on the site; list new ones for the client."),

    # ------------------------------------------------------------------ English content (31, LanguageTool)
    Check("ENG-01", "English content", "No spelling mistakes in the page text",
          "AUTO", [S("31_english", None, r"^spelling$"), S("31_english", r"spelling and grammar")], owner="content"),
    Check("ENG-02", "English content", "No grammar mistakes (verb forms, agreement, repeated phrases)",
          "AUTO", [S("31_english", None, r"^grammar$"), S("31_english", r"\(LanguageTool\)")], owner="content"),
    Check("ENG-03", "English content", "Spacing correct (space after full stops / commas, none before them)",
          "AUTO", [S("31_english", None, r"^spacing$"), S("31_english", r"\(LanguageTool\)")], owner="content"),
    Check("ENG-04", "English content", "Punctuation and typography reviewed (commas, hyphens, capitalisation)",
          "AUTO", [S("31_english", None, r"^(punctuation|typographical)$"), S("31_english", r"\(LanguageTool\)")], fail=NEVER, owner="content"),
    Check("ENG-05", "English content", "Possible word misuse reviewed (their / there, in / on the website ...)",
          "AUTO+HUMAN", [S("31_english", None, r"^word misuse$"), S("31_english", r"\(LanguageTool\)")], fail=NEVER, owner="content",
          how="Read the WARN items of the English Grammar report; real names / terms can be ignored."),

    # ------------------------------------------------------------------ forms
    Check("FRM-01", "Forms", "Lead forms ask for name + email; fields have names, types and autocomplete",
          "AUTO", [S("23_forms", None, r"lead form|fields")], owner="dev"),
    Check("FRM-02", "Forms", "Labels are clean and capitalised; required fields marked and announced",
          "AUTO", [S("23_forms", r"label|required"), S("10_accessibility", r"form field without a label")],
          owner="dev"),
    Check("FRM-03", "Forms", "Empty / invalid submissions are blocked with clear error messages",
          "AUTO", [S("23_forms", None, r"validation|browser")], owner="dev"),
    Check("FRM-04", "Forms", "Submission set up: https endpoint, POST, thank-you page works, spam protection",
          "AUTO", [S("23_forms", None, r"submission|spam|privacy|legal")], owner="dev"),
    Check("FRM-05", "Forms", "A real test submission arrives with clean field names; thank-you page shows",
          "HUMAN", owner="qa", how="Submit each form once with test data; check the email / CRM and the redirect."),
    Check("FRM-06", "Forms", "Site search (if any) returns results", "AUTO", [S("23_forms", None, r"search")],
          owner="dev"),

    # ------------------------------------------------------------------ footer & legal
    Check("FTR-01", "Footer and legal", "Footer links to privacy / terms (and disclaimer on legal sites) work",
          "AUTO", [S("22_business_info", r"footer (has no|link is broken)|no <footer>")], owner="dev"),
    Check("FTR-02", "Footer and legal", "Copyright year is current (generated, not typed)",
          "AUTO", [S("22_business_info", r"copyright")], owner="dev"),
    Check("FTR-03", "Footer and legal", "Legal / utility pages have no lead forms", "AUTO",
          [S("23_forms", r"utility page")], owner="dev"),
    Check("FTR-04", "Footer and legal", "Unknown URLs return a real 404 page with links back",
          "AUTO", [S("09_technical", r"404")], owner="dev"),

    # ------------------------------------------------------------------ code & repo
    Check("CODE-01", "Code and repo", "Production build succeeds", "AUTO", [S("28_repo", r"production build|build fails")],
          owner="dev", how="Stop `next start`, then run  qa.py run CODE-01 --repo-build"),
    Check("CODE-02", "Code and repo", "No ESLint errors and no TypeScript errors",
          "AUTO", [S("28_repo", r"eslint|typescript")], owner="dev"),
    Check("CODE-03", "Code and repo", "README customised; .gitignore complete; no build output committed",
          "AUTO", [S("28_repo", None, r"docs|git")], fail=ONLY_CRITICAL, owner="dev"),
    Check("CODE-04", "Code and repo", "No secrets / .env files committed; security scan of the code clean",
          "AUTO", [S("28_repo", None, r"secrets"), S("28_repo", r"bandit")], owner="dev"),
    Check("CODE-05", "Code and repo", "Dependencies have no high / critical vulnerabilities (npm audit)",
          "AUTO", [S("28_repo", None, r"packages")], owner="dev"),
    Check("CODE-06", "Code and repo", "W3C HTML validator: no errors", "AUTO", [S("25_html_validation")],
          owner="dev"),
    Check("CODE-07", "Code and repo", "No console errors, hydration errors or failed requests",
          "AUTO", [S("13_nextjs", None, r"runtime|hydration|requests|production health", r"debug|console\.log|localhost"),
                   S("12b_lighthouse", r"browser errors")], owner="dev"),
    Check("CODE-08", "Code and repo", "No leftover console.log / localhost / staging URLs",
          "AUTO", [S("13_nextjs", r"console\.log|localhost|development url")], owner="dev"),
    Check("CODE-09", "Code and repo", "Fonts are WOFF2 / WOFF, preloaded, with font-display",
          "AUTO", [S("27_assets", None, r"fonts"), S("13_nextjs", None, r"fonts")], owner="dev"),
    Check("CODE-10", "Code and repo", "Logo is sharp on retina screens (2x bitmap or SVG)",
          "AUTO", [S("27_assets", None, r"logo")], owner="dev"),
    Check("CODE-11", "Code and repo", "Referenced files exist (icons, preload, manifest, feeds, PDFs)",
          "AUTO", [S("27_assets", None, r"referenced files|feed|pdf")], owner="dev"),
    Check("CODE-12", "Code and repo", "ALL CAPS is done with CSS, not typed in the text",
          "AUTO", [S("26_text_quality", r"all caps typed")], fail=NEVER, owner="content"),
    Check("CODE-13", "Code and repo", "Third-party scripts / widgets intended and working (chat, analytics, reviews)",
          "AUTO+HUMAN", [S("16_third_party"), S("19_third_party_urls", r"script|stylesheet|iframe")],
          fail=ONLY_CRITICAL, owner="client", how="Confirm with the client which add-ons (chat, call tracking, "
                                                   "review widgets) the new site must have."),

    # ------------------------------------------------------------------ security
    Check("SEC-01", "Security", "HTTPS everywhere: valid certificate, HTTP -> HTTPS, HSTS, no mixed content",
          "AUTO", [S("11_security", None, r"https|ssl|mixed content", ), S("11_security", r"hsts")], owner="dev"),
    Check("SEC-02", "Security", "Security headers set (CSP, X-Content-Type-Options, frame protection ...)",
          "AUTO", [S("11_security", None, r"^headers$", r"hsts")], fail=ONLY_CRITICAL, owner="dev"),
    Check("SEC-03", "Security", "No exposed files, source maps, server banners or insecure cookies",
          "AUTO", [S("11_security", None, r"exposure|cookies|external scripts|links")], owner="dev"),

    # ------------------------------------------------------------------ performance, accessibility, visual
    Check("PERF-01", "Performance and accessibility", "Lighthouse: no failing scores (Performance, A11y, BP, SEO)",
          "AUTO", [S("12b_lighthouse", r"score|could not")], owner="dev"),
    Check("PERF-02", "Performance and accessibility", "Core Web Vitals pass on a throttled phone (LCP, INP, CLS)",
          "AUTO", [S("12a_cwv")], owner="dev"),
    Check("PERF-03", "Performance and accessibility", "Above-the-fold images not lazy; below-the-fold images lazy",
          "AUTO", [S("04_images", r"lazy")], owner="dev"),
    Check("PERF-04", "Performance and accessibility", "Images optimised (format, size, dimensions, srcset)",
          "AUTO", [S("04_images", None, r"images", r"alt|lazy|broken"), S("13_nextjs", r"next/image")],
          fail=ONLY_CRITICAL, owner="dev"),
    Check("PERF-05", "Performance and accessibility", "Page weight, JavaScript, compression and caching within budget",
          "AUTO", [S("12_performance")], fail=ONLY_CRITICAL, owner="dev"),
    Check("A11Y-01", "Performance and accessibility", "axe-core: no serious / critical accessibility violations",
          "AUTO", [S("10_accessibility", None, r"axe-core|static")], owner="dev"),
    Check("A11Y-02", "Performance and accessibility", "Keyboard: everything reachable, focus visible",
          "AUTO", [S("10_accessibility", None, r"keyboard")], owner="dev"),
    Check("A11Y-03", "Performance and accessibility", "120% / 200% zoom without horizontal scrolling",
          "AUTO", [S("24_navigation", None, r"zoom")], owner="dev"),
    Check("A11Y-04", "Performance and accessibility", "Touch targets big enough on phones",
          "AUTO", [S("10_accessibility", None, r"touch"), S("15_mobile", r"touch")], fail=ONLY_CRITICAL, owner="dev"),
    Check("VIS-01", "Visual", "Mobile layouts: no horizontal scrolling, readable text, usable inputs",
          "AUTO", [S("15_mobile", None, r"mobile|load", r"touch|menu")], owner="dev"),
    Check("VIS-02", "Visual", "Screenshots reviewed: dev matches the approved design", "HUMAN", owner="qa",
          how="Open the screenshots folder of the Navigation report (desktop + phone) next to the Figma frames."),
    Check("VIS-03", "Visual", "Other browsers: Firefox and Safari (WebKit) render without errors",
          "AUTO+HUMAN", [S("24_navigation", None, r"browsers")], owner="dev",
          how="playwright install firefox webkit  enables the automatic part; still check real Safari / iOS once."),
    Check("VIS-04", "Visual", "Animations are smooth and not too slow while scrolling", "HUMAN", owner="qa",
          how="Scroll every main page on a phone and a laptop."),
    Check("VIS-05", "Visual", "Mobile theme colour checked on Android Chrome / iPhone Safari", "HUMAN", owner="qa",
          how="Open the site on a phone and look at the browser bar colour."),
    Check("VIS-06", "Visual", "Live vs dev side-by-side reviewed (visual diff / recording)", "AUTO+HUMAN",
          [S("29_live_vs_dev", None, r"visual")], fail=NEVER, owner="qa",
          how="Run 29 with --visual and look at the *_diff.png images; record a comparison video if required."),
]

BY_ID = {c.id: c for c in CHECKS}
SECTIONS = list(dict.fromkeys(c.section for c in CHECKS))

# which script produces which report key (for qa.py run <ID>)
SCRIPT_FOR_REPORT = {
    "01_sitemap": "01", "02_page_seo": "02", "03_headings": "03", "04_images": "04", "05_links": "05",
    "06_social": "06", "07_schema": "07", "08_hreflang": "08", "09_technical": "09", "10_accessibility": "10",
    "11_security": "11", "12_performance": "12", "12a_cwv": "12a", "12b_lighthouse": "12b", "13_nextjs": "13",
    "14_content": "14", "15_mobile": "15", "16_third_party": "16", "17_heading_order": "17", "18_image_alt": "18",
    "19_third_party_urls": "19", "20_seo_report": "20", "22_business_info": "22", "23_forms": "23",
    "24_navigation": "24", "25_html_validation": "25", "26_text_quality": "26", "27_assets": "27", "28_repo": "28",
    "29_live_vs_dev": "29", "31_english": "31",
}
