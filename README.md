# Website audit & QA scripts

Python scripts that audit a running website and produce **client-ready QA reports**: SEO, links, images,
performance, Core Web Vitals, Lighthouse, accessibility, security, mobile, content, Next.js health, business
details (phone / address / email), forms, navigation menus, HTML validity, text hygiene, English spelling &
grammar, assets, the code repository and live-vs-dev parity.

Every report is saved as **Excel, JSON and CSV** (some also as HTML / Markdown). Two master reports run last:

* **21 Website Health** - a score per category plus every issue of every report, URL by URL.
* **30 QA Checklist** - the launch checklist: **one PASS / WARN / FAIL / SKIP / HUMAN status per check** (90 checks
  such as "NAV-04 mobile menu works", "SEO-07 JSON-LD valid", "ENG-01 no spelling mistakes"), a verdict
  (NEEDS FIXES / REVIEW / READY), the evidence behind every FAIL / WARN, notes for the dev team and questions for
  the client - as Excel, JSON, CSV, **Markdown** (paste into the ticket) and an **HTML page** to preview.

`qa.py` is the control panel for all of it: list checks, run one check / script / section or everything, preview,
delete report data and record the results of the checks a person has to do.

---

## Quick start (every QA run, step by step)

1. **Install once** (section 1): `pip install -r "py files/requirements.txt"` inside the project's `.venv`.
2. **Start the website** to audit, e.g. `npm run build && npm run start` (section 2).
3. **Point the scripts at it**: `NEXT_PUBLIC_REPORT_URL=http://localhost:3000` in `.env.local` (or `--base URL`).
4. **Fill in `py files/qa_config.json`** with what the client confirmed: phone, email, address, live URL, legal site
   or not, forbidden terms ... (section 4). Empty values are auto-detected, so a first run works without it.
5. **Run everything**: `python3 "py files/qa.py" run-all` (= `run_all.py`; ~4-5 h on 540 pages; quick check:
   `run-all --pages sample`, ~15 min).
6. **Read the verdict**: `python3 "py files/qa.py" preview` in the terminal, or `preview --open` for the HTML page.
   Every FAIL / WARN lists the URLs and the evidence; the Excel files hold every detail.
7. **Do the human checks** (HUMAN items: real form submission, Safari, design review ...) and record each one:
   `python3 "py files/qa.py" mark FRM-05 pass "test lead arrived in the inbox" --by <name>`.
8. **After the developers fix something**, re-run only what is affected, e.g.
   `python3 "py files/qa.py" run NAV-04 ENG-01` - the checklist is rebuilt automatically.
9. **Hand over**: paste the Markdown checklist (`report/<date>/markdown/QA_Checklist_Report_*.md`) into the ticket,
   attach the Excel files if needed.
10. **Clean up** old data when you want: `python3 "py files/qa.py" delete --date 2026-10-07` (asks first).

```
py files/
├── qa.py                             ← control panel: list / run / run-all / report / preview / status / mark / delete / config
├── run_all.py                        ← runs every numbered script, one by one (21 + 30 last)
├── seo_common.py                     ← shared helpers: crawler, report writer, colours (not run directly)
├── issue_guide.py                    ← description / expected value / fix for every issue type
├── qa_checks.py                      ← the QA checklist: every check and the report issues that decide it
├── qa_config.json                    ← YOUR project settings: confirmed phone / email / address, live URL ... (section 4)
├── qa_human_checks.json              ← results of the human checks (written by qa.py mark - don't edit by hand)
├── requirements.txt
├── 01_sitemap_checker.py … 20_seo_report.py     ← SEO / performance / accessibility / security reports
├── 21_website_health_report.py       ← master report: scores + every issue
├── 22_business_info_checker.py … 29_live_vs_dev_checker.py, 31_english_grammar_checker.py   ← QA checks
└── 30_qa_checklist_report.py         ← master report: PASS / WARN / FAIL / SKIP / HUMAN checklist (always last)
```

---

## Every script: why we run it and how

All scripts take the same basic options (`--base`, `--pages all|sample`, `--only REGEX`, `--limit N` ...,
section 3) and can be run alone (`python3 "py files/<script>"`), by number (`qa.py run 22`) or with everything
(`qa.py run-all`). Details of what each one checks and which sheets it writes are in section 8.

| # | Report | Why we run it | Run it alone |
|---|---|---|---|
| 01 | Sitemap & Crawl Coverage | Google finds pages through sitemap.xml and robots.txt; a broken sitemap or missing pages means pages don't get indexed | `qa.py run 01` |
| 02 | Page SEO | titles, descriptions and H1s are what search results show - wrong length / duplicates cost clicks and rankings | `qa.py run 02` |
| 03 | Heading Structure | a clean heading outline helps search engines and screen-reader users understand each page | `qa.py run 03` |
| 04 | Image SEO | broken, heavy or badly described images hurt speed, SEO and accessibility | `qa.py run 04` |
| 05 | Link Health | broken / placeholder links and orphan pages lose visitors and ranking signals | `qa.py run 05` (`--no-external` faster) |
| 06 | Social Meta | the preview shown when a page is shared (Facebook, LinkedIn, X, WhatsApp) | `qa.py run 06` |
| 07 | Structured Data | JSON-LD gives rich results (FAQ, breadcrumbs, organisation); invalid schema is ignored | `qa.py run 07` |
| 08 | Hreflang | language versions must point at each other or Google shows the wrong language | `qa.py run 08` |
| 09 | Technical SEO | status codes, redirects, canonicals, noindex and broken HTML decide what can be indexed | `qa.py run 09` |
| 10 | Accessibility | WCAG problems (contrast, labels, keyboard) exclude visitors and create legal risk | `qa.py run 10` |
| 11 | Security | HTTPS, security headers, exposed files - basic protection every launch needs | `qa.py run 11` |
| 12 | Performance | page weight, JavaScript, caching: slow pages lose visitors and rankings | `qa.py run 12` |
| 12a | Core Web Vitals | Google's ranking metrics (LCP, INP, CLS) on a throttled phone | `qa.py run 12a` |
| 12b | Lighthouse | the same scores as PageSpeed Insights, for every page | `qa.py run 12b` |
| 13 | NextJS | framework health: metadata per route, hydration / console errors, missing assets | `qa.py run 13` |
| 14 | Content Quality | thin, duplicate or placeholder content is not launch-ready | `qa.py run 14` |
| 15 | Mobile | most visitors are on phones: no sideways scrolling, readable text, usable inputs | `qa.py run 15` |
| 16 | Third Party | analytics / widgets / embeds slow pages down and can fail | `qa.py run 16` |
| 17 | Heading Order | every heading-level skip, page by page | `qa.py run 17` |
| 18 | Image Alt | every image without a text alternative | `qa.py run 18` |
| 19 | Third Party URLs | every external URL the pages use still works | `qa.py run 19` |
| 20 | SEO Report (all-in-one) | one workbook with the main SEO points, for a quick SEO hand-over | `qa.py run 20` |
| 21 | **Website Health** (master) | one score per category and every issue of every report in one place | `qa.py report` |
| 22 | Business Info | wrong phone numbers / addresses / names cost real leads and confuse Google | `qa.py run 22` |
| 23 | Forms | a broken contact form silently loses leads; tests validation without sending anything | `qa.py run 23` |
| 24 | Navigation | menus must really work with a mouse and a finger, on every screen size and zoom level | `qa.py run 24` |
| 25 | HTML Validation | invalid HTML (W3C) behaves differently in each browser and assistive technology | `qa.py run 25` |
| 26 | Text Quality | encoding garbage (`&amp;`, `â€™`), ALL CAPS typed in, leftover old-vendor names | `qa.py run 26` |
| 27 | Assets | icons, fonts, logos, feeds, PDFs and schema images that are missing or wrong | `qa.py run 27` |
| 28 | Repo Audit | the code itself: secrets, ESLint / TypeScript errors, vulnerable packages, README | `qa.py run 28` (`--repo-build` adds the build) |
| 29 | Live vs Dev | on a migration / redesign nothing from the current live site may get lost | `qa.py run 29 --live https://www.example.com` |
| 30 | **QA Checklist** (master) | the launch decision: PASS / WARN / FAIL / SKIP / HUMAN per check + verdict | `qa.py report` |
| 31 | English Grammar & Spelling | typos and grammar mistakes look unprofessional - every URL gets PASS / WARN / FAIL with wrong vs expected text | `qa.py run 31` |

