#!/usr/bin/env python3
"""
Run tests, collect coverage and mutation testing results, and generate a markdown report.

Usage: python scripts/generate_test_report.py
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "file_processing" / "tests"
REPORT_MD = TEST_DIR / "testing_report.md"


def run_cmd(cmd, cwd=None, capture=True):
    try:
        out = subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT, shell=False, text=True)
        return out
    except subprocess.CalledProcessError as exc:
        return exc.output


def collect_test_counts():
    # Count total collected tests for backend tests
    pytest = shutil.which("pytest")
    if not pytest:
        return None, None

    all_out = run_cmd([pytest, "-q", "--collect-only"])  # collects all tests in repo
    m = re.search(r"collected (\d+) items", all_out)
    total = int(m.group(1)) if m else None

    # Count ISP before/after cases
    before_out = run_cmd([pytest, "-q", "--collect-only", str(TEST_DIR / "test_export_service_isp_before.py")])
    after_out = run_cmd([pytest, "-q", "--collect-only", str(TEST_DIR / "test_export_service_isp_after.py")])
    before = int(re.search(r"collected (\d+) items", before_out).group(1)) if re.search(r"collected (\d+) items", before_out) else None
    after = int(re.search(r"collected (\d+) items", after_out).group(1)) if re.search(r"collected (\d+) items", after_out) else None

    return total, (before, after)


def run_pytest_with_coverage():
    pytest = shutil.which("pytest")
    if not pytest:
        return None

    cmd = [pytest, "-q", "--cov=file_processing.services", "--cov-report=xml"]
    out = run_cmd(cmd)
    cov_percent = None
    m = re.search(r"coverage:.*?(\d+)%", out)
    if m:
        cov_percent = int(m.group(1))
    # fallback: try reading coverage.xml
    cov_xml = ROOT / "coverage.xml"
    if cov_xml.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(str(cov_xml))
            root = tree.getroot()
            metrics = root.find("metrics")
            if metrics is not None and "line-rate" in metrics.attrib:
                rate = float(metrics.attrib["line-rate"]) * 100
                cov_percent = int(round(rate))
        except Exception:
            pass

    return cov_percent, out


def run_mutation_testing():
    mutmut = shutil.which("mutmut")
    if not mutmut:
        return None, None

    # Run mutations for the export_service module only (fastest)
    module_path = ROOT / "file_processing" / "services" / "export_service.py"
    run_cmd([mutmut, "run", "--paths-to-mutate", str(module_path)])
    results = run_cmd([mutmut, "results", "--summary"])  # summary output

    # Try to parse survived/killed/total
    survived = None
    killed = None
    total = None
    m_tot = re.search(r"Ran (\d+) mutations?", results)
    if m_tot:
        total = int(m_tot.group(1))
    m_surv = re.search(r"Survived:\s*(\d+)", results)
    m_kill = re.search(r"Killed:\s*(\d+)", results)
    if m_surv:
        survived = int(m_surv.group(1))
    if m_kill:
        killed = int(m_kill.group(1))

    score = None
    if total is not None and survived is not None:
        killed = total - survived if killed is None else killed
        score = int(round((killed / total) * 100)) if total > 0 else 0

    return score, results


def write_report(total_tests, isp_counts, cov_percent, mut_score):
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Test Metrics Report\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Collected tests (total): {total_tests}\n")
        if isp_counts and isp_counts[0] is not None:
            f.write(f"- ISP before test cases: {isp_counts[0]}\n")
        if isp_counts and isp_counts[1] is not None:
            f.write(f"- ISP after test cases: {isp_counts[1]}\n")
        f.write("\n")
        f.write("## Metrics Table\n\n")
        f.write("| Metric | Sebelum | Sesudah |\n")
        f.write("|---|---:|---:|\n")
        before = isp_counts[0] if isp_counts else "-"
        after = isp_counts[1] if isp_counts else "-"
        f.write(f"| Test Case Count | {before} | {after} |\n")
        cov_display = f"{cov_percent}%" if cov_percent is not None else "-"
        f.write(f"| Code Coverage | - | {cov_display} |\n")
        mut_display = f"{mut_score}%" if mut_score is not None else "-"
        f.write(f"| Mutation Score | - | {mut_display} |\n")
        f.write("\n")
        f.write("## Notes and References\n\n")
        f.write("- ISP (Input Space Partitioning): reduced redundant combinations. See test_export_service_isp_before.py and _after.py.\n")
        f.write("- CFG and cyclomatic complexity: use `radon cc` to compute best practice thresholds.\n")
        f.write("- Mutation testing: use `mutmut` for Python to measure test quality.\n")
        f.write("\n")
        f.write("## How to reproduce locally\n\n")
        f.write("Run the following from the repo root:\n\n")
        f.write("```bash\n")
        f.write("pip install -r backend/requirements-dev.txt\n")
        f.write("cd backend\n")
        f.write("pytest -q --cov=file_processing.services --cov-report=xml\n")
        f.write("mutmut run --paths-to-mutate file_processing/services/export_service.py\n")
        f.write("mutmut results --summary\n")
        f.write("python scripts/generate_test_report.py\n")
        f.write("```\n")


def main():
    total, isp = collect_test_counts()
    cov_percent, py_out = run_pytest_with_coverage()
    mut_score, mut_out = run_mutation_testing()

    write_report(total, isp, cov_percent, mut_score)

    print("Report written to:", REPORT_MD)
    if cov_percent is not None:
        print("Coverage:", cov_percent)
    if mut_score is not None:
        print("Mutation score:", mut_score)


if __name__ == "__main__":
    main()
