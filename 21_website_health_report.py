"""
21 - Website Health master report (always runs last)
  Combines the JSON reports of scripts 01-20 into one report (Excel, JSON and CSV):
    - Website Health: Technical SEO, On-Page SEO, Performance, Accessibility, Security, Image, Link Health,
      Structured Data, Mobile, Content, Lighthouse -> Overall Website Health Score
    - All Issues by URL: every issue from every report, one row per issue, URL by URL. When several reports
      found the identical problem on the same URL it is listed once with every report in "Reported by".
    - URL Summary: per URL, how many critical / important / optimization issues and which reports found them
    - Top issues and Reports
  Grades: 90-100 Excellent | 80-89 Good | 70-79 Needs Improvement | 50-69 Poor | 0-49 Critical

  Uses the reports of the current run (run_all.py sets SEO_RUN_TIME); run on its own it takes the latest
  report of every script, from any date.

  python "py files/21_website_health_report.py"
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font

from seo_common import (CRITICAL, FILLS, IMPORTANT, INFO, ISSUE_COLUMNS, OPTIMIZATION, PROJECT_ROOT, REPORT_ROOT,
                        SEVERITY_ORDER, SITE_WIDE, clean_cell, grade, grade_fill, rel_path, remove_old_reports, report_path, write_csv,
                        write_sheet)

CATEGORIES = [  # (name, weight %, script keys) - a category with no report is "Not measured" and left out
    ("Technical SEO", 15, ["01_sitemap", "09_technical", "08_hreflang", "13_nextjs", "25_html_validation"]),
    ("On-Page SEO", 15, ["02_page_seo", "03_headings", "06_social", "17_heading_order", "20_seo_report",
                         "26_text_quality"]),
    ("Performance", 15, ["12_performance", "12a_cwv", "16_third_party", "27_assets"]),
    ("Accessibility", 10, ["10_accessibility"]),
    ("Security", 8, ["11_security"]),
    ("Image", 7, ["04_images", "18_image_alt"]),
    ("Link Health", 10, ["05_links", "19_third_party_urls"]),
    ("Structured Data", 5, ["07_schema"]),
    ("Mobile", 10, ["15_mobile"]),
    ("Content", 5, ["14_content", "31_english"]),
    ("Lighthouse", 10, ["12b_lighthouse"]),
    ("Business info & Forms", 8, ["22_business_info", "23_forms"]),
    ("Navigation", 7, ["24_navigation"]),
    ("Code & Repo", 5, ["28_repo"]),
    ("Migration (live vs dev)", 5, ["29_live_vs_dev"]),
]


def load_summaries():
    """The JSON report of every script: this run's (run_all.py sets SEO_RUN_TIME), else the latest of each script."""
    run_time = os.environ.get("SEO_RUN_TIME")
    run_date = os.environ.get("SEO_RUN_DATE")
    found = {}
    for f in REPORT_ROOT.glob("*/json/*.json"):
        if f.name.startswith(("Website_Health_Report_", "QA_Checklist_Report_")) or (run_date and run_time and f.parent.parent.name != run_date):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            r = data["report"]
            key = r["key"]
        except (ValueError, KeyError, TypeError):
            continue
        stamp = (f.parent.parent.name, r.get("run_time", ""))
        if run_time and stamp[1] != run_time:
            continue
        if key not in found or stamp > found[key]["_stamp"]:
            found[key] = {"key": key, "title": r["title"], "category": r["category"], "score": r["score"],
                          "grade": r["grade"], "pages": r["pages_checked"], "counts": r["counts"],
                          "report": r.get("excel", ""), "json": rel_path(f), "csv": r.get("csv", ""),
                          "time": stamp[1], "base": r.get("audited_server", ""), "_stamp": stamp}
    return found


# no options: -h shows this help instead of rebuilding the report, and an unknown option is an error
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
summaries = load_summaries()
if not summaries:
    sys.exit("No reports found in py files/report/<date>/json - run the checker scripts first (python \"py files/run_all.py\").")

