import argparse
import re
import shlex
import shutil
import subprocess
import sys
import threading
import os
from datetime import datetime
from pathlib import Path
import json

from . import __version__, config, summarizer, wizard
from . import redactor
from . import stream_capture
from . import parser as report_parser

def get_reports_dir() -> Path:
    return Path.cwd() / config.REPORTS_DIR_NAME

def get_raw_log_dir() -> Path:
    return Path.cwd() / config.RAW_LOG_DIR_NAME

def timestamped_path(directory: Path, ext: str = ".log") -> Path:
    # Use microseconds + PID to avoid collisions in concurrent runs
    ts = datetime.now().isoformat(timespec='microseconds').replace(':', '-')
    pid = os.getpid()
    return directory / f"{ts}_{pid}{ext}"

def open_config_in_editor():
    """Opens the config file in the default editor, ensuring it has the correct structure."""
    config_path = config.CONFIG_FILE

    current = config.load_user_config()

    # Ensure all keys are present with defaults before opening
    updated_data = {
        "provider": current.get("provider") or config.PROVIDER or "",
        "model": current.get("model") or config.MODEL or "",
        "temperature": current.get("temperature", config.TEMPERATURE),
        "api_key": current.get("api_key") or config.API_KEY or "",
        "api_base_url": current.get("api_base_url") or config.API_BASE_URL or "",
        "max_input": current.get("max_input", config.MAX_INPUT),
        "max_output": current.get("max_output", config.MAX_OUTPUT),
        "system_prompt": current.get("system_prompt") or summarizer.DEFAULT_SYSTEM_PROMPT.strip(),
        "save_report": current.get("save_report", config.SAVE_REPORT),
        "save_raw_log": current.get("save_raw_log", config.SAVE_RAW_LOG),
        "quiet": current.get("quiet", config.QUIET),
    }
    config.save_user_config(updated_data)

    print(f"Opening config: {config_path}")
    try:
        if os.name == "nt":
            # Windows: use os.startfile, but catch errors gracefully
            try:
                os.startfile(str(config_path))
            except OSError:
                # Fallback: use notepad if no default app
                subprocess.run(["notepad", str(config_path)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(config_path)], check=True)
        else:
            subprocess.run(["xdg-open", str(config_path)], check=True)
    except Exception as e:
        print(f"Could not open config: {e}")
        print(f"Edit manually: {config_path}")

