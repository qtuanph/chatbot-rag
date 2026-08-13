"""
Master Unit Test Runner for Audit Bug Fix Verification
Executes all unit tests in tests/unit/ and outputs structured test results.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def run_all_unit_tests():
    print("=" * 80)
    print("         🔍 AUDIT FIXES & SYSTEM REGRESSION UNIT TEST SUITE            ")
    print("=" * 80)

    loader = unittest.TestLoader()
    start_dir = str(Path(__file__).resolve().parent)
    suite = loader.discover(start_dir, pattern="test_audit_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("                        TEST EXECUTION SUMMARY                         ")
    print("=" * 80)
    print(f"Total Tests Run   : {result.testsRun}")
    print(f"Passed Tests      : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed Tests      : {len(result.failures)}")
    print(f"Errored Tests     : {len(result.errors)}")
    print("Status            : " + ("✅ ALL TESTS PASSED!" if result.wasSuccessful() else "❌ FAILURES DETECTED!"))
    print("=" * 80)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_all_unit_tests()
    sys.exit(exit_code)
