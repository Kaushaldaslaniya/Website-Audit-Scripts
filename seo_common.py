"""
Shared helpers for the website audit scripts in this folder.

- Pages to audit come from a crawl of the whole site (crawl_site): it starts at the homepage, sitemap.xml and the
  sitemaps in robots.txt, and follows every internal link it finds (<a>, <area>, canonical, hreflang alternates,
  rel=next/prev, iframes, meta refresh, URLs inside JSON-LD and redirects). Then Chrome opens every menu / tab /
  accordion on the main pages (discover_js_links) to find links that only exist after a click, and those are
  crawled too (--no-js-discovery skips this). One crawl is shared by every script of
  a run_all.py run (kept in the system temp folder, not in report/); a script run on its own reuses a crawl of the
  same server from the last 30 minutes (--fresh-crawl forces a new one, --sitemap-only skips crawling).
- Every report is saved in three formats, one folder per format - nothing else is written to report/:
      py files/report/<YYYY-MM-DD>/excel/<Report_Name>_<HH-MM-SS>.xlsx
      py files/report/<YYYY-MM-DD>/json/<Report_Name>_<HH-MM-SS>.json
      py files/report/<YYYY-MM-DD>/csv/<Report_Name>_<HH-MM-SS>.csv     (the "Issues by URL" table)
  py files/report is created automatically if it doesn't exist. Saving a report deletes that report's older
  files (any date); run_all.py empties py files/report before a full run.
  (run_all.py sets SEO_RUN_DATE / SEO_RUN_TIME so every report of one run shares a time stamp).
  All list issues URL by URL, one row / object per issue, with description, current value, expected value
  and recommended fix (see issue_guide.py). 21_website_health_report.py combines the JSON reports.
- The server to audit comes from --base, else $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL (shell environment,
  then .env.local, then .env), else http://localhost:3000.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

try:
    import requests
    from bs4 import BeautifulSoup
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing package ({e.name}). Run:  pip install -r \"py files/requirements.txt\"")

from issue_guide import guide

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
REPORT_ROOT = SCRIPTS_DIR / "report"   # py files/report - created automatically when missing


def ensure_report_root():
    """Create py files/report (and parents) if it doesn't exist yet."""
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    return REPORT_ROOT
DEFAULT_BASE = "http://localhost:3000"
SITE_WIDE = "(site-wide)"

CRITICAL, IMPORTANT, OPTIMIZATION, INFO = "Critical", "Important", "Optimization", "Info"
SEVERITY_ORDER = {CRITICAL: 0, IMPORTANT: 1, OPTIMIZATION: 2, INFO: 3}
PRIORITY = {CRITICAL: "P1 - fix immediately", IMPORTANT: "P2 - fix soon", OPTIMIZATION: "P3 - improve",
            INFO: "P4 - for information"}
PAGE_WEIGHT = {CRITICAL: 25, IMPORTANT: 8, OPTIMIZATION: 2, INFO: 0}   # deducted from a page's 100
SITE_WEIGHT = {CRITICAL: 12, IMPORTANT: 4, OPTIMIZATION: 1, INFO: 0}   # deducted from the final score
MAX_PER_CHECK = 50   # rows kept per (URL, issue); the rest are summarised in one extra row

FILLS = {
    CRITICAL: PatternFill(fill_type="solid", start_color="FFC7CE"),
    IMPORTANT: PatternFill(fill_type="solid", start_color="FFE4B5"),
    OPTIMIZATION: PatternFill(fill_type="solid", start_color="DDEBF7"),
    INFO: PatternFill(fill_type="solid", start_color="F2F2F2"),
    "ok": PatternFill(fill_type="solid", start_color="C6EFCE"),
    "header": PatternFill(fill_type="solid", start_color="1F4E78"),
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 WebsiteAudit/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}
REDIRECT_CODES = (301, 302, 303, 307, 308)


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------
def grade(score):
    if score is None:
        return "Not measured"
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Good"
    if score >= 70:
        return "Needs Improvement"
    if score >= 50:
        return "Poor"
    return "Critical"


def grade_fill(score):
    if not isinstance(score, (int, float)):
        return FILLS[INFO]
    if score >= 90:
        return FILLS["ok"]
    if score >= 70:
        return FILLS[OPTIMIZATION]
    if score >= 50:
        return FILLS[IMPORTANT]
    return FILLS[CRITICAL]


# ---------------------------------------------------------------------------
# Report paths
# ---------------------------------------------------------------------------
def run_date():
    return os.environ.get("SEO_RUN_DATE") or datetime.now().strftime("%Y-%m-%d")


_RUN_TIME = os.environ.get("SEO_RUN_TIME") or datetime.now().strftime("%H-%M-%S")


def run_time():
    return _RUN_TIME


FORMAT_DIRS = {"xlsx": "excel", "json": "json", "csv": "csv", "md": "markdown", "html": "html"}


def report_path(name, ext="xlsx"):
    """report/<date>/<excel|json|csv>/<name>_<time>.<ext> (folders created on demand)."""
    folder = ensure_report_root() / run_date() / FORMAT_DIRS.get(ext, ext)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}_{run_time()}.{ext}"


REPORT_FILE = r"_\d\d-\d\d-\d\d(\.(xlsx|json|csv|md|html))?"   # a file, or a screenshots folder