# ------------------------------------------------------------------ scores
score_rows, total, weights = [], 0.0, 0
for name, weight, keys in CATEGORIES:
    parts = [summaries[k] for k in keys if k in summaries]
    if parts:
        score = round(sum(p["score"] for p in parts) / len(parts), 1)
        total += score * weight
        weights += weight
    else:
        score = None
    score_rows.append((name, score if score is not None else "Not measured", grade(score), weight,
                       ", ".join(f"{p['title']} ({p['score']})" for p in parts) or "not run",
                       sum(p["counts"][CRITICAL] for p in parts), sum(p["counts"][IMPORTANT] for p in parts),
                       sum(p["counts"][OPTIMIZATION] for p in parts)))
overall = round(total / weights, 1) if weights else None

# ------------------------------------------------------------------ every issue of every report
merged = {}          # dedupe key -> issue (with "reported_by")
url_info = {}        # url -> {http_status, in_sitemap, crawl_depth}
missing_json = []
for s in sorted(summaries.values(), key=lambda s: s["key"]):
    path = PROJECT_ROOT / s.get("json", "") if s.get("json") else None
    if not path or not path.exists():
        missing_json.append(s["title"])
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    items = [(u["url"], i) for u in data.get("urls", []) for i in u["issues"]]
    items += [(SITE_WIDE, i) for i in data.get("site_wide_issues", [])]
    for u in data.get("urls", []):
        info = url_info.setdefault(u["url"], {})
        for k in ("http_status", "in_sitemap", "crawl_depth"):
            if info.get(k) in (None, "") and u.get(k) not in (None, ""):
                info[k] = u[k]
    for url, i in items:
        key = (url, i["issue"].strip().lower(), str(i.get("current_value", "")), str(i.get("element", "")),
               str(i.get("details", "")))
        if key in merged:
            m = merged[key]
            if s["title"] not in m["reported_by"]:
                m["reported_by"].append(s["title"])
            if SEVERITY_ORDER.get(i["severity"], 9) < SEVERITY_ORDER.get(m["severity"], 9):
                m["severity"], m["priority"] = i["severity"], i["priority"]
        else:
            merged[key] = dict(i, url=url, reported_by=[s["title"]])
issues = sorted(merged.values(), key=lambda i: (i["url"] == SITE_WIDE, not i["url"].startswith("http"), i["url"],
                                                SEVERITY_ORDER.get(i["severity"], 9), i["category"], i["issue"]))
for i in issues:
    i["report"] = ", ".join(i.pop("reported_by"))
counts = Counter(i["severity"] for i in issues)

by_url = defaultdict(list)
for i in issues:
    by_url[i["url"]].append(i)
url_entries = []
for url, items in by_url.items():
    c = Counter(i["severity"] for i in items)
    info = url_info.get(url, {})
    url_entries.append({"url": url, "http_status": info.get("http_status", ""), "in_sitemap": info.get("in_sitemap"),
                        "crawl_depth": info.get("crawl_depth"),
                        "counts": {sev: c[sev] for sev in (CRITICAL, IMPORTANT, OPTIMIZATION, INFO)},
                        "total_issues": len(items),
                        "reports": sorted({r for i in items for r in i["report"].split(", ")}),
                        "issues": [{k: v for k, v in i.items() if k != "url"} for i in items]})
url_entries.sort(key=lambda e: (e["url"] == SITE_WIDE, -e["counts"][CRITICAL], -e["counts"][IMPORTANT], e["url"]))

types = {}
for i in issues:
    t = types.setdefault((i["severity"], i["issue"]), {"issue": i["issue"], "severity": i["severity"],
                                                       "category": i["category"], "urls": set(), "occurrences": 0,
                                                       "reports": set(), "description": i.get("description", ""),
                                                       "expected_value": i.get("expected_value", ""),
                                                       "recommended_fix": i.get("recommended_fix", "")})
    t["urls"].add(i["url"])
    t["occurrences"] += 1
    t["reports"].update(i["report"].split(", "))
