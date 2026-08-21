"""
Main E2E Test Runner for Glassmorphism Performance HUD.
Runs Tier 1 (Feature), Tier 2 (Boundary), Tier 3 (Interactions), and Tier 4 (Scenarios).
Outputs structured summary, latency metrics, JSON reports, and exits with 0 on 100% pass.
"""

import argparse
import io
import json
import os
import sys
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tests.tier1_feature_tests as t1
import tests.tier2_boundary_tests as t2
import tests.tier3_interaction_tests as t3
import tests.tier4_scenario_tests as t4
import tests.test_adversarial_faults as t5
import tests.test_gui_bridge as t_gui


class HUDTestResult(unittest.TextTestResult):
    """Custom TestResult tracking latency and feature groupings."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_records: List[Dict[str, Any]] = []
        self._test_start_time: float = 0.0

    def startTest(self, test):
        super().startTest(test)
        self._test_start_time = time.perf_counter()

    def addSuccess(self, test):
        super().addSuccess(test)
        duration_ms = (time.perf_counter() - self._test_start_time) * 1000.0
        self.test_records.append({
            "test_id": test.id(),
            "status": "PASS",
            "duration_ms": round(duration_ms, 3),
            "error": None,
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        duration_ms = (time.perf_counter() - self._test_start_time) * 1000.0
        self.test_records.append({
            "test_id": test.id(),
            "status": "FAIL",
            "duration_ms": round(duration_ms, 3),
            "error": self._exc_info_to_string(err, test),
        })

    def addError(self, test, err):
        super().addError(test, err)
        duration_ms = (time.perf_counter() - self._test_start_time) * 1000.0
        self.test_records.append({
            "test_id": test.id(),
            "status": "ERROR",
            "duration_ms": round(duration_ms, 3),
            "error": self._exc_info_to_string(err, test),
        })


def get_tier_suites(
    tiers: Optional[List[int]] = None,
    feature_filter: Optional[str] = None,
) -> Tuple[unittest.TestSuite, Dict[str, List[str]]]:
    """Assemble test suite based on requested tiers and feature filters."""
    suite = unittest.TestSuite()
    tier_mapping: Dict[str, List[str]] = {
        "Tier 1 (Feature Coverage)": [],
        "Tier 2 (Boundary & Fallback)": [],
        "Tier 3 (Cross-Feature Interactions)": [],
        "Tier 4 (Real-World Scenarios)": [],
        "Tier 5 (Adversarial & Chaos)": [],
    }

    loader = unittest.TestLoader()

    # Tier 1 + GUI Bridge tests
    if not tiers or 1 in tiers:
        t1_suite = loader.loadTestsFromModule(t1)
        for test_case in t1_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 1 (Feature Coverage)"].append(test.id())

        gui_suite = loader.loadTestsFromModule(t_gui)
        for test_case in gui_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 1 (Feature Coverage)"].append(test.id())

    # Tier 2
    if not tiers or 2 in tiers:
        t2_suite = loader.loadTestsFromModule(t2)
        for test_case in t2_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 2 (Boundary & Fallback)"].append(test.id())

    # Tier 3
    if not tiers or 3 in tiers:
        t3_suite = loader.loadTestsFromModule(t3)
        for test_case in t3_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 3 (Cross-Feature Interactions)"].append(test.id())

    # Tier 4
    if not tiers or 4 in tiers:
        t4_suite = loader.loadTestsFromModule(t4)
        for test_case in t4_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 4 (Real-World Scenarios)"].append(test.id())

    # Tier 5
    if not tiers or 5 in tiers:
        t5_suite = loader.loadTestsFromModule(t5)
        for test_case in t5_suite:
            for test in test_case:
                if not feature_filter or feature_filter.lower() in test.id().lower():
                    suite.addTest(test)
                    tier_mapping["Tier 5 (Adversarial & Chaos)"].append(test.id())

    return suite, tier_mapping


def print_hud_banner():
    banner = r"""