def _prune_empty_dirs():
    for d in sorted(REPORT_ROOT.glob("**/*"), key=lambda p: len(p.parts), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def remove_old_reports(name):
    """Delete earlier Excel / JSON / CSV files of this report (any date); keeps the current run's files."""
    if not REPORT_ROOT.exists():
        return 0
    import shutil
    removed = 0
    for f in REPORT_ROOT.glob(f"*/*/{name}_*"):
        current = f.parent.parent.name == run_date() and f.name.split(".")[0] == f"{name}_{run_time()}"
        if re.fullmatch(re.escape(name) + REPORT_FILE, f.name) and not current:
            shutil.rmtree(f) if f.is_dir() else f.unlink()
            removed += 1
    _prune_empty_dirs()
    if removed:
        print(f"Removed {removed} old {name} file(s)")
    return removed


def clear_reports():
    """Delete everything inside py files/report (used by run_all.py before a full run)."""
    import shutil
    if REPORT_ROOT.exists() and REPORT_ROOT.parent == SCRIPTS_DIR:
        for item in REPORT_ROOT.iterdir():
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    ensure_report_root()


def screenshot_dir(name):
    """report/<date>/screenshots/<name>_<time>/ - evidence images of a report (replaced with the report)."""
    folder = ensure_report_root() / run_date() / "screenshots" / f"{name}_{run_time()}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# Free command-line tools downloaded on first use (W3C Nu validator ...) - outside the project and report/
TOOLS_DIR = Path.home() / ".cache" / "website-audit-tools"

# Project expectations used by the QA checks (confirmed phone, live URL ...) - see README section "QA config"
QA_CONFIG_FILE = SCRIPTS_DIR / "qa_config.json"



CONFIG_LISTS = ("phones", "emails", "forbidden_terms", "required_footer_links", "social_profiles", "spelling_ignore",
                "nav_expected")
CONFIG_TEXT = ("company", "address", "live_url")
_warned = set()


def warn_once(message):
    if message not in _warned:
        _warned.add(message)
        print(f"WARNING: {message}", file=sys.stderr)


def qa_config():
    """py files/qa_config.json merged over the defaults; keys starting with '_' are comments.
    Values are checked: a single text where a list is expected becomes a one-item list ("phones": "800-..." works),
    "true" / "false" text becomes a boolean, and a value of the wrong kind is ignored with a warning - otherwise a
    typo would silently change what the checks expect (a phone number read letter by letter, legal_site "false"
    counting as true)."""
    cfg = {"company": "", "phones": [], "emails": [], "address": "", "live_url": "", "legal_site": False,
           "forbidden_terms": [], "required_footer_links": ["privacy", "terms"], "social_profiles": [],
           "spelling_ignore": [], "nav_expected": []}
    try:
        data = json.loads(QA_CONFIG_FILE.read_text(encoding="utf-8"))
    except OSError:
        return cfg
    except ValueError as e:
        warn_once(f"{QA_CONFIG_FILE.name} is not valid JSON ({e}) - the default settings are used instead")
        return cfg
    if not isinstance(data, dict):
        warn_once(f"{QA_CONFIG_FILE.name} must be a JSON object {{...}} - the default settings are used instead")
        return cfg
    for k, v in data.items():
        if k.startswith("_"):
            continue
        if k in CONFIG_LISTS:
            if isinstance(v, str):
                v = [v]
            elif not isinstance(v, list):
                warn_once(f"{QA_CONFIG_FILE.name}: \"{k}\" must be a list, e.g. [\"...\"] - ignored")
                continue
            v = [str(x).strip() for x in v if x is not None and str(x).strip()]
        elif k == "legal_site":
            v = v.strip().lower() in ("1", "true", "yes") if isinstance(v, str) else bool(v)
        elif k in CONFIG_TEXT:
            if v is not None and not isinstance(v, str):
                warn_once(f"{QA_CONFIG_FILE.name}: \"{k}\" must be text - ignored")
                continue
            v = (v or "").strip()
        cfg[k] = v
    return cfg


def rel_path(path):
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
REPORT_URL_VAR = "NEXT_PUBLIC_REPORT_URL"


def read_env_file_value(name, files=(".env.local", ".env")):
    """Value of NAME from the project's .env.local / .env (first file that sets it), or ''."""
    for fname in files:
        try:
            lines = (PROJECT_ROOT / fname).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            m = re.match(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.*)$", line)
            if m:
                value = m.group(1).strip()
                if value[:1] in "'\"" and value[-1:] == value[:1]:
                    value = value[1:-1]
                else:
                    value = value.split(" #")[0].strip()
                if value:
                    return value
    return ""


def normalize_base(url):
    """'localhost:3000/' -> 'http://localhost:3000' (scheme added, trailing slash removed)."""
    url = (url or "").strip().rstrip("/")
    return url if re.match(r"(?i)https?://", url) else "http://" + url


def default_base():
    """Server to audit: $SITE_BASE_URL, else NEXT_PUBLIC_REPORT_URL (environment, .env.local, .env),
    else http://localhost:3000."""
    return normalize_base(os.environ.get("SITE_BASE_URL") or os.environ.get(REPORT_URL_VAR)
                          or read_env_file_value(REPORT_URL_VAR) or DEFAULT_BASE)


def env_flag(name):
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def env_int(name, default, minimum=1):
    """Whole-number setting from the environment (run_all.py passes SEO_WORKERS ...); invalid -> the default."""
    raw = os.environ.get(name, "")
    try:
        return max(minimum, int(raw)) if raw.strip() else default
    except ValueError:
        print(f"Ignoring {name}={raw!r} (not a whole number) - using {default}", file=sys.stderr)
        return default


def default_browser_workers():
    """Parallel Chrome instances for the browser scripts: half the CPU cores, 1-4."""
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def int_arg(minimum):
    """argparse type: a whole number >= minimum (a clear message instead of odd behaviour for 0 / -1)."""
    def convert(value):
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError(f"must be a whole number, got {value!r}")
        if n < minimum:
            raise argparse.ArgumentTypeError(f"must be {minimum} or more, got {n}")
        return n
    return convert


def regex_arg(value):
    """argparse type: a valid regular expression."""
    try:
        re.compile(value)
    except re.error as e:
        raise argparse.ArgumentTypeError(f"not a valid regular expression ({e}) - escape special characters, "
                                         f"e.g. --only '/blog/'")
    return value


def base_arg(value):
    """argparse type: the server URL, normalised; it needs a host name."""
    url = normalize_base(value)
    if not urlparse(url).hostname:
        raise argparse.ArgumentTypeError(f"not a server URL: {value!r} (e.g. http://localhost:3000)")
    return url


def parse_args(description, extra=None, default_pages="all"):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--base", type=base_arg, default=default_base(),
                    help=f"server to audit (default: $SITE_BASE_URL, else {REPORT_URL_VAR} from .env.local, "
                         f"else {DEFAULT_BASE}; now %(default)s)")
    ap.add_argument("--workers", type=int_arg(1), default=env_int("SEO_WORKERS", 8),
                    help="parallel requests (default %(default)s)")
    ap.add_argument("--limit", type=int_arg(0), default=0, help="only the first N pages (0 = no limit)")
    ap.add_argument("--only", type=regex_arg, default="", help="regex: only pages whose URL matches")
    ap.add_argument("--pages", choices=("all", "sample"),
                    default=os.environ.get("SEO_PAGES") if os.environ.get("SEO_PAGES") in ("all", "sample")
                    else default_pages,
                    help="all discovered pages, or one sample per page type (default: %(default)s)")
    ap.add_argument("--max-pages", type=int_arg(1), default=env_int("SEO_MAX_PAGES", 5000),
                    help="crawl at most this many URLs (default %(default)s)")
    ap.add_argument("--sitemap-only", action="store_true", default=env_flag("SEO_SITEMAP_ONLY"),
                    help="audit only sitemap.xml URLs (no crawling)")
    ap.add_argument("--fresh-crawl", action="store_true", default=env_flag("SEO_FRESH_CRAWL"),
                    help="crawl again even if a recent crawl of this server exists")
    ap.add_argument("--ignore-robots", action="store_true", default=env_flag("SEO_IGNORE_ROBOTS"),
                    help="also crawl URLs that robots.txt disallows")
    ap.add_argument("--browser-workers", type=int_arg(1),
                    default=env_int("SEO_BROWSER_WORKERS", default_browser_workers()),
                    help="Chrome instances running in parallel in the browser checks (default %(default)s)")
    ap.add_argument("--no-js-discovery", action="store_true", default=env_flag("SEO_NO_JS_DISCOVERY"),
                    help="don't open menus / tabs in Chrome to find links that only appear after JavaScript")
    if extra:
        extra(ap)
    return ap.parse_args()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
_local = threading.local()
_cache = {}
_cache_lock = threading.Lock()


def _session():
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        # Never keep cookies: the site switches language by cookie, so one request must not change the next
        from http.cookiejar import DefaultCookiePolicy
        s.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        _local.session = s
    return s


def fetch(url, method="GET", allow_redirects=True, timeout=60, headers=None, use_cache=True):
    """Cached request -> dict(status, url, headers, content, ms, history, location, error, http_version)."""
    hkey = tuple(sorted((headers or {}).items()))
    key = (method, url, allow_redirects, hkey)
    if use_cache:
        with _cache_lock:
            if key in _cache:
                return _cache[key]
            if allow_redirects:   # a crawl request of the same URL that did not redirect is the same answer
                plain = _cache.get((method, url, False, hkey))
                if plain and plain["status"] not in REDIRECT_CODES:
                    return plain
    start = time.time()
    try:
        r = _session().request(method, url, allow_redirects=allow_redirects, timeout=timeout, headers=headers)
        if method == "HEAD" and r.status_code in (403, 405, 501):
            r = _session().get(url, allow_redirects=allow_redirects, timeout=timeout, headers=headers, stream=True)
            r.close()
        res = {
            "status": r.status_code,
            "url": r.url,
            "headers": r.headers,
            "content": r.content if method == "GET" else b"",
            "ms": int((time.time() - start) * 1000),
            "history": [(h.status_code, h.url, h.headers.get("Location", "")) for h in r.history],
            "location": r.headers.get("Location", ""),
            "error": "",
            "http_version": {10: "HTTP/1.0", 11: "HTTP/1.1", 20: "HTTP/2"}.get(getattr(r.raw, "version", 0), ""),
        }
    except requests.RequestException as e:
        res = {"status": 0, "url": url, "headers": {}, "content": b"", "ms": int((time.time() - start) * 1000),
               "history": [], "location": "", "error": f"{type(e).__name__}: {str(e)[:200]}", "http_version": ""}
    if use_cache:
        with _cache_lock:
            _cache[key] = res
    return res


def follow_redirects(url, max_hops=10):
    """Follow redirects manually -> (final_status, hops[list of (status, url)], loop: bool)."""
    hops, seen, current = [], set(), url
    for _ in range(max_hops):
        res = fetch(current, allow_redirects=False)
        hops.append((res["status"], current))
        if res["status"] in REDIRECT_CODES and res["location"]:
            nxt = urljoin(current, res["location"])
            if nxt in seen or nxt == current:
                return res["status"], hops + [("loop", nxt)], True
            seen.add(current)
            current = nxt
            continue
        return res["status"], hops, False
    return 0, hops, True