---

## 1. One-time setup

Python 3.10 or newer is required.

```bash
cd learning-next-my-app
python3 -m venv .venv                       # optional but recommended
source .venv/bin/activate                   # Windows: .venv\Scripts\activate
pip install -r "py files/requirements.txt"
```

The browser-based scripts (10, 12, 12a, 13, 15, 16, 23, 24, 27, 31, 29 --visual) and the JavaScript link discovery of the crawl use
**Playwright** with your installed **Google Chrome**. **12b (Lighthouse)** also needs **Node.js** - it runs
`npx --yes lighthouse` (free, downloaded on the first run). If Chrome isn't installed, run once:

```bash
playwright install chromium
playwright install firefox webkit     # optional: 24 also checks the main pages in Firefox and WebKit (Safari)
```

**25 (HTML validation)** uses the official W3C Nu checker locally: it needs **Java** (`java -version`); vnu.jar is
downloaded once with npm into `~/.cache/website-audit-tools`. Without Java it sends only the main pages to the public
validator.w3.org. **31 (English)** runs **LanguageTool** locally (free, open source): `language-tool-python` downloads it once (~250 MB, needs the same Java 17+)
into `~/.cache`. **28 (repo audit)** uses npm / npx (ESLint, tsc, npm audit) and Bandit (in requirements.txt).
All tools are free.


---

## 2. Start the website and set its URL

The scripts audit a running server. Its URL is taken from, in this order:

1. `--base http://…` on the command line
2. the `SITE_BASE_URL` environment variable
3. **`NEXT_PUBLIC_REPORT_URL`** - shell environment, then `.env.local`, then `.env`
4. `http://localhost:3000`

```bash
# .env.local
NEXT_PUBLIC_REPORT_URL=http://localhost:3000        # or https://staging.example.com, http://127.0.0.1:4000 ...
```

Change that one line to audit another server - no script needs editing. Every script's `-h` shows the URL it
will use.

```bash
npm run build && npm run start      # recommended: audits the real production output
# or
npm run dev                         # works, but slower and dev-mode timings are not realistic
```

> For production-accurate canonical / Open Graph / sitemap checks, build with the live domain:
> `NEXT_PUBLIC_SITE_URL=https://your-domain.com npm run build`. With `localhost` the sitemap and
> canonical checks will (correctly) report that URLs point to a development host.

---

## 3. Run ALL reports with one command

```bash
python3 "py files/run_all.py"
# or, the same thing through npm
npm run seo:audit
```

`run_all.py` checks the Python packages and that the site is reachable, **crawls the site once** (all scripts
reuse that crawl), then runs **01 → 31** (incl. 12a and 12b) one by one, then **21 (Website Health)** and **30 (QA
Checklist)** last. Everything from one run shares the same date folder and time stamp.
At the end it prints a summary (OK / FAILED + duration per script).

Useful options (with npm add `--` first, e.g. `npm run seo:audit -- --base http://127.0.0.1:4000`):

| Option | What it does |
|---|---|
| `--base http://127.0.0.1:4000` | audit another server / port (default: `NEXT_PUBLIC_REPORT_URL`, see section 2) |
| `--pages sample` | every main page + 2 detail pages per section (fast, ~45 pages) - also `npm run seo:audit:quick` |
| `--pages all` | every discovered page in every script (the default) |
| `--browser-workers 4` | Chrome / Lighthouse runs in parallel in the browser scripts (default: half the CPU cores, max 4; 12a uses half of it) |
| `--no-js-discovery` | crawl the HTML only - don't open menus / tabs in Chrome to find JavaScript-only links |
| `--max-pages 5000` | stop crawling after this many URLs (the Sitemap report warns when the limit is hit) |
| `--sitemap-only` | don't crawl - audit only the URLs listed in sitemap.xml (the old behaviour) |
| `--ignore-robots` | also crawl URLs that robots.txt disallows |
| `--only 02,05,12a` | run only these scripts (21 + 30 still run last) |
| `--live https://www.example.com` | 29 compares the live site with the audited server (default: `qa_config.json` live_url) |
| `--visual` | 29 also screenshots live + dev main pages and measures the difference |
| `--repo-build` | 28 also runs `npm run build` - **stop `next start` first** (the build rewrites `.next`) |
| `--skip 12b,12a` | skip these scripts (e.g. Lighthouse, the slowest one) |
| `--no-browser` | no Chrome: skips 12, 12a, 12b, 15, 24, runs 10, 13, 16, 23, 27, 31 without their browser part and crawls without JavaScript discovery |
| `--workers 4` | parallel requests (default 8; lower it if `npm run dev` struggles) |

Default page selection: **every** script checks **every** discovered page (sitemap + crawl + JavaScript-only
links), the Chrome-based ones too. Measured on this site (~540 pages, 4 browser workers on an 8-core Mac) a full
run takes about **4-5 hours**: 12a Core Web Vitals ~70 min, 12b Lighthouse ~60 min, 15 Mobile ~50 min,
12 Performance ~40 min, everything else together ~30 min. Faster options: `--pages sample` (~15 min),
`--skip 12a,12b` (saves ~2 hours), or one script on one section, e.g.
`python3 "py files/12b_lighthouse_checker.py" --only /technologies/`.


## 3a. QA control panel - `qa.py`

```bash
python3 "py files/qa.py" list                         # all 90 checks: ID, AUTO / HUMAN, which script decides it
python3 "py files/qa.py" run NAV-04 SEO-07            # run only what these checks need, then rebuild 21 + 30
python3 "py files/qa.py" run 22 25 --pages sample     # by script number (+ any run_all.py option)
python3 "py files/qa.py" run Forms                    # every script of a checklist section
python3 "py files/qa.py" run-all --skip 12a,12b       # everything (same as run_all.py)
python3 "py files/qa.py" report                       # rebuild 21 + 30 from the saved JSON (no new audit)
python3 "py files/qa.py" preview                      # FAIL / WARN / SKIP / HUMAN checks in the terminal
python3 "py files/qa.py" preview --status FAIL --evidence 3 --open    # + 3 evidence lines, open the HTML page
python3 "py files/qa.py" status                       # which reports exist, age, pages, server, human results
python3 "py files/qa.py" mark VIS-03 pass "Safari 18 + iOS 18 OK" --by Priya --rebuild
python3 "py files/qa.py" mark SEO-03 pass "SEO approved new home H1"    # overrides an automatic result too
python3 "py files/qa.py" mark SEO-03 clear
python3 "py files/qa.py" delete --report 22 24        # delete reports (asks first; --yes to skip the question)
python3 "py files/qa.py" delete --date 2026-10-07 | --screenshots | --crawl-cache | --human | --all
python3 "py files/qa.py" config                       # the expected values the checks use
```

**How a check gets its status** (deterministic - the same reports always give the same checklist):

| Status | When |
|---|---|
| **FAIL** | a matching issue has a severity that fails this check (Critical / Important by default; some softer checks fail only on Critical) |
| **WARN** | only lower-severity issues matched - review them |
| **PASS** | the reports the check needs ran and none of their issues matched |
| **SKIP** | a needed report didn't run, or it recorded *Not checked: …* (tool missing, option off, live site blocked) - never a silent PASS |
| **HUMAN** | a person must check it - record the result with `qa.py mark` |

