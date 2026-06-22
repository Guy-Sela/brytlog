"""Brytlog custom test runner.

Purpose
- Provides a single, zero-dependency entrypoint to run Brytlog's test modules without pytest.
- Intended for quick local validation and CI (continuous integration) sanity checks.

How it works
- Adds `../src` and this directory to `sys.path` so modules can be imported directly.
- Imports each module listed in `test_modules`.
- If the module exposes a `run()` function, it calls it and expects a boolean result.
- If there is no `run()`, the module is treated as a no-op and counted as pass.
- Any exception is caught, printed with a traceback, and counted as fail.

Notes
- This runner is intentionally simple and only runs the modules explicitly listed in `test_modules` (no automatic discovery by filename/pattern).
- Keep test modules side-effect free on import (no interactive prompts/network) so CI stays deterministic.
"""

import sys
import os
import traceback
from datetime import datetime

# Add src to path so we can import brytlog modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

def run_module(module_name):
    print(f"\n>>> Running module: {module_name}")
    try:
        module = __import__(module_name)
        if hasattr(module, 'run'):
            return module.run()
        else:
            print(f"      [SKIP] Module {module_name} has no 'run' function.")
            return True
    except Exception as e:
        print(f"      [ERROR] Failed to run module {module_name}:")
        traceback.print_exc()
        return False

def main():
    start_time = datetime.now()
    print("=" * 60)
    print(f"BRYTLOG CUSTOM TEST SUITE")
    print(f"Started at: {start_time}")
    print("=" * 60)

    # List of test modules
    test_modules = [
        "test_redaction",
        "test_execution",
        "test_config",
        "test_llm_quality",
        "test_wizard"
    ]

    # Add tests directory to path for imports
    sys.path.append(os.path.dirname(__file__))

    results = {}
    for mod in test_modules:
        success = run_module(mod)
        results[mod] = success

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("-" * 60)
    passed = 0
    failed = 0
    for mod, res in results.items():
        status = "PASSED" if res else "FAILED"
        print(f"{mod:25}: {status}")
        if res:
            passed += 1
        else:
            failed += 1

    print("-" * 60)
    print(f"TOTAL: {len(test_modules)} | PASSED: {passed} | FAILED: {failed}")
    print(f"Duration: {duration}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