# ---------------------------------------------------------------------------
# Site: maps sitemap URLs (maybe the live domain) onto the audited server
# ---------------------------------------------------------------------------
def _bare_host(host):
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _xml_name(tag):
    """XML tag without its namespace: '{http://...}url' -> 'url'."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


class Site:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.base_host = urlparse(self.base).netloc
        self.site_host = None
        self.site_scheme = None
        self.sitemap_urls = []
        self.sitemap_error = ""
        self.sitemap_warning = ""      # the file was read, but has a problem search engines reject (no namespace)
        self.sitemap_entries = []      # every <url> as (loc, lastmod) incl. the child sitemaps - duplicates kept
        self.sitemap_children = []     # sitemap index: (child sitemap URL, HTTP status, problem or "")
        self.sitemap_root = None
        self.sitemap_response = None
        self.crawl = None          # crawl result (see crawl_site), None with --sitemap-only

    # sitemap ---------------------------------------------------------------
    def _entries(self, root):
        """(loc, lastmod) of every <url> of a <urlset>; notes a missing sitemaps.org namespace."""
        out = []
        for u in root:
            if _xml_name(u.tag) != "url":
                continue
            if not u.tag.startswith("{" + SITEMAP_NS + "}"):
                self.sitemap_warning = f'the <urlset> has no sitemaps.org namespace (xmlns="{SITEMAP_NS}")'
            loc = next((c.text.strip() for c in u if _xml_name(c.tag) == "loc" and (c.text or "").strip()), None)
            if loc:
                out.append((loc, next((c.text.strip() for c in u if _xml_name(c.tag) == "lastmod" and c.text), None)))
        return out

    def load_sitemap(self):
        """sitemap.xml, and every sitemap of a sitemap index -> the page URLs (each once)."""
        import xml.etree.ElementTree as ET
        res = fetch(f"{self.base}/sitemap.xml")
        self.sitemap_response = res
        if res["status"] != 200:
            self.sitemap_error = f"HTTP {res['status']} {res['error']}".strip()
            return []
        try:
            root = ET.fromstring(res["content"])
        except ET.ParseError as e:
            self.sitemap_error = f"invalid XML: {e}"
            return []
        self.sitemap_root = root
        entries = self._entries(root)
        for child in (e for e in root if _xml_name(e.tag) == "sitemap"):   # sitemap index
            loc = next((c.text.strip() for c in child if _xml_name(c.tag) == "loc" and (c.text or "").strip()), "")
            if not loc:
                continue
            sub = fetch(self.to_fetch(loc))
            problem = "" if sub["status"] == 200 else f"HTTP {sub['status']} {sub['error']}".strip()
            if not problem:
                try:
                    found = self._entries(ET.fromstring(sub["content"]))
                    entries += found
                    problem = "" if found else "no <url> entries"
                except ET.ParseError as e:
                    problem = f"invalid XML: {e}"
            self.sitemap_children.append((loc, sub["status"], problem))
        self.sitemap_entries = entries
        urls = [loc for loc, _ in entries]
        if urls:
            host = Counter(urlparse(u).netloc for u in urls).most_common(1)[0][0]
            self.site_host = host
            self.site_scheme = urlparse(urls[0]).scheme
        self.sitemap_urls = list(dict.fromkeys(urls))
        return self.sitemap_urls

    # urls ------------------------------------------------------------------
    def is_internal(self, url):
        host = urlparse(url).netloc
        if not host:
            return True
        return _bare_host(host) in {_bare_host(self.base_host), _bare_host(self.site_host)}

    def to_fetch(self, url):
        """Same path/query on the audited server."""
        p = urlparse(url)
        return f"{self.base}{p.path or '/'}" + (f"?{p.query}" if p.query else "")

    def public(self, path_or_url):
        """URL on the canonical (sitemap) host."""
        p = urlparse(path_or_url)
        scheme = self.site_scheme or urlparse(self.base).scheme
        host = self.site_host or self.base_host
        return f"{scheme}://{host}{p.path or '/'}" + (f"?{p.query}" if p.query else "")

    @staticmethod
    def path(url):
        p = urlparse(url).path or "/"
        return p if p == "/" else p.rstrip("/")

    @property
    def is_public(self):
        return bool(self.site_host) and not re.match(r"(localhost|127\.|0\.0\.0\.0|192\.168\.|10\.)", self.site_host)

    # pages -----------------------------------------------------------------
    def page(self, url):
        """GET a page from the audited server -> (response, soup or None)."""
        res = fetch(self.to_fetch(url))
        soup = BeautifulSoup(res["content"], "lxml") if res["status"] == 200 and res["content"] else None
        return res, soup

    def record(self, url):
        """Crawl record of a URL (status, depth, in_sitemap, found_on ...) or {}."""
        if not self.crawl:
            return {}
        return self.crawl["records"].get(clean_url(self, url)) or {}


def norm(url):
    p = urlparse(url)
    path = p.path if p.path in ("", "/") else p.path.rstrip("/")
    return urlunparse((p.scheme, p.netloc.lower(), path or "/", "", p.query, ""))


def select_pages(urls, args, required=True):
    """Apply --only / --pages sample / --limit. A --only pattern that matches no page stops the script (exit 2):
    an empty report would score 100 and turn every check it decides into a false PASS."""
    found = len(urls)
    if args.only:
        urls = [u for u in urls if re.search(args.only, u)]
        if required and found and not urls:
            print(f"No page URL matches --only {args.only!r} ({found} pages found). The pattern is a regular "
                  f"expression searched in the full URL, e.g. --only /blog/")
            sys.exit(2)
    if args.pages == "sample":
        urls = sample_pages(urls)
    if args.limit:
        urls = urls[: args.limit]
    return urls


def sample_pages(urls, per_section=2):
    """Every top-level page plus the first N detail pages of each section (/blog/x, /portfolio/x ...)."""
    picked, per = [], Counter()
    for u in urls:
        parts = [p for p in urlparse(u).path.split("/") if p]
        if len(parts) <= 1 and not urlparse(u).query:
            picked.append(u)
        else:
            section = parts[0] if parts else "?"
            if per[section] < per_section:
                picked.append(u)
                per[section] += 1
    return picked


# ---------------------------------------------------------------------------
# Crawler: discovers every crawlable internal URL, not only the sitemap
# ---------------------------------------------------------------------------
CRAWL_SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|webp|avif|svg|ico|bmp|tiff?|heic|mp4|webm|mov|m4v|avi|mp3|wav|ogg|"
                            r"zip|rar|gz|tgz|tar|7z|exe|dmg|apk|css|js|mjs|map|json|xml|txt|rss|atom|woff2?|ttf|otf|"
                            r"eot|csv|xlsx?|docx?|pptx?)$", re.I)
CRAWL_SKIP_PATH = re.compile(r"^/(_next|api|cdn-cgi|__nextjs[^/]*|_vercel|\.netlify)(/|$)", re.I)
TRACKING_PARAMS = re.compile(r"^(utm_[a-z_]+|fbclid|gclid|dclid|gbraid|wbraid|msclkid|mc_cid|mc_eid|_ga|_gl|igshid|"
                             r"ref_src|_rsc)$", re.I)
NON_WEB = ("#", "mailto:", "tel:", "javascript:", "data:", "sms:", "blob:", "about:", "whatsapp:", "skype:")


def clean_url(site, url):
    """Public form of an internal URL: no fragment, no tracking parameters, lowercase host."""
    p = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    return site.public((p.path or "/") + ("?" + urlencode(query) if query else ""))


def rel_values(tag):
    rel = tag.get("rel") or []
    return {r.lower() for r in (rel if isinstance(rel, list) else rel.split())}


def _jsonld_urls(node, out):
    if isinstance(node, list):
        for n in node:
            _jsonld_urls(n, out)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in ("url", "item", "@id", "mainEntityOfPage", "sameAs", "target") and isinstance(v, str):
                out.append(v)
            elif isinstance(v, (dict, list)):
                _jsonld_urls(v, out)


def discover_links(soup, page_url):
    """Every URL a crawler can find in a page -> list of (absolute_url, how_found)."""
    base_tag = soup.find("base", href=True)
    base = urljoin(page_url, base_tag["href"]) if base_tag else page_url
    found = []

    def add(raw, how):
        raw = (raw or "").strip()
        if raw and not raw.lower().startswith(NON_WEB):
            found.append((urljoin(base, raw).split("#")[0], how))

    for a in soup.find_all(["a", "area"], href=True):
        if "nofollow" not in rel_values(a):
            add(a["href"], "link")
    for link in soup.find_all("link", href=True):
        rel = rel_values(link)
        if "canonical" in rel:
            add(link["href"], "canonical")
        elif "alternate" in rel and link.get("hreflang"):
            add(link["href"], "hreflang")
        elif rel & {"next", "prev"}:
            add(link["href"], "pagination")
    for f in soup.find_all(["iframe", "frame"], src=True):
        add(f["src"], "iframe")
    for m in soup.find_all("meta", attrs={"http-equiv": re.compile("refresh", re.I)}):
        hit = re.search(r"url\s*=\s*['\"]?([^'\";]+)", m.get("content", ""), re.I)
        if hit:
            add(hit.group(1), "meta refresh")
    for s in soup.find_all("script", type="application/ld+json"):
        urls = []
        try:
            _jsonld_urls(json.loads(s.string or s.get_text() or ""), urls)
        except (ValueError, TypeError):
            pass
        for u in urls:
            # a URL template (SearchAction target ".../search?q={search_term_string}") is not a page
            if u.startswith(("http", "/")) and "{" not in u:
                add(u, "json-ld")
    return found


def crawlable(site, url):
    p = urlparse(url)
    return (p.scheme in ("http", "https") and site.is_internal(url)
            and not CRAWL_SKIP_PATH.match(p.path or "/") and not CRAWL_SKIP_EXT.search(p.path or ""))


def _robots(site):
    from urllib import robotparser
    rp = robotparser.RobotFileParser()
    res = fetch(f"{site.base}/robots.txt")
    body = res["content"].decode("utf-8", "replace") if res["status"] == 200 else ""
    rp.parse(body.splitlines())
    declared = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body)
    return rp, declared


def crawl_site(site, max_pages=5000, workers=8, respect_robots=True, js_discovery=False, browser_workers=2):
    """Breadth-first crawl of the audited server, then (js_discovery) the links that only appear after opening
    menus / tabs in Chrome, then a crawl of those.
    -> {"records": {url: record}, "edges": {page: [linked urls]}, "js_links": {page: {url: zone}}, "sitemap": [...],
        "stats": {...}}"""
    from concurrent.futures import ThreadPoolExecutor
    rp, declared = _robots(site)
    sitemap_keys = {clean_url(site, u) for u in site.sitemap_urls}
    records, edges, order = {}, {}, []
    queue, seen = [], set()

    def enqueue(url, source, how):
        key = clean_url(site, url)
        if key in seen:
            if source and key in records:
                records[key]["_sources"].add(source)
            return
        seen.add(key)
        queue.append((key, source, how))

    enqueue(site.public("/"), None, "homepage")
    for u in site.sitemap_urls:
        enqueue(u, None, "sitemap")
    for sm in declared:   # extra sitemaps listed in robots.txt
        if site.is_internal(sm) and norm(site.to_fetch(sm)) != norm(f"{site.base}/sitemap.xml"):
            extra = Site(site.base)
            extra.site_host, extra.site_scheme = site.site_host, site.site_scheme
            import xml.etree.ElementTree as ET
            sub = fetch(site.to_fetch(sm))
            try:
                for loc in ET.fromstring(sub["content"]).iter():
                    if loc.tag.endswith("loc") and loc.text:
                        enqueue(loc.text.strip(), None, "robots.txt sitemap")
            except ET.ParseError:
                pass

    def visit(item):
        key, source, how = item
        rec = {"url": key, "status": None, "content_type": "", "is_html": False, "ms": 0, "via": how,
               "found_on": source or "", "in_sitemap": key in sitemap_keys, "robots_blocked": False,
               "redirect_to": "", "title": "", "canonical": "", "noindex": False, "error": "", "depth": None,
               "_sources": {source} if source else set()}
        links = []
        if not crawlable(site, key):
            rec["error"] = "not crawled (asset / API path)"
            return rec, links
        if respect_robots and not rp.can_fetch("*", key):
            rec["robots_blocked"] = True
            rec["error"] = "blocked by robots.txt"
            return rec, links
        res = fetch(site.to_fetch(key), allow_redirects=False)
        rec.update(status=res["status"], ms=res["ms"], error=res["error"],
                   content_type=res["headers"].get("Content-Type", "").split(";")[0].strip())
        if res["status"] in REDIRECT_CODES and res["location"]:
            target = urljoin(site.to_fetch(key), res["location"])
            rec["redirect_to"] = clean_url(site, target) if site.is_internal(target) else target
            links.append((target, "redirect"))
        elif res["status"] == 200 and "html" in rec["content_type"]:
            rec["is_html"] = True
            soup = BeautifulSoup(res["content"], "lxml")
            rec["title"] = text_of(soup.title)[:200] if soup.title else ""
            canon = soup.find("link", rel=lambda v: v and has_rel(v, "canonical"))
            rec["canonical"] = urljoin(key, canon.get("href", "")) if canon and canon.get("href") else ""
            robots_meta = (meta(soup, name="robots") or "") + " " + res["headers"].get("X-Robots-Tag", "")
            rec["noindex"] = "noindex" in robots_meta.lower() or "none" in robots_meta.lower().split(",")
            links = discover_links(soup, key)
        return rec, links

    def drain(ex):
        nonlocal queue
        while queue and len(records) < max_pages:
            batch, queue = queue[: max_pages - len(records)], queue[max_pages - len(records):]
            for rec, links in ex.map(visit, batch):
                key = rec["url"]
                if key in records:   # already known (e.g. reached twice in one batch)
                    continue
                records[key] = rec
                order.append(key)
                targets = []
                for url, how in links:
                    if not crawlable(site, url):
                        continue
                    target = clean_url(site, url)
                    if how in ("link", "redirect") and target != key:
                        targets.append(target)
                    enqueue(url, key if how != "redirect" else (rec["found_on"] or None), how)
                    if how == "redirect":
                        records_target = records.get(target)
                        if records_target is not None and rec["found_on"]:
                            records_target["_sources"].add(rec["found_on"])
                if targets:
                    edges[key] = sorted(set(targets))
            print(f"  {len(records)} URLs crawled, {len(queue)} queued")

    started = time.time()
    print(f"Crawling {site.base} (max {max_pages} URLs, robots.txt {'respected' if respect_robots else 'ignored'}) ...")
    js_links = {}
    with ThreadPoolExecutor(max(1, workers)) as ex:
        drain(ex)
        if js_discovery:
            # Menus, tabs, accordions and "load more" buttons often render their links only after a click / hover,
            # so the HTML crawl above can't see them. Open them in Chrome, then crawl whatever new URLs appeared.
            seeds = [k for k in sample_pages([k for k in order if records[k]["is_html"] and records[k]["status"] == 200],
                                             per_section=1)]
            static_out = defaultdict(set)
            for src, targets in edges.items():
                static_out[src].update(targets)
            found = discover_js_links(site, seeds, browser_workers)
            for page_url, links in found.items():
                extra = {}
                for url, zone in links.items():
                    if not crawlable(site, url):
                        continue
                    target = clean_url(site, url)
                    if target == page_url or target in static_out[page_url]:
                        continue
                    extra[target] = zone
                    enqueue(url, page_url, "javascript")
                if extra:
                    js_links[page_url] = extra
            new = sum(1 for item in queue if item[2] == "javascript")
            print(f"JavaScript discovery: {sum(len(v) for v in js_links.values())} links that only appear after "
                  f"clicking menus / tabs on {len(seeds)} pages, {new} of them new URLs")
            drain(ex)
    truncated = bool(queue)

    # click depth from the homepage, incoming <a> links, final URL after redirects
    incoming = defaultdict(set)
    for src, targets in edges.items():
        for t in targets:
            incoming[t].add(src)
    home = clean_url(site, site.public("/"))
    depth, frontier = {home: 0}, [home]
    while frontier:
        nxt = []
        for cur in frontier:
            for t in edges.get(cur, ()):
                if t not in depth:
                    depth[t] = depth[cur] + 1
                    nxt.append(t)
        frontier = nxt
    js_targets = {t for links in js_links.values() for t in links}
    for key, rec in records.items():
        rec["depth"] = depth.get(key)
        rec["inlinks"] = len(incoming.get(key, set()) - {key})
        # linked only from menus / tabs that need a click: search engines don't click, so they may never find it
        rec["js_only"] = key in js_targets and not (incoming.get(key, set()) - {key})
        rec["sources"] = len(rec.pop("_sources") - {key})
        final, hops = key, 0
        while records.get(final, {}).get("redirect_to") and hops < 10:
            final, hops = records[final]["redirect_to"], hops + 1
        rec["final_url"] = final
        rec["redirect_hops"] = hops

    stats = {"crawled": len(records), "html_pages": sum(1 for r in records.values() if r["is_html"]),
             "sitemap_urls": len(site.sitemap_urls), "truncated": truncated, "max_pages": max_pages,
             "respect_robots": respect_robots, "js_discovery": bool(js_discovery),
             "js_links": sum(len(v) for v in js_links.values()), "seconds": int(time.time() - started)}
    print(f"Crawl done: {stats['crawled']} URLs, {stats['html_pages']} HTML pages "
          f"({len(site.sitemap_urls)} in sitemap) in {stats['seconds']} s")
    return {"base": site.base, "time": run_time(), "date": run_date(), "created": time.time(),
            "records": records, "order": order, "edges": edges, "js_links": js_links, "sitemap": site.sitemap_urls,
            "robots_sitemaps": declared, "stats": stats}


CRAWL_CACHE = Path(tempfile.gettempdir()) / "website-audit-crawl"   # shared crawl, outside report/


def crawl_cache_path():
    CRAWL_CACHE.mkdir(parents=True, exist_ok=True)
    return CRAWL_CACHE / f"crawl_{run_date()}_{run_time()}.json"


def _load_cached_crawl(site, args):
    max_age = float(os.environ.get("SEO_CRAWL_MAX_AGE", 1800))
    exact = CRAWL_CACHE / f"crawl_{run_date()}_{run_time()}.json"
    now = time.time()
    for old in list(CRAWL_CACHE.glob("crawl_*.json")):   # tidy up crawls older than a day
        try:
            if now - old.stat().st_mtime > 86400:
                old.unlink()
        except OSError:
            pass
    candidates = [exact] if exact.exists() else []
    if not os.environ.get("SEO_RUN_TIME"):   # run on its own: any recent crawl of this server
        valid = []
        for p in CRAWL_CACHE.glob("crawl_*.json"):
            try:
                valid.append((p.stat().st_mtime, p))
            except OSError:
                pass
        candidates += [p for _, p in sorted(valid, reverse=True)]
    for path in candidates:
        try:
            mtime = path.stat().st_mtime
            if path != exact and now - mtime > max_age:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        st = data.get("stats", {})
        if (st.get("html_pages") or 0) <= 0:
            continue
        if data.get("base") == site.base and st.get("max_pages") == args.max_pages \
                and st.get("respect_robots") == (not args.ignore_robots) \
                and (st.get("js_discovery", False) or not want_js_discovery(args)):
            try:
                ts_str = f"{datetime.fromtimestamp(mtime):%H:%M:%S}"
            except Exception:
                ts_str = "cached"
            print(f"Using the crawl from {ts_str} ({st.get('html_pages')} HTML pages)")
            return data
    return None


def want_js_discovery(args):
    """Open menus / tabs in Chrome during the crawl unless disabled or Playwright isn't installed."""
    if getattr(args, "no_js_discovery", False):
        return False
    import importlib.util
    return importlib.util.find_spec("playwright") is not None