A recorded result (`qa.py mark`) applies to the server it was recorded for and replaces the automatic status (both
are shown). The checklist also notes **partial runs** (e.g. `--pages sample`) and reports **mixed servers / dates**.
Verdict: **NEEDS FIXES** (any FAIL) · **REVIEW** (WARN, SKIP or open human checks) · **READY**.


**What each `qa.py` command is for**

| Command | Use it when |
|---|---|
| `list` | you want to know which checks exist and which script decides each one |
| `run <IDs / numbers / section>` | you fixed something and want to re-test only that (the checklist is rebuilt) |
| `run-all` | a full QA pass (start of QA, before launch) |
| `report` | you only changed `qa_config.json` or recorded human results and want new master reports without re-auditing |
| `preview` | you want the result in the terminal (`--open` for the HTML page) |
| `status` | you want to see which reports exist, how old they are and which server they audited |
| `mark` | a person did a HUMAN check, or SEO / the client signed off a WARN |
| `delete` | you want to remove old reports, screenshots, the crawl cache or the recorded human results |
| `config` | you want to see the settings the checks currently use |


## 4. Project settings - `qa_config.json`

### Why this file exists

The checks need to know **what is correct for this client**, and that can't be read from the website itself:
the phone number the client confirmed, the old domain that is being replaced, whether it is a law firm, the
name of the previous agency whose text must not remain ... Without that, a script can only compare the site with
itself (e.g. "the most common phone number on the site"), which misses a site that is consistently wrong.

So all project-specific expectations live in **one JSON file** instead of inside the Python code: the scripts stay
the same for every project, and for a new project you only edit this file. It is read by 22, 23, 24, 26, 29, 31
and shown with `python3 "py files/qa.py" config`.

Rules: valid JSON, keys starting with `_` are comments (ignored), a missing key uses its default, an **empty value
means "auto-detect / don't check"** - so the file can stay empty on a first run.

### The variables

#### `company` - text
* **What:** the business name exactly as it should be written, e.g. `"Roseman Law Firm, PLLC"`.
* **Used by:** 22 Business Info (NAP-06).
* **Effect:** the name in the Organization JSON-LD, `og:site_name`, the title suffix (`Page | Name`) and the
  copyright line must contain it; differences are **Important** (FAIL).
* **Empty:** the name from the Organization JSON-LD is used as the reference and differences are only
  Optimization (WARN). Legal suffixes (LLC, PLLC, Pvt. Ltd ...) are ignored when comparing.

#### `phones` - list of text
* **What:** the confirmed phone number(s), any format: `["800-745-5259"]`, `["+91 95128 15630", "+1 555 0100"]`
  (one per office / line).
* **Used by:** 22 Business Info (NAP-01, NAP-02), 24 Navigation (phone in the header).
* **Effect:** compared on the last 10 digits (so `+1 (800) 745-5259` = `800.745.5259`). A confirmed number that
  appears nowhere is **Critical**; any other number in the header / footer is **Important**; other numbers in
  page text (e.g. a hotline in a blog post) are listed as Info.
* **Empty:** the most common header / footer number is taken as the main number; several different numbers in
  header / footer give a WARN asking you to confirm them here.

#### `emails` - list of text
* **What:** the confirmed email address(es), e.g. `["info@helpforlemoncars.com"]`.
* **Used by:** 22 Business Info (NAP-04).
* **Effect:** a confirmed address that appears nowhere, or a different address in the header / footer, is
  **Important**. `mailto:` links must always match the address shown (checked with or without this value).
* **Empty:** only the mailto-vs-text checks run.

#### `address` - text
* **What:** the confirmed street address on one line, written like the Google Business Profile, e.g.
  `"445 Fort Pitt Blvd., Ste. 240, Pittsburgh, PA 15219"`.
* **Used by:** 22 Business Info (NAP-05).
* **Effect:** if this address (punctuation and case ignored) is not on the site: **Important**.
* **Empty:** only checks that every page shows the same address (`<address>` element / PostalAddress).

#### `live_url` - text (URL)
* **What:** the **current production site** that the new site replaces, e.g. `"https://www.helpforlemoncars.com"`.
* **Used by:** 29 Live vs Dev (MAP-03, MAP-04, VIS-06). `--live URL` on the command line wins over this value.
* **Effect:** every URL of the live sitemap must exist on the audited server or redirect; content is compared
  page by page (title, H1, text length, noindex, schema, phone numbers).
* **Empty:** 29 reports "Not checked" and the checklist shows **SKIP** for those checks (never a fake PASS).
  If the live site blocks bots (HTTP 403) the checks are SKIP with that reason.

#### `legal_site` - true / false
* **What:** `true` for law firms and other sites that need a disclaimer.
* **Used by:** 22 (footer must link a *disclaimer* page), 23 Forms (every lead form needs a **required**
  "I have read the disclaimer" checkbox linking to it), 24 (a visible phone in the header becomes Important).
* **Default:** `false`.

#### `forbidden_terms` - list of text
* **What:** text that must not appear anywhere in the page HTML (case-insensitive): the previous agency
  (`"findlaw"`), the old brand name, the staging domain, `"lorem ipsum"`, `"wp-content"` (WordPress leftovers).
* **Used by:** 26 Text Quality (NAV-10).
* **Effect:** each hit is **Important**, or Optimization inside `/blog/` posts (an in-text mention in an old article
  can be fine - review it).
* **Default:** `["lorem ipsum", "findlaw", "wp-content"]`; `[]` turns the check off.

#### `required_footer_links` - list of text
* **What:** words that must appear in a footer link's text or URL, e.g. `["privacy", "terms", "accessibility"]`.
* **Used by:** 22 Business Info (FTR-01).
* **Effect:** every page whose footer lacks one of them gets an **Important** issue. On legal sites
  `"disclaimer"` is added automatically.
* **Default:** `["privacy", "terms"]`.

#### `social_profiles` - list of URLs
* **What:** the profile URLs the client confirmed, e.g. `["https://www.facebook.com/helpforlemoncars/"]`.
* **Used by:** 22 Business Info (NAV-06).
* **Effect:** each expected profile that isn't linked on the site is **Important**. Social links on the site are
  always checked: not the network's homepage / a share URL, and responding.
* **Empty:** only the links found on the site are checked; a site with no social links gets a WARN to confirm.

#### `spelling_ignore` - list of text (optional, normally empty)
* **What:** words the English check (31) must never report.
* **Used by:** 31 English Grammar & Spelling (ENG-01).
* **Why it is usually empty:** 31 recognises names, brands and the site's own terms **automatically** (words the
  site uses on several pages or in its URLs, capitalised names, acronyms, file names, British / American
  spellings ...), so there is no word list to maintain. Use this only for a rare word that is still reported after
  you confirmed it is correct.

#### `nav_expected` - list of text
* **What:** top-level menu items that must exist, e.g. `["Home", "About", "Practice Areas", "Reviews", "Contact"]`.
* **Used by:** 24 Navigation (NAV-03).
* **Effect:** an item missing from the header menu is **Important**. (The mobile menu is always compared with the
  desktop menu, with or without this list.)
* **Empty:** no fixed list is checked.

### Example for a law firm

```json
{
  "company": "Roseman Law Firm, PLLC",
  "phones": ["800-745-5259"],
  "emails": ["info@helpforlemoncars.com"],
  "address": "445 Fort Pitt Blvd., Ste. 240, Pittsburgh, PA 15219",
  "live_url": "https://www.helpforlemoncars.com",
  "legal_site": true,
  "forbidden_terms": ["findlaw", "lorem ipsum", "wp-content"],
  "required_footer_links": ["privacy", "accessibility"],
  "social_profiles": ["https://www.facebook.com/helpforlemoncars/"],
  "spelling_ignore": [],
  "nav_expected": ["Home", "About", "Practice Areas", "Reviews", "Contact"]
}
```