issue_types = sorted(types.values(), key=lambda t: (SEVERITY_ORDER.get(t["severity"], 9), -len(t["urls"]), -t["occurrences"]))

# ------------------------------------------------------------------ Excel
remove_old_reports("Website_Health_Report")
path = report_path("Website_Health_Report")
json_path = report_path("Website_Health_Report", "json")
csv_path = report_path("Website_Health_Report", "csv")
base = next(iter(summaries.values())).get("base", "")
wb = Workbook()
ws = wb.active
ws.title = "Website Health"
ws.append(["Website Health Report"])
ws["A1"].font = Font(bold=True, size=18)
ws.append(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
ws.append(["Audited server", base])
ws.append(["URLs with issues", sum(1 for e in url_entries if e["url"] != SITE_WIDE)])
ws.append(["Issues (all reports, de-duplicated)",
           f"{len(issues)}: {counts[CRITICAL]} critical, {counts[IMPORTANT]} important, {counts[OPTIMIZATION]} optimization"])
ws.append([])
ws.append(["Overall Website Health Score", overall if overall is not None else "Not measured", grade(overall)])
for c in ws[ws.max_row]:
    c.font = Font(bold=True, size=14)
ws.cell(row=ws.max_row, column=2).fill = ws.cell(row=ws.max_row, column=3).fill = grade_fill(overall)
ws.append([])
ws.append(["Category", "Score", "Grade", "Weight %", "Based on", "Critical", "Important", "Optimization"])
for c in ws[ws.max_row]:
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = FILLS["header"]
for r in score_rows:
    ws.append(list(r))
    ws.cell(row=ws.max_row, column=2).fill = ws.cell(row=ws.max_row, column=3).fill = grade_fill(r[1])
ws.append([])
ws.append(["Grades: 90-100 Excellent | 80-89 Good | 70-79 Needs Improvement | 50-69 Poor | 0-49 Critical"])
missing = [k for _, _, keys in CATEGORIES for k in keys if k not in summaries]
if missing:
    ws.append(["Not included (script not run or failed)", ", ".join(missing)])
if missing_json:
    ws.append(["Scores only (no issue details - re-run these scripts)", ", ".join(missing_json)])
for col, w in zip("ABCDEFGH", (36, 14, 20, 10, 90, 9, 10, 13)):
    ws.column_dimensions[col].width = w

columns = [(k, "Reported by" if k == "report" else h, w) for k, h, w in ISSUE_COLUMNS]
write_sheet(wb.create_sheet("All Issues by URL"), [h for _, h, _ in columns],
            [[i.get(k, "") for k, _, _ in columns] for i in issues], [w for _, _, w in columns], severity_col=2)

url_rows = []
for e in url_entries:
    names = Counter(i["issue"] for i in e["issues"])
    url_rows.append((e["url"], e["http_status"], "" if e["in_sitemap"] is None else ("yes" if e["in_sitemap"] else "no"),
                     "" if e["crawl_depth"] is None else e["crawl_depth"], e["counts"][CRITICAL], e["counts"][IMPORTANT],
                     e["counts"][OPTIMIZATION], e["total_issues"], ", ".join(e["reports"]),
                     "; ".join(n + (f" (x{c})" if c > 1 else "") for n, c in names.items())))
uws = wb.create_sheet("URL Summary")
write_sheet(uws, ["URL", "HTTP", "In sitemap", "Crawl depth", "Critical", "Important", "Optimization", "Total issues",
                  "Reports", "Issues"], url_rows, (55, 7, 10, 11, 9, 10, 13, 12, 60, 120))
for row in range(2, uws.max_row + 1):
    for col, sev in ((5, CRITICAL), (6, IMPORTANT), (7, OPTIMIZATION)):
        if uws.cell(row=row, column=col).value:
            uws.cell(row=row, column=col).fill = FILLS[sev]

write_sheet(wb.create_sheet("Top issues"), ["Severity", "Issue", "Category", "URLs", "Occurrences", "Reports", "Description",
                                            "Expected / recommended value", "Recommended fix"],
            [(t["severity"], t["issue"], t["category"], len(t["urls"]), t["occurrences"], ", ".join(sorted(t["reports"])),
              t["description"], t["expected_value"], t["recommended_fix"]) for t in issue_types],
            (13, 50, 20, 7, 12, 40, 60, 40, 70), severity_col=1)

report_rows = [(s["title"], s["score"], s["grade"], s["pages"], s["counts"][CRITICAL], s["counts"][IMPORTANT],
                s["counts"][OPTIMIZATION], f"{s['_stamp'][0]} {s['_stamp'][1]}", s["report"], s.get("json", ""))
               for s in sorted(summaries.values(), key=lambda s: s["key"])]
rws = wb.create_sheet("Reports")
write_sheet(rws, ["Report", "Score", "Grade", "Pages", "Critical", "Important", "Optimization", "Run", "Excel", "JSON"],
            report_rows, (32, 8, 20, 8, 9, 10, 13, 20, 60, 60))
for row in range(2, rws.max_row + 1):
    rws.cell(row=row, column=2).fill = grade_fill(rws.cell(row=row, column=2).value)
wb.save(path)

# ------------------------------------------------------------------ JSON
for t in issue_types:
    t["urls"], t["reports"] = len(t["urls"]), sorted(t["reports"])
json_path.write_text(json.dumps({
    "report": {"title": "Website Health Report", "generated": datetime.now().isoformat(timespec="seconds"),
               "audited_server": base, "overall_score": overall, "grade": grade(overall),
               "total_issues": len(issues), "counts": {s: counts[s] for s in (CRITICAL, IMPORTANT, OPTIMIZATION, INFO)},
               "excel": rel_path(path), "csv": rel_path(csv_path)},
    "categories": [{"category": r[0], "score": r[1], "grade": r[2], "weight": r[3], "based_on": r[4],
                    "critical": r[5], "important": r[6], "optimization": r[7]} for r in score_rows],
    "reports": [{k: v for k, v in s.items() if k != "_stamp"} | {"run": " ".join(s["_stamp"])}
                for s in sorted(summaries.values(), key=lambda s: s["key"])],
    "issue_types": issue_types,
    "urls": [e for e in url_entries if e["url"] != SITE_WIDE],
    "site_wide_issues": next((e["issues"] for e in url_entries if e["url"] == SITE_WIDE), []),
}, indent=1, ensure_ascii=False, default=str))

write_csv(csv_path, [h for _, h, _ in columns], ([i.get(k, "") for k, _, _ in columns] for i in issues))

print("\n" + "=" * 70)
print("✓ Website Health Master Report generated successfully!")
print("=" * 70)
print(f"  • Excel Report:  {rel_path(path)}")
print(f"  • JSON Report:   {rel_path(json_path)}")
print(f"  • CSV Report:    {rel_path(csv_path)}")
print("-" * 70)
print("CATEGORY SCORES:")
for name, score, g, *_ in score_rows:
    print(f"  {name:<18} {score if isinstance(score, (int, float)) else '-':>6}  {g}")
print(f"  {'OVERALL':<18} {overall if overall is not None else '-':>6}  {grade(overall)}")
print(f"  Total: {len(issues)} issues on {sum(1 for e in url_entries if e['url'] != SITE_WIDE)} URLs "
      f"({counts[CRITICAL]} critical, {counts[IMPORTANT]} important, {counts[OPTIMIZATION]} optimization)")
print("=" * 70 + "\n")
