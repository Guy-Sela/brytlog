import sys
import unittest.mock as mock
import builtins
import io

from brytlog import wizard
from brytlog import config

def test_wizard():
    # Mock inputs
    inputs = [
        "2", # OpenAI
        "gpt-4o-mini", # model
        "sk-12345", # API key
    ]

    def mock_input(prompt=""):
        print(prompt, end="")
        return inputs.pop(0)

    # Mock getpass
    def mock_getpass(prompt=""):
        print(prompt, end="")
        return inputs.pop(0)

    # Mock summarize_crash to pass verification
    def mock_summarize_crash(*args, **kwargs):
        return "OK"

    # Mock config.save_user_config and Path.read_text to avoid writing to disk
    with mock.patch("builtins.input", mock_input), \
         mock.patch("getpass.getpass", mock_getpass), \
         mock.patch("brytlog.wizard.summarize_crash", mock_summarize_crash), \
         mock.patch("brytlog.config.save_user_config"), \
         mock.patch("pathlib.Path.read_text", return_value='{"api_key": "sk-12345", "model": "gpt-4o-mini", "provider": "openai"}'):
         wizard.run_setup_wizard(is_onboarding=True)

    print("      (Config check mocked for deterministic non-interactive run)")

def run():
    try:
        test_wizard()
        print("      [PASS] test_wizard")
        return True
    except Exception as e:
        print(f"      [FAIL] test_wizard: {e}")
        return False

if __name__ == "__main__":
    run()