### The other support files

| File | Who writes it | What it is for |
|---|---|---|
| `qa_human_checks.json` | `qa.py mark` (don't edit by hand) | the results of the checks a person did (HUMAN items, or a sign-off that overrides an automatic result), with date, name, note and the server they apply to. Kept outside `report/`, so deleting reports doesn't lose them; `qa.py delete --human` clears them. |
| `qa_checks.py` | developers | the checklist itself: every check ID, its section, and which report issues decide PASS / WARN / FAIL. Add a check here when you add a new kind of issue. |
| `issue_guide.py` | developers | the Description / Expected value / Recommended fix text for every issue type. |
| ~~`qa_dictionary.json`~~ | - | **no longer used.** An earlier version of 31 had a hand-written list of allowed words. It was removed: a list like that must be maintained for every project and is itself never checked. 31 now decides dynamically (LanguageTool + the site's own vocabulary), see section 8 / 31. |

---

## 5. Run ONE report

```bash
python3 "py files/02_page_seo_checker.py"
python3 "py files/05_link_checker.py" --base http://127.0.0.1:4000 --no-external
python3 "py files/12a_core_web_vitals_checker.py" --runs 3
python3 "py files/12b_lighthouse_checker.py" --only /technologies/ --browser-workers 3
python3 "py files/21_website_health_report.py"     # rebuild the master report from the latest reports
```

Every numbered script (01-31) accepts `--base`, `--pages all|sample`, `--limit N` (first N pages),
`--only REGEX` (only URLs matching), `--workers N`, `--browser-workers N`, `--max-pages N`, `--sitemap-only`,
`--fresh-crawl`, `--no-js-discovery` and `--ignore-robots`. `-h` shows each script's own options. A script run on its own reuses a crawl of the same server
from the last 30 minutes (`--fresh-crawl` forces a new one).


---

## 6. Where the reports are saved

```
py files/report/                                 ← created automatically if missing
└── 2026-10-07/                                  ← one folder per date
    ├── excel/
    │   ├── Sitemap_Report_14-30-05.xlsx         ← <Report_Name>_<HH-MM-SS>.xlsx (all sheets)
    │   ├── …
    │   └── Website_Health_Report_14-30-05.xlsx  ← master report of that run
    ├── markdown/  html/                         ← QA checklist as Markdown + HTML page, English report as HTML
    ├── screenshots/Navigation_Report_14-30-05/  ← desktop / phone / menu screenshots (24), live vs dev (29 --visual)
    ├── json/
    │   ├── Sitemap_Report_14-30-05.json         ← the same report as JSON
    │   ├── …
    │   └── Website_Health_Report_14-30-05.json
    └── csv/
        ├── Sitemap_Report_14-30-05.csv          ← the "Issues by URL" table (one row per issue)
        ├── …
        └── Website_Health_Report_14-30-05.csv   ← every issue of every report
```

All reports are saved inside `py files/report/` (the folder is created automatically if it doesn't exist).
Only report files are written - no logs or helper files. **Old reports are replaced automatically:**

* a **full run** (`run_all.py` without `--only` / `--skip`) empties `py files/report/` first;
* running **one script** (or `--only` / `--skip`) deletes only that report's previous Excel, JSON and CSV files
  (from any date) when the new ones are saved - other reports are kept.

So the folder always holds just the latest version of each report. (The shared crawl is cached in the system temp folder and
cleaned up after a day.) 


---

## 7. How issues and scores work

Every report is saved as Excel, JSON and CSV. The Excel file has these base sheets:

* **Summary** - score (0-100), grade, pages checked, crawl totals, number of Critical / Important / Optimization
  issues and a table of every issue type (pages affected, description, expected value, fix).
* **Issues by URL** - one row per issue, sorted URL by URL (site-wide and source-code findings last):

  | Column | Content |
  |---|---|
  | URL | page where the issue was found (`(site-wide)`, `file: …` or `route: …` for non-page findings) |
  | Severity / Priority | Critical (P1) · Important (P2) · Optimization (P3) · Info (P4) |
  | Category / Issue | area and name of the check |
  | Description | what is wrong and why it matters |
  | Current value | what was found (e.g. `72 chars: <title text>`, `HTTP 404`, `H2 -> H4`) |
  | Expected / recommended value | what it should be (e.g. `30-60 characters`, `HTTP 200`, `<= 2.5 s`) |
  | Recommended fix | how to fix it in this Next.js project |
  | Element / resource | the image, link, element, header, file … concerned |
  | Details | extra context (other pages sharing a duplicate, viewport, impact …) |
  | Page HTTP / In sitemap | from the crawl |
  | Report | the report that found it |

  The same issue on the same URL is repeated once per element (e.g. every image without alt), up to 50 rows;
  beyond that one row says how many more there are.
* **URL Summary** - one row per URL: HTTP, in sitemap, clicks from home, page score, issue counts and the list of
  issues (pages without issues are listed as "No issues").
* extra sheets with the raw data for that report (described below).

The **CSV** file is the *Issues by URL* table (same columns; opens in Excel / Google Sheets).
The **JSON** file has everything: `report` (score, counts, crawl totals), `issue_types`, `urls` (each URL with
its `issues` list, every issue with `id`, `severity`, `priority`, `category`, `issue`, `description`,
`current_value`, `expected_value`, `recommended_fix`, `element`, `details`, `http_status`, `in_sitemap`),
`site_wide_issues` and `data` (every extra sheet as a list of objects).

| Severity | Meaning | Score impact |
|---|---|---|
| **Critical** (red) | breaks indexing/ranking or the page itself - fix first | -25 per page, -12 site-wide |
| **Important** (orange) | clearly hurts SEO / users | -8 per page, -4 site-wide |
| **Optimization** (blue) | improvement / best practice | -2 per page, -1 site-wide |

Each page starts at 100; a problem counts once per page even if it repeats. The report score is the average
page score minus site-wide problems. Grades: **90-100 Excellent · 80-89 Good · 70-79 Needs Improvement ·
50-69 Poor · 0-49 Critical**.

---

## 8. What each report checks and shows

Each section starts with **Why** we run the report, then what it checks and the extra Excel sheets it writes.

### 01 · Sitemap & Crawl Coverage Report - `01_sitemap_checker.py`
**Why:** Google discovers pages through sitemap.xml and robots.txt; pages missing from the sitemap or blocked by robots.txt get indexed late or never.
Checks: sitemap.xml reachable, valid XML, ≤ 50,000 URLs / 50 MB, served as XML, HTTPS, not a localhost host,
one host, duplicate URLs, upper/lower-case duplicates, `<lastmod>` present / valid / not in the future;
robots.txt reachable, not blocking the site, has `Sitemap:` on the right host; every sitemap URL returns 200
(no redirect), is indexable (no noindex, self canonical) and allowed by robots.txt; **crawl coverage**: live
pages found by crawling but **missing from the sitemap**, broken internal URLs, internal URLs that redirect, URLs
blocked by robots.txt, crawl limit reached - each with the page that links to it.
Sheets: **Sitemap URLs** (URL, HTTP, response ms, indexable, canonical, robots.txt) · **Crawled URLs** (every
discovered URL: HTTP, type, in sitemap, found via, found on, clicks from home, incoming links, redirect target,
noindex, canonical, title) · **robots.txt** (the file, line by line).

### 02 · Page SEO Report - `02_page_seo_checker.py`
**Why:** Title, description and H1 are what people see in search results; wrong lengths and duplicates lower clicks and rankings.
Checks: title missing / too short (< 30) / too long (> 60) / duplicate / multiple `<title>`; meta description
missing / too short (< 70) / too long (> 160) / duplicate / multiple; meta keywords (reported only when
present - Google ignores them); H1 missing / multiple / empty / too short / same as title; no H2; page topic
(URL slug words) present in title and H1; description mentions the title topic; SEO-friendly URL
(lowercase, hyphens, short, not deep, no IDs/parameters).
Sheet **Pages**: URL, title + length, description + length, meta keywords, H1 text, number of H1-H6,
topic words, URL verdict.

### 03 · Heading Structure Report - `03_heading_checker.py`
**Why:** A clean heading outline lets search engines and screen-reader users understand the structure of each page.
Checks: first heading is H1, exactly one H1, no skipped level going down (H2 → H4), empty headings, very long
headings (> 90 chars), duplicate heading text on a page.
Sheets: **Heading Order** (URL, H1-H6 counts, full order "H1 > H2 > H3 …", Status Correct/Incorrect, issue) ·
**Outline** (every heading of every page, indented by level - read the page structure like a table of contents).

### 04 · Image SEO Report - `04_image_seo_checker.py`
**Why:** Images are usually the heaviest part of a page and need text alternatives; broken or oversized images hurt speed, SEO and accessibility.
Checks every `<img>`: alt missing / empty (OK only for decorative) / generic ("image", "logo") / a file name /
duplicated on the page / keyword-stuffed / > 125 chars; image URL HTTP status (broken images); file size
(> 300 KB = oversized); real format (AVIF / WebP / JPEG / PNG / SVG / GIF - JPEG/PNG should be WebP/AVIF);
width/height attributes (layout shift); real pixel size vs displayed size; lazy loading (below-the-fold
images lazy, first/LCP image not lazy); `srcset` (responsive); next/image used; file-name quality
(`IMG_1234.jpg`, hashes, spaces, uppercase).
Sheets: **Images** (page, image URL, alt, HTTP, bytes, format, width×height attribute, natural size, loading,
srcset, next/image, file name, severity, issues) · **Images per page** (`<img>` count per page).

### 05 · Link Health Report - `05_link_checker.py`
**Why:** Broken links lose visitors, placeholder links look unfinished, and pages nobody links to are hard for Google to find.
Checks: internal/external link counts, broken internal links (404 / 5xx), redirecting links, redirect chains and
loops, empty links, `javascript:` links, links without text, non-descriptive anchors ("click here", "read
more"), `nofollow` on internal links, `target=_blank` without `rel=noopener`, `sponsored` / `ugc` (listed),
excessive links (> 150), pages with no / few (< 3) internal links; **architecture**: orphan pages, crawl depth
from the homepage (> 3 clicks), pages not reachable by links, homepage links to every main section, hub pages
(industries, technologies, blog, portfolio, services, tools) link to all their detail pages, breadcrumbs on
nested pages, header and footer links; **links that only appear after clicking a menu / tab** (their status is
checked too, pages linked *only* that way are reported - search engines don't click). External links are checked too (`--no-external` to skip; sites that
block bots show as "unverified").
Sheets: **Link status** (every link target with HTTP, result, redirect path, how many pages link it) ·
**Crawl depth** (clicks from home, incoming and outgoing links per page) · **Hub coverage** · **Header & footer** ·
**All links** (page, link, internal/external, anchor text, rel) · **JavaScript-only links** (page, link, zone
menu / content / footer, whether any HTML link to it exists).

### 06 · Social Meta Report - `06_social_meta_checker.py`
**Why:** Open Graph / Twitter tags decide how a page looks when it is shared on social networks and messengers.
Checks: `og:title`, `og:description`, `og:image`, `og:image:alt`, `og:image:width`, `og:image:height`,
`og:url` (= canonical, absolute), `og:type`, `og:site_name`, `og:locale`; OG image reachable, really an image,
not SVG, 1200×630, < 5 MB, width/height tags match the real image; `twitter:card` (summary_large_image),
`twitter:title`, `twitter:description`, `twitter:image` (+ broken); duplicate `og:title`; same share image on
most pages.
Sheets: **Social tags** (every tag per page + OG image HTTP / real size) · **Share images** (each image, HTTP,
type, size, how many pages use it).

### 07 · Structured Data Report - `07_structured_data_checker.py`
**Why:** Valid JSON-LD earns rich results (FAQ, breadcrumbs, business details); invalid or wrong schema is ignored by Google.
Checks: JSON-LD present, parse errors, `@context`, schema types; the expected type per page (Organization +
WebSite on home, Organization/AboutPage, ContactPage, CollectionPage/Blog, BlogPosting/Article on articles,
Service on service / technology / tool pages, CreativeWork on portfolio projects, JobPosting/WebPage on
careers); BreadcrumbList on nested pages; FAQPage when the page has an FAQ section; LocalBusiness when an
address is shown; required and recommended properties per type (e.g. Article: headline, author,
datePublished, image, publisher); breadcrumb items complete; FAQ answers present; duplicate blocks / `@id`s.
Sheets: **Pages** (URL, number of JSON-LD blocks, types) · **Entities** (every schema object: type, @id, name,
properties it has).

### 08 · Hreflang Report - `08_hreflang_checker.py`
**Why:** Language versions must reference each other, otherwise visitors land on the wrong language and versions compete in search.
Checks: hreflang tags present for every language (en, it, de, fr, es - change with `--languages`), valid
language / country codes, absolute URLs, self-reference, `x-default`, alternates return 200, return links
(the other language links back), duplicate codes / one URL for several languages, `<html lang>`;
**localized routes** (`/it/…`, `/de/…`): status / redirect, `<html lang>` matches, canonical, content really
translated (not an identical English copy), title and description translated.
Sheets: **hreflang tags** (page, code, alternate URL) · **Localized routes** (path, language, URL, HTTP or
redirect, lang, canonical, title, content translated?, description translated?).

### 09 · Technical SEO Report - `09_technical_seo_checker.py`
**Why:** Status codes, redirects, canonicals and noindex decide which pages can be indexed at all.
Checks: HTTP status per page (4xx, 5xx), redirects, redirect chains, redirect loops, unknown URLs return a real
404 (no soft 404) with links back into the site, HTTPS, HTTP → HTTPS (permanent), www / non-www; canonical
missing / duplicate / not self-referencing / relative / pointing to a non-200 page / in `<body>`; noindex /
nofollow / `none` via meta robots, googlebot or `X-Robots-Tag`; URL structure (uppercase, underscores,
parameters, trailing slash); duplicate URLs: trailing-slash, uppercase (live sites only) and `?utm=` variants
must redirect or canonicalise; **HTML health**: doctype, `<html>/<head>/<body>`, charset, viewport, multiple
`<title>` / descriptions, duplicate IDs, empty links / buttons, deprecated tags, links inside links, block
elements inside `<p>`, leaked JSX attributes.
Sheets: **Pages** (final HTTP, redirects, canonical, robots, X-Robots-Tag, HTML size) · **URL variants**
(each variant requested, HTTP, canonical or redirect target).

### 10 · Accessibility Report - `10_accessibility_checker.py`
**Why:** Accessibility problems lock out visitors with disabilities and are a legal risk (WCAG / ADA).
Static (every page): image alt, unnamed `svg role=img`, form fields without labels (placeholder is not a label),
buttons / links without accessible names, heading hierarchy, landmarks (`main`, `header`, `nav`, `footer`),
`<html lang>`, duplicate IDs, broken `aria-labelledby` / `aria-describedby`, invalid ARIA attributes / roles,
`aria-hidden` on focusable elements, positive tabindex, skip link, iframe titles, video captions, live region
for form errors.
Browser (every page, Chrome): **axe-core** (incl. **colour contrast** and ARIA rules), keyboard navigation (Tab
reaches elements), **focus visibility** (focused element shows an outline / ring), clickable elements that
keyboard users can't reach, **touch targets** on a 390 px phone (< 24 px Important, < 44 px Optimization).
Sheet **Browser results** (page, check, axe rule, impact, elements, description, help link).

### 11 · Security Report - `11_security_checker.py`
**Why:** HTTPS and security headers are the minimum protection for visitors and the site.
Checks: HTTPS, SSL certificate (valid, issuer, days until expiry, TLS version), HTTP → HTTPS, HSTS (≥ 180 days),
`Content-Security-Policy` (+ weak `unsafe-inline` / `*`), `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
`Permissions-Policy`, `X-Frame-Options` or CSP `frame-ancestors`, `Server` / `X-Powered-By` disclosure, cookie
`Secure` / `SameSite`, mixed content (http:// scripts, styles, images, iframes, forms), third-party scripts
without Subresource Integrity, `target=_blank` without noopener, publicly readable `.env` / `.git` / backups,
exposed JavaScript source maps. (SSL / HSTS / HTTP→HTTPS run only against a public https site.)
Sheets: **Security headers** (each header per page) · **External scripts** (host, URL, SRI, loading) ·
**SSL certificate**.

### 12 · Performance Report - `12_performance_checker.py`  *(Chrome, desktop)*
**Why:** Page weight and JavaScript decide how fast the site feels; slow pages lose visitors and rankings.
Measures per page: DNS, connection, TTFB, DOMContentLoaded, load, FCP, LCP (+ which element), CLS, TBT, lab
INP, DOM size / depth, HTML / JS / CSS / image / font KB, total KB, number of requests, third-party requests,
render-blocking resources, **unused JavaScript and CSS** (Chrome coverage), gzip / brotli compression,
`Cache-Control` on `/_next/static`, CDN, HTTP/1.1 vs HTTP/2/3, preload / preconnect / dns-prefetch.
Every page is loaded in a fresh browser context (cold cache, like a first visit).
`--lighthouse` also runs Google Lighthouse (via `npx`) for **Speed Index** and the Lighthouse score (12b runs the full
Lighthouse audit).
Sheets: **Metrics** (one row per page with all numbers above) · **Largest resources** (top 15 per page).

### 12a · Core Web Vitals Report - `12a_core_web_vitals_checker.py`  *(Chrome, throttled mobile)*
**Why:** Core Web Vitals are Google's page-experience ranking metrics, measured here like a mid-range phone on a slow network.
Lab test like Lighthouse mobile: phone viewport, Slow 4G, 4× slower CPU, empty cache. **LCP, INP, CLS** plus
FCP, TTFB, TBT (Speed Index with `--lighthouse`), each rated Good / Needs improvement / Poor with Google's
thresholds (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1, FCP ≤ 1.8 s, TTFB ≤ 0.8 s, TBT ≤ 200 ms, SI ≤ 3.4 s) and
PASS / FAIL per page. `--runs 3` uses the median of 3 loads; `--desktop` tests desktop instead.
INP here is a lab estimate from real clicks - real-user INP is in Search Console / PageSpeed Insights.
Sheet **Core Web Vitals** (value + rating for every metric, LCP element, PASS/FAIL).

### 12b · Lighthouse Report - `12b_lighthouse_checker.py`  *(Google Lighthouse via npx, free)*
**Why:** Gives the same scores as PageSpeed Insights / Chrome DevTools, for every page, so results match what clients test themselves.
The engine behind PageSpeed Insights and Chrome DevTools, run locally on every page: **Performance,
Accessibility, Best Practices and SEO scores** (0-100), the lab metrics (FCP, LCP, TBT, CLS, Speed Index, TTI)
and **every failed Lighthouse audit** as its own issue ("Lighthouse: ..." with Lighthouse's description, the
failing elements / resources and its "Learn more" guide). Mobile profile by default, `--desktop` for desktop.
The report score is the average of the four category scores. Needs Node.js; `--skip 12b` leaves it out.
Sheets: **Lighthouse scores** (one row per page) · **Failed audits** (page, category, audit, score, value, examples).

### 13 · NextJS Report - `13_nextjs_checker.py`
**Why:** Next.js-specific problems (missing metadata, hydration errors, missing build assets) break pages in ways other checks don't see.
Source code: every route in `src/app` has `metadata` / `generateMetadata` (dynamic routes need
`generateMetadata` + `generateStaticParams`), pages that are Client Components, `metadataBase` in the root
layout, `robots`, `sitemap`, `manifest`, `favicon`, `icon`, `apple-icon`, `opengraph-image`, `twitter-image`
files, raw `<img>` instead of `next/image`, external font stylesheets instead of `next/font`, `next.config`
(image optimisation, AVIF, production source maps, `poweredByHeader`), hard-coded localhost / staging URLs,
leftover `console.log`.
Rendered pages: duplicate meta tags, dynamic pages showing the default (homepage) title, canonical / OG
absolute, Twitter tags, images not using next/image, development URLs or debug text (`undefined`, `NaN`,
`TODO`) visible on the page.
Browser (every page): console errors, **hydration errors**, uncaught JS errors, failed requests, missing `/_next`
assets, failed API calls, content that only exists after JavaScript (server HTML vs rendered words).
Favicon / browser metadata: favicon, apple-touch-icon, manifest (name, icons 192/512, start_url, display,
colours), theme-color, site name.
Sheets: **Routes** · **Special files** · **Source findings** · **Rendered pages** · **Browser**.

### 14 · Content Quality Report - `14_content_checker.py`
**Why:** Thin, duplicate or placeholder content is not launch-ready and ranks poorly.
Checks the text inside `<main>`: empty (< 50 words), very short (< 150), thin (< 300), duplicate pages (identical
text), near-duplicates (≥ 90 % similar), paragraphs repeated on 5+ pages, placeholder text (lorem ipsum,
coming soon, TODO, TBD, dummy, example.com, "test page"), generic AI / filler phrases, blog articles without
author / publication date / updated date, readability (Flesch score < 30, sentences > 28 words).
Sheets: **Pages** (words, Flesch, words per sentence, author, published, updated) · **Near duplicates** (page
pairs + similarity %) · **Repeated paragraphs**.

### 15 · Mobile Report - `15_mobile_checker.py`  *(Chrome, 360 / 390 / 768 px)*
**Why:** Most visitors use phones; sideways scrolling, tiny text and unusable inputs make them leave.
Per viewport: viewport meta, **horizontal scroll** (and which elements cause it), images / tables / fixed modals
wider than the screen, text < 12 px, form fields < 16 px (iPhone zoom) or too wide, touch targets < 24 / 44 px,
buttons with cut-off text, mobile CLS, mobile LCP, and the **mobile menu** (button found, opens real links,
has `aria-expanded`, links fit the screen). Change sizes with `--viewports 375x667,414x896`.
Sheet **Mobile results** (one row per page × viewport).

### 16 · Third Party Report - `16_third_party_checker.py`
**Why:** Analytics tags, widgets and embeds slow pages down and can fail or leak data.
HTML (every page): external scripts, stylesheets, fonts, images, iframes, embeds and preconnects, grouped by
vendor (Google Analytics, Tag Manager, Hotjar, Meta Pixel, LinkedIn, YouTube, Google Fonts, reCAPTCHA, Maps,
CDNs, chat widgets …), render-blocking third-party CSS/JS, heavy YouTube embeds.
Browser (every page): every third-party request with status, time, size and type, failed requests, external API
calls, too many third-party requests (> 10 / > 20), slow third-party domains.
Sheets: **Domains** (vendor, pages, requests, KB, avg ms, failed, types) · **Resources in HTML** ·
**Browser requests**.

### 17 · Heading Order Report - `17_heading_order_report.py`
**Why:** Lists every heading-level skip page by page, for fixing heading structure quickly.
First heading must be H1 and no level may be skipped going down - **every** violation on a page is reported (the
original script stopped at the first one).
Sheet **Heading Order**: URL, H1-H6 counts, heading order, Status (Correct / Incorrect), all problems.

### 18 · Image Alt Report - `18_image_alt_report.py`
**Why:** Lists every image without a text alternative, page by page.
Missing alt (Important) and empty alt on non-decorative images (Optimization), one issue per image.
Sheets: **Image Alt Summary** (URL, total images, with alt, missing alt, empty alt, Status Correct / Warning /
Error) · **Image Issues** (page, image number, image URL, status, issue).

### 19 · Third Party URL Report - `19_third_party_url_report.py`
**Why:** External URLs (scripts, images, embeds, links) change or disappear; this confirms they still work.
Every third-party URL found in the pages (links, images + srcset, scripts, stylesheets, iframes, media, forms,
embeds) is requested once: broken, timeout, SSL error (Critical for scripts / stylesheets / iframes), redirect,
`http://` on an https page; 401/403/429 answers are "Unverified" (the site blocks bots), not errors.
Sheets: **Third Party Summary** (page, third-party URL, type, HTTP status, Working / Redirect / Error /
Timeout / SSL Error, final URL, redirect chain, error, checked at) · **Third Party Domains** (domain,
occurrences, pages, example URLs).

### 20 · SEO Report (all-in-one) - `20_seo_report.py`
**Why:** One workbook with the most important SEO points, for a quick hand-over to the SEO team.
A single-file SEO audit covering the most important points of 01-09 in one workbook (titles, descriptions,
canonical, robots, Open Graph, Twitter, JSON-LD, images, links, duplicates, orphans, slugs, thin content).
Options: `--external` (third-party links), `--hreflang`, `--psi-key KEY` (Google PageSpeed field-style
metrics for public sites). Sheets: **Summary**, **Site-wide**, **Pages** (with a score per page), **Issues**,
**Images**, **Links**, **Duplicates**.

### 21 · Website Health Report - `21_website_health_report.py`  *(master, runs last)*
**Why:** One overall score and every issue of every report in one place, without duplicates.
Combines all reports of the run - the scores and **every issue**, URL by URL:

| Category | Weight | From reports |
|---|---|---|
| Technical SEO | 15 % | 01 Sitemap, 08 Hreflang, 09 Technical SEO, 13 NextJS |
| On-Page SEO | 15 % | 02 Page SEO, 03 Headings, 06 Social Meta, 17 Heading Order, 20 SEO Report |
| Performance | 15 % | 12 Performance, 12a Core Web Vitals, 16 Third Party |
| Accessibility | 10 % | 10 Accessibility |
| Security | 8 % | 11 Security |
| Image | 7 % | 04 Image SEO, 18 Image Alt |
| Link Health | 10 % | 05 Links, 19 Third Party URLs |
| Structured Data | 5 % | 07 Structured Data |
| Mobile | 10 % | 15 Mobile |
| Content | 5 % | 14 Content, 31 English Grammar |
| Lighthouse | 10 % | 12b Lighthouse (average of its Performance / Accessibility / Best Practices / SEO scores) |
| Business info & Forms | 8 % | 22 Business Info, 23 Forms |
| Navigation | 7 % | 24 Navigation |
| Code & Repo | 5 % | 28 Repo Audit |
| Migration (live vs dev) | 5 % | 29 Live vs Dev |

25 HTML Validation counts in Technical SEO, 26 Text Quality in On-Page SEO and 27 Assets in Performance.

Sheets: **Website Health** (overall score + grade, every category's score / grade / issue counts) · **All Issues
by URL** (every issue from every report with all the columns above; the identical issue found by several reports
on the same URL is listed once, with all of them in "Reported by") · **URL Summary** (per URL: issue counts and
the reports that found them) · **Top issues** (every issue type, worst first, with description and fix) ·
**Reports** (score of each report and its Excel / JSON file). Saved as Excel, JSON and CSV (CSV = All Issues by URL). A category whose scripts
were skipped shows "Not measured" and is left out of the overall score.

---

### 22 · Business Info Report - `22_business_info_checker.py`
**Why:** A wrong phone number, email or address on a business site costs real leads and confuses Google's business listing.
Phone numbers written on every page vs the confirmed number(s) (`qa_config.json` phones, else the most common
header / footer number), written numbers that aren't tel: links, **tel: / mailto: links that dial / mail something
else than the text shows**, phone visible in the header, JSON-LD telephone / email shown on the page, the same
address on every page (and the confirmed one), one business name across Organization JSON-LD / og:site_name / title
suffix / copyright, required footer links (privacy, terms, disclaimer on legal sites) that work, copyright with the
current year, social links that are real profiles (not the network homepage / a share URL) and respond.
Sheets: **Phone numbers** · **Emails** · **Business names** · **Social links** · **Contact per page**.

### 23 · Forms Report - `23_forms_checker.py`
**Why:** A contact form that silently fails loses every lead; this tests validation in a real browser without sending anything.
HTML (every form on every page): lead forms ask for name + email, fields have names / ids, labels showing `*` match
`required` / `aria-required`, type=email / type=tel, autocomplete, submit button with text, https + POST, the
thank-you redirect works, spam protection, privacy notice, the legal-site disclaimer checkbox, no lead forms on
legal / utility pages. **Chrome (every unique form once):** submits the **empty** form and an **invalid email** -
nothing may be sent, errors must show, focus should move to the first invalid field; site search returns results.
**Every POST is blocked during the test, so nothing is ever submitted.**
Sheets: **Forms** (each unique form, its fields, on how many pages) · **Browser tests**.

### 24 · Navigation Report - `24_navigation_checker.py`  *(Chrome, real mouse / taps)*
**Why:** Menus have to work with a real mouse and a real finger - a menu button that is off-screen on a phone hides the whole site.
Desktop (1440 px, each distinct header): every dropdown opens on hover or click and stays on screen, every menu
link is 200, `nav_expected` items exist, phone visible. Phone (390 + 360 px): the menu button is on screen and can
be **really tapped** (a JavaScript click would hide an off-screen / covered button), the menu opens, links aren't
cut off, sub-menus (also nested ones) open, it closes (Escape / close button), **the mobile menu offers every page
of the desktop menu**, tap-to-call. Every page: **120 % and 200 % zoom** without horizontal scrolling. Screenshots
of the main pages (desktop + phone + menus) for the visual review; the main pages in **Firefox and WebKit** when
installed. Options: `--screenshots all|main|none`, `--no-zoom`, `--engines firefox,webkit`.
Sheets: **Menus** · **Desktop menu links** · **Zoom** · **Other browsers**.

### 25 · HTML Validation Report - `25_html_validation_checker.py`
**Why:** Invalid HTML is repaired differently by every browser and screen reader; the W3C validator is the reference QA teams use.
Every page's HTML through the **W3C Nu checker** (vnu.jar, locally): errors = Important, warnings = Optimization;
messages that differ only in a quoted value are grouped. Sheets: **Distinct messages** · **Pages**.

### 26 · Text Quality Report - `26_text_quality_checker.py`
**Why:** Encoding artefacts (&amp;, â€™), ALL CAPS typed into the text and names of the previous vendor look unprofessional and are easy to miss.
HTML entities shown as text (`&amp;`, `&#39;`) and mojibake (`â€™`) in titles, descriptions, social tags and text;
titles / H1s in ALL CAPS, all lowercase or with extra spaces; ALL CAPS typed in the text (use CSS
`text-transform`); `forbidden_terms` from `qa_config.json` anywhere in the HTML. Spelling and grammar are checked by
31. Sheet: **Pages**.

### 27 · Assets Report - `27_assets_checker.py`
**Why:** Icons, fonts, logos, feeds and the images referenced in schema are often forgotten in a migration.
Every URL inside JSON-LD and every icon / manifest / preload link responds (e.g. a schema image that was never
uploaded); JSON-LD value formats (jsonschema: absolute URLs, ISO dates, headline length); fonts WOFF2 / WOFF with
font-display and a preload; favicon / apple-touch-icon / manifest icon sizes (Pillow); **logo sharp on retina**
(Chrome at 2x); RSS / Atom feed valid with entries; linked PDFs (size, and with PyMuPDF: title, text layer).
Sheets: **Referenced files** · **Fonts** · **Icons** · **Logos** · **Feeds** · **PDFs**.

### 28 · Repo Audit Report - `28_repo_audit.py`  *(source code, no server needed)*
**Why:** Problems in the code itself: committed secrets, lint / TypeScript errors, vulnerable packages, an unusable README.
README customised and complete, `.gitignore` covers node_modules / .next / .env / __pycache__, no `.env` / keys /
build output committed, no huge files, one lockfile, **secrets in committed files** (private keys, AWS / GitHub /
Stripe / Slack tokens, hard-coded passwords), package.json scripts and pinned versions, **npm audit**, **ESLint**
(the committed JS / TS), **TypeScript** (`tsc --noEmit`), **Bandit** on the Python scripts, TODO count;
`--build` (or `run_all.py --repo-build`) also runs the production build.
Sheets: **npm audit** · **ESLint** · **TypeScript** · **Bandit** · **TODO comments** · **Dependencies**.

### 29 · Live vs Dev Report - `29_live_vs_dev_checker.py`
**Why:** On a redesign or migration every old URL and its content must survive, or rankings and links are lost.
Needs the live site (`--live` / `qa_config.json` live_url; otherwise every check is SKIP). Every URL of the live
sitemap (or a crawl when it has none) must exist on the audited server or redirect to a working page (not the
homepage); per page on both: noindex now, much less text, title / H1 / description changed, H2 sections and schema
types lost, phone / fax numbers dropped; dev-only pages that look like test / demo pages or `-2` duplicates.
`--visual` screenshots the main pages on both and measures the pixel difference (Pillow).
Sheets: **Live URLs** · **Content parity** · **Only on dev** · **Visual diff**.

### 30 · QA Checklist Report - `30_qa_checklist_report.py`  *(master, runs after 21)*
**Why:** Turns all reports into the launch decision: PASS / WARN / FAIL / SKIP / HUMAN per check and a verdict.
See section 3a. Excel sheets: **Summary** · **Checklist** (status, automatic status, result, owner, counts) ·
**Evidence** (every issue behind each check) · **Human checks** · **Reports**; plus JSON, CSV, Markdown and HTML.

### 31 · English Grammar & Spelling Report - `31_english_grammar_checker.py`
**Why:** spelling and grammar mistakes look unprofessional to clients and visitors and are hard to spot by reading
hundreds of pages; this gives every URL a clear PASS / WARN / FAIL with the wrong text next to the correct text.

**How it checks (no word lists to maintain):**
1. Every page is opened in Chrome and its **visible text is read exactly as visitors see it** (`innerText`, also
   text rendered by JavaScript; `--no-browser` reads the server HTML instead). Text in code blocks is skipped.
2. Each **unique text block** is checked once with **LanguageTool** (free, open source, runs locally; the engine
   behind many writing tools) - spelling, grammar, punctuation, typography, spacing and confused words.
   Text repeated on many pages (header, footer, shared sections) is reported once, on the first page, with
   "also on N other pages".
3. False positives are removed **dynamically**, from the site itself: words used on 3+ pages / in 3+ text blocks /
   in the site's URLs are its vocabulary (Redis, Figma, Ahmedabad ...); a capitalised word used on 2+ pages is a
   name; capitalised words mid-sentence, acronyms (NHTSA), words with digits / dots / camelCase (Next.js, iPhone),
   file extensions (.tsx), hyphenated compounds and British / American variants (organise / organize) are not
   reported as misspellings; a capitalised near-miss is only a WARN ("possible - probably a name").
   A handful of LanguageTool rules that don't fit website copy (headings without a full stop, typographic quotes
   ...) are switched off in the script (`WEB_COPY_RULES`).
4. Spelling suggestions are ranked so the expected text is the likely word ("vehical" -> **vehicle**).

**Status per URL:** **PASS** (light green) no issue · **WARN** (light yellow) only possible issues (punctuation,
typography, word misuse, capitalised near-misses) · **FAIL** (light red) a spelling, grammar or spacing mistake ·
**SKIP** not an English page (`<html lang>`) or no text.

**Every issue shows:** Check ID · URL · page title · status · issue type (Spelling / Grammar / Punctuation /
Typographical / Spacing / Word misuse) · severity · **Wrong input** (the exact wrong text, red) · **Actual output**
(the sentence as it is on the page now, red) · **Expected output** (the sentence with the correction, green) ·
suggested correction(s) · reason · location (zone, element, character position) · confidence (High / Medium / Low)
· the LanguageTool rule.

Example (from the test page):

| Wrong input | Actual output | Expected output | Reason |
|---|---|---|---|
| `was been` | He was been arrested by police after the crash. | He was arrested by police after the crash. | Did you mean "was" or "has been"? |
| `vehical` | The vehical has several problems with the brakes and steering. | The vehicle has several problems with the brakes and steering. | Possible spelling mistake |
| `issuesthat` | We explain the common issuesthat drivers face with dealers. | We explain the common issues that drivers face with dealers. | Possible spelling mistake (missing space) |

**Outputs:** Excel (sheets **URL results** - every URL with status, sections, words and counts per type, coloured;
**Issue details** - every issue with all the columns above, wrong text red / expected text green; **Summary
counts**; plus the standard Summary / Issues by URL / URL Summary), JSON, CSV and an **HTML page**
(`report/<date>/html/English_Grammar_Report_<time>.html`) with summary cards, a filter (FAIL / WARN / PASS / SKIP)
and, per URL, boxes for Wrong input / Actual output (red), Expected output (green) and the reason.

Options: `--language en-GB` (default `en-US`), `--style` (also wordiness / redundancy suggestions), `--no-browser`,
`--public-api` (use the public LanguageTool server instead of Java - rate-limited, main pages only).
Checklist: ENG-01 spelling, ENG-02 grammar, ENG-03 spacing (FAIL on errors), ENG-04 punctuation / typography and
ENG-05 word misuse (review-only, WARN).


## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `Can't reach http://localhost:3000/` | start the site (`npm run start`), or fix `NEXT_PUBLIC_REPORT_URL` in `.env.local` / pass `--base` |
| a page is missing from the reports | check the **Crawled URLs** sheet of the Sitemap report: it lists every discovered URL and why it wasn't audited (redirect, error, robots.txt, not HTML) |
| `Missing Python packages` | `pip install -r "py files/requirements.txt"` (inside the venv) |
| `This script needs Playwright` / Chrome not found | `pip install playwright`, then install Google Chrome or `playwright install chromium` |
| dev server restarts / errors during the run | use the production build (`npm run build && npm run start`) or `--workers 3` |
| one script failed | the run continues; scroll up in the terminal to its error, then re-run it alone |
| a check is SKIP | the result line says why (script not run, `Not checked: …` with the fix, e.g. install Java / Firefox, pass `--live`); run it with `qa.py run <ID>` |
| a PASS / FAIL is wrong for this project | adjust `qa_config.json` (confirmed values, forbidden terms ...) or record a sign-off with `qa.py mark <ID> pass "reason"` |
| scores look worse on localhost | sitemap / canonical / HTTPS / HSTS checks expect the live https domain - build with `NEXT_PUBLIC_SITE_URL` |
| 31 says `Not checked: spelling and grammar (LanguageTool)` | install Java 17+ (`brew install openjdk`) and `pip install language-tool-python`; the first run downloads LanguageTool (~250 MB) - or use `--public-api` |
| 31 reports a correct word | if it's a real name / term used only once, add it to `qa_config.json` `spelling_ignore`, or record a sign-off with `qa.py mark ENG-01 pass "reason"` |
