"""
31 - English grammar & spelling checker (LanguageTool, free and offline)
  Every page's visible text is read in Chrome (innerText - exactly what visitors see, including text rendered by
  JavaScript; --no-browser reads the server HTML instead) and checked with LanguageTool for:
    Spelling        misspelled words ("vehical" -> "vehicle")
    Grammar         wrong verb forms, agreement ... ("He was been arrested" -> "He had been arrested")
    Punctuation     commas, sentence punctuation
    Typographical   capitalisation and other typing mistakes
    Spacing         missing / extra spaces ("issues.We", "word ,")
    Word misuse     confused words (their / there, loose / lose ...) - reported as "possible" (WARN)
    Style           only with --style (wordiness, redundancy)

  No word lists: false positives are filtered dynamically, from the site itself -
    - the site's own vocabulary: a word used on 3+ pages, or a capitalised word used on 2+ pages (brands, tools,
      places, people: Redis, Figma, Ahmedabad), is not a typo
    - capitalised words mid-sentence that are not a 1-letter slip, acronyms (NHTSA), words with digits / dots /
      camelCase (Next.js, H1, iPhone), file extensions (.tsx), British / American variants (organise / organize),
      compounds the engine only splits (wealthtech -> "wealth tech"), spelling hits without any suggestion
    - LanguageTool rules that don't fit website copy are switched off in WEB_COPY_RULES below
  (qa_config.json spelling_ignore stays available as an optional override; it is empty by default.)

  Each unique text block is checked once: text that repeats on many pages (header, footer, shared sections) is
  reported once, on the first page, with "also on N other pages".

  Result per URL: PASS (no issue) / WARN (only possible issues) / FAIL (spelling / grammar / spacing error) /
  SKIP (not an English page, or no text). Every issue: Check ID, URL, page title, type, severity, Wrong input,
  Actual output, Expected output, suggested correction, reason, location, confidence.
  Saved like every report (Excel, JSON, CSV) plus an HTML page with the wrong text in red and the expected text in
  green: py files/report/<date>/html/English_Grammar_Report_<time>.html

  LanguageTool (~250 MB, needs Java 17+) is downloaded once by language-tool-python into ~/.cache.
  --public-api uses the free public LanguageTool server instead (no Java; rate-limited, main pages only).

  python "py files/31_english_grammar_checker.py" [--base URL] [--style] [--language en-US] [--no-browser]
"""
import hashlib
import html
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from seo_common import (EXPECTED_COLOR, IMPORTANT, INFO, OPTIMIZATION, STATUS_COLORS, WRONG_COLOR, Audit, describe,
                        load_site, parse_args, qa_config, rel_path, report_path, run_browser_pages, run_parallel,
                        sample_pages, select_pages, text_blocks, text_of)


def extra(ap):
    ap.add_argument("--language", default="en-US", help="LanguageTool language (en-US, en-GB ...; default %(default)s)")
    ap.add_argument("--style", action="store_true", help="also report style suggestions (wordiness, redundancy)")
    ap.add_argument("--no-browser", action="store_true", help="read the server HTML instead of the page in Chrome")
    ap.add_argument("--public-api", action="store_true",
                    help="use the public LanguageTool server (no Java needed; rate-limited: main pages only)")


args = parse_args("English grammar & spelling checker", extra)
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("31_english", "English Grammar Report", "English", site)