def load_site(args, need_sitemap=True):
    """Read sitemap.xml, crawl the site (or reuse this run's crawl) -> (site, list of page URLs to audit)."""
    site = Site(args.base)
    site.load_sitemap()
    if getattr(args, "sitemap_only", False):
        urls = list(site.sitemap_urls)
    else:
        data = None if args.fresh_crawl else _load_cached_crawl(site, args)
        if data is None:
            data = crawl_site(site, args.max_pages, args.workers, respect_robots=not args.ignore_robots,
                              js_discovery=want_js_discovery(args), browser_workers=args.browser_workers)
            if (data.get("stats", {}).get("html_pages") or 0) > 0:
                try:
                    crawl_cache_path().write_text(json.dumps(data, default=list))
                except OSError:
                    pass
        site.crawl = data
        if not site.site_host:   # no sitemap: report URLs on the audited host
            site.site_host, site.site_scheme = site.base_host, urlparse(site.base).scheme
        recs = data["records"]
        # crawled-only pages that canonicalise to another URL (e.g. ?filter variants) are declared duplicates:
        # they are listed in the Sitemap report's "Crawled URLs" sheet but not audited as pages of their own
        pages = [k for k in data["order"] if recs[k]["is_html"] and recs[k]["status"] == 200
                 and (recs[k]["in_sitemap"] or not recs[k]["canonical"] or norm(recs[k]["canonical"]) == norm(k))]
        pages.sort(key=lambda k: not recs[k]["in_sitemap"])   # sitemap pages first, then crawl order
        urls = pages
    if need_sitemap and not urls:
        recs = list(((site.crawl or {}).get("records") or {}).values())
        if recs and all(r.get("robots_blocked") for r in recs):
            why = "robots.txt blocks every URL - add --ignore-robots to audit the site anyway"
        elif recs and any(r.get("status") for r in recs):
            seen = Counter(str(r.get("status") or r.get("error") or "?") for r in recs)
            why = f"no page answered HTTP 200 with HTML (answers: {', '.join(f'{k} x{n}' for k, n in seen.most_common(5))})"
        else:
            why = f"sitemap: {site.sitemap_error or 'ok'}. Is the site running?"
        print(f"No pages found at {site.base} ({why}).")
        sys.exit(2)
    if site.crawl:
        extra = sum(1 for u in urls if not site.crawl["records"][u]["in_sitemap"])
        print(f"{len(urls)} pages to audit ({len(urls) - extra} from the sitemap, {extra} found only by crawling)")
    return site, urls


