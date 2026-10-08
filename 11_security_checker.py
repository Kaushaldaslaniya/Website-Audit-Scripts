"""
11 - Security checker
  HTTPS, SSL certificate (validity, issuer, expiry), HTTP -> HTTPS, HSTS, security headers
  (Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
  X-Frame-Options / frame-ancestors), exposed server information (Server, X-Powered-By),
  mixed content / insecure resources, insecure form actions, external scripts (+ Subresource Integrity),
  third-party script hosts, cookie flags, exposed sensitive files (.env, .git), exposed source maps,
  target=_blank without rel=noopener.

  python "py files/11_security_checker.py" [--base URL]
"""
import re
import socket
import ssl
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, Audit, fetch, load_site, parse_args, run_parallel,
                        select_pages)

SECURITY_HEADERS = [  # (header, severity, recommended value)
    ("Content-Security-Policy", IMPORTANT, "default-src 'self'; script-src 'self' 'nonce-...'; frame-ancestors 'none'"),
    ("Strict-Transport-Security", IMPORTANT, "max-age=31536000; includeSubDomains"),
    ("X-Content-Type-Options", IMPORTANT, "nosniff"),
    ("Referrer-Policy", OPTIMIZATION, "strict-origin-when-cross-origin"),
    ("Permissions-Policy", OPTIMIZATION, "camera=(), microphone=(), geolocation=()"),
]
SENSITIVE = ["/.env", "/.env.local", "/.git/HEAD", "/.git/config", "/package.json", "/.DS_Store", "/next.config.js",
             "/.next/BUILD_ID", "/server.js", "/phpinfo.php", "/wp-admin/", "/backup.zip"]

args = parse_args("Security checker")
site, urls = load_site(args)
pages = select_pages(urls, args)
audit = Audit("11_security", "Security Report", "Security", site)
header_rows, script_rows, cert_rows = [], [], []
script_hosts = defaultdict(set)

# ------------------------------------------------------------ HTTPS & certificate
if site.site_scheme != "https":
    audit.site(CRITICAL, "HTTPS", "Site URLs are not HTTPS", f"{site.site_scheme}://{site.site_host}")
if site.is_public and site.site_scheme == "https":
    host = site.site_host.split(":")[0]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock, ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
            expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (expires - datetime.now(timezone.utc)).days
            issuer = dict(x[0] for x in cert["issuer"]).get("organizationName", "")
            cert_rows.append((host, issuer, cert["notBefore"], cert["notAfter"], days, tls.version()))
            if days < 0:
                audit.site(CRITICAL, "SSL", "SSL certificate expired", cert["notAfter"])
            elif days < 14:
                audit.site(CRITICAL, "SSL", "SSL certificate expires within 14 days", f"{days} days")
            elif days < 30:
                audit.site(IMPORTANT, "SSL", "SSL certificate expires within 30 days", f"{days} days")
            if tls.version() in ("TLSv1", "TLSv1.1"):
                audit.site(IMPORTANT, "SSL", "Old TLS version negotiated", tls.version())
    except ssl.SSLCertVerificationError as e:
        audit.site(CRITICAL, "SSL", "Invalid SSL certificate", str(e)[:150])
    except OSError as e:
        audit.site(IMPORTANT, "SSL", "Could not check SSL certificate", str(e)[:150])
    plain = fetch(f"http://{host}/", allow_redirects=False)
    if not plain["location"].startswith("https://"):
        audit.site(CRITICAL, "HTTPS", "HTTP does not redirect to HTTPS", f"HTTP {plain['status']} -> {plain['location']}")
else:
    audit.note("SSL / HSTS", "skipped - audited host is not a public https site")

# ------------------------------------------------------------ sensitive files & source maps
for path in SENSITIVE:
    r = fetch(f"{site.base}{path}", allow_redirects=False)
    if r["status"] == 200 and len(r["content"]) > 0 and b"<html" not in r["content"][:500].lower():
        audit.site(CRITICAL, "Exposure", "Sensitive file is publicly readable", current=f"HTTP 200, {len(r['content'])} bytes",
                   element=path)