def run(
    argv: list[str],
    provider: str,
    model: str,
    api_key: str | None,
    api_base_url: str | None,
    save_report: bool,
    save_raw_log: bool,
    quiet: bool,
    json_output: bool,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_output: int = 1000,
    max_input: int = 4000
) -> int:
    if not argv:
        print("brytlog: no command provided.", file=sys.stderr)
        return 1

    use_shell = len(argv) == 1 and any(char in argv[0] for char in " |&;<>()$^%")

    # Check if command exists before trying to run it (prevents some platform-specific subprocess issues)
    if not use_shell and argv:
        cmd_name = argv[0]
        if not shutil.which(cmd_name):
            print(f"brytlog: command not found: {cmd_name}", file=sys.stderr)
            return 127

    # Handle Windows shell execution
    if os.name == 'nt' and use_shell:
        # On Windows, use cmd.exe which is more compatible with bash-like syntax
        # Wrap the command string in quotes to handle spaces and special chars
        exec_args = ["cmd.exe", "/c"] + argv
        use_shell = False
    else:
        exec_args = argv[0] if use_shell else argv

    if quiet and not json_output:
        print("brytlog: running (quiet mode)...", file=sys.stderr)

    try:
        proc = subprocess.Popen(
            exec_args,
            shell=use_shell,
            stdin=subprocess.DEVNULL if quiet else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except (OSError, FileNotFoundError) as e:
        print(f"brytlog: failed to start command: {e}", file=sys.stderr)
        return 127

    unified_acc = stream_capture.StreamAccumulator()

    raw_log_file = None
    started_threads = []
    try:
        if save_raw_log:
            try:
                raw_log_dir = get_raw_log_dir()
                raw_log_dir.mkdir(parents=True, exist_ok=True)
                raw_log_path = timestamped_path(raw_log_dir, ".txt")
                raw_log_file = open(raw_log_path, "w", encoding="utf-8")
            except OSError as e:
                print(f"brytlog: warning: could not open raw log file: {e}", file=sys.stderr)
                save_raw_log = False

        out_stream = None if quiet else sys.stdout
        err_stream = None if quiet else sys.stderr

        file_lock = threading.Lock()

        t1 = threading.Thread(target=stream_capture.stream_pipe, args=(proc.stdout, unified_acc, out_stream, raw_log_file, file_lock))
        t2 = threading.Thread(target=stream_capture.stream_pipe, args=(proc.stderr, unified_acc, err_stream, raw_log_file, file_lock))

        t1.start()
        started_threads.append(t1)
        t2.start()
        started_threads.append(t2)

        try:
            return_code = proc.wait()
        except KeyboardInterrupt:
            try:
                return_code = proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                return_code = proc.wait()
            return 130
    finally:
        for t in started_threads:
            t.join()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        if raw_log_file:
            raw_log_file.close()

    if return_code < 0:
        return_code = 128 + abs(return_code)

    if return_code == 0:
        output_full = unified_acc.get_content()
        lines = output_full.splitlines(keepends=True)
        from . import scanner
        needs_llm, payload = scanner.scan_success_log(lines)

        if not needs_llm:
            if quiet:
                print("\n✅ Success. No warnings detected.", file=sys.stderr)
            return 0

        # Needs LLM summary
        command_str_raw = shlex.join(argv)
        command_str = redactor.redact(command_str_raw)
        payload = redactor.redact(payload)

        raw_report = summarizer.summarize_success(
            command=command_str,
            payload=payload,
            provider=provider,
            model=model,
            api_key=api_key,
            api_base_url=api_base_url,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output=max_output
        )

        try:
            use_colors = sys.stderr.isatty() and not os.environ.get("NO_COLOR")
        except (AttributeError, OSError):
            use_colors = False

        DIM = "\033[37m" if use_colors else ""
        BLD = "\033[1m" if use_colors else ""
        RST = "\033[0m" if use_colors else ""

        term_width = shutil.get_terminal_size((80, 20)).columns
        bar_len = 60
        indent = " " * max(0, (term_width - bar_len) // 2)

        if json_output:
            import json
            success_json = json.dumps({
                "status": "success_with_warnings",
                "report": raw_report,
                "metadata": {
                    "command": command_str,
                    "exit_code": 0
                }
            }, indent=2)
            print("\n\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
            print(success_json, file=sys.stdout)
            print("\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
        else:
            title_text = "brytlog nuance extract"
            full_title = f"🧠📜 {BLD}{title_text}{RST}"
            title_indent = " " * max(0, (term_width - len(title_text) - 4) // 2)

            print("\n\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
            print(title_indent + full_title + "\n", file=sys.stderr)
            print(raw_report, file=sys.stderr)
            print("\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)

        return 0

    if return_code >= 128:
        return return_code

    # --- Crash detected ---
    try:
        output_full = unified_acc.get_content()

        command_str_raw = shlex.join(argv)
        command_str = redactor.redact(command_str_raw)
        timestamp = datetime.now().isoformat(timespec="seconds")
        tailed_output = stream_capture.extract_payload(output_full, max_input)

        # Redact sensitive data from the output before it goes to the LLM or logs
        tailed_output = redactor.redact(tailed_output)

        raw_report = summarizer.summarize_crash(
            command=command_str,
            output=tailed_output,
            provider=provider,
            model=model,
            api_key=api_key,
            api_base_url=api_base_url,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output=max_output
        )

        # Parse report
        parsed = report_parser.parse_report(raw_report)

        # Prepare metadata for logs/JSON
        metadata = {
            "command": command_str,
            "timestamp": timestamp,
            "exit_code": return_code,
            "provider": provider,
            "model": model
        }

        try:
            use_colors = sys.stderr.isatty() and not os.environ.get("NO_COLOR")
        except (AttributeError, OSError):
            use_colors = False
        RED = "\033[31m" if use_colors else ""
        GRN = "\033[32m" if use_colors else ""
        BRN = "\033[33m" if use_colors else ""
        DIM = "\033[37m" if use_colors else ""
        BLD = "\033[1m" if use_colors else ""
        RST = "\033[0m" if use_colors else ""

        term_width = shutil.get_terminal_size((80, 20)).columns
        bar_len = 60
        indent = " " * max(0, (term_width - bar_len) // 2)

        log_path = None
        if save_report:
            try:
                log_dir = get_reports_dir()
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = timestamped_path(log_dir)
            except OSError as e:
                print(f"brytlog: warning: could not create reports directory: {e}", file=sys.stderr)
                save_report = False
                log_path = None

        if save_report:
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"Command: {redactor.redact(command_str_raw)}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Exit Code: {return_code}\n")
                    f.write("-" * 40 + "\n")
                    f.write("RAW LOG:\n")
                    f.write(redactor.redact(output_full))
                    f.write("\n" + "-" * 40 + "\n")
                    f.write("AI REPORT:\n")
                    f.write(raw_report)
            except OSError as e:
                print(f"brytlog: warning: could not save report file: {e}", file=sys.stderr)
                log_path = None

        parse_warning = None
        if json_output:
            if not parsed["problems"]:
                parse_warning = "Report format not recognized. Included raw_report as fallback."
                print(f"{BRN}⚠️  {parse_warning}{RST}", file=sys.stderr)
            final_json = report_parser.to_json_report(
                parsed,
                metadata,
                raw_report=raw_report if parse_warning else None,
                parse_warning=parse_warning
            )
            print("\n\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
            print(final_json, file=sys.stdout)
            print("\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
            if log_path:
                print(f"Full report → {log_path}", file=sys.stderr)
            if save_raw_log and raw_log_file:
                print(f"Full raw log → {raw_log_path}", file=sys.stderr)
        else:
            # Standard pretty print
            title_text = "brytlog crash report"
            full_title = f"🧠📜 {BLD}{title_text}{RST}"
            title_indent = " " * max(0, (term_width - len(title_text) - 4) // 2)

            print("\n\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
            print(title_indent + full_title + "\n", file=sys.stderr)

            if not parsed["problems"]:
                # Fallback if parsing failed or report is just text
                print(raw_report, file=sys.stderr)
            else:
                for i, p in enumerate(parsed["problems"]):
                    prefix = f" {i+1}" if len(parsed["problems"]) > 1 else ""
                    print(f"{RED}Problem{prefix}{RST}", file=sys.stderr)
                    print(p["problem"], file=sys.stderr)
                    print(f"\n{GRN}Fix{prefix}{RST}", file=sys.stderr)
                    print(p["fix"], file=sys.stderr)
                    print(file=sys.stderr)

            if log_path:
                print(f"Full report → {log_path}", file=sys.stderr)
            if save_raw_log and raw_log_file:
                print(f"Full raw log → {raw_log_path}", file=sys.stderr)

            print("\n" + indent + f"{DIM}─{RST}" * bar_len + "\n", file=sys.stderr)
    except Exception as e:
        # Guarantee we never crash the wrapper and lose the exit code
        print(f"\nbrytlog: error generating crash report: {e}", file=sys.stderr)

    return return_code

def split_args(args: list[str]) -> tuple[list[str], list[str]]:
    """
    Separates brytlog's optional flags from the command to execute.
    Stops parsing at the first argument that doesn't look like a known brytlog flag,
    or at the `--` separator.
    """
    known_flags = {
        "--provider", "--model", "--api-key", "--api-base-url",
        "--config", "--reset", "--test", "--logs", "--no-log", "--json",
        "--quiet", "--no-quiet", "--no-raw-log", "--help", "-h",
        "--version", "-v", "--upgrade"
    }
    flags_taking_values = {"--provider", "--model", "--api-key", "--api-base-url"}

    brytlog_args = []
    command_args = []

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--":
            command_args.extend(args[i+1:])
            break

        if arg in known_flags or any(arg.startswith(f"{f}=") for f in flags_taking_values):
            brytlog_args.append(arg)
            # If it's a flag that takes a space-separated value
            if arg in flags_taking_values and i + 1 < len(args) and not args[i+1].startswith("-"):
                brytlog_args.append(args[i+1])
                i += 1
        elif arg.startswith("-") and arg not in known_flags:
            # Reached a flag that belongs to the command
            command_args.extend(args[i:])
            break
        else:
            # Reached the command itself
            command_args.extend(args[i:])
            break

        i += 1

    return brytlog_args, command_args


def check_pypi_version() -> str | None:
    """Queries PyPI JSON API for the latest version of brytlog with a timeout."""
    import urllib.request
    try:
        url = "https://pypi.org/pypi/brytlog/json"
        req = urllib.request.Request(url, headers={"User-Agent": "brytlog-update-checker"})
        with urllib.request.urlopen(req, timeout=1.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["info"]["version"]
    except Exception:
        return None

def is_newer(current: str, latest: str) -> bool:
    """Compares version strings robustly without packaging dependency."""
    try:
        def parse_version(v: str) -> list[int]:
            m = re.match(r"^(\d+(?:\.\d+)*)", v)
            if m:
                return [int(x) for x in m.group(1).split(".")]
            return [0]
        return parse_version(latest) > parse_version(current)
    except Exception:
        return latest != current

def start_update_check() -> None:
    """Spawns a daemon thread to check for updates if 24 hours have passed."""
    if os.environ.get("CI") or os.environ.get("BRYTLOG_DISABLE_UPDATE_CHECK") == "1":
        return
    if not sys.stdout.isatty() and not sys.stderr.isatty():
        return
    import time
    try:
        cfg = config.load_user_config()
        last_check = cfg.get("last_update_check", 0)
        if time.time() - last_check > 86400:
            def _run():
                latest = check_pypi_version()
                if latest:
                    try:
                        current_cfg = config.load_user_config()
                        current_cfg["latest_pypi_version"] = latest
                        current_cfg["last_update_check"] = time.time()
                        config.save_user_config(current_cfg)
                    except Exception:
                        pass
            t = threading.Thread(target=_run, daemon=True)
            t.start()
    except Exception:
        pass

def show_update_notification() -> None:
    """Prints a yellow notification to stderr if a newer version is available."""
    try:
        cfg = config.load_user_config()
        latest = cfg.get("latest_pypi_version")
        if latest and is_newer(__version__, latest):
            yellow = "\033[33m"
            rst = "\033[0m"
            dim = "\033[2m"
            print(
                f"\n{yellow}💡 A new version of brytlog is available: {latest} (installed: {__version__}){rst}\n"
                f"{dim}Run 'brytlog --upgrade' to update automatically.{rst}\n",
                file=sys.stderr,
                flush=True
            )
    except Exception:
        pass


def main():
    start_update_check()
    raw_args = sys.argv[1:]
    brytlog_args, command_args = split_args(raw_args)

    parser = argparse.ArgumentParser(
        prog="brytlog",
        description="Run any command. Get a plain-English AI powered crash report if it fails.",
        usage="brytlog [options] <command> [args...]",
        add_help=True,
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit",
    )
    parser.add_argument(
        "--provider",
        default=config.PROVIDER,
        help=f"LLM provider (google, anthropic, {', '.join(config.KNOWN_PROVIDERS.keys())}, custom). Default: ({config.PROVIDER})",
    )
    parser.add_argument(
        "--model",
        default=config.MODEL,
        help=f"LLM model to use. Default: {config.MODEL}",
    )
    parser.add_argument(
        "--api-key",
        default=config.API_KEY,
        help="LLM API key (fallback: BRYTLOG_API_KEY env var)",
    )
    parser.add_argument(
        "--api-base-url",
        default=config.API_BASE_URL,
        help="Base URL for custom OpenAI-compatible endpoints (fallback: BRYTLOG_API_BASE_URL)",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Open the configuration file in the default OS application",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset configuration to defaults",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Upgrade brytlog to the latest version on PyPI (Python Package Index)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a simulated crash to test the LLM configuration",
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="List recent smartlogs from the local brytlog-reports/ directory",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable writing to the local brytlog-reports/ directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the crash report as plain JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mute the live stream of raw logs in the terminal",
    )
    parser.add_argument(
        "--no-quiet",
        action="store_true",
        help="Display the live stream of raw logs in the terminal (override quiet default)",
    )
    parser.add_argument(
        "--no-raw-log",
        action="store_true",
        help="Disable writing the raw log file",
    )

    if ("--help" in brytlog_args or "-h" in brytlog_args) and not command_args:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args(brytlog_args)

    if args.reset:
        config.reset_config()
        print("✅ Configuration reset. Run `brytlog --config` to set up again.")
        show_update_notification()
        sys.exit(0)

    if args.upgrade:
        print("🚀 Upgrading brytlog to the latest version...")
        import subprocess
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "brytlog"],
                check=True
            )
            print("✅ Upgrade successful!")
            sys.exit(res.returncode)
        except Exception as e:
            print(f"❌ Upgrade failed: {e}", file=sys.stderr)
            sys.exit(1)

    if args.logs:
        log_dir = get_reports_dir()
        if not log_dir.exists() or not any(log_dir.iterdir()):
            print(f"No smartlogs found in {config.REPORTS_DIR_NAME}/.")
            show_update_notification()
            sys.exit(0)

        log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        print("\n--- Recent Smartlogs ---")
        for f in log_files:
            print(f"- {f.name}  (modified: {datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')})")
        print()
        show_update_notification()
        sys.exit(0)

    if args.config:
        open_config_in_editor()
        show_update_notification()
        sys.exit(0)

    if args.test:
        print("🧪 Running demo test to illustrate functionality...")
        import tempfile
        import textwrap

        test_content = textwrap.dedent("""
            import sys

            def process_data(payload):
                print("Analyzing metrics...")
                # This will fail: 'total' is an int, but 'items' is a string in this payload
                average = payload['total'] / payload['items']
                return average

            def main():
                print("Starting data ingestion...")
                data = {
                    "status": "online",
                    "total": 500,
                    "items": "5"  # Bug: This should be an integer
                }
                print(f"Configuration: {data}")
                process_data(data)

            if __name__ == "__main__":
                main()
        """).strip()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
            tf.write(test_content)
            temp_path = tf.name

        command = [sys.executable, temp_path]
    else:
        command = command_args

    if not command and not args.test:
        parser.print_help()
        sys.exit(1)

    # Re-read config from disk so wizard-saved values are picked up.
    # CLI flags override file values; env vars already baked into args defaults.
    _cfg = config.load_user_config()
    provider = args.provider or _cfg.get("provider", "")
    model = args.model or _cfg.get("model", "")
    api_key = args.api_key or _cfg.get("api_key", "")
    api_base_url = args.api_base_url or _cfg.get("api_base_url", "")
    system_prompt = _cfg.get("system_prompt") or config.SYSTEM_PROMPT
    temperature = _cfg.get("temperature", config.TEMPERATURE)
    max_output = _cfg.get("max_output", config.MAX_OUTPUT)
    max_input = _cfg.get("max_input", config.MAX_INPUT)
    save_report = _cfg.get("save_report", config.SAVE_REPORT) and not args.no_log
    save_raw_log = _cfg.get("save_raw_log", config.SAVE_RAW_LOG) and not args.no_raw_log
    quiet = (args.quiet or config.QUIET) and not args.no_quiet
    json_output = args.json

    needs_setup = False
    if not provider or not model:
        needs_setup = True
    elif not api_key and provider != "ollama":
        needs_setup = True
    elif provider == "custom" and not api_base_url:
        needs_setup = True

    if needs_setup:
        print("⚠️  Missing configuration. Running setup wizard...", file=sys.stderr)
        try:
            wiz_config = wizard.run_setup_wizard(
                is_onboarding=True
            )
            provider = wiz_config.provider
            model = wiz_config.model
            api_key = wiz_config.api_key
            api_base_url = wiz_config.api_base_url
            system_prompt = wiz_config.system_prompt
            temperature = wiz_config.temperature
            max_output = wiz_config.max_output
            save_report = wiz_config.save_report
            max_input = wiz_config.max_input
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            if 'temp_path' in locals():
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            sys.exit(1)

    allowed_providers = set(config.KNOWN_PROVIDERS.keys()) | {"google", "anthropic", "custom"}
    if provider and provider not in allowed_providers and not api_base_url:
        bar = "─" * 60
        print(f"\n{bar}", file=sys.stderr)
        print(f"⚠️  Invalid LLM provider '{provider}'.", file=sys.stderr)
        print("Set a known provider or pass --api-base-url for custom endpoints.", file=sys.stderr)
        print(f"{bar}\n", file=sys.stderr)
        sys.exit(1)

    exit_code = run(
        command,
        provider=provider,
        model=model,
        api_key=api_key,
        api_base_url=api_base_url,
        save_report=save_report,
        save_raw_log=save_raw_log,
        quiet=quiet,
        json_output=json_output,
        system_prompt=system_prompt,
        temperature=temperature,
        max_output=max_output,
        max_input=max_input
    )

    if args.test and 'temp_path' in locals():
        try:
            os.remove(temp_path)
        except OSError:
            pass

    if args.test or not quiet or exit_code != 0:
        show_update_notification()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
