# QA Report - http://localhost:3000

- **Verdict:** **NEEDS FIXES**
- **Generated:** 2026-10-08 15:21
- **Audited server:** http://localhost:3000
- **Legal site:** no
- **Reports used:** 1 (31_english)
- **Checks:** 90 total - FAIL 2, WARN 3, PASS 1, SKIP 74, HUMAN 10
- **Pages:** 543 HTML pages crawled (540 in the sitemap)

## Fixes required

1. **ENG-01** No spelling mistakes in the page text - 58 issue(s) on 46 page(s): Spelling: Possible spelling mistake found. (57x); Spelling: Possible spelling mistake. “…” is British English. _(owner: content)_
   - `/industries/agriculture: [Important] Spelling: Possible spelling mistake found. - agri (content · <p> #844 p.text-body-lg.mt-5 · chars 38-42)`
   - `/technologies/redux-development: [Important] Spelling: Possible spelling mistake found. - toolset (content · <p> #1432 p.text-sm.md:text-base · chars 43-50)`
   - `/technologies/storybook-development: [Important] Spelling: Possible spelling mistake found. - args (content · <p> #1077 p.text-lg.text-[hsl(var(--muted-foreground))] · chars 6-10)`
   - `/technologies/vuejs-development: [Important] Spelling: Possible spelling mistake found. - destructure (content · <li> #1016 li.flex.items-start · chars 15-26)`
   - `/tools/git: [Important] Spelling: Possible spelling mistake found. - fixup (content · <p> #902 p.text-body-lg.mt-4 · chars 123-128)`
   - `/tools/jira: [Important] Spelling: Possible spelling mistake found. - burnup (content · <p> #936 p.text-xs.leading-relaxed · chars 12-18)`
   - `/blog/building-accessible-web-applications-wcag-2-2-aa: [Optimization] Spelling: Possible spelling mistake found. - aa (content · <p> #859 p · chars 132-134)`
   - `/blog/building-ultra-low-latency-apis-rust-axum: [Optimization] Spelling: Possible spelling mistake found. - jemalloc (content · <li> #856 li · chars 7-15)`
   - ...and 50 more (see the Excel / HTML report)
2. **ENG-02** No grammar mistakes (verb forms, agreement, repeated phrases) - 65 issue(s) on 65 page(s): Grammar: This phrase is duplicated. You should probably use “…” only once. (59x); Grammar: You’ve repeated a verb. Did you mean to only write one of them?; Grammar: A determiner may be missing.; +4 more issue types _(owner: content)_
   - `/blog/micro-frontends-module-federation-2026: [Important] Grammar: You’ve repeated a verb. Did you mean to only write one of them? - sharing shared (content · <p> #848 p · chars 206-220)`
   - `/blog/zero-trust-architecture-identity-security-perimeter: [Important] Grammar: A determiner may be missing. - least (content · <li> #851 li · chars 4-9)`
   - `/industries/ai-data: [Important] Grammar: The plural noun “…” cannot be used with the article “…”. Did you mean “…” or “…”? - a Service applications (content · <p> #963 p.text-small.relative · chars 42-64)`
   - `/portfolio/fleetcare-maintenance: [Important] Grammar: The word “…” is spelled with a hyphen. - cross references (content · <li> #916 li.flex.items-start · chars 32-48)`
   - `/technologies/adobe-xd-design: [Important] Grammar: This phrase is duplicated. You should probably use “…” only once. - Adobe XD Adobe XD (content · <h2> #1174 h2.text-h2.mb-5 · chars 25-42)`
   - `/technologies/affiliate-marketing: [Important] Grammar: This phrase is duplicated. You should probably use “…” only once. - Affiliate Marketing Affiliate Marketing (content · <h2> #1174 h2.text-h2.mb-5 · chars 25-64)`
   - `/technologies/ai-agents-development: [Important] Grammar: This phrase is duplicated. You should probably use “…” only once. - AI Agents AI Agents (content · <h2> #1174 h2.text-h2.mb-5 · chars 25-44)`
   - `/technologies/ai-development: [Important] Grammar: This phrase is duplicated. You should probably use “…” only once. - Artificial Intelligence Artificial Intelligence (content · <h2> #1174 h2.text-h2.mb-5 · chars 25-72)`
   - ...and 57 more (see the Excel / HTML report)

## Warnings to review

1. **ENG-03** Spacing correct (space after full stops / commas, none before them) - 3 issue(s) on 3 page(s): Spacing: Add a space between sentences. (3x) _(owner: content)_
   - `/blog/high-throughput-microservices-go-grpc: [Optimization] Spacing: Add a space between sentences. - Pool (content · <li> #855 li · chars 13-17)`
   - `/technologies/net-development: [Optimization] Spacing: Add a space between sentences. - Extensions (content · <li> #1023 li.flex.items-start · chars 10-20)`
   - `/technologies/xamarin-development: [Optimization] Spacing: Add a space between sentences. - Forms (content · <p> #935 p.text-[hsl(var(--muted-foreground))].leading-relaxed · chars 15-20)`