# Modern software, developer, and technical vocabulary (never report as spelling mistakes)
TECH_WORDS = {
    # Configuration, tooling, build systems
    "tsconfig", "jsconfig", "webpack", "vite", "esbuild", "tsup", "rollup", "turbopack",
    "babel", "postcss", "autoprefixer", "tailwindcss", "tailwind", "eslint", "prettier",
    "biome", "swc", "linter", "linting", "typecheck", "codemod", "codemods", "polyfill",
    "polyfills", "transpile", "transpiler", "treeshaking", "tree-shaking", "minification",
    "sourcemap", "sourcemaps", "bundle", "bundler", "bundlers", "monorepo", "monorepos",
    "subgrid", "codebase", "codebases", "toolset", "toolsets",

    # TypeScript / JavaScript / Languages
    "typescript", "javascript", "ecmascript", "golang", "rust", "kotlin", "swift",
    "csharp", "php", "ruby", "scala", "elixir", "erlang", "dart", "lua", "python",
    "destructure", "destructuring", "async", "await", "boolean", "bool", "enums", "enum",
    "args", "params", "kwargs", "stdin", "stdout", "stderr", "mutex", "mutexes",
    "struct", "structs", "tuple", "tuples", "runnables", "runnable", "composables",
    "composable", "middleware", "middlewares", "schema", "schemas", "nullish",
    "templating", "templated", "regex", "regexes", "datetime", "timestamp", "timestamps",
    "metadata", "payload", "payloads", "uuid", "guid", "bitwise", "iter", "iters",

    # Web & Frontend frameworks
    "react", "reactjs", "nextjs", "vue", "vuejs", "nuxt", "nuxtjs", "angular", "angularjs",
    "svelte", "sveltekit", "solidjs", "astro", "remix", "gatsby", "jquery", "alpinejs",
    "htmx", "preact", "redux", "mobx", "zustand", "recoil", "jotai", "tanstack",
    "shadcn", "radix", "lucide", "critters", "clsx", "cva", "stylable", "nuqs", "jsdom",
    "framer", "supertest", "cypress", "playwright", "puppeteer", "vitest", "jest",
    "frontend", "backend", "fullstack", "devops", "serverless", "microservices",
    "microservice", "isomorphic", "hydration", "dehydration", "ssr", "ssg", "isr", "csr",
    "rsc", "jank", "viewport", "viewports", "favicon", "favicons",

    # Backend, DB, APIs, Auth, Cloud
    "nodejs", "expressjs", "nestjs", "fastify", "koa", "django", "flask", "fastapi",
    "springboot", "laravel", "rails", "aspnet", "graphql", "grpc", "restful", "webhook",
    "webhooks", "orm", "prisma", "drizzle", "typeorm", "sequelize", "mongoose",
    "strapi", "contentful", "sanity", "payload", "wordpress", "woocommerce", "shopify",
    "bigcommerce", "magento", "drupal", "postgresql", "postgres", "mysql", "sqlite",
    "mongodb", "redis", "memcached", "cassandra", "dynamodb", "couchdb", "mariadb",
    "supabase", "firebase", "firestore", "elasticsearch", "opensearch", "solr", "qdrant",
    "chromadb", "pinecone", "weaviate", "sharding", "resharding", "patroni", "jemalloc",
    "aws", "azure", "gcp", "cloudflare", "vercel", "netlify", "heroku", "digitalocean",
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "puppet", "chef",
    "jenkins", "gitlab", "github", "bitbucket", "prometheus", "grafana", "sentry",
    "nginx", "caddy", "envoy", "traefik", "distroless", "rootless", "seccomp", "apparmor",
    "trivy", "grype", "wolfi", "tfsec", "oauth", "jwt", "saml", "sso", "auth0", "clerk",
    "cognito", "bcrypt", "argon2", "cors", "csrf", "xss", "csp", "cve", "keystore",
    "dylib", "dyld", "fanout", "protobuf", "autograd", "vulkan", "metal", "wasm",
    "webassembly", "webrtc", "webgl", "socketio", "rabbitmq", "kafka", "celery",
    "brevo", "sabre", "postbot", "postman", "sendgrid", "mailchimp", "twilio", "stripe",

    # Acronyms & Short terms
    "ui", "ux", "gui", "cli", "sdk", "sdks", "api", "apis", "ia", "aa", "aaa",
    "wcag", "a11y", "i18n", "l10n", "seo", "sem", "crm", "erp", "cms", "slis", "slos",
    "sli", "slo", "sla", "slas", "kpi", "kpis", "roi", "ci", "cd", "cy", "ttl",

    # British variants in computing
    "memoisation", "memoised", "customisation", "customised", "optimisation",
    "optimised", "synchronisation", "synchronised", "initialisation", "initialised",
    "serialisation", "serialised", "prioritisation", "prioritised", "standardisation",
    "organises", "organise", "organised", "organising"
}


def load_project_terms():
    """Extract known technical identifiers from the local package.json (libraries, scripts)."""
    terms = set()
    for candidate_dir in (Path.cwd(), Path(__file__).resolve().parent.parent):
        pkg_file = candidate_dir / "package.json"
        if pkg_file.is_file():
            try:
                import json
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                for sec in ("dependencies", "devDependencies", "peerDependencies", "scripts"):
                    for k in data.get(sec, {}):
                        for part in re.split(r"[^a-zA-Z0-9]+", k):
                            if len(part) >= 2 and not part.isdigit():
                                terms.add(part.lower())
            except Exception:
                pass
    return terms


IGNORE = ({w.strip().lower() for w in qa_config().get("spelling_ignore", []) if w.strip()}
          | TECH_WORDS | load_project_terms())


class SpellMatch:
    """Synthetic match object for spellchecker issues when LanguageTool misses them or is offline."""
    def __init__(self, rule_id, category, rule_issue_type, message, replacements, offset, error_length):
        self.rule_id = rule_id
        self.category = category
        self.rule_issue_type = rule_issue_type
        self.message = message
        self.replacements = list(replacements)
        self.offset = offset
        self.error_length = error_length


# LanguageTool rules that misfire on website copy (headings / buttons have no full stop, typographic quotes and
# dashes are a design choice, "range of AI" -> "ais", "tools our teams use to build" -> "used to")
WEB_COPY_RULES = {"UPPERCASE_SENTENCE_START", "PUNCTUATION_PARAGRAPH_END", "EN_QUOTES", "DASH_RULE", "ELLIPSIS",
                  "WORD_CONTAINS_UNDERSCORE", "ENGLISH_WORD_REPEAT_BEGINNING_RULE", "EN_UNPAIRED_QUOTES",
                  "SENTENCE_FRAGMENT", "MULTIPLICATION_SIGN", "PLUS_MINUS_SIGN", "ARROWS", "TO_NON_BASE",
                  "EN_SPECIFIC_CASE", "A_COLLECTIVE_OF_NN", "USE_TO_VERB"}
SHARED = 5            # a text block on this many pages is a shared component: report it once
MIN_WORDS = 1         # extract blocks down to 1 word so navigation, buttons, and short titles are checked for typos
BATCH_CHARS = 20000   # text sent to LanguageTool per request

