import json
import os
import sys
from pathlib import Path

# Config file path
if os.environ.get("HOME"):
    _home = Path(os.environ.get("HOME"))
else:
    _home = Path(os.environ.get("USERPROFILE", Path.home()))
CONFIG_FILE = _home / ".brytlog.json"

def default_config() -> dict:
    return {
        "provider": "",
        "model": "",
        "api_key": "",
        "api_base_url": "",
        "system_prompt": "",
        "temperature": 0.2,
        "max_output": 1000,
        "max_input": 4000,
        "save_report": True,
        "save_raw_log": True,
        "quiet": True,
        "latest_pypi_version": "",
        "last_update_check": 0,
    }


def load_user_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            print(
                f"\n⚠️  Warning: Config file is corrupted or unreadable: {CONFIG_FILE}\n"
                "Reverting to default values. You can run `brytlog --reset` or `brytlog --config` to fix it.",
                file=sys.stderr
            )
            return default_config()
    return default_config()

def save_user_config(data: dict):
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if os.name == 'nt':
        flags |= os.O_BINARY  # Prevent line-ending translation on Windows
    fd = os.open(CONFIG_FILE, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(json.dumps(data, indent=4).encode("utf-8"))

def reset_config():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()

_user_config = load_user_config()

# Known OpenAI-compatible base URLs
KNOWN_PROVIDERS = {
    "openai": "https://api.openai.com/v1",
    "grok": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
    # Google and Anthropic use custom API formats and are handled separately.
}

# LLM Configuration (Hierarchy: Env Var -> ~/.brytlog.json -> Default)
PROVIDER = os.environ.get("BRYTLOG_PROVIDER", _user_config.get("provider", ""))
MODEL = os.environ.get("BRYTLOG_MODEL", _user_config.get("model", ""))
API_KEY = os.environ.get("BRYTLOG_API_KEY", _user_config.get("api_key", ""))
API_BASE_URL = os.environ.get("BRYTLOG_API_BASE_URL", _user_config.get("api_base_url", ""))

# Advanced Configuration
SYSTEM_PROMPT = os.environ.get("BRYTLOG_SYSTEM_PROMPT", _user_config.get("system_prompt", ""))
TEMPERATURE = float(os.environ.get("BRYTLOG_TEMPERATURE", _user_config.get("temperature", 0.2)))
MAX_OUTPUT = int(os.environ.get("BRYTLOG_MAX_OUTPUT", _user_config.get("max_output", 1000)))

# Log settings
SAVE_REPORT = os.environ.get("BRYTLOG_SAVE_REPORT", str(_user_config.get("save_report", True))).lower() == "true"
SAVE_RAW_LOG = os.environ.get("BRYTLOG_SAVE_RAW_LOG", str(_user_config.get("save_raw_log", True))).lower() == "true"
QUIET = os.environ.get("BRYTLOG_QUIET", str(_user_config.get("quiet", True))).lower() == "true"
REPORTS_DIR_NAME = "brytlog-reports"
RAW_LOG_DIR_NAME = "brytlog-raw"
MAX_INPUT = int(os.environ.get("BRYTLOG_MAX_INPUT", _user_config.get("max_input", 4000)))