2. **ENG-04** Punctuation and typography reviewed (commas, hyphens, capitalisation) - 104 issue(s) on 85 page(s): Punctuation: Use a comma before “…” if it connects two independent clauses (unless they are closely con (26x); Typographical: This word is normally spelled as one. (25x); Typographical: For abbreviations such as “…”, use all capital letters. The rare word “…” is a synonym for (17x); +18 more issue types _(owner: content)_
   - `/: [Optimization] Punctuation: If specifying a range, consider using an en dash instead of a hyphen. - 4-6 (content · <p> #2099 p.text-sm.md:text-base · chars 88-91)`
   - `/: [Optimization] Punctuation: If specifying a range, consider using an en dash instead of a hyphen. - 3-6 (content · <p> #2099 p.text-sm.md:text-base · chars 137-140)`
   - `/: [Optimization] Typographical: This word is normally spelled as one. - multi-vendor (content · <p> #1537 p.text-[hsl(var(--muted-foreground))].text-sm · chars 11-23)`
   - `/blog/agentic-rag-with-self-corrective-graph-search: [Optimization] Typographical: For abbreviations such as “…”, use all capital letters. The rare word “…” is a synonym for - ai (content · <p> #848 p · chars 101-103)`
   - `/blog/ai-powered-semantic-vulnerability-detection-in-ci: [Optimization] Typographical: For abbreviations such as “…”, use all capital letters. The rare word “…” is a synonym for - ai (content · <p> #848 p · chars 105-107)`
   - `/blog/azure-devops-to-github-actions-migration-blueprint: [Optimization] Typographical: The official name of this software platform is spelled with a capital “…”. - github (content · <p> #859 p · chars 101-107)`
   - `/blog/building-autonomous-multi-agent-ai-workflows: [Optimization] Typographical: This word is normally spelled as one. - multi-step (content · <p> #848 p · chars 41-51)`
   - `/blog/building-fast-and-safe-webhooks-for-saas-platforms: [Optimization] Typographical: The recommended spelling for the acronym for “…” is “…”. - saas (content · <p> #859 p · chars 121-125)`
   - ...and 96 more (see the Excel / HTML report)
3. **ENG-05** Possible word misuse reviewed (their / there, in / on the website ...) - 4 issue(s) on 3 page(s): Word misuse: The usual collocation for technology is “…”, not “…”. (2x); Word misuse: The usual collocation for “…” is “…”. Did you mean “…”?; Word misuse: Consider using a more common abbreviation of this university degree. - also confirm by hand: Read the WARN items of the English Grammar report; real names / terms can be ignored. _(owner: content)_
   - `/blog/modern-headless-wordpress-graphql-nextjs-ssr: [Optimization] Word misuse: The usual collocation for “…” is “…”. Did you mean “…”? - in WordPress (content · <blockquote> #858 blockquote · chars 11-23)`
   - `/internships: [Optimization] Word misuse: Consider using a more common abbreviation of this university degree. - B.Sc (content · <li> #1066 li.flex.items-start · chars 66-70)`
   - `/terms-of-service: [Optimization] Word misuse: The usual collocation for technology is “…”, not “…”. - in the website (content · <p> #844 p · chars 134-148)`
   - `/terms-of-service: [Optimization] Word misuse: The usual collocation for technology is “…”, not “…”. - in the website (content · <p> #853 p · chars 18-32)`

## Not checked (SKIP)

- **NAP-01** Phone number is the confirmed number everywhere (header, footer, content, schema) - not run: 22 (22_business_info)
- **NAP-02** Every written phone number is a tel: link that dials the number shown - not run: 22 (22_business_info)
- **NAP-03** Phone is visible and tappable in the desktop and mobile header - not run: 22 (22_business_info), 24 (24_navigation)
- **NAP-04** Email addresses are correct and mailto: links match the address shown - not run: 22 (22_business_info)
- **NAP-05** Address is the same on every page (and matches the confirmed / Google listing) - not run: 22 (22_business_info) - how: Compare the address with the Google Business Profile.
- **NAP-06** Business name is written the same way everywhere (schema, og:site_name, titles) - not run: 22 (22_business_info)
- **NAV-01** No broken internal links, pages or redirect loops - not run: 01 (01_sitemap), 05 (05_links), 09 (09_technical)
- **NAV-02** No broken external links / third-party URLs - not run: 05 (05_links), 19 (19_third_party_urls)
- **NAV-03** Desktop dropdown menus open and their links work - not run: 24 (24_navigation)
- **NAV-04** Mobile menu: button on screen and tappable, opens, links not cut off, closes - not run: 15 (15_mobile), 24 (24_navigation)
- **NAV-05** Mobile menu offers the same pages as the desktop menu - not run: 24 (24_navigation)
- **NAV-06** Social links point to real, working profiles - not run: 22 (22_business_info) - how: Confirm the profile list with the client (qa_config.json social_profiles).
- **NAV-07** Every page is reachable by links (no orphans, not only via JS menus) - not run: 05 (05_links)
- **NAV-08** Hub pages link their detail pages; breadcrumbs on nested pages - not run: 05 (05_links)
- **NAV-09** Links have descriptive text - not run: 05 (05_links), 12b (12b_lighthouse)
- **NAV-10** No leftover / forbidden terms (old vendor, old brand, staging names) - not run: 26 (26_text_quality)
- **NAV-11** Internal URLs are lowercase, hyphenated and consistent - not run: 02 (02_page_seo), 09 (09_technical)
- **SEO-01** Every page has a unique title and meta description of the right length - not run: 02 (02_page_seo)
- **SEO-02** Titles / descriptions / social tags have no odd characters (&amp;, &#39;, mojibake) - not run: 26 (26_text_quality)
- **SEO-04** Exactly one meaningful H1 per page; headings in order - not run: 02 (02_page_seo), 03 (03_headings), 17 (17_heading_order)
- **SEO-05** Canonical tag on every page points to itself (absolute, 200) - not run: 09 (09_technical), 13 (13_nextjs)
- **SEO-06** No page is noindex / nofollow by mistake; robots.txt allows the site - not run: 01 (01_sitemap), 09 (09_technical)
- **SEO-07** JSON-LD parses, has the expected types and valid values / URLs - not run: 07 (07_schema), 27 (27_assets)
- **SEO-08** Expected schema type per page (Organization, Service, BlogPosting, Breadcrumbs ...) - not run: 07 (07_schema)
- **SEO-09** Favicon, apple-touch-icon, manifest icons and theme-color set - not run: 13 (13_nextjs), 27 (27_assets)
- **SEO-10** Social share (Open Graph / Twitter) tags complete; share image works (1200x630) - not run: 06 (06_social)
- **SEO-11** Titles and H1s are not ALL CAPS / all lowercase / padded with spaces - not run: 26 (26_text_quality)
- **SEO-12** Every content image has accurate alt text - not run: 04 (04_images), 18 (18_image_alt) - how: Skim the Image alt sheet: alt texts must describe this client's images (no other company's names).
- **SEO-14** Language versions / hreflang correct (multi-language sites) - not run: 08 (08_hreflang)
- **MAP-01** sitemap.xml valid, https, on the live host, every URL 200 and indexable - not run: 01 (01_sitemap)
- **MAP-02** Every live page is in the sitemap; robots.txt points to it - not run: 01 (01_sitemap)
- **MAP-03** Every URL of the current live site exists on the new site or redirects - not run: 29 (29_live_vs_dev)
- **MAP-04** Content carried over from the live site (text, H1s, schema, numbers) - not run: 29 (29_live_vs_dev) - how: Open the Content parity sheet; get an SEO sign-off for changed titles / H1s.
- **MAP-05** No test / demo / duplicate pages published - not run: 14 (14_content), 29 (29_live_vs_dev)
- **MAP-06** No lorem ipsum, placeholder or debug text - not run: 13 (13_nextjs), 14 (14_content)
- **MAP-07** No empty / very thin pages - not run: 14 (14_content)
- **MAP-08** Articles show author and dates - not run: 14 (14_content)
- **FRM-01** Lead forms ask for name + email; fields have names, types and autocomplete - not run: 23 (23_forms)
- **FRM-02** Labels are clean and capitalised; required fields marked and announced - not run: 10 (10_accessibility), 23 (23_forms)
- **FRM-03** Empty / invalid submissions are blocked with clear error messages - not run: 23 (23_forms)
- **FRM-04** Submission set up: https endpoint, POST, thank-you page works, spam protection - not run: 23 (23_forms)
- **FRM-06** Site search (if any) returns results - not run: 23 (23_forms)
- **FTR-01** Footer links to privacy / terms (and disclaimer on legal sites) work - not run: 22 (22_business_info)
- **FTR-02** Copyright year is current (generated, not typed) - not run: 22 (22_business_info)
- **FTR-03** Legal / utility pages have no lead forms - not run: 23 (23_forms)
- **FTR-04** Unknown URLs return a real 404 page with links back - not run: 09 (09_technical)
- **CODE-01** Production build succeeds - not run: 28 (28_repo) - how: Stop `next start`, then run  qa.py run CODE-01 --repo-build
- **CODE-02** No ESLint errors and no TypeScript errors - not run: 28 (28_repo)
- **CODE-03** README customised; .gitignore complete; no build output committed - not run: 28 (28_repo)
- **CODE-04** No secrets / .env files committed; security scan of the code clean - not run: 28 (28_repo)
- **CODE-05** Dependencies have no high / critical vulnerabilities (npm audit) - not run: 28 (28_repo)
- **CODE-06** W3C HTML validator: no errors - not run: 25 (25_html_validation)
- **CODE-07** No console errors, hydration errors or failed requests - not run: 12b (12b_lighthouse), 13 (13_nextjs)
- **CODE-08** No leftover console.log / localhost / staging URLs - not run: 13 (13_nextjs)
- **CODE-09** Fonts are WOFF2 / WOFF, preloaded, with font-display - not run: 13 (13_nextjs), 27 (27_assets)
- **CODE-10** Logo is sharp on retina screens (2x bitmap or SVG) - not run: 27 (27_assets)
- **CODE-11** Referenced files exist (icons, preload, manifest, feeds, PDFs) - not run: 27 (27_assets)
- **CODE-12** ALL CAPS is done with CSS, not typed in the text - not run: 26 (26_text_quality)
- **CODE-13** Third-party scripts / widgets intended and working (chat, analytics, reviews) - not run: 16 (16_third_party), 19 (19_third_party_urls) - how: Confirm with the client which add-ons (chat, call tracking, review widgets) the new site must have.
- **SEC-01** HTTPS everywhere: valid certificate, HTTP -> HTTPS, HSTS, no mixed content - not run: 11 (11_security)
- **SEC-02** Security headers set (CSP, X-Content-Type-Options, frame protection ...) - not run: 11 (11_security)
- **SEC-03** No exposed files, source maps, server banners or insecure cookies - not run: 11 (11_security)
- **PERF-01** Lighthouse: no failing scores (Performance, A11y, BP, SEO) - not run: 12b (12b_lighthouse)
- **PERF-02** Core Web Vitals pass on a throttled phone (LCP, INP, CLS) - not run: 12a (12a_cwv)
- **PERF-03** Above-the-fold images not lazy; below-the-fold images lazy - not run: 04 (04_images)
- **PERF-04** Images optimised (format, size, dimensions, srcset) - not run: 04 (04_images), 13 (13_nextjs)
- **PERF-05** Page weight, JavaScript, compression and caching within budget - not run: 12 (12_performance)
- **A11Y-01** axe-core: no serious / critical accessibility violations - not run: 10 (10_accessibility)
- **A11Y-02** Keyboard: everything reachable, focus visible - not run: 10 (10_accessibility)
- **A11Y-03** 120% / 200% zoom without horizontal scrolling - not run: 24 (24_navigation)
- **A11Y-04** Touch targets big enough on phones - not run: 10 (10_accessibility), 15 (15_mobile)
- **VIS-01** Mobile layouts: no horizontal scrolling, readable text, usable inputs - not run: 15 (15_mobile)
- **VIS-03** Other browsers: Firefox and Safari (WebKit) render without errors - not run: 24 (24_navigation) - how: playwright install firefox webkit  enables the automatic part; still check real Safari / iOS once.
- **VIS-06** Live vs dev side-by-side reviewed (visual diff / recording) - not run: 29 (29_live_vs_dev) - how: Run 29 with --visual and look at the *_diff.png images; record a comparison video if required.

## Human checks

- [ ] **CTX-01** Brief / scope read; every requested page and feature is built _(how: Compare the project brief / ticket with the site; post open questions on the ticket.)_
- [ ] **CTX-02** Ticket comments and dev notes read; requested changes are done _(how: Read every comment on the ticket / card and check each request on the site.)_
- [ ] **CTX-03** Design (Figma) comments read; the site follows the approved design _(how: Open the Figma file, read the comment threads, compare the main pages with the frames.)_
- [ ] **CTX-04** Open questions for the client listed and sent _(how: Copy the 'Questions for the client' block of this report into the ticket.)_
- [ ] **NAP-05** Address is the same on every page (and matches the confirmed / Google listing) _(how: Compare the address with the Google Business Profile.)_
- [ ] **NAP-07** Phone numbers / addresses inside images and videos match _(how: Watch the videos and look at banner images for old phone numbers or addresses.)_
- [ ] **NAV-06** Social links point to real, working profiles _(how: Confirm the profile list with the client (qa_config.json social_profiles).)_
- [ ] **SEO-03** Home page title, description and H1 approved by SEO _(how: Send the home title / description / H1 (Page SEO report) to SEO; record the sign-off with qa.py mark.)_
- [ ] **SEO-12** Every content image has accurate alt text _(how: Skim the Image alt sheet: alt texts must describe this client's images (no other company's names).)_
- [ ] **MAP-04** Content carried over from the live site (text, H1s, schema, numbers) _(how: Open the Content parity sheet; get an SEO sign-off for changed titles / H1s.)_
- [ ] **MAP-09** Testimonials / reviews up to date (newest 5-star reviews added) _(how: Compare the Google reviews with the reviews on the site; list new ones for the client.)_
- [ ] **ENG-05** Possible word misuse reviewed (their / there, in / on the website ...) _(how: Read the WARN items of the English Grammar report; real names / terms can be ignored.)_
- [ ] **FRM-05** A real test submission arrives with clean field names; thank-you page shows _(how: Submit each form once with test data; check the email / CRM and the redirect.)_
- [ ] **CODE-13** Third-party scripts / widgets intended and working (chat, analytics, reviews) _(how: Confirm with the client which add-ons (chat, call tracking, review widgets) the new site must have.)_
- [ ] **VIS-02** Screenshots reviewed: dev matches the approved design _(how: Open the screenshots folder of the Navigation report (desktop + phone) next to the Figma frames.)_
- [ ] **VIS-03** Other browsers: Firefox and Safari (WebKit) render without errors _(how: playwright install firefox webkit  enables the automatic part; still check real Safari / iOS once.)_
- [ ] **VIS-04** Animations are smooth and not too slow while scrolling _(how: Scroll every main page on a phone and a laptop.)_
- [x] **VIS-05** Mobile theme colour checked on Android Chrome / iPhone Safari - PASS: Checked on Pixel 8 + iPhone 15
- [ ] **VIS-06** Live vs dev side-by-side reviewed (visual diff / recording) _(how: Run 29 with --visual and look at the *_diff.png images; record a comparison video if required.)_