+=============================================================================+
|             NETA_OS :: GLASSMORPHISM PERFORMANCE HUD TEST RUNNER            |
|                     Automated 4-Tier Verification Engine                    |
+=============================================================================+"""
    print(banner)


def run_e2e_suite(
    tiers: Optional[List[int]] = None,
    feature_filter: Optional[str] = None,
    verbose: bool = False,
    json_report_path: Optional[str] = None,
) -> int:
    """Execute test suite and format HUD report."""
    print_hud_banner()

    suite, tier_mapping = get_tier_suites(tiers, feature_filter)
    total_loaded = suite.countTestCases()
    print(f"[*] Discovered {total_loaded} tests across selected tiers/filters.")
    if tiers:
        print(f"[*] Active Tiers: {tiers}")
    if feature_filter:
        print(f"[*] Feature Filter: {feature_filter}")
    print("-------------------------------------------------------------------------------")

    stream = sys.stdout if verbose else io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2 if verbose else 1,
        resultclass=HUDTestResult,
    )

    start_time = time.perf_counter()
    result: HUDTestResult = runner.run(suite)  # type: ignore
    elapsed_total_sec = time.perf_counter() - start_time

    passed = total_loaded - len(result.failures) - len(result.errors)
    pass_pct = (passed / total_loaded * 100.0) if total_loaded > 0 else 0.0

    # Calculate latency metrics
    durations = [r["duration_ms"] for r in result.test_records]
    avg_duration_ms = (sum(durations) / len(durations)) if durations else 0.0
    max_duration_ms = max(durations) if durations else 0.0

    print("\n+=============================================================================+")
    print("|                               EXECUTION SUMMARY                             |")
    print("+=============================================================================+")
    print(f"  Total Test Cases : {total_loaded:4d}")
    print(f"  Tests Passed     : {passed:4d}  [{pass_pct:6.2f}%]")
    print(f"  Tests Failed     : {len(result.failures):4d}")
    print(f"  Test Errors      : {len(result.errors):4d}")
    print(f"  Total Duration   : {elapsed_total_sec:6.3f}s")
    print(f"  Avg Test Latency : {avg_duration_ms:6.3f}ms")
    print(f"  Max Test Latency : {max_duration_ms:6.3f}ms")
    print("+-----------------------------------------------------------------------------+")

    # Breakdown by tier
    print("| TIER BREAKDOWN                                                              |")
    for tier_name, test_ids in tier_mapping.items():
        if test_ids:
            tier_records = [r for r in result.test_records if r["test_id"] in test_ids]
            t_pass = sum(1 for r in tier_records if r["status"] == "PASS")
            t_total = len(tier_records)
            t_pct = (t_pass / t_total * 100.0) if t_total > 0 else 0.0
            print(f"  {tier_name:<38}: {t_pass:3d}/{t_total:3d} passed ({t_pct:5.1f}%)")
    print("+=============================================================================+")

    if result.wasSuccessful():
        print("| STATUS: [PASS] 100% TEST SUITE VERIFICATION SUCCESSFUL                      |")
        print("+=============================================================================+\n")
    else:
        print("| STATUS: [FAIL] VERIFICATION FAILED WITH DEFECTS                             |")
        print("+=============================================================================+\n")
        if not verbose and (result.failures or result.errors):
            print("Failure Details:")
            for test, err in result.failures:
                print(f"[FAIL] {test.id()}:\n{err}")
            for test, err in result.errors:
                print(f"[ERROR] {test.id()}:\n{err}")

    # Generate JSON Report if requested
    if json_report_path:
        report_data = {
            "timestamp": time.time(),
            "total_tests": total_loaded,
            "passed": passed,
            "failed": len(result.failures),
            "errors": len(result.errors),
            "pass_percentage": round(pass_pct, 2),
            "total_duration_sec": round(elapsed_total_sec, 4),
            "avg_latency_ms": round(avg_duration_ms, 3),
            "max_latency_ms": round(max_duration_ms, 3),
            "status": "PASS" if result.wasSuccessful() else "FAIL",
            "tier_breakdown": {
                tier_name: {
                    "count": len(test_ids),
                    "passed": sum(1 for r in result.test_records if r["test_id"] in test_ids and r["status"] == "PASS"),
                }
                for tier_name, test_ids in tier_mapping.items()
                if test_ids
            },
            "records": result.test_records,
        }
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"[+] JSON Test Report exported to: {json_report_path}")

    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description="Glassmorphism Performance HUD E2E Test Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4, 5], nargs="+", help="Specific tiers to run (1-5)")
    parser.add_argument("--feature", type=str, help="Filter tests by feature keyword (e.g. F04, CPU, GPU)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test execution output")
    parser.add_argument("--json-report", type=str, help="Path to write JSON test report")

    args = parser.parse_args()
    exit_code = run_e2e_suite(
        tiers=args.tier,
        feature_filter=args.feature,
        verbose=args.verbose,
        json_report_path=args.json_report,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
