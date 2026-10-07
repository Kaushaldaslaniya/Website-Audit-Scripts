# Website Audit Scripts

**Complete Website SEO, Performance, Accessibility, Security & Health Audit System**

A Python-based website auditing system for **Next.js and modern websites**. It crawls the complete website, discovers URLs beyond the sitemap, runs 21 audit/report scripts, and generates detailed **Excel, JSON, and CSV reports**.

Created and maintained by **CodeWithKD**.

---

## 🚀 What This Project Does

This project performs a complete website health audit covering:

* SEO
* Technical SEO
* Sitemap & crawl coverage
* Page metadata
* Headings
* Images
* Links
* Open Graph / Social metadata
* Structured data
* Hreflang
* Accessibility
* Security
* Performance
* Core Web Vitals
* Mobile responsiveness
* Content quality
* Next.js implementation
* Third-party resources
* Website architecture
* Overall website health

The system does **not rely only on `sitemap.xml`**.

It starts with the sitemap and then discovers additional internal URLs through the website itself.

---

# ⭐ Main Features

### Complete Website Crawling

The crawler starts from:

* Homepage
* `sitemap.xml`
* Sitemaps declared in `robots.txt`

It then discovers additional internal URLs from:

* Internal links
* Canonical URLs
* Hreflang URLs
* `rel="next"` / `rel="prev"`
* Iframes
* Meta refresh
* JSON-LD
* Redirects
* Other crawlable website resources

Therefore, pages that are **not included in the sitemap can still be discovered and audited**.

---

### 📊 Detailed Reports

Every audit generates:

```text
Excel
JSON
CSV
```

Each issue is associated with the exact URL where it was detected.

If one URL contains 10 issues, all 10 issues are reported separately.

Example:

```text
URL: /about

Issue 1 → Missing meta description
Issue 2 → Multiple H1 headings
Issue 3 → Missing image alt text
Issue 4 → Broken internal link
Issue 5 → Missing canonical
```

No issue is overwritten or lost.

---

# 📁 Project Structure

```text
py files/
│
├── run_all.py
├── seo_common.py
├── issue_guide.py
├── requirements.txt
│
├── 01_sitemap_checker.py
├── 02_page_seo_checker.py
├── 03_heading_checker.py
├── 04_image_seo_checker.py
├── 05_link_checker.py
├── 06_social_meta_checker.py
├── 07_structured_data_checker.py
├── 08_hreflang_checker.py
├── 09_technical_seo_checker.py
├── 10_accessibility_checker.py
├── 11_security_checker.py
├── 12_performance_checker.py
├── 12a_core_web_vitals_checker.py
├── 13_nextjs_checker.py
├── 14_content_checker.py
├── 15_mobile_checker.py
├── 16_third_party_checker.py
├── 17_heading_order_report.py
├── 18_image_alt_report.py
├── 19_third_party_url_report.py
├── 20_seo_report.py
│
└── 21_website_health_report.py
    └── Master website health report
```

### Shared files

| File                          | Purpose                                                   |
| ----------------------------- | --------------------------------------------------------- |
| `run_all.py`                  | Runs all audit scripts in sequence                        |
| `seo_common.py`               | Shared crawler, URL, report and utility functions         |
| `issue_guide.py`              | Issue descriptions, expected values and recommended fixes |
| `21_website_health_report.py` | Combines all reports into one master report               |

---

# 🛠️ 1. Installation

## Requirements

* Python **3.10+**
* Node.js
* npm
* Running website
* Google Chrome for browser-based checks

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r "py files/requirements.txt"
```

---

## Browser Setup

Several reports use **Playwright** and Chromium for browser-based testing.

If required:

```bash
playwright install chromium
```

These browser-based checks are used for areas such as:

* Performance
* Core Web Vitals
* Accessibility
* Mobile
* Next.js runtime checks
* Third-party requests

---

# 🌐 2. Start Your Website

The audit scripts require a running website.

Recommended:

```bash
npm run build
npm run start
```

Development mode can also be used:

```bash
npm run dev
```

For the most accurate production audit, use:

```bash
npm run build && npm run start
```

---

# ⚙️ 3. Configure Website URL

The audit URL is selected in this order:

1. `--base`
2. `SITE_BASE_URL`
3. `NEXT_PUBLIC_REPORT_URL`
4. `.env.local`
5. `.env`
6. `http://localhost:3000`