## Notes for SEO / content

```
- ENG-01 No spelling mistakes in the page text: 58 issue(s) on 46 page(s): Spelling: Possible spelling mistake found. (57x); Spelling: Possible spelling mistake. “…” is British English. e.g. /industries/agriculture: [Important] Spelling: Possible spelling mistake found. - agri (content · <p> #844 p.text-body-lg.mt-5 · chars 38-42)
- ENG-02 No grammar mistakes (verb forms, agreement, repeated phrases): 65 issue(s) on 65 page(s): Grammar: This phrase is duplicated. You should probably use “…” only once. (59x); Grammar: You’ve repeated a verb. Did you mean to only write one of them?; Grammar: A determiner may be missing.; +4 more issue types e.g. /blog/micro-frontends-module-federation-2026: [Important] Grammar: You’ve repeated a verb. Did you mean to only write one of them? - sharing shared (content · <p> #848 p · chars 206-220)
- ENG-03 Spacing correct (space after full stops / commas, none before them): 3 issue(s) on 3 page(s): Spacing: Add a space between sentences. (3x) e.g. /blog/high-throughput-microservices-go-grpc: [Optimization] Spacing: Add a space between sentences. - Pool (content · <li> #855 li · chars 13-17)
- ENG-04 Punctuation and typography reviewed (commas, hyphens, capitalisation): 104 issue(s) on 85 page(s): Punctuation: Use a comma before “…” if it connects two independent clauses (unless they are closely con (26x); Typographical: This word is normally spelled as one. (25x); Typographical: For abbreviations such as “…”, use all capital letters. The rare word “…” is a synonym for (17x); +18 more issue types e.g. /: [Optimization] Punctuation: If specifying a range, consider using an en dash instead of a hyphen. - 4-6 (content · <p> #2099 p.text-sm.md:text-base · chars 88-91)
- ENG-05 Possible word misuse reviewed (their / there, in / on the website ...): 4 issue(s) on 3 page(s): Word misuse: The usual collocation for technology is “…”, not “…”. (2x); Word misuse: The usual collocation for “…” is “…”. Did you mean “…”?; Word misuse: Consider using a more common abbreviation of this university degree. - also confirm by hand: Read the WARN items of the English Grammar report; real names / terms can be ignored. e.g. /blog/modern-headless-wordpress-graphql-nextjs-ssr: [Optimization] Word misuse: The usual collocation for “…” is “…”. Did you mean “…”? - in WordPress (content · <blockquote> #858 blockquote · chars 11-23)
```

