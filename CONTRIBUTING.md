# Contributing to brytlog

Thank you for your interest in contributing! Brytlog replaces raw logs with an AI summary, thus saving developers time, trouble and money.

## Development Setup

1. Clone the repository.
2. Install dependencies: `pip install -e ".[dev]"`
3. Run tests: `python tests/run_tests.py`

## Architecture

Brytlog is designed to be highly modular:
- `cli.py`: Entry point and UI.
- `config.py`: Configuration management (Hierarchy: Env Var -> ~/.brytlog.json -> Default).
- `scanner.py`: Heuristic-based log analyzer for success runs.
- `stream_capture.py`: Handles subprocess execution and output buffering.
- `summarizer.py`: Orchestrates calls to various LLM providers.
- `llm_client.py`: Zero-dependency HTTP client for API calls.
- `parser.py`: Transforms LLM text into structured data.
- `redactor.py`: Strips sensitive data (PII, tokens) from logs.
- `wizard.py`: Interactive setup and verification.

## Reporting Bugs and Feature Requests

- **Bugs**: Please open an issue and include the raw log (`brytlog-raw/`) and the AI report (`brytlog-reports/`) if applicable.
- **Features**: Open an issue to discuss the feature before starting implementation.

## Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Implement** your changes.
3. **Verify** your work:
   - Run tests: `python tests/run_tests.py`
   - Check linting: `ruff check`
   - Check formatting: `ruff format`
   - Check types: `mypy .`
4. **Submit** the PR. Ensure the description clearly explains the problem and your solution.

## Testing Standards

We use a custom test suite to validate end-to-end functionality and LLM report quality.
- Every new feature should include a corresponding test in the `tests/` directory.
- Redaction patterns must be tested in `test_redaction.py`.
- LLM quality evaluations use a stronger model (e.g., Gemini Pro) to score the output of the tested model.

## Code Style

We use `ruff` for linting and formatting, and `mypy` for type checking. Before submitting a PR, please run:
- `ruff check`
- `ruff format`
- `mypy .`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