Example:

```env
NEXT_PUBLIC_REPORT_URL=http://localhost:3000
```

For staging:

```env
NEXT_PUBLIC_REPORT_URL=https://staging.example.com
```

For another local port:

```env
NEXT_PUBLIC_REPORT_URL=http://127.0.0.1:4000
```

No Python script needs to be modified when changing the website URL.

---

# 🌍 Production Domain

For accurate production SEO checks, build the application using the actual website domain.

Example:

```bash
NEXT_PUBLIC_SITE_URL=https://your-domain.com npm run build
```

This is important for checks such as:

* Canonical URLs
* Open Graph URLs
* Sitemap URLs
* HTTPS
* Production host
* Absolute URLs

Using `localhost` can intentionally cause these checks to report development URLs.

---

# ▶️ 4. Run the Complete Audit

The easiest way to run everything:

```bash
python3 "py files/run_all.py"
```

Or, if configured in `package.json`:

```bash
npm run seo:audit
```

The execution order is:

```text
01
 ↓
02
 ↓
03
 ↓
...
 ↓
20
 ↓
21 Website Health Report
```

`21_website_health_report.py` always runs last because it combines the results from the other reports.

---

# ⚡ Quick Audit

For a faster audit:

```bash
python3 "py files/run_all.py" --pages sample
```

Or:

```bash
npm run seo:audit:quick
```

---

# 🔧 5. Audit Options

| Option             | Description                     |
| ------------------ | ------------------------------- |
| `--base URL`       | Audit a specific website/server |
| `--pages all`      | Audit every discovered page     |
| `--pages sample`   | Use a smaller page sample       |
| `--max-pages N`    | Maximum URLs to crawl           |
| `--sitemap-only`   | Audit sitemap URLs only         |
| `--ignore-robots`  | Ignore robots.txt restrictions  |
| `--only 02,05,12a` | Run only selected reports       |
| `--skip 12,15`     | Skip selected reports           |
| `--no-browser`     | Disable browser-based checks    |
| `--workers N`      | Number of parallel requests     |
| `--fresh-crawl`    | Force a new crawl               |
| `--limit N`        | Limit pages checked by a script |
| `--only REGEX`     | Audit URLs matching a pattern   |

Example:

```bash
python3 "py files/run_all.py" \
  --base http://127.0.0.1:4000 \
  --pages all \
  --workers 4
```

---

# 🧪 6. Run an Individual Report

Example:

```bash
python3 "py files/02_page_seo_checker.py"
```

Link audit:

```bash
python3 "py files/05_link_checker.py" \
  --base http://127.0.0.1:4000
```

Core Web Vitals:

```bash
python3 "py files/12a_core_web_vitals_checker.py" \
  --runs 3 \
  --pages all
```

Rebuild the master report:

```bash
python3 "py files/21_website_health_report.py"
```

Use:

```bash
python3 "py files/XX_script.py" -h
```

to see the available options for any individual report.

---

# 📂 7. Report Output

Reports are automatically created inside:

```text
py files/report/
```

If the folder does not exist, it is created automatically.

The structure is:

```text
py files/
└── report/
    └── 2026-10-07/
        │
        ├── excel/
        │   ├── Sitemap_Report_14-30-05.xlsx
        │   ├── Page_SEO_Report_14-30-05.xlsx
        │   ├── Image_SEO_Report_14-30-05.xlsx
        │   └── Website_Health_Report_14-30-05.xlsx
        │
        ├── json/
        │   ├── Sitemap_Report_14-30-05.json
        │   ├── Page_SEO_Report_14-30-05.json
        │   └── Website_Health_Report_14-30-05.json
        │
        └── csv/
            ├── Sitemap_Report_14-30-05.csv
            ├── Page_SEO_Report_14-30-05.csv
            └── Website_Health_Report_14-30-05.csv
```

---

# 🔄 Report Management

A complete audit run automatically manages previous reports.

### Full run

