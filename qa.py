"""
QA control panel for the website audit scripts - list, run, preview, delete, mark.

  python "py files/qa.py" list                          every QA check (ID, type, scripts) and every script
  python "py files/qa.py" run NAV-04 SEO-07             run what these checks need, then rebuild 21 + 30
  python "py files/qa.py" run 22 25 --pages sample      run scripts by number (any run_all.py option works)
  python "py files/qa.py" run SEO                       run every script of a checklist section
  python "py files/qa.py" run-all [--skip 12b]          run_all.py: every script, then 21 + 30
  python "py files/qa.py" report                        rebuild 21 (health) + 30 (checklist) from the saved JSON
  python "py files/qa.py" preview [--status FAIL] [--open]   checklist in the terminal / open the HTML page
  python "py files/qa.py" status                        which reports exist, how old, which server, human results
  python "py files/qa.py" mark VIS-03 pass "Checked Safari 18 + iOS" [--by Name]   record a person's result
  python "py files/qa.py" mark SEO-03 clear             remove it again
  python "py files/qa.py" delete --report 22 24 | --date 2026-10-07 | --screenshots | --crawl-cache | --human | --all
                                                        delete report data (asks first; --yes skips the question)
  python "py files/qa.py" config                        the expected values used by the checks (qa_config.json)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_checks import BY_ID, CHECKS, SCRIPT_FOR_REPORT, SECTIONS   # noqa: E402
from seo_common import CRAWL_CACHE, QA_CONFIG_FILE, REPORT_ROOT, PROJECT_ROOT, default_base, qa_config   # noqa: E402

HUMAN_FILE = HERE / "qa_human_checks.json"
TTY = sys.stdout.isatty()
COLORS = {"FAIL": "31", "WARN": "33", "PASS": "32", "SKIP": "90", "HUMAN": "35", "head": "1;36"}


def c(text, key):
    return f"\033[{COLORS[key]}m{text}\033[0m" if TTY and key in COLORS else str(text)


def scripts():
    """{prefix: (file, report name)} for every numbered script (report name from its save() call)."""
    out = {}
    for p in sorted(HERE.glob("[0-9][0-9]*_*.py")):
        src = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'\.save\("([^"]+)"\)', src) or re.search(r'remove_old_reports\("([^"]+)"\)', src) \
            or re.search(r'name = "([A-Z][A-Za-z_]+_Report)"', src)
        out[p.name.split("_", 1)[0]] = (p.name, m.group(1) if m else "")
    return out


def latest_checklist():
    files = sorted(REPORT_ROOT.glob("*/json/QA_Checklist_Report_*.json"), key=lambda p: p.stat().st_mtime)
    while files:
        try:
            data = json.loads(files[-1].read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("report"), dict) and isinstance(data.get("checks"), list):
                return data
        except (OSError, ValueError):
            pass
        files.pop()   # unreadable / not a checklist: fall back to the one before
    return None


# ------------------------------------------------------------------ list
def cmd_list(a):
    print(c(f"{len(CHECKS)} QA checks", "head"))
    for section in SECTIONS:
        if a.section and a.section.lower() not in section.lower():
            continue
        print(c(f"\n{section}", "head"))
        for ch in CHECKS:
            if ch.section == section:
                src = ", ".join(SCRIPT_FOR_REPORT.get(r, r) for r in ch.reports) or "-"
                print(f"  {ch.id:<8} {ch.kind:<10} [{src:<10}] {ch.title}")
    print(c("\nScripts", "head"))
    for prefix, (fname, name) in scripts().items():
        print(f"  {prefix:<4} {fname:<36} {name}")
    print("\nRun one:  qa.py run NAV-04   |   qa.py run 24   |   everything:  qa.py run-all")


# ------------------------------------------------------------------ run
def resolve(targets):
    """Check IDs / script numbers / section names -> script prefixes."""
    known = scripts()
    prefixes, unknown = [], []
    for t in targets:
        norm = t.zfill(2) if t.isdigit() else t
        t_up = norm.upper()
        if t_up in BY_ID:
            ch = BY_ID[t_up]
            if ch.kind == "HUMAN":
                print(f"{t_up} is a human check - record the result with:  qa.py mark {t_up} pass \"note\"")
            prefixes += [SCRIPT_FOR_REPORT[r] for r in ch.reports if r in SCRIPT_FOR_REPORT]
        elif norm.lower() in known:
            prefixes.append(norm.lower())
        elif any(norm.lower() in s.lower() for s in SECTIONS) and len(norm) > 2:
            for ch in CHECKS:
                if norm.lower() in ch.section.lower():
                    prefixes += [SCRIPT_FOR_REPORT[r] for r in ch.reports if r in SCRIPT_FOR_REPORT]
        else:
            unknown.append(t)
    if unknown:
        sys.exit(f"Unknown check / script / section: {', '.join(unknown)}  (see: qa.py list)")
    return [p for p in dict.fromkeys(prefixes) if p not in ("21", "30")]


def run_all(extra):
    cmd = [sys.executable, str(HERE / "run_all.py"), *extra]
    print(c("$ " + " ".join(f'"{x}"' if " " in x else x for x in cmd), "head"))
    return subprocess.call(cmd)


def cmd_run(a, passthrough):
    prefixes = resolve(a.targets)
    if not prefixes:
        sys.exit("Nothing to run (only human checks given) - the checklist is rebuilt with:  qa.py report")
    print(f"Scripts: {', '.join(prefixes)} (then 21 + 30)")
    sys.exit(run_all(["--only", ",".join(prefixes), *passthrough]))


def cmd_run_all(a, passthrough):
    sys.exit(run_all(passthrough))


def cmd_report(a, passthrough):
    code = 0
    for s in ("21_website_health_report.py", "30_qa_checklist_report.py"):
        code |= subprocess.call([sys.executable, str(HERE / s)])
    if code == 0:
        cmd_preview(argparse.Namespace(status="FAIL", open=False, all=False))
    sys.exit(code)


# ------------------------------------------------------------------ preview
def cmd_preview(a):
    data = latest_checklist()
    if not data:
        sys.exit("No QA checklist yet - run:  qa.py run-all   (or qa.py report if the other reports exist)")
    r = data["report"]
    v = r["verdict"]
    print(c(f"QA CHECKLIST  {v}", "FAIL" if v == "NEEDS FIXES" else "WARN" if v == "REVIEW" else "PASS"),
          f" {r['generated']}  {r['audited_server']}")
    print("  " + "   ".join(c(f"{k} {n}", k) for k, n in r["counts"].items()))
    if r.get("mixed_servers"):
        print(c(f"  ! reports from different servers: {r['mixed_servers']}", "WARN"))
    want = None if a.all else ({x.strip().upper() for x in a.status.split(",")} if a.status else
                               {"FAIL", "WARN", "SKIP", "HUMAN"})
    for section in SECTIONS:
        rows = [ch for ch in data["checks"] if ch["section"] == section and (want is None or ch["status"] in want)]
        if not rows:
            continue
        print(c(f"\n{section}", "head"))
        for ch in rows:
            status = ch["status"]
            print(f"  {c(status.ljust(5), status)} {ch['id']:<8} {ch['title'][:70]}")
            print(f"        {ch['result'][:200]}")
            for e in ch.get("evidence", [])[: getattr(a, "evidence", 0)]:
                print(f"          - {e['url']} [{e['severity']}] {e['issue']}: {str(e.get('current_value', ''))[:90]}")
    print(f"\nFiles: {r['html']}\n       {r['markdown']}\n       {r['excel']}")
    if a.open:
        target_html = Path(r["html"]) if Path(r["html"]).is_absolute() else (PROJECT_ROOT / r["html"])
        webbrowser.open(target_html.resolve().as_uri())


# ------------------------------------------------------------------ status
def cmd_status(a):
    known = {name: prefix for prefix, (_, name) in scripts().items()}
    rows = []
    for f in sorted(REPORT_ROOT.glob("*/json/*.json")):
        m = re.match(r"(.+)_(\d\d-\d\d-\d\d)\.json$", f.name)
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))["report"]
        except (ValueError, KeyError, OSError):
            continue
        age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
        rows.append((known.get(m.group(1), "?") if m else "?", m.group(1) if m else f.name, f.parent.parent.name,
                     m.group(2) if m else "", rep.get("pages_checked", ""), rep.get("score", rep.get("verdict", "")),
                     rep.get("audited_server", ""), f"{age.days}d {age.seconds // 3600}h"))
    print(c(f"Reports in {REPORT_ROOT}", "head"))
    if not rows:
        print("  (none)")
    for r in sorted(rows):
        print(f"  {r[0]:<4} {r[1]:<28} {r[2]} {r[3]}  pages {str(r[4]):<5} score {str(r[5]):<12} {r[6]}  ({r[7]} old)")
    missing = [f"{p} {n}" for p, (_, n) in scripts().items() if n and n not in {r[1] for r in rows}]
    if missing:
        print(c("Not run yet: ", "WARN") + ", ".join(missing))
    shots = list(REPORT_ROOT.glob("*/screenshots/*"))
    if shots:
        print(f"Screenshots: {', '.join(str(s.relative_to(REPORT_ROOT)) for s in shots)}")
    crawls = list(CRAWL_CACHE.glob("crawl_*.json")) if CRAWL_CACHE.exists() else []
    print(f"Crawl cache: {len(crawls)} file(s) in {CRAWL_CACHE}")
    human = load_human()
    print(c(f"Human results ({HUMAN_FILE.name}): {len(human)}", "head"))
    for k, v in sorted(human.items()):
        print(f"  {k:<8} {c(v['status'].upper(), v['status'].upper())} {v.get('date', '')} {v.get('by', '')}: {v.get('note', '')}")
    print(f"Server now: {default_base()}")


# ------------------------------------------------------------------ mark
def load_human():
    try:
        return json.loads(HUMAN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cmd_mark(a):
    cid = a.id.upper()
    if cid not in BY_ID:
        sys.exit(f"Unknown check {cid} (see: qa.py list)")
    human = load_human()
    if a.status == "clear":
        if human.pop(cid, None) is None:
            sys.exit(f"{cid}: no manual result recorded - nothing to clear")
        print(f"{cid}: manual result removed")
    else:
        human[cid] = {"status": a.status.upper(), "note": " ".join(a.note), "by": a.by or os.environ.get("USER", ""),
                      "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "server": "" if a.any_server else default_base()}
        print(f"{cid}: {a.status.upper()} recorded" + ("" if a.any_server else f" for {default_base()}"))
    HUMAN_FILE.write_text(json.dumps(human, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.rebuild:
        subprocess.call([sys.executable, str(HERE / "30_qa_checklist_report.py")])
    else:
        print('Rebuild the checklist with:  qa.py report   (or add --rebuild)')


# ------------------------------------------------------------------ delete
def cmd_delete(a):
    targets = []
    if a.all:
        targets += [p for p in REPORT_ROOT.iterdir()] if REPORT_ROOT.exists() else []
    if a.date:
        bad = [d for d in a.date if not re.fullmatch(r"\d{4}-\d\d-\d\d", d)]
        if bad:   # only date folders: "..", "/" or "../.." would point outside py files/report
            sys.exit(f"--date takes report date folders like 2026-10-07, not: {', '.join(bad)}")
        targets += [REPORT_ROOT / d for d in a.date if (REPORT_ROOT / d).is_dir()]
    if a.report:
        known = scripts()
        names = set()
        for r in a.report:
            r = r.zfill(2) if r.isdigit() else r   # 1 -> 01
            if not re.fullmatch(r"[A-Za-z0-9_]+", r):
                sys.exit(f"--report takes script numbers or report names, not: {r}")
            if r.lower() in known:
                names.add(known[r.lower()][1])
            else:
                names.add(r)
        given = {r.zfill(2) if r.isdigit() else r for r in a.report}
        names |= {"Website_Health_Report" if "21" in given else "", "QA_Checklist_Report" if "30" in given else ""}
        names.discard("")
        for n in names:
            targets += [f for f in REPORT_ROOT.glob(f"*/*/{n}_*") if re.fullmatch(re.escape(n) + r"_\d\d-\d\d-\d\d(\..+)?", f.name)]
    if a.screenshots:
        targets += list(REPORT_ROOT.glob("*/screenshots"))
    if a.crawl_cache and CRAWL_CACHE.exists():
        targets += list(CRAWL_CACHE.glob("crawl_*.json"))
    if a.human and HUMAN_FILE.exists():
        targets.append(HUMAN_FILE)
    allowed = (REPORT_ROOT.resolve(), CRAWL_CACHE.resolve())
    targets = [t for t in dict.fromkeys(targets) if t == HUMAN_FILE or
               any(t.resolve() != root and t.resolve().is_relative_to(root) for root in allowed)]
    if not targets:
        sys.exit("Nothing to delete (give --report / --date / --screenshots / --crawl-cache / --human / --all)")
    print("Will delete:")
    for t in targets:
        print(f"  {t}{'/' if t.is_dir() else ''}")
    try:
        answer = "y" if a.yes else input("Delete these? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer not in ("y", "yes"):
        sys.exit("\nCancelled - nothing deleted")
    for t in targets:
        shutil.rmtree(t) if t.is_dir() else t.unlink(missing_ok=True)
    for d in sorted(REPORT_ROOT.glob("**/*"), key=lambda p: len(p.parts), reverse=True) if REPORT_ROOT.exists() else []:
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"Deleted {len(targets)} item(s)")


def cmd_config(a):
    print(c(f"{QA_CONFIG_FILE}", "head"))
    for k, v in qa_config().items():
        print(f"  {k:<22} {json.dumps(v, ensure_ascii=False)}")
    print("Empty values are auto-detected from the site. Edit the file to set the confirmed values.")


def main():
    ap = argparse.ArgumentParser(description="QA control panel", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="every check and script")
    p.add_argument("--section", default="")
    p = sub.add_parser("run", help="run checks / scripts / sections (+ any run_all.py option)")
    p.add_argument("targets", nargs="+")
    sub.add_parser("run-all", help="run every script (+ any run_all.py option)")
    sub.add_parser("report", help="rebuild the health + checklist reports from the saved JSON")
    p = sub.add_parser("preview", help="show the checklist")
    p.add_argument("--status", default="", help="comma list, e.g. FAIL,WARN (default: everything but PASS)")
    p.add_argument("--all", action="store_true", help="also PASS")
    p.add_argument("--evidence", type=lambda v: max(0, int(v)), default=0, help="show N evidence lines per check")
    p.add_argument("--open", action="store_true", help="open the HTML page in the browser")
    sub.add_parser("status", help="saved reports, ages, servers, human results")
    p = sub.add_parser("mark", help="record a person's result for a check")
    p.add_argument("id")
    p.add_argument("status", choices=("pass", "fail", "warn", "skip", "clear"))
    p.add_argument("note", nargs="*")
    p.add_argument("--by", default="")
    p.add_argument("--any-server", action="store_true", help="apply to every audited server (default: this one)")
    p.add_argument("--rebuild", action="store_true", help="rebuild the checklist report right away")
    p = sub.add_parser("delete", help="delete report data")
    p.add_argument("--report", nargs="+", help="script numbers or report names, e.g. 22 24 Forms_Report")
    p.add_argument("--date", nargs="+", help="report date folders, e.g. 2026-10-07")
    p.add_argument("--screenshots", action="store_true")
    p.add_argument("--crawl-cache", action="store_true")
    p.add_argument("--human", action="store_true", help="the recorded human results")
    p.add_argument("--all", action="store_true", help="everything in py files/report")
    p.add_argument("--yes", action="store_true", help="don't ask")
    sub.add_parser("config", help="show qa_config.json")
    a, passthrough = ap.parse_known_args()
    if passthrough and a.cmd not in ("run", "run-all"):
        ap.error(f"unrecognized arguments: {' '.join(passthrough)}")
    {"list": cmd_list, "status": cmd_status, "mark": cmd_mark, "delete": cmd_delete, "config": cmd_config,
     "preview": cmd_preview}.get(a.cmd, lambda x: None)(a)
    if a.cmd == "run":
        cmd_run(a, passthrough)
    elif a.cmd == "run-all":
        cmd_run_all(a, passthrough)
    elif a.cmd == "report":
        cmd_report(a, passthrough)


if __name__ == "__main__":
    main()