## Questions for the client

```
- MAP-09 Testimonials / reviews up to date (newest 5-star reviews added) (Compare the Google reviews with the reviews on the site; list new ones for the client.)
```

## Full checklist

### Project context

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| CTX-01 | Brief / scope read; every requested page and feature is built | HUMAN | HUMAN |  | qa |
| CTX-02 | Ticket comments and dev notes read; requested changes are done | HUMAN | HUMAN |  | qa |
| CTX-03 | Design (Figma) comments read; the site follows the approved design | HUMAN | HUMAN |  | qa |
| CTX-04 | Open questions for the client listed and sent | HUMAN | HUMAN |  | qa |

### Business info

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| NAP-01 | Phone number is the confirmed number everywhere (header, footer, content, schema) | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| NAP-02 | Every written phone number is a tel: link that dials the number shown | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| NAP-03 | Phone is visible and tappable in the desktop and mobile header | AUTO | SKIP | not run: 22 (22_business_info), 24 (24_navigation) | dev |
| NAP-04 | Email addresses are correct and mailto: links match the address shown | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| NAP-05 | Address is the same on every page (and matches the confirmed / Google listing) | AUTO+HUMAN | SKIP | not run: 22 (22_business_info) | client |
| NAP-06 | Business name is written the same way everywhere (schema, og:site_name, titles) | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| NAP-07 | Phone numbers / addresses inside images and videos match | HUMAN | HUMAN |  | qa |

