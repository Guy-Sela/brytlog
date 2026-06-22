import os, sys, json
from pathlib import Path

CONFIG_FILE = Path.home() / ".brytlog.json"

def save_user_config(data: dict):
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=4))

save_user_config({"provider": "openai", "model": "gpt-4o-mini"})
print("Saved")
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    print(f.read())
