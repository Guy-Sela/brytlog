import re

KEYWORDS = re.compile(r'(?i)\b(warn|warning|error|deprecated|skip|skipped|fail|failed|exception)\b')

def scan_success_log(lines: list[str]) -> tuple[bool, str]:
    """
    Scans the logs of a successful run.
    Returns (needs_llm, payload)
    """
    if not lines:
        return False, ""

    head_lines = lines[:15]
    tail_lines = lines[-15:] if len(lines) > 15 else []

    warnings = []

    for line in lines:
        if KEYWORDS.search(line):
            warnings.append(line)
            if len(warnings) >= 50:
                break

    if not warnings:
        return False, "✅ Success. No warnings detected."

    payload = "--- Head ---\n" + "".join(head_lines)
    payload += "\n--- Warnings/Notices ---\n" + "".join(warnings)
    if tail_lines:
        payload += "\n--- Tail ---\n" + "".join(tail_lines)

    return True, payload