### Navigation and links

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| NAV-01 | No broken internal links, pages or redirect loops | AUTO | SKIP | not run: 01 (01_sitemap), 05 (05_links), 09 (09_technical) | dev |
| NAV-02 | No broken external links / third-party URLs | AUTO | SKIP | not run: 05 (05_links), 19 (19_third_party_urls) | content |
| NAV-03 | Desktop dropdown menus open and their links work | AUTO | SKIP | not run: 24 (24_navigation) | dev |
| NAV-04 | Mobile menu: button on screen and tappable, opens, links not cut off, closes | AUTO | SKIP | not run: 15 (15_mobile), 24 (24_navigation) | dev |
| NAV-05 | Mobile menu offers the same pages as the desktop menu | AUTO | SKIP | not run: 24 (24_navigation) | dev |
| NAV-06 | Social links point to real, working profiles | AUTO+HUMAN | SKIP | not run: 22 (22_business_info) | client |
| NAV-07 | Every page is reachable by links (no orphans, not only via JS menus) | AUTO | SKIP | not run: 05 (05_links) | seo |
| NAV-08 | Hub pages link their detail pages; breadcrumbs on nested pages | AUTO | SKIP | not run: 05 (05_links) | seo |
| NAV-09 | Links have descriptive text | AUTO | SKIP | not run: 05 (05_links), 12b (12b_lighthouse) | content |
| NAV-10 | No leftover / forbidden terms (old vendor, old brand, staging names) | AUTO | SKIP | not run: 26 (26_text_quality) | content |
| NAV-11 | Internal URLs are lowercase, hyphenated and consistent | AUTO | SKIP | not run: 02 (02_page_seo), 09 (09_technical) | dev |

