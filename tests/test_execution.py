import subprocess
import sys
import os
import time
from brytlog import stream_capture, scanner

def test_stream_capture():
    # Simple python script that prints to stdout and stderr
    script = "import sys; print('hello'); print('error', file=sys.stderr); sys.exit(1)"
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,  # Match production: binary mode with no buffering
    )

    unified_acc = stream_capture.StreamAccumulator()
    import threading
    t1 = threading.Thread(target=stream_capture.stream_pipe, args=(proc.stdout, unified_acc, None))
    t2 = threading.Thread(target=stream_capture.stream_pipe, args=(proc.stderr, unified_acc, None))

    t1.start()
    t2.start()

    exit_code = proc.wait()
    t1.join()
    t2.join()

    content = unified_acc.get_content()
    assert exit_code == 1
    assert "hello" in content
    assert "error" in content

def test_payload_extraction():
    lines = [f"line {i}" for i in range(100)]
    output = "\n".join(lines)
    tailed = stream_capture.extract_payload(output, 20)

    assert "line 0" in tailed
    assert "line 99" in tailed
    assert "truncated" in tailed.lower()
    assert len(tailed.splitlines()) <= 23 # 10 head + 1 separator + 10 tail (approx)

def brytlog_cmd(args, input=None):
    env = os.environ.copy()
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["PYTHONIOENCODING"] = "utf-8"

    # Set fake credentials to avoid the wizard in automated tests
    env["BRYTLOG_API_KEY"] = "fake-key"
    env["BRYTLOG_PROVIDER"] = "openai"

    return subprocess.run(
        [sys.executable, "-m", "brytlog.cli"] + args,
        input=input,
        env=env,
        text=True,
        capture_output=True
    )

def test_quiet_mode_aborts_interactive_prompts():
    """
    Ensures that when running in quiet mode (default), interactive prompts
    are aborted with an EOFError because stdin is set to DEVNULL.
    This prevents the AI agent from getting stuck on an invisible prompt.
    """
    script = "x = input('prompt: '); print(f'input was {x}')"
    # By default quiet mode is on
    res = brytlog_cmd([sys.executable, "-c", script])
    assert res.returncode != 0
    # Python raises an EOFError when input() is called on an empty stdin/DEVNULL
    # We check stdout or stderr for the error message
    assert "EOFError" in res.stderr or "EOFError" in res.stdout or "brytlog crash report" in res.stderr

def test_no_quiet_mode_allows_stdin():
    """
    Ensures that with --no-quiet, stdin is available to the child process.
    """
    script = "x = input('prompt: '); print(f'input was {x}')"
    res = brytlog_cmd(["--no-quiet", sys.executable, "-c", script], input="hello\n")
    assert res.returncode == 0
    assert "input was hello" in res.stdout

def test_scanner_success_no_warnings():
    lines = ["Starting...\n", "Doing work...\n", "Done.\n"]
    needs_llm, payload = scanner.scan_success_log(lines)
    assert not needs_llm
    assert "Success" in payload

def test_scanner_success_with_warnings():
    lines = ["Starting...\n", "Warning: something deprecated\n", "Done.\n"]
    needs_llm, payload = scanner.scan_success_log(lines)
    assert needs_llm
    assert "Warning: something deprecated" in payload

def run():
    tests = [
        test_stream_capture,
        test_payload_extraction,
        test_quiet_mode_aborts_interactive_prompts,
        test_no_quiet_mode_allows_stdin,
        test_scanner_success_no_warnings,
        test_scanner_success_with_warnings
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
