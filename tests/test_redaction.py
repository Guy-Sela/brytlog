from brytlog import redactor

def test_jwt():
    text = "User token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoyNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    redacted = redactor.redact(text)
    assert "[REDACTED_JWT]" in redacted
    assert "eyJhbGci" not in redacted

def test_api_key():
    text = "Starting with key sk-1234567890abcdef1234567890abcdef"
    redacted = redactor.redact(text)
    assert "[REDACTED_API_KEY]" in redacted
    assert "sk-123" not in redacted

def test_email():
    text = "Contact us at support@example.com for help"
    redacted = redactor.redact(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "support@example.com" not in redacted

def test_ip():
    text = "Connected to 192.168.1.1 on port 80"
    redacted = redactor.redact(text)
    assert "[REDACTED_IP]" in redacted
    assert "192.168.1.1" not in redacted

def test_path():
    text = "Error in /Users/admin/dev/brytlog/main.py"
    redacted = redactor.redact(text)
    assert "/Users/[USER]/dev/brytlog/main.py" in redacted
    assert "admin" not in redacted

    # Windows path test
    text_win = "Error in C:\\Users\\admin\\dev\\brytlog\\main.py"
    redacted_win = redactor.redact(text_win)
    assert "C:\\Users\\[USER]\\dev\\brytlog\\main.py" in redacted_win
    assert "admin" not in redacted_win

def run():
    tests = [
        test_jwt,
        test_api_key,
        test_email,
        test_ip,
        test_path
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