```bash
python3 "py files/run_all.py"
```

The previous report contents are replaced with the latest complete run.

### Individual report

If you run only one report, only that report's previous files are replaced.

Other reports remain unchanged.

This keeps the report directory clean and prevents outdated versions from being mixed with the latest results.

---

# 📋 8. Report Structure

Each report contains detailed information such as:

* URL
* HTTP status
* Page title
* Category
* Issue
* Severity
* Priority
* Description
* Current value
* Expected value
* Recommended fix
* Element/resource
* Additional details
* Source report

---

# 🔴 Severity Levels

| Severity         | Priority | Meaning                                                                                      |
| ---------------- | -------- | -------------------------------------------------------------------------------------------- |
| **Critical**     | P1       | Major issue affecting website functionality, indexing, security or important user experience |
| **Important**    | P2       | Significant SEO, accessibility, performance or usability problem                             |
| **Optimization** | P3       | Recommended improvement or best practice                                                     |
| **Info**         | P4       | Informational finding                                                                        |

---

# 📊 9. Website Health Score

The master report calculates scores for:

| Category        | Weight |
| --------------- | -----: |
| Technical SEO   |    15% |
| On-Page SEO     |    15% |
| Performance     |    15% |
| Accessibility   |    10% |
| Security        |     8% |
| Images          |     7% |
| Link Health     |    10% |
| Structured Data |     5% |
| Mobile          |    10% |
| Content         |     5% |

### Score Grades

|  Score | Grade             |
| -----: | ----------------- |
| 90–100 | Excellent         |
|  80–89 | Good              |
|  70–79 | Needs Improvement |
|  50–69 | Poor              |
|   0–49 | Critical          |

> **Important:** This is an internal website-audit score. It is not a Google ranking score and does not guarantee search-engine rankings.

---

# 📑 10. Master Website Health Report

The final report is generated by:

```text
21_website_health_report.py
```

It combines the results of the other audit scripts.

The master report includes:

### Website Health

* Overall score
* Overall grade
* Category scores
* Issue counts
* Critical issues
* Important issues
* Optimization issues

### All Issues by URL

Every issue is listed against the exact URL where it was detected.

If a URL contains multiple issues, every issue is retained.

### URL Summary

Each URL includes:

* HTTP status
* Sitemap status
* Page score
* Issue count
* Critical issues
* Important issues
* Optimization issues
* Reports that detected the issues

### Top Issues

The most common and highest-priority issues are listed first with:

* Issue
* Description
* Number of affected pages
* Severity
* Recommended fix

---

# 🔍 11. Audit Reports

## 01 — Sitemap & Crawl Coverage

Checks:

* Sitemap availability
* Sitemap XML validity
* Sitemap limits
* Duplicate URLs
* Invalid URLs
* `<lastmod>`
* Robots.txt
* Sitemap declarations
* Sitemap HTTP status
* Redirecting sitemap URLs
* Noindex sitemap URLs
* Canonical problems
* URLs missing from sitemap
* Broken internal URLs
* Crawl coverage
* Crawl depth

---

## 02 — Page SEO

Checks:

* Page title
* Title length
* Duplicate titles
* Multiple titles
* Meta description
* Description length
* Duplicate descriptions
* Meta keywords
* H1
* Multiple H1
* Missing H1
* H2/H3 structure
* URL structure
* Topic relevance

---

## 03 — Heading Structure

Checks:

* H1
* H2
* H3
* H4
* H5
* H6
* Heading hierarchy
* Skipped heading levels
* Empty headings
* Duplicate headings
* Long headings

---

## 04 — Image SEO

Checks:

* Missing alt
* Empty alt
* Generic alt
* Duplicate alt
* Keyword stuffing
* Broken images
* Image size
* Image format
* Width/height
* Lazy loading
* `srcset`
* Responsive images
* `next/image`
* Image filenames

---

## 05 — Link Health

Checks:

* Internal links
* External links
* Broken links
* Redirects
* Redirect chains
* Empty links
* `javascript:` links
* Weak anchor text
* Nofollow
* Sponsored links
* UGC
* Excessive links
* Orphan pages
* Crawl depth
* Internal linking architecture

---