CATEGORY = {"TYPOS": "Spelling", "GRAMMAR": "Grammar", "PUNCTUATION": "Punctuation", "TYPOGRAPHY": "Typographical",
            "CASING": "Typographical", "CONFUSED_WORDS": "Word misuse", "SEMANTICS": "Word misuse",
            "COLLOCATIONS": "Word misuse", "NONSTANDARD_PHRASES": "Word misuse", "STYLE": "Style",
            "REDUNDANCY": "Style", "PLAIN_ENGLISH": "Style", "WIKIPEDIA": "Style", "MISC": "Style"}
TYPES = ["Spelling", "Grammar", "Punctuation", "Typographical", "Spacing", "Word misuse", "Style"]
CERTAIN_SPACING = {"SENTENCE_WHITESPACE", "COMMA_PARENTHESIS_WHITESPACE", "WHITESPACE_RULE", "SPACE_BEFORE_PARENTHESIS",
                   "DOUBLE_PUNCTUATION"}


# ------------------------------------------------------------------ 1. text of every page
page_info = {}                       # url -> {title, lang, blocks: [(location, text)], note}
occurrences = defaultdict(list)      # text -> [(url, location)]
word_pages = defaultdict(set)        # lowercase word -> pages (the site's own vocabulary)
word_blocks = Counter()              # lowercase word -> number of different text blocks it appears in


def blocks_of(soup):
    out = []
    for n, (el, text, zone) in enumerate(text_blocks(soup), 1):
        words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text)
        if len(words) < MIN_WORDS or sum(len(w) for w in words) < 0.5 * len(text.replace(" ", "")):
            continue   # too short, or mostly numbers / symbols / code
        out.append((f"{zone} · <{el.name}> #{n} {describe(el, 70)}", text))
    return out


RENDERED_JS = """
() => {
  const SKIP = 'script,style,noscript,template,svg,code,pre,kbd,samp';
  const TAGS = 'h1,h2,h3,h4,h5,h6,p,li,button,a,td,th,label,figcaption,blockquote,dt,dd,span,summary,caption,div';
  const PARENTS = 'p,li,h1,h2,h3,h4,h5,h6,td,th,dd,dt,blockquote,figcaption,button,a,label,summary,caption,div';
  const out = [];
  document.body.querySelectorAll(TAGS).forEach((el, n) => {
    if (el.closest(SKIP) || el.querySelector('p,li,h1,h2,h3,h4,h5,h6,div')) return;
    if (['A','SPAN','BUTTON','LABEL','DIV'].includes(el.tagName) && el.parentElement && el.parentElement.closest(PARENTS)) return;
    const zone = el.closest('header,nav') ? 'header' : el.closest('footer') ? 'footer' : 'content';
    const label = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
        (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
    // innerText puts a line break between parts the browser shows on separate lines: check each line on its own
    (el.innerText || el.textContent || '').split(/\\n+/).forEach(line => {
      line = line.replace(/\\s+/g, ' ').trim();
      if (line) out.push([zone + ' · <' + el.tagName.toLowerCase() + '> #' + (n + 1) + ' ' + label, line]);
    });
  });
  return { lang: (document.documentElement.lang || 'en').toLowerCase(), title: document.title, blocks: out };
}
"""


def usable(text):
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text)
    return len(words) >= MIN_WORDS and sum(len(w) for w in words) >= 0.5 * len(text.replace(" ", ""))


def read_rendered(browser, loc):
    audit.checked(loc)
    ctx = browser.context(width=1366, height=900)
    page = ctx.new_page()
    try:
        page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
        page.wait_for_timeout(800)
        r = page.evaluate(RENDERED_JS)
    finally:
        ctx.close()
    info = {"title": r["title"], "lang": r["lang"], "note": "", "blocks": []}
    if not r["lang"].startswith("en"):
        info["note"] = f"not English (lang={r['lang']}) - skipped"
    else:
        info["blocks"] = [(location, text) for location, text in r["blocks"] if usable(text)]
    page_info[loc] = info


def read(loc):
    audit.checked(loc)
    res, soup = site.page(loc)
    if not soup:
        page_info[loc] = {"title": "", "lang": "", "blocks": [], "note": f"not reachable (HTTP {res['status']})"}
        return
    lang = ((soup.html.get("lang") if soup.html else "") or "en").lower()
    page_info[loc] = {"title": text_of(soup.title) if soup.title else "", "lang": lang, "note": "",
                      "blocks": blocks_of(soup) if lang.startswith("en") else []}
    if not lang.startswith("en"):
        page_info[loc]["note"] = f"not English (lang={lang}) - skipped"


if args.no_browser:
    print(f"Reading the server HTML of {len(pages)} pages ...")
    run_parallel(read, pages, args.workers)
else:
    print(f"Reading the rendered text of {len(pages)} pages in Chrome ...")
    run_browser_pages(read_rendered, pages, args.browser_workers, "pages read")
    for loc in pages:
        if loc not in page_info:   # Chrome failed on it: fall back to the server HTML
            read(loc)

for loc, info in page_info.items():
    if not info["blocks"] and not info["note"]:
        info["note"] = "no checkable text" + (" in the server HTML (try without --no-browser)" if args.no_browser else "")
    for location, text in info["blocks"]:
        occurrences[text].append((loc, location))
        for w in set(re.findall(r"[a-z][a-z'’-]{2,}", text.lower())):
            word_pages[w].add(loc)
