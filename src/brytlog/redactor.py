import re

PATTERNS = [
    # --- High-Confidence Specific Signatures ---
    # JWTs
    (re.compile(r'ey[a-zA-Z0-9_-]{2,}\.[a-zA-Z0-9_-]{2,}\.[a-zA-Z0-9_-]{2,}'), '[REDACTED_JWT]'),
    # Generic API Keys / Bearer Tokens (e.g. sk-...)
    (re.compile(r'\bsk-[a-zA-Z0-9]{20,}\b'), '[REDACTED_API_KEY]'),
    # AWS Access Key IDs
    (re.compile(r'\b(AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b'), '[REDACTED_AWS_KEY_ID]'),
    # Google/GCP API Key
    (re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'), '[REDACTED_GCP_KEY]'),
    # GitHub Tokens
    (re.compile(r'\bghp_[a-zA-Z0-9]{36}\b'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'\bgithub_pat_[a-zA-Z0-9]{82}\b'), '[REDACTED_GITHUB_TOKEN]'),
    # Stripe Secret Key (including Restricted Keys)
    (re.compile(r'\b(sk|rk)_live_[0-9a-zA-Z]{24}\b'), r'[REDACTED_STRIPE_KEY]'),
    # Slack Token
    (re.compile(r'\bxox[baprs]-[0-9a-zA-Z]{10,48}\b'), '[REDACTED_SLACK_TOKEN]'),
    # Generic DB URLs (e.g. postgres://user:pass@...)
    (re.compile(r'\b[a-z]+://[^:]+:[^@\s]+@[^\s]+\b'), '[REDACTED_DB_URL]'),
    # Passwords in URLs (e.g. http://user:pass@host)
    (re.compile(r'([a-zA-Z][a-zA-Z0-9+.-]+://[^:]+:)([^@]+)(@[^/]+)'), r'\1[REDACTED_PASSWORD]\3'),
    # Private Keys
    (re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----', re.DOTALL), '[REDACTED_PRIVATE_KEY]'),

    # --- PII & Network ---
    # Emails
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),
    # IPv4 Addresses
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[REDACTED_IP]'),
    # IPv6 Addresses
    (re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}\b'), '[REDACTED_IP_V6]'),
    # Credit Card (Basic)
    (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b'), '[REDACTED_CARD]'),

    # --- System & Context-Aware ---
    # Potentially sensitive user directories in paths
    (re.compile(r'([/\\])(Users|home)([/\\])([^/\\ ]+)'), r'\1\2\3[USER]'),
    # Secret assignments (key=val, key: val). Handles hyphens/underscores.
    (re.compile(
        r'(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|credential|auth[_-]?token|pwd|private[_-]?key|session[_-]?id|db[_-]?url|auth|api[_-]?secret)\b'
        r'\s*[:=]\s*'
        r'(?!\[REDACTED)'
        r'["\']?([^"\'\s,;&]+)["\']?'
    ), r'\1=[REDACTED]'),
    # CLI flag secrets with a space-separated value (e.g. --api-key 1234).
    # Requires a leading dash to avoid false positives on prose/code.
    (re.compile(
        r'(?i)(--?(?:password|passwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|credential|auth[_-]?token|pwd|private[_-]?key|session[_-]?id|db[_-]?url|api[_-]?secret))'
        r'\s+'
        r'(?!\[REDACTED)'
        r'["\']?([^"\'\s,;&-][^"\'\s,;&]*)["\']?'
    ), r'\1 [REDACTED]'),
]

def redact(text: str) -> str:
    if not text:
        return text
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