## 06 — Social Metadata

Checks:

* `og:title`
* `og:description`
* `og:image`
* `og:image:alt`
* `og:image:width`
* `og:image:height`
* `og:url`
* `og:type`
* `og:site_name`
* `og:locale`
* Twitter/X card
* Twitter title
* Twitter description
* Twitter image
* Social image validity

---

## 07 — Structured Data

Checks:

* JSON-LD
* Schema types
* JSON-LD parsing
* Organization
* WebSite
* WebPage
* BreadcrumbList
* Article
* BlogPosting
* Service
* FAQPage
* LocalBusiness
* Required properties
* Recommended properties
* Duplicate schema
* Invalid schema

---

## 08 — Hreflang

Checks:

* Hreflang tags
* Language codes
* Country codes
* Absolute URLs
* Self-reference
* `x-default`
* Return links
* Duplicate language codes
* Localized routes
* `<html lang>`
* Translation consistency

---

## 09 — Technical SEO

Checks:

* HTTP status
* 4xx errors
* 5xx errors
* Redirects
* Redirect chains
* Redirect loops
* HTTPS
* HTTP → HTTPS
* WWW consistency
* Canonical
* Noindex
* Nofollow
* X-Robots-Tag
* URL structure
* Query parameters
* Trailing slash
* Duplicate URLs
* HTML structure
* Duplicate IDs
* Invalid HTML patterns

---

## 10 — Accessibility

Checks:

* Image accessibility
* Form labels
* Accessible names
* Buttons
* Links
* Headings
* Landmarks
* Language
* ARIA
* Duplicate IDs
* Keyboard navigation
* Focus visibility
* Iframe titles
* Touch targets
* Color contrast where browser testing is available

---

## 11 — Security

Checks:

* HTTPS
* SSL certificate
* TLS
* HSTS
* CSP
* X-Content-Type-Options
* Referrer-Policy
* Permissions-Policy
* X-Frame-Options
* Frame ancestors
* Server disclosure
* X-Powered-By
* Cookies
* Mixed content
* Third-party scripts
* Source maps
* Public `.env`
* Public `.git`
* Backup files

---

## 12 — Performance

Checks:

* DNS
* Connection time
* TTFB
* DOMContentLoaded
* Page load
* FCP
* LCP
* CLS
* TBT
* DOM size
* JavaScript size
* CSS size
* Image size
* Font size
* Total page size
* Request count
* Third-party requests
* Render-blocking resources
* Unused JavaScript
* Unused CSS
* Compression
* Cache headers
* HTTP protocol
* Preload
* Preconnect
* DNS-prefetch

---

## 12a — Core Web Vitals

Measures:

* LCP
* INP
* CLS
* FCP
* TTFB
* TBT
* Speed Index

The report rates each metric as:

```text
Good
Needs Improvement
Poor
```

The tests can be executed multiple times and use the median result where configured.

> Lab-based INP is an approximation. Real-user INP should be validated using real-user data such as Google Search Console or PageSpeed Insights.

---

## 13 — Next.js Health

Checks:

* Metadata
* `generateMetadata`
* `metadataBase`
* Dynamic routes
* `generateStaticParams`
* `robots`
* `sitemap`
* Manifest
* Favicon
* Apple icon
* Open Graph images
* Twitter images
* `next/image`
* `next/font`
* Next.js configuration
* Image optimization
* Source maps
* `poweredByHeader`
* Localhost URLs
* Staging URLs
* Debug text
* Console errors
* Hydration errors
* Failed API requests
* Missing Next.js assets

---

## 14 — Content Quality

Checks:

* Empty pages
* Thin content
* Short content
* Duplicate content
* Near-duplicate content
* Repeated paragraphs
* Placeholder text
* Lorem ipsum
* TODO/TBD
* Test content
* Generic/filler content
* Author information
* Publication date
* Updated date
* Readability

---

## 15 — Mobile

Checks multiple mobile/tablet viewports for:

* Viewport
* Horizontal scrolling
* Oversized elements
* Images
* Tables
* Modals
* Text size
* Forms
* Touch targets
* Button overflow
* Mobile menu
* Mobile CLS
* Mobile LCP