def item_failed(item, error, label):
    """An unexpected error on one page / URL: print it and record it as "Not checked" in the running report (the QA
    checklist then shows SKIP, never a silent PASS) - one odd page must not stop a report of hundreds of pages."""
    msg = f"{type(error).__name__}: {error}"
    print(f"  ! {str(item)[:120]}: {msg[:200]}", flush=True)
    audit = Audit.current
    if audit is not None:
        url = item if isinstance(item, str) and item.startswith("http") else SITE_WIDE
        audit.add(url, INFO, "Script error", f"Not checked: {label} (the script failed on this item)",
                  current=msg[:300], element=str(item)[:200], expected="the check runs",
                  fix="Re-run the script; if the error repeats, report it with the URL so the script can be fixed.",
                  description="The script raised an error while checking this item, so its result is unknown "
                              "(not a pass).")


def run_parallel(func, items, workers, label="pages"):
    """func(item) for every item on `workers` threads -> results in item order (None where func failed)."""
    from concurrent.futures import ThreadPoolExecutor
    results, total = [], len(items)

    def safe(item):
        try:
            return func(item)
        except Exception as e:   # noqa: BLE001 - recorded as "Not checked" for that item
            item_failed(item, e, label)
            return None

    with ThreadPoolExecutor(max(1, workers)) as ex:
        for i, r in enumerate(ex.map(safe, items), 1):
            results.append(r)
            if i % 10 == 0 or i == total:
                pct = int((i / total) * 100) if total else 100
                print(f"  {i}/{total} {label} ({pct}%)", flush=True)
    return results


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def text_of(tag):
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def meta(soup, name=None, prop=None):
    if name:
        tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
    else:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return (tag.get("content") or "").strip() if tag else None


def metas(soup, name=None, prop=None):
    if name:
        return soup.find_all("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
    return soup.find_all("meta", attrs={"property": prop})


def has_rel(tag_rel, value):
    rel = tag_rel if isinstance(tag_rel, list) else (tag_rel or "").split()
    return value in [r.lower() for r in rel]


def describe(el, limit=120):
    """Short CSS-like description of an element: tag#id.class [attr] 'text'."""
    if el is None:
        return ""
    s = el.name or ""
    if el.get("id"):
        s += f"#{el['id']}"
    classes = el.get("class") or []
    if classes:
        s += "." + ".".join(classes[:3])
    for attr in ("href", "src", "name", "type", "role", "aria-label"):
        if el.get(attr):
            s += f" [{attr}={str(el[attr])[:60]}]"
            break
    txt = text_of(el)[:40]
    if txt:
        s += f" '{txt}'"
    return s[:limit]


def main_text(soup):
    """Visible text of <main> (falls back to <body>) without scripts/styles/svg."""
    import copy
    main = soup.find("main") or soup.body or soup
    main = copy.copy(main)
    for t in main.find_all(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    return text_of(main)


TEXT_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "button", "a", "td", "th", "label", "figcaption",
                   "blockquote", "dt", "dd", "span", "summary", "caption", "div"]
_BLOCK_PARENTS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dd", "dt", "blockquote", "figcaption",
                  "button", "a", "label", "summary", "caption", "div"]
_NO_TEXT = ("script", "style", "noscript", "template", "svg", "code", "pre", "kbd", "samp")


def rendered_text(el):
    """Text as the browser shows it: child elements are NOT separated by an extra space (text_of() adds one, which
    turns "Semicolon<span>.</span>" into "Semicolon ."), <br> becomes a space, whitespace is collapsed."""
    parts = []
    for node in el.descendants:
        if getattr(node, "name", None) == "br":
            parts.append(" ")
        elif isinstance(node, str) and not node.find_parent(_NO_TEXT) and type(node).__name__ == "NavigableString":
            parts.append(str(node))
    return " ".join("".join(parts).split())


def text_blocks(soup):
    """Visible text blocks of a page -> [(element, text, zone)], each piece of text once: leaf-ish blocks (headings,
    paragraphs, list items, cells, buttons, divs without block children ...), inline elements only when they are not
    inside such a block,
    nothing inside code / svg / scripts. zone = header | footer | content."""
    out = []
    body = soup.body or soup
    for el in body.find_all(TEXT_BLOCK_TAGS):
        if el.find_parent(_NO_TEXT) or el.find(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div"]):
            continue
        if el.name in ("a", "span", "button", "label", "div") and el.find_parent(_BLOCK_PARENTS):
            continue
        t = rendered_text(el)
        if not t:
            continue
        zone = "header" if el.find_parent(["header", "nav"]) else "footer" if el.find_parent("footer") else "content"
        out.append((el, t, zone))
    return out


STOPWORDS = set("a an and are as at be by for from how in into is it its of on or our the to we with your you "
                "services service development company solutions".split())


def topic_words(text, exclude=""):
    words = re.findall(r"[a-z0-9.+#]+", (text or "").lower())
    skip = set(re.findall(r"[a-z0-9]+", (exclude or "").lower()))
    return {w for w in words if len(w) > 2 and w not in STOPWORDS and w not in skip}


def slug_words(path):
    return {w for w in re.split(r"[-/_]", path.lower()) if len(w) > 2 and w not in STOPWORDS}


# ---------------------------------------------------------------------------
# Browser (Playwright) — uses the installed Google Chrome when available
# ---------------------------------------------------------------------------
class Browser:
    def __init__(self, headless=True):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            sys.exit("This script needs Playwright:  pip install playwright   "
                     "(it uses your installed Google Chrome; otherwise also run:  playwright install chromium)")
        self._pw = sync_playwright().start()
        try:
            self.browser = self._pw.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            try:
                self.browser = self._pw.chromium.launch(headless=headless)
            except Exception as e:
                self._pw.stop()
                sys.exit(f"Could not start Chrome/Chromium ({e}). Install Google Chrome or run:  playwright install chromium")

    def context(self, mobile=False, width=1440, height=900, **kw):
        if mobile:
            device = dict(viewport={"width": width or 390, "height": height or 844}, device_scale_factor=3,
                          is_mobile=True, has_touch=True,
                          user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                     "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        else:
            device = dict(viewport={"width": width, "height": height})
        device.update(kw)
        return self.browser.new_context(**device)

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def scroll_page(page, step=600, pause=120, max_steps=80):
    """Scroll to the bottom and back so lazy content / scroll animations load. At most max_steps stops (~10 s):
    a very tall page is scrolled in bigger steps instead of taking minutes."""
    page.evaluate(
        """async ([step, pause, maxSteps]) => {
            const sleep = (ms) => new Promise(r => setTimeout(r, ms));
            const s = Math.max(step, Math.ceil(document.documentElement.scrollHeight / maxSteps));
            for (let y = 0, n = 0; y < document.documentElement.scrollHeight && n < maxSteps; y += s, n++) {
                window.scrollTo(0, y); await sleep(pause);
            }
            window.scrollTo(0, 0); await sleep(pause);
        }""",
        [step, pause, max_steps],
    )


def run_browser_pages(func, items, workers, label="pages"):
    """func(browser, item) for every item on `workers` threads, each with its own Chrome (Playwright's sync API
    needs one instance per thread). -> results in item order (None where func raised)."""
    import queue as queue_mod
    items = list(items)
    results = [None] * len(items)
    work = queue_mod.Queue()
    for i, item in enumerate(items):
        work.put((i, item))
    done, lock, failures = [0], threading.Lock(), []

    def worker():
        try:
            browser = Browser()
        except SystemExit as e:   # Browser() exits when Chrome can't start
            failures.append(str(e))
            return
        try:
            while True:
                try:
                    i, item = work.get_nowait()
                except queue_mod.Empty:
                    return
                try:
                    if not browser.browser.is_connected():   # Chrome crashed: start a new one
                        browser.close()
                        browser = Browser()
                    results[i] = func(browser, item)
                except Exception as e:   # noqa: BLE001 - recorded as "Not checked" for that item
                    item_failed(item if not isinstance(item, tuple) else item[0], e, label)
                with lock:
                    done[0] += 1
                    n = done[0]
                if n % 10 == 0 or n == len(items):
                    pct = int((n / len(items)) * 100) if items else 100
                    print(f"  {n}/{len(items)} {label} ({pct}%)", flush=True)
        finally:
            try:
                browser.close()
            except Exception:
                pass

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(workers, len(items))))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if failures and len(failures) == len(threads):
        sys.exit(failures[0])
    return results


