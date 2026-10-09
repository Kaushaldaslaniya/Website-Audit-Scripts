"""
28 - Repository audit (the project's source code and git repo - no server needed)
  docs:      README.md exists, is customised (not the create-next-app text) and says how to run / build
  git:       .gitignore covers node_modules, .next, .env*, __pycache__; no .env / private keys / build output /
             __pycache__ / .DS_Store committed; no huge files committed; only one lockfile
  secrets:   committed files scanned for private keys, AWS / GitHub / Stripe / Slack tokens, hard-coded passwords
  packages:  package.json has build / start / lint scripts, no "latest" / "*" versions;
             npm audit: known vulnerabilities in dependencies (high / critical = Important)
  code:      ESLint errors / warnings, TypeScript errors (tsc --noEmit), Bandit security scan of the Python audit
             scripts (pip install bandit), TODO / FIXME count
  build:     --build runs `npm run build` (production build must succeed). Off by default: it rewrites .next,
             which breaks a `next start` server that is running from it - stop the server first.

  python "py files/28_repo_audit.py" [--build] [--no-lint] [--no-typecheck] [--no-npm-audit]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from seo_common import (CRITICAL, IMPORTANT, INFO, OPTIMIZATION, PROJECT_ROOT, SCRIPTS_DIR, Audit, default_base)

ap = argparse.ArgumentParser(description="Repository audit")
ap.add_argument("--build", action="store_true", default=os.environ.get("SEO_REPO_BUILD") == "1",
                help="also run npm run build (stop `next start` first - the build rewrites .next)")
ap.add_argument("--no-lint", action="store_true")
ap.add_argument("--no-typecheck", action="store_true")
ap.add_argument("--no-npm-audit", action="store_true")
args, extra = ap.parse_known_args()   # common options (--base, --pages ...) don't apply here
if extra:
    print(f"Ignoring option(s) this script doesn't use: {' '.join(extra)}")
audit = Audit("28_repo", "Repo Audit Report", "Repository", default_base())
ROOT = PROJECT_ROOT


def run(cmd, timeout=900):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return None, "", f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, "", f"timed out after {timeout} s"


def F(path):
    return f"file: {path}"


code, out, _ = run(["git", "ls-files", "-z"])
tracked = [f for f in out.split("\0") if f] if code == 0 else []
if code != 0:
    audit.not_checked("Git", "committed files", "not a git repository / git missing")

# ------------------------------------------------------------------ README
readme = ROOT / "README.md"
if not readme.exists():
    audit.add(F("README.md"), IMPORTANT, "Docs", "No README.md", current="(missing)",
              expected="a README that explains the project, how to run, build and deploy it")
else:
    text = readme.read_text(encoding="utf-8", errors="replace")
    if "bootstrapped with [`create-next-app`]" in text or "This is a [Next.js](https://nextjs.org) project" in text:
        audit.add(F("README.md"), IMPORTANT, "Docs", "README is the default create-next-app text", current=text[:120],
                  expected="a README written for this project")
    elif len(text) < 300:
        audit.add(F("README.md"), OPTIMIZATION, "Docs", "README is very short", current=f"{len(text)} characters")
    if not re.search(r"npm (run )?(dev|build|start)|yarn (dev|build)|pnpm (dev|build)", text):
        audit.add(F("README.md"), OPTIMIZATION, "Docs", "README doesn't say how to run / build the project",
                  expected="the install / dev / build / start commands")

# ------------------------------------------------------------------ .gitignore
gi = ROOT / ".gitignore"
rules = gi.read_text(encoding="utf-8", errors="replace").splitlines() if gi.exists() else []
if not gi.exists():
    audit.add(F(".gitignore"), CRITICAL, "Git", "No .gitignore", current="(missing)")
for pattern, needles, sev in (("node_modules", ("node_modules",), IMPORTANT), (".next", (".next",), IMPORTANT),
                              (".env files", (".env", ".env*", ".env*.local", ".env.local"), CRITICAL),
                              ("__pycache__", ("__pycache__", "*.pyc", "*.py[cod]"), OPTIMIZATION)):
    if gi.exists() and not any(any(r.strip().lstrip("/").rstrip("/") == n.rstrip("/") for n in needles) for r in rules):
        audit.add(F(".gitignore"), sev, "Git", f".gitignore doesn't ignore {pattern}", current="(no rule)",
                  expected=" or ".join(needles))

# ------------------------------------------------------------------ committed files
SECRET_FILES = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|id_rsa|id_ed25519|.*\.pem|.*\.p12|.*\.pfx|.*\.key|credentials\.json|"
                          r"service-account.*\.json)$", re.I)
ARTEFACTS = re.compile(r"(^|/)(\.next|node_modules|__pycache__|\.turbo|out|dist|coverage)/|(^|/)\.DS_Store$|"
                       r"\.tsbuildinfo$|\.pyc$", re.I)
artefacts = []
for f in tracked:
    if SECRET_FILES.search(f) and not re.search(r"\.(example|sample|template)$", f):
        audit.add(F(f), CRITICAL, "Secrets", "Secret / environment file committed to git", current=f,
                  fix="git rm --cached the file, add it to .gitignore, and rotate every key it contained.")
    elif ARTEFACTS.search(f):
        artefacts.append(f)
    try:
        size = (ROOT / f).stat().st_size
    except OSError:
        continue
    if size > 5 * 1024 * 1024:
        audit.add(F(f), OPTIMIZATION, "Git", "Large file committed (over 5 MB)", current=f"{size // 1048576} MB",
                  fix="Compress it, host it elsewhere, or use Git LFS.")
if artefacts:
    groups = {}
    for f in artefacts:
        key = next((p for p in ("__pycache__", ".next", "node_modules", ".DS_Store", ".tsbuildinfo", ".pyc", "dist", "out")
                    if p in f), "build output")
        groups.setdefault(key, []).append(f)
    for key, files in groups.items():
        audit.add(F(files[0]), OPTIMIZATION, "Git", "Build output / cache files committed",
                  current=f"{len(files)} {key} file(s)", element=", ".join(files[:5]),
                  fix=f"git rm -r --cached the {key} files and add {key} to .gitignore.")
lockfiles = [f for f in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb") if (ROOT / f).exists()]
if len(lockfiles) > 1:
    audit.add(F(lockfiles[0]), IMPORTANT, "Packages", "More than one lockfile", current=", ".join(lockfiles),
              expected="one package manager / lockfile")
elif not lockfiles:
    audit.add(F("package.json"), IMPORTANT, "Packages", "No lockfile committed", expected="package-lock.json")
if any(re.search(r"(^|/)\.env", f) for f in os.listdir(ROOT)) and not (ROOT / ".env.example").exists():
    audit.add(F(".env.example"), OPTIMIZATION, "Docs", "No .env.example", expected="the variable names (no values)")

# ------------------------------------------------------------------ secrets in committed text files
PATTERNS = [
    (CRITICAL, "Private key in source", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (CRITICAL, "AWS access key in source", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (CRITICAL, "GitHub token in source", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    (CRITICAL, "Stripe live secret key in source", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{20,}\b")),
    (CRITICAL, "Slack token in source", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (IMPORTANT, "Hard-coded password / secret in source",
     re.compile(r"(?i)\b(password|passwd|secret|api_?key|client_secret|auth_token)\b\s*[:=]\s*['\"][^'\"\s$`{]{10,}['\"]")),
    (OPTIMIZATION, "Google API key in source (restrict it to your domains)", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
]
TEXT_EXT = re.compile(r"\.(js|jsx|ts|tsx|mjs|cjs|json|py|env|yml|yaml|toml|md|txt|sh|html|css|ini|cfg)$|^[^.]+$", re.I)
secret_hits = 0
for f in tracked:
    if not TEXT_EXT.search(f) or re.search(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml)$", f):
        continue
    path = ROOT / f
    try:
        if path.stat().st_size > 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for sev, label, rx in PATTERNS:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            secret_hits += 1
            shown = m.group(0)
            audit.add(F(f), sev, "Secrets", label, current=shown[:12] + "…" if len(shown) > 12 else shown,
                      element=f"{f}:{line}", fix="Move the value to an environment variable (not committed) and "
                      "rotate it - anything that was pushed must be treated as leaked.")

# ------------------------------------------------------------------ package.json
pkg_rows = []
try:
    pkg = json.loads((ROOT / "package.json").read_text())
except (OSError, ValueError):
    pkg = None
    audit.add(F("package.json"), CRITICAL, "Packages", "package.json missing or invalid")
if pkg:
    scripts = pkg.get("scripts", {})
    for s in ("build", "start", "lint"):
        if s not in scripts:
            audit.add(F("package.json"), IMPORTANT if s == "build" else OPTIMIZATION, "Packages",
                      f"No '{s}' script in package.json", current="(missing)")
    for section in ("dependencies", "devDependencies"):
        for name, ver in (pkg.get(section) or {}).items():
            pkg_rows.append((section, name, ver))
            if ver in ("latest", "*", "") or ver.startswith(("http", "git")):
                audit.add(F("package.json"), IMPORTANT, "Packages", "Unpinned dependency version",
                          current=f"{name}: {ver}", expected="a semver range, e.g. ^1.2.3")

npm = shutil.which("npm")
npx = shutil.which("npx")
# ------------------------------------------------------------------ npm audit
vuln_rows = []
if args.no_npm_audit or not npm:
    audit.not_checked("Packages", "npm audit", "--no-npm-audit" if npm else "npm not found")
else:
    print("npm audit ...")
    code, out, err = run([npm, "audit", "--json"], timeout=300)
    try:
        data = json.loads(out)
        if not isinstance(data, dict) or "error" in data:   # offline / no lockfile: npm prints {"error": {...}}
            raise ValueError((data.get("error") or {}).get("summary", "") if isinstance(data, dict) else "")
        for name, v in (data.get("vulnerabilities") or {}).items():
            sev = v.get("severity", "")
            via = [x.get("title", "") for x in v.get("via", []) if isinstance(x, dict)]
            vuln_rows.append((name, sev, v.get("range", ""), "; ".join(via)[:200], v.get("fixAvailable") not in (False, None)))
            level = IMPORTANT if sev in ("high", "critical") else (OPTIMIZATION if sev == "moderate" else None)
            if level:
                audit.add(F("package.json"), level, "Packages", f"Vulnerable dependency ({sev})",
                          current=f"{name} {v.get('range', '')}", element="; ".join(via)[:200],
                          fix="npm audit fix (or upgrade the package that pulls it in).")
    except (ValueError, AttributeError) as e:
        audit.not_checked("Packages", "npm audit", (str(e) or err or out)[:200], "Run npm audit by hand (needs the internet).")

# ------------------------------------------------------------------ ESLint
lint_rows = []
if args.no_lint or not npx:
    audit.not_checked("Code", "ESLint", "--no-lint" if npx else "npx not found")
else:
    print("ESLint ...")
    # lint the project's own committed JS / TS (not .venv, node_modules or anything else on disk)
    lint_files = [f for f in tracked if re.search(r"\.(jsx?|tsx?|mjs|cjs)$", f) and not f.startswith(("py files/", "."))]
    results, failed = [], ""
    for i in range(0, len(lint_files), 200):   # batches keep the command line under the OS argument limit
        code, out, err = run([npx, "--no-install", "eslint", "--no-warn-ignored", "-f", "json", *lint_files[i:i + 200]],
                             timeout=900)
        try:
            batch = json.loads(out)
            results.extend(batch if isinstance(batch, list) else [])
        except ValueError:
            failed = failed or (err or out)[:200] or f"eslint exited with code {code}"
    try:
        if failed:
            raise ValueError(failed)
        for r in results:
            rel = os.path.relpath(r["filePath"], ROOT)
            for m in r.get("messages", []):
                sev = IMPORTANT if m.get("severity") == 2 else OPTIMIZATION
                rule = m.get("ruleId") or "parse"
                lint_rows.append((rel, m.get("line"), "error" if sev == IMPORTANT else "warning", rule, m.get("message", "")[:150]))
                audit.add(F(rel), sev, "Code", f"ESLint {'error' if sev == IMPORTANT else 'warning'}: {rule}",
                          current=m.get("message", "")[:200], element=f"{rel}:{m.get('line')}",
                          fix="Fix the code at the line shown (npm run lint).")
    except ValueError as e:
        audit.not_checked("Code", "ESLint", str(e)[:200], "Run npm run lint by hand.")

# ------------------------------------------------------------------ TypeScript
ts_rows = []
if args.no_typecheck or not npx or not (ROOT / "tsconfig.json").exists():
    audit.not_checked("Code", "TypeScript", "--no-typecheck" if args.no_typecheck else
                      ("npx not found" if not npx else "no tsconfig.json"))
else:
    print("TypeScript (tsc --noEmit) ...")
    code, out, err = run([npx, "--no-install", "tsc", "--noEmit", "--pretty", "false"], timeout=900)
    for line in (out + err).splitlines():
        m = re.match(r"(.+?)\((\d+),\d+\): error (TS\d+): (.*)", line)
        if m:
            ts_rows.append((m.group(1), m.group(2), m.group(3), m.group(4)[:200]))
            audit.add(F(m.group(1)), IMPORTANT, "Code", f"TypeScript error {m.group(3)}", current=m.group(4)[:200],
                      element=f"{m.group(1)}:{m.group(2)}", fix="Fix the type error (npx tsc --noEmit).")
    if code not in (0, None) and not ts_rows:
        audit.add(F("tsconfig.json"), IMPORTANT, "Code", "TypeScript check failed", current=(out + err)[:300])

# ------------------------------------------------------------------ Bandit (Python audit scripts)
bandit_rows = []
venv_bandit = Path(sys.executable).parent / "bandit"   # installed in the same virtualenv as this script
bandit = str(venv_bandit) if venv_bandit.exists() else shutil.which("bandit")
if not bandit:
    audit.not_checked("Code", "Bandit (Python security)", "bandit not installed", "pip install bandit")
else:
    print("Bandit ...")
    code, out, err = run([bandit, "-r", str(SCRIPTS_DIR), "-f", "json", "-q", "-x", str(SCRIPTS_DIR / "report")], timeout=300)
    try:
        for r in json.loads(out).get("results", []):
            sev = {"HIGH": IMPORTANT, "MEDIUM": OPTIMIZATION}.get(r.get("issue_severity"))
            rel = os.path.relpath(r["filename"], ROOT)
            bandit_rows.append((rel, r.get("line_number"), r.get("issue_severity"), r.get("test_id"), r.get("issue_text", "")[:150]))
            if sev and r.get("issue_confidence") in ("HIGH", "MEDIUM"):
                audit.add(F(rel), sev, "Code", f"Bandit {r.get('test_id')}: {r.get('test_name')}",
                          current=r.get("issue_text", "")[:200], element=f"{rel}:{r.get('line_number')}",
                          fix=f"See {r.get('more_info', 'the Bandit docs')}.")
    except ValueError:
        audit.not_checked("Code", "Bandit (Python security)", (err or out)[:200])

# ------------------------------------------------------------------ TODO / FIXME
todos = []
for f in tracked:
    if f.startswith("src/") and re.search(r"\.(tsx?|jsx?|css)$", f):
        try:
            for n, line in enumerate((ROOT / f).read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line):
                    todos.append((f, n, line.strip()[:150]))
        except OSError:
            pass
if todos:
    audit.site(INFO, "Code", "TODO / FIXME comments in src", current=f"{len(todos)} comment(s)", element=f"{todos[0][0]}:{todos[0][1]}")

# ------------------------------------------------------------------ production build (opt-in)
if args.build and npm:
    print("npm run build ... (production build)")
    code, out, err = run([npm, "run", "build"], timeout=1800)
    if code != 0:
        tail = "\n".join((out + err).strip().splitlines()[-15:])
        audit.add(F("package.json"), CRITICAL, "Build", "Production build fails", current=tail[:500],
                  fix="Run npm run build and fix the first error it prints.")
    else:
        audit.note("Production build", "OK")
else:
    audit.not_checked("Build", "production build", "--build not given (it rewrites .next - stop `next start` first)",
                      'python "py files/28_repo_audit.py" --build   (or run_all.py --repo-build)')

audit.note("Files in git", len(tracked))
audit.sheet("npm audit", ["Package", "Severity", "Range", "Advisories", "Fix available"], vuln_rows, (30, 10, 20, 80, 12))
audit.sheet("ESLint", ["File", "Line", "Level", "Rule", "Message"], lint_rows, (60, 7, 9, 36, 80))
audit.sheet("TypeScript", ["File", "Line", "Code", "Message"], ts_rows, (60, 7, 10, 90))
audit.sheet("Bandit", ["File", "Line", "Severity", "Test", "Issue"], bandit_rows, (50, 7, 10, 8, 90))
audit.sheet("TODO comments", ["File", "Line", "Text"], todos, (60, 7, 90))
audit.sheet("Dependencies", ["Section", "Package", "Version"], pkg_rows, (16, 40, 16))
audit.save("Repo_Audit_Report")
