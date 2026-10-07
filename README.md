# Website audit scripts

Run these commands (from the project folder):

1. `source .venv/bin/activate`
2. `python "py files/run_all.py"`



Python scripts that audit the website (SEO, links, images, performance, Core Web Vitals, accessibility,
security, mobile, content, Next.js health) and save every report as **Excel and JSON**. The last script, **21**,
combines all of them into one **Website Health** report: a score per category plus every issue from every report,
listed URL by URL.

* **Which server?** `NEXT_PUBLIC_REPORT_URL` in `.env.local` (see section 2).
* **Which pages?** The whole site is **crawled**: the homepage, sitemap.xml and the sitemaps in robots.txt are the
  starting points, and every internal URL found in links, canonicals, hreflang alternates, rel=next/prev, iframes,
  meta refresh, JSON-LD and redirects is followed. Pages that are not in the sitemap are audited too.
  Links that only appear **after JavaScript** (mega-menu tabs, mobile menu, accordions, "load more") are found by
  opening every menu / tab in Chrome during the crawl, then crawled like the others.
* **Every page in every report** - including the Chrome-based ones (Performance, Core Web Vitals, Lighthouse,
  Mobile, accessibility / Next.js / third-party browser checks). Chrome runs several pages in parallel.
  `--pages sample` gives a quick run instead.
* **One row per issue.** If a URL has five problems it has five rows, each with description, current value,
  expected value and recommended fix.

```
py files/
├── run_all.py                        ← runs every script below, one by one (21 last)
├── seo_common.py                     ← shared helpers: crawler, report writer (not run directly)
├── issue_guide.py                    ← description / expected value / fix for every issue type
├── requirements.txt
├── 01_sitemap_checker.py … 16_third_party_checker.py
├── 17_heading_order_report.py … 20_seo_report.py
└── 21_website_health_report.py       ← master report (always last)
```

---

## 1. One-time setup

Python 3.10 or newer is required.

```bash
cd learning-next-my-app
python3 -m venv .venv                       # optional but recommended
source .venv/bin/activate                   # Windows: .venv\Scripts\activate
pip install -r "py files/requirements.txt"
```

The browser-based scripts (10, 12, 12a, 13, 15, 16) and the JavaScript link discovery of the crawl use
**Playwright** with your installed **Google Chrome**. **12b (Lighthouse)** also needs **Node.js** - it runs
`npx --yes lighthouse` (free, downloaded on the first run). If Chrome isn't installed, run once:

```bash
playwright install chromium
```

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
reuse that crawl), then runs **01 → 20** (incl. 12a and 12b) one by one and **21 (Website Health)** last. Everything from one run
shares the same date folder and time stamp.
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
| `--only 02,05,12a` | run only these scripts (21 still runs last) |
| `--skip 12b,12a` | skip these scripts (e.g. Lighthouse, the slowest one) |
| `--no-browser` | no Chrome: skips 12, 12a, 12b, 15, runs 10, 13, 16 without their browser part and crawls without JavaScript discovery |
| `--workers 4` | parallel requests (default 8; lower it if `npm run dev` struggles) |

Default page selection: **every** script checks **every** discovered page (sitemap + crawl + JavaScript-only
links), the Chrome-based ones too. Measured on this site (~540 pages, 4 browser workers on an 8-core Mac) a full
run takes about **4-5 hours**: 12a Core Web Vitals ~70 min, 12b Lighthouse ~60 min, 15 Mobile ~50 min,
12 Performance ~40 min, everything else together ~30 min. Faster options: `--pages sample` (~15 min),
`--skip 12a,12b` (saves ~2 hours), or one script on one section, e.g.
`python3 "py files/12b_lighthouse_checker.py" --only /technologies/`.

## 4. Run ONE report

```bash
python3 "py files/02_page_seo_checker.py"
python3 "py files/05_link_checker.py" --base http://127.0.0.1:4000 --no-external
python3 "py files/12a_core_web_vitals_checker.py" --runs 3
python3 "py files/12b_lighthouse_checker.py" --only /technologies/ --browser-workers 3
python3 "py files/21_website_health_report.py"     # rebuild the master report from the latest reports
```

Every numbered script (01-20) accepts `--base`, `--pages all|sample`, `--limit N` (first N pages),
`--only REGEX` (only URLs matching), `--workers N`, `--browser-workers N`, `--max-pages N`, `--sitemap-only`,
`--fresh-crawl`, `--no-js-discovery` and `--ignore-robots`. `-h` shows each script's own options. A script run on its own reuses a crawl of the same server
from the last 30 minutes (`--fresh-crawl` forces a new one).