JS_LINK_RECORDER = """
(() => {
  const links = window.__auditLinks = new Map();
  const zone = a => a.closest('header, nav, [role=dialog], [role=menu], [role=navigation]') ? 'menu'
      : a.closest('footer') ? 'footer' : 'content';
  const put = a => { const z = zone(a), old = links.get(a.href);   // a link seen in a menu counts as a menu link
      if (!old || (z === 'menu' && old !== 'menu')) links.set(a.href, z); };
  const grab = n => { if (!n || n.nodeType !== 1) return;
      if (n.matches('a[href], area[href]')) put(n);
      n.querySelectorAll('a[href], area[href]').forEach(put); };
  window.__auditGrab = () => grab(document.documentElement);
  new MutationObserver(ms => ms.forEach(m => m.type === 'attributes' ? grab(m.target) : m.addedNodes.forEach(grab)))
      .observe(document, { childList: true, subtree: true, attributes: true, attributeFilter: ['href'] });
})();
"""

# Opens every menu / tab / accordion / "load more" it can find, depth first: open one menu, click through its tabs and
# sub-sections, then the next menu (opening a menu usually closes the previous one). header / nav / footer are only
# explored on the first page: they are the same on every page.
JS_LINK_EXPLORER = """
async ([skipChrome, maxClicks]) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const chrome = el => el.closest('header, nav, footer, [role=dialog], [role=navigation]');
  const MORE = /^(load|show|view|see|read) (more|all)|^more$|^expand/i;
  const EXPANDER = '[aria-expanded], [aria-haspopup], summary';
  const usable = el => visible(el) && !el.disabled && !el.closest('a, form') && el.type !== 'submit'
      && !(skipChrome && chrome(el));
  const done = new WeakSet();
  let clicks = 0;
  const click = async (el, wait) => {
    try { el.click(); } catch (e) { return false; }
    clicks++; await sleep(wait); window.__auditGrab(); return true;
  };
  window.__auditGrab();
  if (!skipChrome) {   // hover menus
    for (const el of document.querySelectorAll('header li, header [aria-haspopup], nav li, nav [aria-haspopup]')) {
      ['pointerover', 'mouseover'].forEach(t => el.dispatchEvent(new MouseEvent(t, { bubbles: true })));
      await sleep(60); window.__auditGrab();
    }
  }
  const tops = [...document.querySelectorAll(EXPANDER)].filter(usable);
  const topSet = new Set(tops);
  const candidates = () => [...document.querySelectorAll(
      '[aria-expanded="false"], [aria-haspopup]:not([aria-expanded="true"]), [role=tab]:not([aria-selected="true"]), ' +
      'details:not([open]) > summary, button, [role=button]')]
    .filter(el => !done.has(el) && !topSet.has(el) && usable(el)
            && (el.matches(EXPANDER + ', [role=tab]') || MORE.test((el.innerText || '').trim())));
  const explore = async depth => {
    if (depth > 4) return;
    for (const el of candidates()) {
      if (clicks >= maxClicks) return;
      if (done.has(el)) continue;
      done.add(el);
      if (!el.isConnected || !visible(el)) continue;
      if (await click(el, 180) && el.matches(EXPANDER)) await explore(depth + 1);
    }
  };
  await explore(1);   // tabs / accordions already on the page
  for (const t of tops) {
    if (clicks >= maxClicks) break;
    if (!t.isConnected || !visible(t)) continue;
    if (t.getAttribute('aria-expanded') !== 'true') await click(t, 300);
    await explore(1);
  }
  window.__auditGrab();
  return { clicks, links: [...window.__auditLinks.entries()] };
}
"""


def discover_js_links(site, pages, workers=2):
    """Links that exist only after clicking menus / tabs / accordions -> {page: {absolute url: zone}}.
    The first page is explored on a desktop and a phone viewport including header / nav / footer (desktop mega menus
    and the mobile menu); the other pages only outside them."""
    if not pages:
        return {}
    first = pages[0]

    def explore(browser, loc):
        out = {}
        views = [("desktop", False, 1440, 900)] + ([("phone", True, 390, 844)] if loc == first else [])
        for _, mobile, w, h in views:
            ctx = browser.context(mobile=mobile, width=w, height=h)
            ctx.add_init_script(JS_LINK_RECORDER)
            page = ctx.new_page()

            def stay(route, page=page):   # the page must not navigate away while buttons are clicked
                try:
                    req = route.request
                    leave = (req.is_navigation_request() and req.frame == page.main_frame
                             and page.url not in ("about:blank", "") and req.url.split("#")[0] != page.url.split("#")[0])
                except Exception:
                    leave = False
                route.abort() if leave else route.continue_()

            page.route("**/*", stay)
            try:
                page.goto(site.to_fetch(loc), wait_until="load", timeout=60000)
                page.wait_for_timeout(600)
                res = page.evaluate(JS_LINK_EXPLORER, [loc != first, 250])
                for href, zone in res["links"]:
                    full = href.split("#")[0]
                    if full.startswith("http") and site.is_internal(full):
                        out.setdefault(full, zone)
            except Exception as e:
                print(f"  ! JavaScript discovery failed on {loc}: {str(e)[:120]}")
            finally:
                ctx.close()
        return loc, out

    print(f"Opening menus / tabs in Chrome on {len(pages)} pages to find JavaScript-only links ...")
    return {loc: links for loc, links in filter(None, run_browser_pages(explore, pages, workers, "pages explored"))}


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------
ISSUE_COLUMNS = [  # (json key, Excel header, width)
    ("url", "URL", 50), ("severity", "Severity", 13), ("priority", "Priority", 19), ("category", "Category", 18),
    ("issue", "Issue", 42), ("description", "Description", 60), ("current_value", "Current value", 45),
    ("expected_value", "Expected / recommended value", 40), ("recommended_fix", "Recommended fix", 70),
    ("element", "Element / resource", 40), ("details", "Details", 50), ("http_status", "Page HTTP", 9),
    ("in_sitemap", "In sitemap", 10), ("report", "Report", 24),
]


def clip(value, limit=2000):
    s = "" if value is None else str(value)
    return s if len(s) <= limit else s[: limit - 3] + "..."