# ------------------------------------------------------------ per page
def check(loc):
    audit.checked(loc)
    res = fetch(site.to_fetch(loc))
    if res["status"] != 200:
        audit.add(loc, CRITICAL, "Status", "Page not reachable", f"HTTP {res['status']}")
        return
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res["content"], "lxml")
    h = {k.lower(): v for k, v in res["headers"].items()}
    https_page = loc.startswith("https://")

    for name, sev, recommended in SECURITY_HEADERS:
        if name == "Strict-Transport-Security" and not (site.is_public and https_page):
            continue
        if name.lower() not in h:
            audit.add(loc, sev, "Headers", f"Missing {name}", current="(header not sent)", expected=f"{name}: {recommended}")
    if h.get("x-content-type-options", "nosniff").lower() != "nosniff":
        audit.add(loc, IMPORTANT, "Headers", "X-Content-Type-Options is not nosniff", current=h["x-content-type-options"],
                  expected="nosniff")
    csp = h.get("content-security-policy", "")
    if "x-frame-options" not in h and "frame-ancestors" not in csp:
        audit.add(loc, IMPORTANT, "Headers", "No clickjacking protection (X-Frame-Options or CSP frame-ancestors)",
                  current="neither header sent", expected="X-Frame-Options: DENY or CSP frame-ancestors 'none'")
    script_src = re.search(r"script-src([^;]*)", csp)
    if script_src and ("'unsafe-inline'" in script_src.group(1) or " * " in f" {script_src.group(1)} "):
        audit.add(loc, OPTIMIZATION, "Headers", "Weak CSP for scripts ('unsafe-inline' or *)",
                  current=f"script-src{script_src.group(1)}"[:200], expected="script-src 'self' 'nonce-...'")
    hsts = h.get("strict-transport-security", "")
    if hsts:
        m = re.search(r"max-age=(\d+)", hsts)
        if not m or int(m.group(1)) < 15552000:
            audit.add(loc, OPTIMIZATION, "Headers", "HSTS max-age below 180 days", current=hsts,
                      expected="max-age=31536000; includeSubDomains")
    for name in ("server", "x-powered-by", "x-aspnet-version"):
        if name in h and (name != "server" or re.search(r"\d", h[name])):
            audit.add(loc, OPTIMIZATION, "Exposure", f"{name} header reveals server software", current=f"{name}: {h[name]}",
                      expected="header removed")
    raw_cookie = res["headers"].get("Set-Cookie", "")
    for cookie in re.split(r",\s*(?=[^;,=\s]+=)", raw_cookie) if raw_cookie else []:
        flags = cookie.lower()
        name = cookie.split("=", 1)[0].strip()
        if https_page and "secure" not in flags:
            audit.add(loc, IMPORTANT, "Cookies", "Cookie without Secure flag", current=cookie[:150], element=name)
        if "samesite" not in flags:
            audit.add(loc, OPTIMIZATION, "Cookies", "Cookie without SameSite", current=cookie[:150], element=name)
    header_rows.append((loc, *[h.get(n.lower(), "") for n, _, _ in SECURITY_HEADERS], h.get("x-frame-options", ""),
                        h.get("server", ""), h.get("x-powered-by", "")))

    # mixed content / insecure resources
    for tag, attr in (("script", "src"), ("link", "href"), ("img", "src"), ("iframe", "src"), ("source", "src"),
                      ("video", "src"), ("audio", "src"), ("form", "action")):
        for el in soup.find_all(tag):
            val = (el.get(attr) or "").strip()
            if val.startswith("http://") and not re.match(r"http://(localhost|127\.)", val):
                sev = CRITICAL if tag in ("script", "iframe", "form") else IMPORTANT
                audit.add(loc, sev, "Mixed content", f"Insecure (http://) <{tag}>", current=val[:200],
                          expected="https://" + val[7:200])
    # external scripts
    for s in soup.find_all("script", src=True):
        src = urljoin(loc, s["src"])
        host = urlparse(src).netloc
        if site.is_internal(src):
            continue
        script_hosts[host].add(loc)
        if not s.get("integrity"):
            audit.add(loc, OPTIMIZATION, "External scripts", "Third-party script without Subresource Integrity",
                      current="no integrity attribute", element=src[:200])
        script_rows.append((loc, host, src[:200], "yes" if s.get("integrity") else "no", s.get("crossorigin", ""),
                            "async" if s.has_attr("async") else "defer" if s.has_attr("defer") else "blocking"))
    for a in soup.find_all("a", target="_blank", href=True):
        raw_rel = a.get("rel")
        rel = " ".join(raw_rel) if isinstance(raw_rel, list) else str(raw_rel or "")
        if "noopener" not in rel and "noreferrer" not in rel and not site.is_internal(urljoin(loc, a["href"])):
            audit.add(loc, OPTIMIZATION, "Links", "target=_blank without rel=noopener", current=f'rel="{rel}"',
                      element=a["href"][:200])
    # exposed source maps (first-party JS)
    for s in soup.find_all("script", src=True)[:6]:
        src = urljoin(site.to_fetch(loc), s["src"])
        if site.is_internal(src) and src.endswith(".js"):
            m = fetch(site.to_fetch(src) + ".map", "HEAD")
            if m["status"] == 200:
                audit.add(loc, IMPORTANT, "Exposure", "JavaScript source map is public", current="HTTP 200",
                          element=src.rsplit("/", 1)[-1] + ".map")
                break


print(f"Checking {len(pages)} pages ...")
run_parallel(check, pages, args.workers)
audit.note("Third-party script hosts", ", ".join(sorted(script_hosts)) or "none")
audit.sheet("Security headers", ["URL", *[n for n, _, _ in SECURITY_HEADERS], "X-Frame-Options", "Server", "X-Powered-By"],
            header_rows, (50, 40, 30, 14, 25, 30, 14, 18, 14))
audit.sheet("External scripts", ["Page", "Host", "Script", "SRI", "crossorigin", "Loading"], script_rows, (50, 30, 70, 6, 12, 10))
audit.sheet("SSL certificate", ["Host", "Issuer", "Valid from", "Expires", "Days left", "TLS"], cert_rows, (30, 30, 26, 26, 10, 10))
audit.save("Security_Report")