### SEO

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| SEO-01 | Every page has a unique title and meta description of the right length | AUTO | SKIP | not run: 02 (02_page_seo) | seo |
| SEO-02 | Titles / descriptions / social tags have no odd characters (&amp;, &#39;, mojibake) | AUTO | SKIP | not run: 26 (26_text_quality) | content |
| SEO-03 | Home page title, description and H1 approved by SEO | HUMAN | HUMAN |  | seo |
| SEO-04 | Exactly one meaningful H1 per page; headings in order | AUTO | SKIP | not run: 02 (02_page_seo), 03 (03_headings), 17 (17_heading_order) | seo |
| SEO-05 | Canonical tag on every page points to itself (absolute, 200) | AUTO | SKIP | not run: 09 (09_technical), 13 (13_nextjs) | dev |
| SEO-06 | No page is noindex / nofollow by mistake; robots.txt allows the site | AUTO | SKIP | not run: 01 (01_sitemap), 09 (09_technical) | seo |
| SEO-07 | JSON-LD parses, has the expected types and valid values / URLs | AUTO | SKIP | not run: 07 (07_schema), 27 (27_assets) | dev |
| SEO-08 | Expected schema type per page (Organization, Service, BlogPosting, Breadcrumbs ...) | AUTO | SKIP | not run: 07 (07_schema) | seo |
| SEO-09 | Favicon, apple-touch-icon, manifest icons and theme-color set | AUTO | SKIP | not run: 13 (13_nextjs), 27 (27_assets) | dev |
| SEO-10 | Social share (Open Graph / Twitter) tags complete; share image works (1200x630) | AUTO | SKIP | not run: 06 (06_social) | seo |
| SEO-11 | Titles and H1s are not ALL CAPS / all lowercase / padded with spaces | AUTO | SKIP | not run: 26 (26_text_quality) | content |
| SEO-12 | Every content image has accurate alt text | AUTO+HUMAN | SKIP | not run: 04 (04_images), 18 (18_image_alt) | content |
| SEO-14 | Language versions / hreflang correct (multi-language sites) | AUTO | SKIP | not run: 08 (08_hreflang) | seo |

### Sitemap and content

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| MAP-01 | sitemap.xml valid, https, on the live host, every URL 200 and indexable | AUTO | SKIP | not run: 01 (01_sitemap) | dev |
| MAP-02 | Every live page is in the sitemap; robots.txt points to it | AUTO | SKIP | not run: 01 (01_sitemap) | dev |
| MAP-03 | Every URL of the current live site exists on the new site or redirects | AUTO | SKIP | not run: 29 (29_live_vs_dev) | dev |
| MAP-04 | Content carried over from the live site (text, H1s, schema, numbers) | AUTO+HUMAN | SKIP | not run: 29 (29_live_vs_dev) | content |
| MAP-05 | No test / demo / duplicate pages published | AUTO | SKIP | not run: 14 (14_content), 29 (29_live_vs_dev) | content |
| MAP-06 | No lorem ipsum, placeholder or debug text | AUTO | SKIP | not run: 13 (13_nextjs), 14 (14_content) | content |
| MAP-07 | No empty / very thin pages | AUTO | SKIP | not run: 14 (14_content) | content |
| MAP-08 | Articles show author and dates | AUTO | SKIP | not run: 14 (14_content) | content |
| MAP-09 | Testimonials / reviews up to date (newest 5-star reviews added) | HUMAN | HUMAN |  | client |

### English content

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| ENG-01 | No spelling mistakes in the page text | AUTO | FAIL | 58 issue(s) on 46 page(s): Spelling: Possible spelling mistake found. (57x); Spelling: Possible spelling mistake. “…” is British English. | content |
| ENG-02 | No grammar mistakes (verb forms, agreement, repeated phrases) | AUTO | FAIL | 65 issue(s) on 65 page(s): Grammar: This phrase is duplicated. You should probably use “…” only once. (59x); Grammar: You’ve repeated a verb. Did you mean to only write one of them?; Grammar: A determiner may be missing. | content |
| ENG-03 | Spacing correct (space after full stops / commas, none before them) | AUTO | WARN | 3 issue(s) on 3 page(s): Spacing: Add a space between sentences. (3x) | content |
| ENG-04 | Punctuation and typography reviewed (commas, hyphens, capitalisation) | AUTO | WARN | 104 issue(s) on 85 page(s): Punctuation: Use a comma before “…” if it connects two independent clauses (unless they are closely con (26x); Typographical: This word is normally spelled as one. (25x); Typographical: For ab | content |
| ENG-05 | Possible word misuse reviewed (their / there, in / on the website ...) | AUTO+HUMAN | WARN | 4 issue(s) on 3 page(s): Word misuse: The usual collocation for technology is “…”, not “…”. (2x); Word misuse: The usual collocation for “…” is “…”. Did you mean “…”?; Word misuse: Consider using a more common abbreviati | content |

### Forms

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| FRM-01 | Lead forms ask for name + email; fields have names, types and autocomplete | AUTO | SKIP | not run: 23 (23_forms) | dev |
| FRM-02 | Labels are clean and capitalised; required fields marked and announced | AUTO | SKIP | not run: 10 (10_accessibility), 23 (23_forms) | dev |
| FRM-03 | Empty / invalid submissions are blocked with clear error messages | AUTO | SKIP | not run: 23 (23_forms) | dev |
| FRM-04 | Submission set up: https endpoint, POST, thank-you page works, spam protection | AUTO | SKIP | not run: 23 (23_forms) | dev |
| FRM-05 | A real test submission arrives with clean field names; thank-you page shows | HUMAN | HUMAN |  | qa |
| FRM-06 | Site search (if any) returns results | AUTO | SKIP | not run: 23 (23_forms) | dev |

### Footer and legal

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| FTR-01 | Footer links to privacy / terms (and disclaimer on legal sites) work | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| FTR-02 | Copyright year is current (generated, not typed) | AUTO | SKIP | not run: 22 (22_business_info) | dev |
| FTR-03 | Legal / utility pages have no lead forms | AUTO | SKIP | not run: 23 (23_forms) | dev |
| FTR-04 | Unknown URLs return a real 404 page with links back | AUTO | SKIP | not run: 09 (09_technical) | dev |

### Code and repo

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| CODE-01 | Production build succeeds | AUTO | SKIP | not run: 28 (28_repo) | dev |
| CODE-02 | No ESLint errors and no TypeScript errors | AUTO | SKIP | not run: 28 (28_repo) | dev |
| CODE-03 | README customised; .gitignore complete; no build output committed | AUTO | SKIP | not run: 28 (28_repo) | dev |
| CODE-04 | No secrets / .env files committed; security scan of the code clean | AUTO | SKIP | not run: 28 (28_repo) | dev |
| CODE-05 | Dependencies have no high / critical vulnerabilities (npm audit) | AUTO | SKIP | not run: 28 (28_repo) | dev |
| CODE-06 | W3C HTML validator: no errors | AUTO | SKIP | not run: 25 (25_html_validation) | dev |
| CODE-07 | No console errors, hydration errors or failed requests | AUTO | SKIP | not run: 12b (12b_lighthouse), 13 (13_nextjs) | dev |
| CODE-08 | No leftover console.log / localhost / staging URLs | AUTO | SKIP | not run: 13 (13_nextjs) | dev |
| CODE-09 | Fonts are WOFF2 / WOFF, preloaded, with font-display | AUTO | SKIP | not run: 13 (13_nextjs), 27 (27_assets) | dev |
| CODE-10 | Logo is sharp on retina screens (2x bitmap or SVG) | AUTO | SKIP | not run: 27 (27_assets) | dev |
| CODE-11 | Referenced files exist (icons, preload, manifest, feeds, PDFs) | AUTO | SKIP | not run: 27 (27_assets) | dev |
| CODE-12 | ALL CAPS is done with CSS, not typed in the text | AUTO | SKIP | not run: 26 (26_text_quality) | content |
| CODE-13 | Third-party scripts / widgets intended and working (chat, analytics, reviews) | AUTO+HUMAN | SKIP | not run: 16 (16_third_party), 19 (19_third_party_urls) | client |

### Security

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| SEC-01 | HTTPS everywhere: valid certificate, HTTP -> HTTPS, HSTS, no mixed content | AUTO | SKIP | not run: 11 (11_security) | dev |
| SEC-02 | Security headers set (CSP, X-Content-Type-Options, frame protection ...) | AUTO | SKIP | not run: 11 (11_security) | dev |
| SEC-03 | No exposed files, source maps, server banners or insecure cookies | AUTO | SKIP | not run: 11 (11_security) | dev |

### Performance and accessibility

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| PERF-01 | Lighthouse: no failing scores (Performance, A11y, BP, SEO) | AUTO | SKIP | not run: 12b (12b_lighthouse) | dev |
| PERF-02 | Core Web Vitals pass on a throttled phone (LCP, INP, CLS) | AUTO | SKIP | not run: 12a (12a_cwv) | dev |
| PERF-03 | Above-the-fold images not lazy; below-the-fold images lazy | AUTO | SKIP | not run: 04 (04_images) | dev |
| PERF-04 | Images optimised (format, size, dimensions, srcset) | AUTO | SKIP | not run: 04 (04_images), 13 (13_nextjs) | dev |
| PERF-05 | Page weight, JavaScript, compression and caching within budget | AUTO | SKIP | not run: 12 (12_performance) | dev |
| A11Y-01 | axe-core: no serious / critical accessibility violations | AUTO | SKIP | not run: 10 (10_accessibility) | dev |
| A11Y-02 | Keyboard: everything reachable, focus visible | AUTO | SKIP | not run: 10 (10_accessibility) | dev |
| A11Y-03 | 120% / 200% zoom without horizontal scrolling | AUTO | SKIP | not run: 24 (24_navigation) | dev |
| A11Y-04 | Touch targets big enough on phones | AUTO | SKIP | not run: 10 (10_accessibility), 15 (15_mobile) | dev |

### Visual

| ID | Check | Type | Status | Result | Owner |
|----|-------|------|--------|--------|-------|
| VIS-01 | Mobile layouts: no horizontal scrolling, readable text, usable inputs | AUTO | SKIP | not run: 15 (15_mobile) | dev |
| VIS-02 | Screenshots reviewed: dev matches the approved design | HUMAN | HUMAN |  | qa |
| VIS-03 | Other browsers: Firefox and Safari (WebKit) render without errors | AUTO+HUMAN | SKIP | not run: 24 (24_navigation) | dev |
| VIS-04 | Animations are smooth and not too slow while scrolling | HUMAN | HUMAN |  | qa |
| VIS-05 | Mobile theme colour checked on Android Chrome / iPhone Safari | HUMAN | PASS | PASS by QA on 2026-10-08 14:22: Checked on Pixel 8 + iPhone 15 | qa |
| VIS-06 | Live vs dev side-by-side reviewed (visual diff / recording) | AUTO+HUMAN | SKIP | not run: 29 (29_live_vs_dev) | qa |

## Reports used

| Key | Report | Run | Pages | Score | File |
|---|---|---|---|---|---|
| 31_english | English Grammar Report | 2026-10-08 15-07-44 | 541 | 98.4 | `py files/report/2026-10-08/json/English_Grammar_Report_15-07-44.json` |