class Audit:
    """Collects issues + extra sheets, scores them and saves the Excel + JSON report and the summary JSON."""
    current = None   # the report this script is building (run_parallel records per-item errors in it)

    def __init__(self, key, title, category, site=""):
        Audit.current = self
        self.key, self.title, self.category = key, title, category
        self.web = site if isinstance(site, Site) else None   # the Site (crawl info for the URL columns)
        self.base = site.base if isinstance(site, Site) else site
        self.issues = []            # list of issue dicts (see ISSUE_COLUMNS)
        self.pages = set()          # URLs that were checked (for per-page scoring)
        self.sheets = []            # (name, headers, rows, widths, severity_col)
        self.notes = []             # (label, value) shown on the Summary sheet
        self.started = time.time()
        self._lock = threading.Lock()
        self._per_check = Counter()
        self.score_override = None

    def add(self, url, severity, category, check, detail="", *, current=None, expected=None, fix=None,
            element=None, description=None):
        """Record one issue. `detail` is the old free-text field: used as Current value when `current` isn't given,
        otherwise kept in Details. Description / expected / fix default to issue_guide.py."""
        url = url or SITE_WIDE
        with self._lock:
            self._per_check[(url, check)] += 1
            if self._per_check[(url, check)] > MAX_PER_CHECK:
                return
            d_desc, d_exp, d_fix = guide(check, category)
            if current is None:
                current, details = detail, ""
            else:
                details = detail
            self.issues.append({
                "url": url, "severity": severity, "priority": PRIORITY.get(severity, ""), "category": category,
                "issue": check, "description": description or d_desc, "current_value": clip(current, 500),
                "expected_value": clip(expected if expected is not None else d_exp, 300),
                "recommended_fix": fix or d_fix, "element": clip(element, 300), "details": clip(details, 500),
            })

    def site_issue(self, severity, category, check, detail="", **kw):
        self.add(SITE_WIDE, severity, category, check, detail, **kw)

    def not_checked(self, category, what, reason, how=""):
        """Record that a check could not run (tool missing, option off ...). The QA checklist shows SKIP for it
        instead of a misleading PASS. Info severity: no score impact."""
        self.add(SITE_WIDE, INFO, category, f"Not checked: {what}", current=reason,
                 expected="the check runs", fix=how or "See the reason in Current value.",
                 description="This check did not run, so its result is unknown (not a pass).")

    def checked(self, url):
        with self._lock:
            self.pages.add(url)

    def note(self, label, value):
        self.notes.append((label, value))

    def sheet(self, name, headers, rows, widths=None, severity_col=None, fills=None):
        """Extra Excel sheet (also saved in the JSON 'data'). fills: {1-based column: "RRGGBB" for every row, or
        {cell value: "RRGGBB"}} - e.g. a PASS / WARN / FAIL status column, see STATUS_COLORS."""
        self.sheets.append((name, headers, rows, widths, severity_col, fills))

    # scoring ---------------------------------------------------------------
    def _page_deductions(self):
        per_page = defaultdict(int)
        site_checks, page_checks = set(), set()
        for i in self.issues:
            url, sev, check = i["url"], i["severity"], i["issue"]
            if url == SITE_WIDE or (self.pages and url not in self.pages):
                site_checks.add((sev, check))   # site/file-level: counted once per distinct check
            else:
                page_checks.add((url, sev, check))   # a repeated problem on one page counts once
        for url, sev, _ in page_checks:
            per_page[url] += PAGE_WEIGHT.get(sev, 0)
        return per_page, site_checks

    def page_score(self, url):
        per_page, _ = self._page_deductions()
        return max(0, 100 - per_page.get(url, 0))

    def score(self):
        if self.score_override is not None:
            return self.score_override
        per_page, site_checks = self._page_deductions()
        site_deduction = sum(SITE_WEIGHT.get(sev, 0) for sev, _ in site_checks)
        pages = self.pages or set(per_page)
        page_avg = sum(max(0, 100 - per_page.get(p, 0)) for p in pages) / len(pages) if pages else 100
        return max(0, min(100, round(page_avg - min(site_deduction, 60), 1)))

    # output ----------------------------------------------------------------
    def _finalise_issues(self):
        """Add the 'more occurrences' rows, crawl info and stable ids; sort URL by URL."""
        for (url, check), n in self._per_check.items():
            if n > MAX_PER_CHECK:
                first = next(i for i in self.issues if i["url"] == url and i["issue"] == check)
                extra = dict(first, current_value=f"{n - MAX_PER_CHECK} more occurrences not listed",
                             element="", details=f"{n} occurrences in total")
                self.issues.append(extra)
        self._per_check.clear()
        for i in self.issues:
            rec = self.web.record(i["url"]) if self.web and i["url"].startswith("http") else {}
            i["http_status"] = rec.get("status", "") if rec else ""
            i["in_sitemap"] = ("yes" if rec.get("in_sitemap") else "no") if rec else ""
            i["report"] = self.title
            raw = "|".join(str(i[k]) for k in ("url", "issue", "current_value", "element"))
            i["id"] = f"{self.key}-{hashlib.md5((self.key + raw).encode(), usedforsecurity=False).hexdigest()[:10]}"
        url_rank = lambda u: (u == SITE_WIDE, not u.startswith("http"), u)
        self.issues.sort(key=lambda i: (url_rank(i["url"]), SEVERITY_ORDER.get(i["severity"], 9), i["category"],
                                        i["issue"]))

    def _issue_types(self):
        grouped = {}
        for i in self.issues:
            g = grouped.setdefault((i["severity"], i["category"], i["issue"]),
                                   {"issue": i["issue"], "severity": i["severity"], "priority": i["priority"],
                                    "category": i["category"], "urls": set(), "occurrences": 0,
                                    "description": i["description"], "expected_value": i["expected_value"],
                                    "recommended_fix": i["recommended_fix"]})
            g["urls"].add(i["url"])
            g["occurrences"] += 1
        out = sorted(grouped.values(), key=lambda g: (SEVERITY_ORDER.get(g["severity"], 9), -len(g["urls"]),
                                                      -g["occurrences"]))
        for g in out:
            g["pages"] = len(g.pop("urls"))
        return out

    def _url_rows(self):
        """One entry per URL: every checked page (also those without issues) and every URL with issues."""
        by_url = defaultdict(list)
        for i in self.issues:
            by_url[i["url"]].append(i)
        per_page, _ = self._page_deductions()
        urls = sorted(set(by_url) | self.pages, key=lambda u: (u == SITE_WIDE, not u.startswith("http"), u))
        out = []
        for u in urls:
            items = by_url.get(u, [])
            counts = Counter(i["severity"] for i in items)
            rec = self.web.record(u) if self.web and u.startswith("http") else {}
            out.append({
                "url": u, "http_status": rec.get("status", "") if rec else "",
                "in_sitemap": rec.get("in_sitemap") if rec else None,
                "crawl_depth": rec.get("depth") if rec else None,
                "score": max(0, 100 - per_page.get(u, 0)) if u in self.pages else None,
                "counts": {s: counts[s] for s in (CRITICAL, IMPORTANT, OPTIMIZATION, INFO)},
                "total_issues": len(items),
                "issues": [{k: v for k, v in i.items() if k != "url"} for i in items],
            })
        return out

    def save(self, report_name=None):
        self._finalise_issues()
        score = self.score()
        counts = Counter(i["severity"] for i in self.issues)
        name = report_name or self.title.replace(" ", "_")
        remove_old_reports(name)   # a report replaces its previous Excel / JSON / CSV files
        path, json_path, csv_path = report_path(name), report_path(name, "json"), report_path(name, "csv")
        issue_types = self._issue_types()
        url_rows = self._url_rows()
        crawl_stats = (self.web.crawl or {}).get("stats", {}) if self.web else {}
        meta_rows = [("Score (0-100)", score), ("Grade", grade(score)), ("Audited server", self.base),
                     ("Pages checked", len(self.pages)),
                     ("URLs with issues", sum(1 for r in url_rows if r["total_issues"] and r["url"] != SITE_WIDE)),
                     ("Critical issues", counts[CRITICAL]), ("Important issues", counts[IMPORTANT]),
                     ("Optimization issues", counts[OPTIMIZATION]), ("Info", counts[INFO]),
                     ("Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                     ("Duration", f"{int(time.time() - self.started)} s")]
        if crawl_stats:
            meta_rows.append(("URLs discovered by crawl", f"{crawl_stats.get('crawled')} URLs, "
                              f"{crawl_stats.get('html_pages')} HTML pages, {crawl_stats.get('sitemap_urls')} in sitemap"))
        elif self.web:
            meta_rows.append(("Page source", "sitemap.xml only (--sitemap-only)"))
        meta_rows += self.notes

        # ---------------- Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        ws.append([self.title])
        ws["A1"].font = Font(bold=True, size=16)
        for r in meta_rows:
            ws.append([clean_cell(v) for v in r])
        ws["B2"].fill = ws["B3"].fill = grade_fill(score)
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=1):
            label = row[0].value or ""
            for sev in (CRITICAL, IMPORTANT, OPTIMIZATION):
                if label.startswith(sev):
                    row[0].fill = FILLS[sev]
        ws.append([])
        ws.append(["Issue", "Severity", "Category", "Pages", "Occurrences", "Description", "Expected / recommended value",
                   "Recommended fix"])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = FILLS["header"]
        for g in issue_types:
            ws.append([clean_cell(v) for v in (g["issue"], g["severity"], g["category"], g["pages"], g["occurrences"],
                                               g["description"], g["expected_value"], g["recommended_fix"])])
            ws.cell(row=ws.max_row, column=2).fill = FILLS.get(g["severity"], FILLS[INFO])
        for col, w in zip("ABCDEFGH", (50, 30, 20, 8, 12, 60, 40, 70)):
            ws.column_dimensions[col].width = w

        write_sheet(wb.create_sheet("Issues by URL"), [h for _, h, _ in ISSUE_COLUMNS],
                    [[i.get(k, "") for k, _, _ in ISSUE_COLUMNS] for i in self.issues],
                    [w for _, _, w in ISSUE_COLUMNS], severity_col=2)
        url_sheet_rows = []
        for r in url_rows:
            names = Counter(i["issue"] for i in r["issues"])
            url_sheet_rows.append((r["url"], r["http_status"], "" if r["in_sitemap"] is None else
                                   ("yes" if r["in_sitemap"] else "no"),
                                   "" if r["crawl_depth"] is None else r["crawl_depth"],
                                   "" if r["score"] is None else r["score"], r["counts"][CRITICAL], r["counts"][IMPORTANT],
                                   r["counts"][OPTIMIZATION], r["total_issues"],
                                   "; ".join(f"{n}" + (f" (x{c})" if c > 1 else "") for n, c in names.items())
                                   or "No issues"))
        uws = wb.create_sheet("URL Summary")
        write_sheet(uws, ["URL", "HTTP", "In sitemap", "Crawl depth", "Score", "Critical", "Important", "Optimization",
                          "Total issues", "Issues"], url_sheet_rows, (55, 7, 10, 11, 7, 9, 10, 13, 12, 120))
        for row in range(2, uws.max_row + 1):
            uws.cell(row=row, column=5).fill = grade_fill(uws.cell(row=row, column=5).value)
            for col, sev in ((6, CRITICAL), (7, IMPORTANT), (8, OPTIMIZATION)):
                if uws.cell(row=row, column=col).value:
                    uws.cell(row=row, column=col).fill = FILLS[sev]
        for name_, headers, rows, widths, severity_col, fills in self.sheets:
            write_sheet(wb.create_sheet(name_[:31]), headers, rows, widths, severity_col, fills)
        wb.save(path)

        # ---------------- JSON
        report = {
            "report": {"key": self.key, "title": self.title, "category": self.category, "audited_server": self.base,
                       "generated": datetime.now().isoformat(timespec="seconds"),
                       "duration_seconds": int(time.time() - self.started), "score": score, "grade": grade(score),
                       "pages_checked": len(self.pages),
                       "counts": {s: counts[s] for s in (CRITICAL, IMPORTANT, OPTIMIZATION, INFO)},
                       "total_issues": len(self.issues), "crawl": crawl_stats, "run_date": run_date(),
                       "run_time": run_time(), "excel": rel_path(path), "csv": rel_path(csv_path)},
            "notes": {str(k): v for k, v in self.notes},
            "issue_types": issue_types,
            "urls": [r for r in url_rows if r["url"] != SITE_WIDE],
            "site_wide_issues": next((r["issues"] for r in url_rows if r["url"] == SITE_WIDE), []),
            "data": {n: [dict(zip(h, (_jsonable(v) for v in row))) for row in rows] for n, h, rows, *_ in self.sheets},
        }
        json_path.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
        write_csv(csv_path, [h for _, h, _ in ISSUE_COLUMNS], ([i.get(k, "") for k, _, _ in ISSUE_COLUMNS]
                                                              for i in self.issues))

        # the HTML page some reports write next to these files (looked up, not created: no empty html/ folder)
        html_page = REPORT_ROOT / run_date() / FORMAT_DIRS["html"] / f"{name}_{run_time()}.html"
        failed = sum(1 for i in self.issues if i["category"] == "Script error")
        print("\n" + "=" * 70)
        print(f"✓ {self.title} - Report generated successfully!")
        print("=" * 70)
        print(f"  • Excel Report:  {rel_path(path)}")
        print(f"  • JSON Report:   {rel_path(json_path)}")
        print(f"  • CSV Report:    {rel_path(csv_path)}")
        if html_page.exists():
            print(f"  • HTML Report:   {rel_path(html_page)}")
        print("-" * 70)
        print(f"  Score: {score}/100 ({grade(score)}) | {counts[CRITICAL]} critical, {counts[IMPORTANT]} important, {counts[OPTIMIZATION]} optimization, {counts[INFO]} info")
        print(f"  Pages Checked: {len(self.pages)} | Total Issues: {len(self.issues)}")
        if failed:
            print(f"  ⚠ {failed} item(s) could not be checked because of a script error - listed as "
                  f"'Not checked' (category Script error) in the report")
        print("=" * 70 + "\n")
        return path


# keep the old name: audit.site(severity, category, check, detail) records a site-wide issue
Audit.site = Audit.site_issue


def _jsonable(v):
    if isinstance(v, set):
        return sorted(v)
    if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
        return v
    return str(v)


def clean_cell(v):
    if isinstance(v, (list, dict, set, tuple)):
        v = json.dumps(sorted(v) if isinstance(v, set) else v, default=str)[:2000]
    if isinstance(v, str):
        v = ILLEGAL_CHARACTERS_RE.sub("", v)
        if len(v) > 32000:
            v = v[:32000] + "..."
    return v


def write_csv(path, headers, rows):
    """UTF-8 CSV with a BOM so Excel opens accents / symbols correctly."""
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])


