import re
import json

def _normalize_report_text(raw_text: str) -> str:
    lines = raw_text.splitlines()
    normalized = []
    for line in lines:
        stripped = line.strip()
        stripped = re.sub(r"^[-*>#]+\s+", "", stripped)
        stripped = re.sub(r"\*\*(Problem|Fix)\*\*", r"\1", stripped, flags=re.IGNORECASE)
        normalized.append(stripped)
    return "\n".join(normalized)


def parse_report(raw_text: str) -> dict:
    """
    Parses the LLM's plain text report into a structured dictionary.
    Handles both Single and Multi-Problem formats.
    """
    problems = []

    text = _normalize_report_text(raw_text)

    # Check for multi-problem format
    multi_pattern = re.compile(
        r"Problem\s*\d*\s*:?\s*(.*?)\s*Fix\s*\d*\s*:?\s*(.*?)(?=Problem\s*\d*\s*:|$)",
        re.DOTALL | re.IGNORECASE
    )

    matches = multi_pattern.findall(text)
    if matches and len(matches) > 1:
        for problem, fix in matches:
            problems.append({
                "problem": problem.strip(),
                "fix": fix.strip()
            })
    else:
        # Fallback to single problem format
        single_pattern = re.compile(
            r"Problem\s*\d*\s*:?\s*(.*?)\s*Fix\s*\d*\s*:?\s*(.*?)$",
            re.DOTALL | re.IGNORECASE
        )
        match = single_pattern.search(text)
        if match:
            problems.append({
                "problem": match.group(1).strip(),
                "fix": match.group(2).strip()
            })

    return {"problems": problems}


def to_json_report(report_dict: dict, metadata: dict, raw_report: str | None = None, parse_warning: str | None = None) -> str:
    """
    Wraps the parsed report and metadata into a final JSON string.
    """
    payload = {
        "brytlog_crash_report": {
            "metadata": metadata,
            "report": report_dict["problems"]
        }
    }
    if raw_report is not None:
        payload["brytlog_crash_report"]["raw_report"] = raw_report
    if parse_warning:
        payload["brytlog_crash_report"]["parse_warning"] = parse_warning
    return json.dumps(payload, indent=2)