---

## 16 — Third-Party Resources

Checks:

* External JavaScript
* External CSS
* Fonts
* Images
* Iframes
* Embeds
* Analytics
* Google Tag Manager
* Hotjar
* Meta Pixel
* LinkedIn
* YouTube
* Google Fonts
* reCAPTCHA
* Maps
* CDNs
* Chat widgets
* Third-party request performance

---

## 17 — Heading Order

Additional heading validation for:

* H1 order
* Heading hierarchy
* Skipped levels
* Multiple violations
* Every violation on every page

---

## 18 — Image Alt

Detailed image-alt report covering:

* Missing alt
* Empty alt
* Decorative images
* Image URL
* Image number
* Page URL
* Issue status

---

## 19 — Third-Party URL

Checks third-party URLs for:

* Broken URLs
* Redirects
* Timeouts
* SSL errors
* HTTP resources on HTTPS pages
* 401
* 403
* 429
* Final URL
* Redirect chain

---

## 20 — SEO Master Audit

A consolidated SEO audit covering major areas from reports 01–09:

* Titles
* Descriptions
* Canonical
* Robots
* Open Graph
* Twitter
* JSON-LD
* Images
* Links
* Duplicate metadata
* Orphan pages
* URL structure
* Content

---

## 21 — Website Health Master Report

The final master report combines all previous reports into one complete website-health overview.

It includes:

```text
Overall Website Score
        ↓
Category Scores
        ↓
URL Summary
        ↓
All Issues
        ↓
Issue Priorities
        ↓
Recommended Fixes
```

---

# 🧠 12. Issue Reporting

Every issue contains detailed information.

Example:

```text
URL:
https://example.com/about

Category:
SEO

Issue:
Missing Meta Description

Severity:
Important

Description:
The page does not contain a meta description.

Current Value:
Missing

Expected Value:
A unique, relevant meta description.

Recommended Fix:
Add a unique meta description describing the page content.
```

Multiple issues on the same URL are always preserved.

---

# 🔁 13. Audit → Fix → Audit Again

The recommended workflow is:

```text
Run Audit
    ↓
Review Reports
    ↓
Fix Issues
    ↓
Run Audit Again
    ↓
Review New Reports
    ↓
Fix Remaining Issues
    ↓
Run Audit Again
    ↓
Final Verification
```

The goal is to continuously improve the website health score and eliminate significant issues.

---

# 🧹 14. Troubleshooting

| Problem                      | Solution                                            |
| ---------------------------- | --------------------------------------------------- |
| Website cannot be reached    | Start the website or check `NEXT_PUBLIC_REPORT_URL` |
| Missing Python package       | Run `pip install -r "py files/requirements.txt"`    |
| Playwright missing           | Install Playwright and Chromium                     |
| Development server crashes   | Use `npm run build && npm run start`                |
| Audit is slow                | Use `--pages sample` or reduce `--workers`          |
| Page missing                 | Check the `Crawled URLs` sheet                      |
| Localhost SEO issues         | Use the real production domain                      |
| Browser checks fail          | Check Chrome/Chromium and Playwright installation   |
| Reports contain old data     | Run a complete audit again                          |
| Some URLs are not in sitemap | Check crawl-discovered URLs                         |

---

# 🎯 Project Goal

The goal of this project is to provide a **complete automated website health auditing system** that gives developers a clear understanding of:

* What is wrong
* Where it is wrong
* Why it matters
* How important it is
* How to fix it
* Whether the fix improved the website

The final target is a **high-quality, technically healthy, accessible, secure, performant and SEO-friendly website**.

---

# 📺 CodeWithKD

Created and maintained by **CodeWithKD**.

### YouTube

**@codewithkd**

CodeWithKD focuses on practical development content including:

* JavaScript
* React.js
* Next.js
* Frontend Development
* Web Development
* Programming
* Developer Tools
* Coding Tutorials
* Real-world Projects

Follow **CodeWithKD** for more practical coding and web-development projects.

---

# ⭐ Support

If this project helps you improve your website, consider supporting **CodeWithKD** by following the channel and sharing the project with other developers.

---

## 📜 License

```text
MIT License
```

---