# light backgrounds with dark text (readable): status values and "wrong" / "expected" columns
STATUS_COLORS = {"PASS": "C6EFCE", "FAIL": "FFC7CE", "WARN": "FFEB9C", "SKIP": "E7E6E6", "HUMAN": "E4DFEC"}
WRONG_COLOR, EXPECTED_COLOR = "FFC7CE", "C6EFCE"
_FILL_CACHE = {}


def _fill(color):
    if color not in _FILL_CACHE:
        _FILL_CACHE[color] = PatternFill(fill_type="solid", start_color=color)
    return _FILL_CACHE[color]


def write_sheet(ws, headers, rows, widths=None, severity_col=None, fills=None):
    ws.append(list(headers))
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = FILLS["header"]
    row_no = ws.max_row   # counted here: ws.max_row scans every cell, so calling it per row is quadratic
    for r in rows:
        ws.append([clean_cell(v) for v in r])
        row_no += 1
        if severity_col:
            cell = ws.cell(row=row_no, column=severity_col)
            cell.fill = FILLS.get(cell.value, FILLS["ok"])
        for col, rule in (fills or {}).items():
            cell = ws.cell(row=row_no, column=col)
            color = rule if isinstance(rule, str) else rule.get(cell.value)
            if color and cell.value not in (None, ""):
                cell.fill = _fill(color)
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions
    top = Alignment(vertical="top")   # one shared style object (a new one per cell is slow on big sheets)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = top


# ---------------------------------------------------------------------------
# Browser performance metrics (used by 12_performance_checker + 12a_core_web_vitals_checker)
# ---------------------------------------------------------------------------
PERF_INIT_SCRIPT = """
(() => {
  const m = window.__perf = { lcp: 0, lcpEl: '', cls: 0, longTasks: [], events: [] };
  const po = (type, fn, extra) => { try { new PerformanceObserver(l => l.getEntries().forEach(fn))
      .observe(Object.assign({ type, buffered: true }, extra || {})); } catch (e) {} };
  po('largest-contentful-paint', e => { m.lcp = e.startTime;
      m.lcpEl = e.element ? (e.element.tagName.toLowerCase() + (e.element.id ? '#' + e.element.id : '') +
        (e.url ? ' ' + e.url.split('/').pop().slice(0, 60) : ' "' + (e.element.innerText || '').slice(0, 40) + '"')) : ''; });
  po('layout-shift', e => { if (!e.hadRecentInput) m.cls += e.value; });
  po('longtask', e => m.longTasks.push([e.startTime, e.duration]));
  po('event', e => m.events.push([e.name, e.duration, e.interactionId || 0]), { durationThreshold: 16 });
})();
"""

COLLECT_METRICS_JS = """
() => {
  const m = window.__perf || {};
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
  const fcp = fcpEntry ? fcpEntry.startTime : 0;
  const tbt = (m.longTasks || []).filter(([s]) => s >= fcp).reduce((t, [, d]) => t + Math.max(0, d - 50), 0);
  const inter = {};
  (m.events || []).forEach(([n, d, id]) => { if (id) inter[id] = Math.max(inter[id] || 0, d); });
  const durations = Object.values(inter).sort((a, b) => b - a);
  const resources = performance.getEntriesByType('resource').map(r => ({
      url: r.name, type: r.initiatorType, size: r.transferSize, body: r.encodedBodySize, decoded: r.decodedBodySize,
      duration: Math.round(r.duration), protocol: r.nextHopProtocol, blocking: r.renderBlockingStatus || '' }));
  let depth = 0;
  const walk = (el, d) => { depth = Math.max(depth, d); for (const c of el.children) walk(c, d + 1); };
  walk(document.documentElement, 1);
  return {
    dns: nav.domainLookupEnd - nav.domainLookupStart, connect: nav.connectEnd - nav.connectStart,
    ttfb: nav.responseStart, download: nav.responseEnd - nav.responseStart,
    domContentLoaded: nav.domContentLoadedEventEnd, load: nav.loadEventEnd,
    protocol: nav.nextHopProtocol, htmlTransfer: nav.transferSize, htmlSize: nav.decodedBodySize,
    fcp, lcp: m.lcp || fcp, lcpEl: m.lcpEl, cls: m.cls || 0, tbt, longTasks: (m.longTasks || []).length,
    inp: durations.length ? durations[Math.min(durations.length - 1, Math.floor(durations.length / 50))] : null,
    domNodes: document.getElementsByTagName('*').length, domDepth: depth, resources,
    preload: document.querySelectorAll('link[rel=preload]').length,
    preconnect: [...document.querySelectorAll('link[rel=preconnect]')].map(l => l.href),
    dnsPrefetch: [...document.querySelectorAll('link[rel=dns-prefetch]')].map(l => l.href),
  };
}
"""

INTERACTION_TARGET_JS = """
(i) => {
  // the i-th element that is safe to click: the click point must not land on a link, a form or a submit button
  // (a paragraph that starts with a tel: / page link would otherwise leave the page that is being measured)
  const all = [...document.querySelectorAll('h1, h2, p, button:not([type=submit]), [role=tab], summary')]
      .filter(e => e.offsetParent !== null && !e.closest('a, form'));
  let n = 0;
  for (const t of all) {
    t.scrollIntoView({ block: 'center' });
    const r = t.getBoundingClientRect();
    const x = r.x + Math.min(8, r.width / 2), y = r.y + Math.min(8, r.height / 2);
    const hit = document.elementFromPoint(x, y);
    if (!hit || hit.closest('a[href], form, [type=submit], [role=link]')) continue;
    if (n++ === i) return { x, y };
  }
  return null;
}
"""


def simulate_interactions(page, count=5):
    """Real (trusted) clicks + a key press so Chrome records Event Timing entries for INP."""
    for i in range(count):
        try:
            pos = page.evaluate(INTERACTION_TARGET_JS, i)
            if not pos:
                break
            page.mouse.click(pos["x"], pos["y"])
            page.wait_for_timeout(250)
        except Exception:
            break
    try:
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass


def rate(value, good, poor):
    if value is None:
        return "n/a"
    return "Good" if value <= good else ("Poor" if value > poor else "Needs improvement")
