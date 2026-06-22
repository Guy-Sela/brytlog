import os
import importlib
from brytlog import config

def test_config_precedence():
    # Mock environment variable
    os.environ["BRYTLOG_PROVIDER"] = "test-env-provider"

    # Reload config to pick up env var
    importlib.reload(config)

    try:
        assert config.PROVIDER == "test-env-provider"
    finally:
        # Clean up
        if "BRYTLOG_PROVIDER" in os.environ:
            del os.environ["BRYTLOG_PROVIDER"]
        importlib.reload(config)

def run():
    tests = [
        test_config_precedence
    ]

    success = True
    for t in tests:
        try:
            t()
            print(f"      [PASS] {t.__name__}")
        except Exception as e:
            print(f"      [FAIL] {t.__name__}: {e}")
            success = False
    return success