for text in occurrences:
    word_blocks.update(set(re.findall(r"[a-z][a-z'’-]{2,}", text.lower())))
# words in the site's own URLs (/technologies/prisma-orm-development) are the site's subject vocabulary
slug_words = {w for u in (site.crawl["records"] if site.crawl else urls)
              for w in re.split(r"[^a-z0-9]+", u.split("://", 1)[-1].split("/", 1)[-1].lower()) if len(w) > 2}

unique = list(occurrences)
if args.public_api:   # the public server allows ~20 requests a minute: main pages only
    keep = set(sample_pages(pages, per_section=0))
    unique = [t for t in unique if any(u in keep for u, _ in occurrences[t])]
total_chars = sum(len(t) for t in unique)
print(f"{sum(len(i['blocks']) for i in page_info.values())} text sections, {len(unique)} unique "
      f"({total_chars // 1000}k characters) to check")

# ------------------------------------------------------------------ 2. LanguageTool
matches = []          # (text, match)
tool = None
try:
    import language_tool_python as ltp
    if args.public_api:
        tool = ltp.LanguageToolPublicAPI(args.language)
    else:
        try:
            tool = ltp.LanguageTool(args.language, config={"cacheSize": 5000, "pipelineCaching": True,
                                                           "maxCheckThreads": 6})
        except Exception:
            tool = ltp.LanguageTool(args.language)
    tool.disabled_rules.update(WEB_COPY_RULES)
    if not args.style:
        tool.disabled_categories.update({"STYLE", "REDUNDANCY", "PLAIN_ENGLISH", "WIKIPEDIA"})
except Exception as e:   # no Java / download failed / no internet for the public API
    reason = f"{type(e).__name__}: {str(e)[:150]}"
    audit.not_checked("English", "grammar (LanguageTool)", reason,
                      "Install Java 17+ (brew install openjdk) or run with --public-api for grammar checks.")

try:   # word frequencies of the pyspellchecker library: rank spelling suggestions by how common the word is
    from spellchecker import SpellChecker
    _SPELL = SpellChecker()
    _FREQ = _SPELL.word_frequency
except ImportError:
    _SPELL = _FREQ = None


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ranked(word, replacements):
    """LanguageTool's spelling suggestions plus the dictionary words 1-2 edits away, most likely first: same start of
    the word first, then frequency (10x less per extra edit) - 'vehical' -> vehicle, not vesical / medical."""
    if not _FREQ:
        return list(replacements)
    low = word.lower()
    pool = list(replacements[:6])
    if word.isalpha() and len(word) < 25:
        pool += sorted(_SPELL.known(_SPELL.edit_distance_1(low)) | _SPELL.known(_SPELL.edit_distance_2(low)))
    pool = [c.capitalize() if word[:1].isupper() and c.islower() else c for c in pool if c.lower() != low]
    pool = list(dict.fromkeys(pool))

    def prefix(c):
        n = 0
        while n < min(len(low), len(c)) and low[n] == c.lower()[n]:
            n += 1
        return min(n, 4)

    def score(c):   # typos keep the start of the word: shared prefix first, then frequency per edit
        d = edit_distance(low, c.lower())
        return (d > 2, -prefix(c), -(_FREQ[c.lower()] if c.replace(" ", "").isalpha() else 0) / 10 ** d,
                pool.index(c))
    return sorted(pool, key=score)[:6] if pool else list(replacements)