---

## 5. Where the reports are saved

```
py files/report/                                 ← created automatically if missing
└── 2026-10-07/                                  ← one folder per date
    ├── excel/
    │   ├── Sitemap_Report_14-30-05.xlsx         ← <Report_Name>_<HH-MM-SS>.xlsx (all sheets)
    │   ├── …
    │   └── Website_Health_Report_14-30-05.xlsx  ← master report of that run
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

## 6. How issues and scores work

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

## 7. What each report checks and shows

### 01 · Sitemap & Crawl Coverage Report - `01_sitemap_checker.py`
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
Checks: title missing / too short (< 30) / too long (> 60) / duplicate / multiple `<title>`; meta description
missing / too short (< 70) / too long (> 160) / duplicate / multiple; meta keywords (reported only when
present - Google ignores them); H1 missing / multiple / empty / too short / same as title; no H2; page topic
(URL slug words) present in title and H1; description mentions the title topic; SEO-friendly URL
(lowercase, hyphens, short, not deep, no IDs/parameters).
Sheet **Pages**: URL, title + length, description + length, meta keywords, H1 text, number of H1-H6,
topic words, URL verdict.

### 03 · Heading Structure Report - `03_heading_checker.py`
Checks: first heading is H1, exactly one H1, no skipped level going down (H2 → H4), empty headings, very long
headings (> 90 chars), duplicate heading text on a page.
Sheets: **Heading Order** (URL, H1-H6 counts, full order "H1 > H2 > H3 …", Status Correct/Incorrect, issue) ·
**Outline** (every heading of every page, indented by level - read the page structure like a table of contents).

### 04 · Image SEO Report - `04_image_seo_checker.py`
Checks every `<img>`: alt missing / empty (OK only for decorative) / generic ("image", "logo") / a file name /
duplicated on the page / keyword-stuffed / > 125 chars; image URL HTTP status (broken images); file size
(> 300 KB = oversized); real format (AVIF / WebP / JPEG / PNG / SVG / GIF - JPEG/PNG should be WebP/AVIF);
width/height attributes (layout shift); real pixel size vs displayed size; lazy loading (below-the-fold
images lazy, first/LCP image not lazy); `srcset` (responsive); next/image used; file-name quality
(`IMG_1234.jpg`, hashes, spaces, uppercase).
Sheets: **Images** (page, image URL, alt, HTTP, bytes, format, width×height attribute, natural size, loading,
srcset, next/image, file name, severity, issues) · **Images per page** (`<img>` count per page).

### 05 · Link Health Report - `05_link_checker.py`
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
Checks: `og:title`, `og:description`, `og:image`, `og:image:alt`, `og:image:width`, `og:image:height`,
`og:url` (= canonical, absolute), `og:type`, `og:site_name`, `og:locale`; OG image reachable, really an image,
not SVG, 1200×630, < 5 MB, width/height tags match the real image; `twitter:card` (summary_large_image),
`twitter:title`, `twitter:description`, `twitter:image` (+ broken); duplicate `og:title`; same share image on
most pages.
Sheets: **Social tags** (every tag per page + OG image HTTP / real size) · **Share images** (each image, HTTP,
type, size, how many pages use it).

### 07 · Structured Data Report - `07_structured_data_checker.py`
Checks: JSON-LD present, parse errors, `@context`, schema types; the expected type per page (Organization +
WebSite on home, Organization/AboutPage, ContactPage, CollectionPage/Blog, BlogPosting/Article on articles,
Service on service / technology / tool pages, CreativeWork on portfolio projects, JobPosting/WebPage on
careers); BreadcrumbList on nested pages; FAQPage when the page has an FAQ section; LocalBusiness when an
address is shown; required and recommended properties per type (e.g. Article: headline, author,
datePublished, image, publisher); breadcrumb items complete; FAQ answers present; duplicate blocks / `@id`s.
Sheets: **Pages** (URL, number of JSON-LD blocks, types) · **Entities** (every schema object: type, @id, name,
properties it has).

### 08 · Hreflang Report - `08_hreflang_checker.py`
Checks: hreflang tags present for every language (en, it, de, fr, es - change with `--languages`), valid
language / country codes, absolute URLs, self-reference, `x-default`, alternates return 200, return links
(the other language links back), duplicate codes / one URL for several languages, `<html lang>`;
**localized routes** (`/it/…`, `/de/…`): status / redirect, `<html lang>` matches, canonical, content really
translated (not an identical English copy), title and description translated.
Sheets: **hreflang tags** (page, code, alternate URL) · **Localized routes** (path, language, URL, HTTP or
redirect, lang, canonical, title, content translated?, description translated?).

### 09 · Technical SEO Report - `09_technical_seo_checker.py`
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
Checks: HTTPS, SSL certificate (valid, issuer, days until expiry, TLS version), HTTP → HTTPS, HSTS (≥ 180 days),
`Content-Security-Policy` (+ weak `unsafe-inline` / `*`), `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
`Permissions-Policy`, `X-Frame-Options` or CSP `frame-ancestors`, `Server` / `X-Powered-By` disclosure, cookie
`Secure` / `SameSite`, mixed content (http:// scripts, styles, images, iframes, forms), third-party scripts
without Subresource Integrity, `target=_blank` without noopener, publicly readable `.env` / `.git` / backups,
exposed JavaScript source maps. (SSL / HSTS / HTTP→HTTPS run only against a public https site.)
Sheets: **Security headers** (each header per page) · **External scripts** (host, URL, SRI, loading) ·
**SSL certificate**.

### 12 · Performance Report - `12_performance_checker.py`  *(Chrome, desktop)*
Measures per page: DNS, connection, TTFB, DOMContentLoaded, load, FCP, LCP (+ which element), CLS, TBT, lab
INP, DOM size / depth, HTML / JS / CSS / image / font KB, total KB, number of requests, third-party requests,
render-blocking resources, **unused JavaScript and CSS** (Chrome coverage), gzip / brotli compression,
`Cache-Control` on `/_next/static`, CDN, HTTP/1.1 vs HTTP/2/3, preload / preconnect / dns-prefetch.
Every page is loaded in a fresh browser context (cold cache, like a first visit).
`--lighthouse` also runs Google Lighthouse (via `npx`) for **Speed Index** and the Lighthouse score (12b runs the full
Lighthouse audit).
Sheets: **Metrics** (one row per page with all numbers above) · **Largest resources** (top 15 per page).

### 12a · Core Web Vitals Report - `12a_core_web_vitals_checker.py`  *(Chrome, throttled mobile)*
Lab test like Lighthouse mobile: phone viewport, Slow 4G, 4× slower CPU, empty cache. **LCP, INP, CLS** plus
FCP, TTFB, TBT (Speed Index with `--lighthouse`), each rated Good / Needs improvement / Poor with Google's
thresholds (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1, FCP ≤ 1.8 s, TTFB ≤ 0.8 s, TBT ≤ 200 ms, SI ≤ 3.4 s) and
PASS / FAIL per page. `--runs 3` uses the median of 3 loads; `--desktop` tests desktop instead.
INP here is a lab estimate from real clicks - real-user INP is in Search Console / PageSpeed Insights.
Sheet **Core Web Vitals** (value + rating for every metric, LCP element, PASS/FAIL).

### 12b · Lighthouse Report - `12b_lighthouse_checker.py`  *(Google Lighthouse via npx, free)*
The engine behind PageSpeed Insights and Chrome DevTools, run locally on every page: **Performance,
Accessibility, Best Practices and SEO scores** (0-100), the lab metrics (FCP, LCP, TBT, CLS, Speed Index, TTI)
and **every failed Lighthouse audit** as its own issue ("Lighthouse: ..." with Lighthouse's description, the
failing elements / resources and its "Learn more" guide). Mobile profile by default, `--desktop` for desktop.
The report score is the average of the four category scores. Needs Node.js; `--skip 12b` leaves it out.
Sheets: **Lighthouse scores** (one row per page) · **Failed audits** (page, category, audit, score, value, examples).

### 13 · NextJS Report - `13_nextjs_checker.py`
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
Checks the text inside `<main>`: empty (< 50 words), very short (< 150), thin (< 300), duplicate pages (identical
text), near-duplicates (≥ 90 % similar), paragraphs repeated on 5+ pages, placeholder text (lorem ipsum,
coming soon, TODO, TBD, dummy, example.com, "test page"), generic AI / filler phrases, blog articles without
author / publication date / updated date, readability (Flesch score < 30, sentences > 28 words).
Sheets: **Pages** (words, Flesch, words per sentence, author, published, updated) · **Near duplicates** (page
pairs + similarity %) · **Repeated paragraphs**.

### 15 · Mobile Report - `15_mobile_checker.py`  *(Chrome, 360 / 390 / 768 px)*
Per viewport: viewport meta, **horizontal scroll** (and which elements cause it), images / tables / fixed modals
wider than the screen, text < 12 px, form fields < 16 px (iPhone zoom) or too wide, touch targets < 24 / 44 px,
buttons with cut-off text, mobile CLS, mobile LCP, and the **mobile menu** (button found, opens real links,
has `aria-expanded`, links fit the screen). Change sizes with `--viewports 375x667,414x896`.
Sheet **Mobile results** (one row per page × viewport).

### 16 · Third Party Report - `16_third_party_checker.py`
HTML (every page): external scripts, stylesheets, fonts, images, iframes, embeds and preconnects, grouped by
vendor (Google Analytics, Tag Manager, Hotjar, Meta Pixel, LinkedIn, YouTube, Google Fonts, reCAPTCHA, Maps,
CDNs, chat widgets …), render-blocking third-party CSS/JS, heavy YouTube embeds.
Browser (every page): every third-party request with status, time, size and type, failed requests, external API
calls, too many third-party requests (> 10 / > 20), slow third-party domains.
Sheets: **Domains** (vendor, pages, requests, KB, avg ms, failed, types) · **Resources in HTML** ·
**Browser requests**.

### 17 · Heading Order Report - `17_heading_order_report.py`
First heading must be H1 and no level may be skipped going down - **every** violation on a page is reported (the
original script stopped at the first one).
Sheet **Heading Order**: URL, H1-H6 counts, heading order, Status (Correct / Incorrect), all problems.

### 18 · Image Alt Report - `18_image_alt_report.py`
Missing alt (Important) and empty alt on non-decorative images (Optimization), one issue per image.
Sheets: **Image Alt Summary** (URL, total images, with alt, missing alt, empty alt, Status Correct / Warning /
Error) · **Image Issues** (page, image number, image URL, status, issue).

### 19 · Third Party URL Report - `19_third_party_url_report.py`
Every third-party URL found in the pages (links, images + srcset, scripts, stylesheets, iframes, media, forms,
embeds) is requested once: broken, timeout, SSL error (Critical for scripts / stylesheets / iframes), redirect,
`http://` on an https page; 401/403/429 answers are "Unverified" (the site blocks bots), not errors.
Sheets: **Third Party Summary** (page, third-party URL, type, HTTP status, Working / Redirect / Error /
Timeout / SSL Error, final URL, redirect chain, error, checked at) · **Third Party Domains** (domain,
occurrences, pages, example URLs).

### 20 · SEO Report (all-in-one) - `20_seo_report.py`
A single-file SEO audit covering the most important points of 01-09 in one workbook (titles, descriptions,
canonical, robots, Open Graph, Twitter, JSON-LD, images, links, duplicates, orphans, slugs, thin content).
Options: `--external` (third-party links), `--hreflang`, `--psi-key KEY` (Google PageSpeed field-style
metrics for public sites). Sheets: **Summary**, **Site-wide**, **Pages** (with a score per page), **Issues**,
**Images**, **Links**, **Duplicates**.

### 21 · Website Health Report - `21_website_health_report.py`  *(master, runs last)*
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
| Content | 5 % | 14 Content |
| Lighthouse | 10 % | 12b Lighthouse (average of its Performance / Accessibility / Best Practices / SEO scores) |

Sheets: **Website Health** (overall score + grade, every category's score / grade / issue counts) · **All Issues
by URL** (every issue from every report with all the columns above; the identical issue found by several reports
on the same URL is listed once, with all of them in "Reported by") · **URL Summary** (per URL: issue counts and
the reports that found them) · **Top issues** (every issue type, worst first, with description and fix) ·
**Reports** (score of each report and its Excel / JSON file). Saved as Excel, JSON and CSV (CSV = All Issues by URL). A category whose scripts
were skipped shows "Not measured" and is left out of the overall score.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `Can't reach http://localhost:3000/` | start the site (`npm run start`), or fix `NEXT_PUBLIC_REPORT_URL` in `.env.local` / pass `--base` |
| a page is missing from the reports | check the **Crawled URLs** sheet of the Sitemap report: it lists every discovered URL and why it wasn't audited (redirect, error, robots.txt, not HTML) |
| `Missing Python packages` | `pip install -r "py files/requirements.txt"` (inside the venv) |
| `This script needs Playwright` / Chrome not found | `pip install playwright`, then install Google Chrome or `playwright install chromium` |
| dev server restarts / errors during the run | use the production build (`npm run build && npm run start`) or `--workers 3` |
| one script failed | the run continues; scroll up in the terminal to its error, then re-run it alone |
| scores look worse on localhost | sitemap / canonical / HTTPS / HSTS checks expect the live https domain - build with `NEXT_PUBLIC_SITE_URL` |