def is_compound_word(w):
    """Recognise modern compound words composed of two valid words or tech terms (toolset, codebase, subgrid, datetime...)."""
    w = w.lower()
    if len(w) < 5:
        return False
    # Check common tech/English prefixes
    for prefix in ("sub", "re", "pre", "un", "post", "auto", "multi", "micro", "macro", "meta", "mono", "cross", "inter", "hyper"):
        if w.startswith(prefix) and len(w) > len(prefix) + 2:
            rem = w[len(prefix):]
            if (_SPELL and rem in _SPELL) or rem in IGNORE:
                return True
    # Check suffixes
    for suffix in ("up", "in", "on", "out", "off", "to", "set", "grid", "base", "time", "store", "flow", "pack", "kit", "stack"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            left = w[:-len(suffix)]
            if (_SPELL and left in _SPELL) or left in IGNORE:
                return True
    for i in range(3, len(w) - 2):
        left, right = w[:i], w[i:]
        left_ok = (_SPELL and left in _SPELL) or left in IGNORE
        right_ok = (_SPELL and right in _SPELL) or right in IGNORE
        if left_ok and right_ok:
            return True
    return False


if tool:
    batches, cur, size = [], [], 0
    for t in unique:
        if cur and size + len(t) > BATCH_CHARS:
            batches.append(cur)
            cur, size = [], 0
        cur.append(t)
        size += len(t) + 2
    if cur:
        batches.append(cur)
    lock = threading.Lock()
    done = [0]

    def check(batch):
        joined = "\n\n".join(batch)
        starts, pos = [], 0
        for t in batch:
            starts.append(pos)
            pos += len(t) + 2
        try:
            found = tool.check(joined)
        except Exception as e:
            print(f"  ! LanguageTool failed on a batch: {str(e)[:120]}")
            found = []
        out = []
        for m in found:
            i = max(k for k, s in enumerate(starts) if s <= m.offset)
            text = batch[i]
            local = m.offset - starts[i]
            if local + m.error_length <= len(text):
                out.append((text, local, m))
        with lock:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(batches):
                print(f"  {done[0]}/{len(batches)} batches checked")
        return out

    print(f"Checking {len(batches)} batches with LanguageTool ({args.language}) ...")
    with ThreadPoolExecutor(1 if args.public_api else 3) as ex:
        for out in ex.map(check, batches):
            matches += out
    try:
        tool.close()
    except Exception:
        pass


# ------------------------------------------------------------------ 3. classify + filter false positives
def issue_type(m):
    cat = (m.category or "").upper()
    rid = m.rule_id or ""
    if cat == "TYPOS" or (m.rule_issue_type or "") == "misspelling":
        return "Spelling"
    if "WHITESPACE" in rid or "SPACE" in rid or (m.rule_issue_type or "") == "whitespace":
        return "Spacing"
    return CATEGORY.get(cat, "Grammar" if (m.rule_issue_type or "") == "grammar" else "Typographical")


# Pure-python spellchecker scan: ensures no misspelled words (e.g. 'teechnologies') are missed,
# even if LanguageTool was offline, rate-limited, or skipped them in a batch.
if _SPELL:
    existing_typo_spans = {(text, start) for text, start, m in matches if issue_type(m) == "Spelling"}
    for text in unique:
        for match_obj in re.finditer(r"\b[A-Za-z][A-Za-z'’-]*\b", text):
            raw_w = match_obj.group(0).strip("'’")
            low = raw_w.lower()
            start = match_obj.start()
            if (text, start) in existing_typo_spans:
                continue
            if len(raw_w) <= 2 or low in IGNORE or low in _SPELL or is_compound_word(low):
                continue
            if re.search(r"[\d._/@#+]", raw_w) or (raw_w.isupper() and len(raw_w) <= 6) or re.search(r"[a-z][A-Z]|[A-Z]{2}[a-z]", raw_w):
                continue
            if text[max(0, start - 1):start] in (".", "/", "@", "#", "-", "_") or text[start + len(raw_w):][:1] in ("/", "_"):
                continue
            if "-" in raw_w or not re.search(r"[aeiouy]", low):
                continue
            cands = _SPELL.candidates(low) or set()
            if not cands:
                continue
            cands_list = ranked(raw_w, list(cands))
            best = cands_list[0]
            d = edit_distance(low, best.lower())
            if d <= 2:
                sm = SpellMatch(rule_id="SPELLCHECK_TYPO", category="TYPOS", rule_issue_type="misspelling",
                                message="Possible spelling mistake found.", replacements=cands_list,
                                offset=start, error_length=len(raw_w))
                matches.append((text, start, sm))
                existing_typo_spans.add((text, start))


def sentence_bounds(text, start, end):
    """Start / end of the sentence around [start, end) in a text block."""
    left = max(text.rfind(p, 0, start) for p in (". ", "! ", "? ", ": ")) + 2
    left = 0 if left < 2 else left
    right = min([i + 1 for i in (text.find(p, end) for p in (". ", "! ", "? ")) if i >= 0] + [len(text)])
    return left, right


FUNCTION_WORDS = set("a an the that and for with from this these those our your you are was were has have had not but "
                     "can will its into onto than then them they their there what when which who why how all any is "
                     "to of in on at by as it be we i if in so do".split())


def british_variant(word, suggestion):
    """True when the word is the British spelling of the suggested (American) word: organise / colour / centre /
    programme / practise / travelled / catalogue / defence / licence ... - a variant, not a mistake."""
    w, sg = word.lower(), suggestion.lower()
    us_z = re.sub(r"is(e|ed|es|ing|ation|ations|er|ers|able)$", r"iz\1", w)
    if us_z == sg or (_SPELL and us_z in _SPELL) or us_z in IGNORE:
        return True
    us = re.sub(r"is(e|ed|es|ing|ation|ations|er|ers|able)$", r"iz\1", w)
    us = re.sub(r"yse(d|s)?$", r"yze\1", us)
    us = re.sub(r"our(s|ed|ing|ite|ites|able|ful)?$", r"or\1", us)
    us = re.sub(r"(t|b)re(s|d)?$", r"\1er\2", us)
    us = re.sub(r"ogue(s)?$", r"og\1", us)
    us = re.sub(r"ence$", "ense", us) if us.endswith(("defence", "licence", "offence", "pretence")) else us
    us = us.replace("programme", "program").replace("practis", "practic").replace("travell", "travel") \
        .replace("cancell", "cancel").replace("model l", "model").replace("labell", "label").replace("fulfil", "fulfill")
    if w.startswith("practis") and sg.startswith("practic"):
        return True
    return us == sg or us.replace("-", "") == sg.replace("-", "") or w.replace("-", "") == sg.replace("-", "")


def keep(text, start, m, kind):
    wrong = text[start:start + m.error_length]
    if kind == "Spelling":
        w = wrong.strip("'’")
        low_w = w.lower()
        if not m.replacements:
            return None                                   # no dictionary word close by: a name / term
        if low_w in IGNORE:
            return None
        if _SPELL and w.isalpha() and w.islower() and _SPELL.known([low_w]):
            return None                                   # a real dictionary word: not a misspelling
        if re.search(r"[\d._/@#+]", w) or (w.isupper() and len(w) <= 6) or re.search(r"[a-z][A-Z]|[A-Z]{2}[a-z]", w):
            return None                                   # Next.js, H1, NHTSA, iPhone, HRNest, camelCase
        if text[max(0, start - 1):start] in (".", "/", "@", "#", "-", "_") or text[start + len(wrong):][:1] in ("/", "_"):
            return None                                   # file extensions / paths: next.config.mjs, Dashboard.tsx
        if "-" in w:
            return None                                   # un-cached, help-centre: a compound, not a misspelling
        if not re.search(r"[aeiouy]", low_w):
            return None                                   # pnpm, dbt: an abbreviation, not a word
        if is_compound_word(low_w):
            return None                                   # legitimate compound term (subgrid, toolset, codebase...)
        if "british" in (m.message or "").lower() or any(british_variant(w, r) for r in m.replacements):
            return None                                   # British / American variant, not a mistake

        best = m.replacements[0]
        if " " in best and best.replace(" ", "").lower() == low_w:
            # "issuesthat" -> "issues that" is a missing space; "wealthtech" -> "wealth tech" is a compound term
            if not any(part in FUNCTION_WORDS for part in best.lower().split()):
                return None

        distance = edit_distance(low_w, best.lower())
        used_on = len(word_pages.get(low_w, ()))
        # Only suppress repeated words if they are NOT a close typo (distance <= 2) of a real dictionary word
        if (used_on >= 3 or word_blocks[low_w] >= 3) and distance > 2:
            return None                                   # proper brand / name used across multiple pages
        if w[:1].isupper() and used_on >= 2 and distance > 2:
            return None                                   # capitalised custom name on 2+ pages
        if w[:1].isupper() and distance > 2:
            return None                                   # capitalised and far from any known word: proper name

        # Confidence:
        if distance <= 1:
            return "High"                                 # 1-letter typo: clear misspelling (FAIL)
        if distance == 2 and (_SPELL and best.lower() in _SPELL):
            return "Medium"                               # 2-letter typo of common word (FAIL)
        if distance > 2:
            return "Low"                                  # distant candidate: review (WARN)
        return "Medium"
    if m.rule_id == "SENTENCE_WHITESPACE":
        if not re.search(r"[a-z]{3}[.!?]$", text[:start]):
            return None                                   # "S.G Highway", "B.E./B.Tech": abbreviations, not "end.Next"
        nxt = re.match(r"[A-Za-z']+", text[start:])
        if not nxt or nxt.group(0).lower() not in FUNCTION_WORDS:
            return "Low"                                  # sync.Pool, Xamarin.Forms: probably a code name - review
    if m.rule_id == "COMMA_PARENTHESIS_WHITESPACE" and re.match(r"\s?\.[A-Za-z]", text[start:start + 3]):
        return None                                       # " .gitlab-ci.yml": a file name, not a stray full stop
    if kind == "Word misuse":
        return "Medium"
    if kind == "Style":
        return "Low"
    if not m.replacements:
        return "Low"
    return "High" if len(m.replacements) == 1 else "Medium"


SEVERITY = {"Spelling": IMPORTANT, "Grammar": IMPORTANT, "Spacing": IMPORTANT, "Punctuation": OPTIMIZATION,
            "Typographical": OPTIMIZATION, "Word misuse": OPTIMIZATION, "Style": INFO}
detail_rows, page_issues, seen = [], defaultdict(list), set()
for text, start, m in matches:
    kind = issue_type(m)
    if kind == "Style" and not args.style:
        continue
    # For short phrases (< 3 words, e.g. menu links, button labels), only report Spelling issues
    words_in_text = re.findall(r"[A-Za-z]+", text)
    if len(words_in_text) < 3 and kind != "Spelling":
        continue
    end = start + m.error_length
    wrong = text[start:end]
    if kind == "Spelling" and (m.rule_id.startswith("EN_COMPOUNDS") or " " in wrong.strip()):
        kind = "Typographical"      # hyphenation advice ("live streaming" -> "live-streaming"), not a misspelling
    if kind == "Spelling":
        m.replacements = ranked(wrong, m.replacements)   # rank first: the confidence depends on the best suggestion
    confidence = keep(text, start, m, kind)
    if not confidence:
        continue
    sev = SEVERITY[kind]
    if kind == "Spacing" and m.rule_id not in CERTAIN_SPACING:
        sev = OPTIMIZATION
    if confidence == "Low" and sev == IMPORTANT:
        sev = OPTIMIZATION          # possible issue: WARN, not FAIL
    s0, s1 = sentence_bounds(text, start, end)
    actual = text[s0:s1].strip()
    fix = m.replacements[0] if m.replacements else ""
    expected = (text[s0:start] + fix + text[end:s1]).strip() if m.replacements else "(rephrase - see reason)"
    reason = re.sub(r"\s+", " ", m.message or "").strip()
    places = occurrences[text]
    first_url = places[0][0]
    others = sorted({u for u, _ in places} - {first_url})
    shared = len(others) + 1 >= SHARED
    targets = [places[0]] if shared else list(dict.fromkeys(places))
    rule_label = re.sub(r"[“\"'‘][^”\"'’]*[”\"'’]", "“…”", reason)[:90]
    for url, location in targets:
        key = (url, m.rule_id, wrong, actual)
        if key in seen:
            continue
        seen.add(key)
        cid = f"ENG-{kind[:4].upper()}-{hashlib.md5('|'.join(key).encode(), usedforsecurity=False).hexdigest()[:6]}"
        status = "FAIL" if sev == IMPORTANT else "WARN"
        also = f"also on {len(others)} other page(s) (shared section): {', '.join(site.path(u) for u in others[:5])}" \
            if shared and others else ""
        suggestion = ", ".join(m.replacements[:4]) or "(no automatic suggestion)"
        audit.add(url, sev, kind, f"{kind}: {rule_label}", current=wrong, expected=expected[:300],
                  description=reason, element=f"{location} · chars {start}-{end}",
                  detail=f"Actual: {actual[:250]} | confidence {confidence} | rule {m.rule_id}" + (f" | {also}" if also else ""),
                  fix=f"Change '{wrong}' to '{fix}'." if fix else "Rephrase the sentence (see Description).")
        info = page_info[url]
        row = {"Check ID": cid, "URL": url, "Page title": info["title"][:120], "Status": status, "Issue type": kind,
               "Severity": sev, "Wrong input": wrong, "Actual output": actual[:400], "Expected output": expected[:400],
               "Suggested correction": suggestion, "Reason": reason, "Location": f"{location} · chars {start}-{end}",
               "Confidence": confidence, "Rule": m.rule_id, "Shared section": also}
        detail_rows.append(row)
        page_issues[url].append(row)

# ------------------------------------------------------------------ 4. URL results, summary, sheets
url_rows, status_count = [], Counter()
for loc in pages:
    info = page_info.get(loc, {"title": "", "lang": "", "blocks": [], "note": "not read"})
    items = page_issues.get(loc, [])
    kinds = Counter(i["Issue type"] for i in items)
    if info["note"] and not info["blocks"]:
        status = "SKIP"
    elif any(i["Status"] == "FAIL" for i in items):
        status = "FAIL"
    elif items:
        status = "WARN"
    else:
        status = "PASS"
    status_count[status] += 1
    words = sum(len(t.split()) for _, t in info["blocks"])
    url_rows.append((loc, info["title"][:100], status, info["lang"], len(info["blocks"]), words, len(items),
                     *(kinds.get(k, 0) for k in TYPES[:6]), info["note"]))
type_count = Counter(r["Issue type"] for r in detail_rows)
words_total = sum(r[5] for r in url_rows)
summary = [("Pages scanned", len(pages)), ("Text sections scanned", sum(r[4] for r in url_rows)),
           ("Unique text sections checked", len(unique)), ("Words scanned", words_total),
           ("Issues found", len(detail_rows))] + [(f"{k} issues", type_count.get(k, 0)) for k in TYPES] + \
          [("PASS pages", status_count["PASS"]), ("WARN pages", status_count["WARN"]),
           ("FAIL pages", status_count["FAIL"]), ("SKIP pages (not English / no text)", status_count["SKIP"]),
           ("Engine", f"LanguageTool {'public API' if args.public_api else 'local'} ({args.language}) + SpellChecker" if tool
            else "SpellChecker (LanguageTool offline)")]
for label, value in summary:
    audit.note(label, value)
STATUS_FILL = {3: STATUS_COLORS}
audit.sheet("URL results", ["URL", "Page title", "Status", "lang", "Text sections", "Words", "Issues", *TYPES[:6], "Note"],
            url_rows, (55, 40, 9, 7, 12, 8, 8, 9, 9, 12, 13, 9, 11, 40), fills=STATUS_FILL)
cols = ["Check ID", "URL", "Page title", "Status", "Issue type", "Severity", "Wrong input", "Actual output",
        "Expected output", "Suggested correction", "Reason", "Location", "Confidence", "Rule", "Shared section"]
detail_rows.sort(key=lambda r: (r["Status"] != "FAIL", r["URL"], r["Issue type"]))
audit.sheet("Issue details", cols, [[r[c] for c in cols] for r in detail_rows],
            (18, 50, 30, 8, 13, 12, 25, 60, 60, 30, 50, 45, 11, 30, 40),
            fills={4: STATUS_COLORS, 7: WRONG_COLOR, 8: WRONG_COLOR, 9: EXPECTED_COLOR, 10: EXPECTED_COLOR})
audit.sheet("Summary counts", ["Measure", "Value"], summary, (36, 30))
audit.save("English_Grammar_Report")

# ------------------------------------------------------------------ 5. HTML page (wrong = red, expected = green)
E = html.escape
cards = "".join(f'<div class="card {k.lower()}"><b>{status_count[k]}</b>{k} pages</div>' for k in ("PASS", "WARN", "FAIL", "SKIP"))
stats = "".join(f"<tr><th>{E(str(a))}</th><td>{E(str(b))}</td></tr>" for a, b in summary)
url_html = []
for row in sorted(url_rows, key=lambda r: ({"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}[r[2]], r[0])):
    loc, title, status = row[0], row[1], row[2]
    items = page_issues.get(loc, [])
    body = ""
    for i in items:
        body += (f'<div class="issue"><div class="meta"><span class="pill {i["Status"].lower()}">{i["Status"]}</span>'
                 f'<b>{E(i["Issue type"])}</b> · {E(i["Check ID"])} · confidence {E(i["Confidence"])} · {E(i["Location"])}</div>'
                 f'<div class="box wrong"><small>WRONG INPUT</small><code>{E(i["Wrong input"])}</code></div>'
                 f'<div class="box wrong"><small>ACTUAL OUTPUT (on the page now)</small>{E(i["Actual output"])}</div>'
                 f'<div class="box right"><small>EXPECTED OUTPUT</small>{E(i["Expected output"])}</div>'
                 f'<div class="reason"><small>REASON</small>{E(i["Reason"])}<br><small>SUGGESTED CORRECTION</small>'
                 f'{E(i["Suggested correction"])}{("<br><small>SHARED</small>" + E(i["Shared section"])) if i["Shared section"] else ""}</div></div>')
    note = f" · {E(row[-1])}" if row[-1] else ""
    url_html.append(f'<details class="url {status.lower()}" data-s="{status}"{" open" if status == "FAIL" and len(url_html) < 5 else ""}>'
                    f'<summary><span class="pill {status.lower()}">{status}</span><a href="{E(loc)}">{E(site.path(loc))}</a>'
                    f'<span class="muted">{E(title)} · {row[6]} issue(s) · {row[5]} words{note}</span></summary>{body}</details>')
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>English Grammar Report</title><style>
:root{{--bg:#f6f7fb;--fg:#1d2433;--card:#fff;--line:#e3e6ee;--muted:#5d6678;--red:#ffe1e3;--redb:#e5484d;--green:#dcf5e5;
--greenb:#30a46c;--yellow:#fff4c2;--yellowb:#d39e00;--gray:#ececf0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111318;--fg:#e8eaf0;--card:#1a1d24;--line:#2a2f3a;--muted:#9aa1b2;
--red:#4a1d22;--green:#16351f;--yellow:#3d3410;--gray:#262a33}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 60px}}h1{{margin:0 0 6px}}.muted{{color:var(--muted);font-size:13px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:16px 0}}
.card{{border-radius:14px;padding:12px;font-weight:600;cursor:pointer;border:2px solid transparent}}.card b{{display:block;font-size:28px}}
.card.pass{{background:var(--green)}}.card.fail{{background:var(--red)}}.card.warn{{background:var(--yellow)}}.card.skip{{background:var(--gray)}}
table{{border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;width:100%;max-width:520px;font-size:14px}}
th,td{{padding:6px 12px;border-bottom:1px solid var(--line);text-align:left}}
.url{{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--line);border-radius:12px;margin:8px 0;padding:0 14px}}
.url.pass{{border-left-color:var(--greenb)}}.url.fail{{border-left-color:var(--redb)}}.url.warn{{border-left-color:var(--yellowb)}}
summary{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:10px 0;cursor:pointer}}summary a{{color:inherit;font-weight:600;overflow-wrap:anywhere}}
.pill{{border-radius:999px;padding:1px 10px;font:700 12px system-ui;color:#1d2433}}.pill.pass{{background:#c6efce}}.pill.fail{{background:#ffc7ce}}
.pill.warn{{background:#ffeb9c}}.pill.skip{{background:#e7e6e6}}.issue{{border-top:1px dashed var(--line);padding:10px 0}}
.meta{{font-size:13px;margin-bottom:6px;overflow-wrap:anywhere}}.box{{border-radius:10px;padding:8px 12px;margin:6px 0;overflow-wrap:anywhere}}
.box small,.reason small{{display:block;font:700 11px system-ui;letter-spacing:.04em;color:var(--muted)}}
.wrong{{background:var(--red);border-left:4px solid var(--redb)}}.right{{background:var(--green);border-left:4px solid var(--greenb)}}
.reason{{font-size:14px;overflow-wrap:anywhere}}.filters button{{margin:0 6px 6px 0;padding:6px 12px;border-radius:10px;border:1px solid var(--line);
background:var(--card);color:var(--fg);cursor:pointer}}
</style></head><body><main><h1>English Grammar &amp; Spelling Report</h1>
<p class="muted">{E(site.base)} · {len(pages)} pages · LanguageTool {E(args.language)}</p>
<div class="cards">{cards}</div><table>{stats}</table><h2>Results by URL</h2>
<div class="filters"><button data-f="ALL">All</button><button data-f="FAIL">FAIL</button><button data-f="WARN">WARN</button>
<button data-f="PASS">PASS</button><button data-f="SKIP">SKIP</button></div>{''.join(url_html)}</main>
<script>document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>document.querySelectorAll('.url').forEach(u=>
u.style.display=b.dataset.f==='ALL'||u.dataset.s===b.dataset.f?'':'none'));</script></body></html>"""
hpath = report_path("English_Grammar_Report", "html")
hpath.write_text(page, encoding="utf-8")
print(f"      {rel_path(hpath)}")
print("  " + " | ".join(f"{a}: {b}" for a, b in summary[:5]) + f" | PASS {status_count['PASS']}, WARN "
      f"{status_count['WARN']}, FAIL {status_count['FAIL']}, SKIP {status_count['SKIP']}")
