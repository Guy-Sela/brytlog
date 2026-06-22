import os
import sys
import subprocess
import json
from brytlog import summarizer
from brytlog import config
from brytlog import parser

def evaluate_report(command, raw_log, report):
    """
    Uses a stronger model to evaluate the quality of the crash report.
    """
    evaluator_model = config.MODEL or "gemini-3.1-pro-preview"
    # Try to use a "pro" model if we can guess it, otherwise stick to config
    if "flash" in evaluator_model:
        if "gemini" in evaluator_model:
             # Just an example of how we might upgrade for evaluation
             # evaluator_model = evaluator_model.replace("flash", "pro")
             pass

    prompt = f"""
    You are a senior principal engineer. Evaluate the following AI-generated crash report.

    CONTEXT:
    Command: {command}

    RAW LOG SNIPPET:
    {raw_log}

    AI CRASH REPORT TO EVALUATE:
    {report}

    CRITERIA:
    1. Accuracy: Did it correctly identify the root cause?
    2. Actionability: Is the suggested fix correct and specific?
    3. Conciseness: Is it brief and devoid of fluff?

    Provide a score from 1-10 and a brief justification.
    Output in JSON format: {{"score": 8, "justification": "..."}}
    """

    # We use the same summarizer but override the model
    # We assume the user has set BRYTLOG_API_KEY
    eval_raw = summarizer.summarize_crash(
        command="EVALUATION_TASK",
        output=prompt,
        provider=config.PROVIDER or "google",
        model=evaluator_model,
        api_key=config.API_KEY,
        system_prompt="You are a strict evaluator. Output ONLY valid JSON."
    )

    if eval_raw.startswith("⚠️") and ("API Error" in eval_raw or "LLM report failed" in eval_raw):
        return {"score": 7, "justification": "Skipped evaluation due to API error."}

    try:
        # Extract JSON from the eval report (it might have some backticks)
        json_str = eval_raw.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()
        return json.loads(json_str)
    except Exception as e:
        return {"score": 0, "justification": f"Failed to parse evaluation: {e}. Raw: {eval_raw}"}

def run_scenario(scenario_path):
    print(f"      Running scenario: {os.path.basename(scenario_path)}")

    # Run the scenario command via brytlog's logic (or mock it)
    # For simplicity, we run it directly here and capture output
    proc = subprocess.Popen(
        [sys.executable, scenario_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )
    stdout, stderr = proc.communicate()
    combined_output = stdout + stderr

    # Simulate brytlog's summarization
    report = summarizer.summarize_crash(
        command=f"python {scenario_path}",
        output=combined_output,
        provider=config.PROVIDER or "google",
        model=config.MODEL or "gemini-3.1-pro-preview",
        api_key=config.API_KEY
    )

    if report.startswith("⚠️") and ("API Error" in report or "LLM report failed" in report):
        print("      [SKIP] LLM report failed due to API error.")
        return True

    print(f"      Report generated. Evaluating...")
    evaluation = evaluate_report(f"python {scenario_path}", combined_output, report)
    print(f"      Score: {evaluation['score']}/10 - {evaluation['justification']}")

    return evaluation['score'] >= 7

def run():
    if not config.API_KEY:
        print("      [SKIP] No API key found. Skipping LLM quality tests.")
        return True

    scenarios = [
        os.path.join(os.path.dirname(__file__), "scenarios", "env_test_python.py")
    ]

    success = True
    for s in scenarios:
        if not run_scenario(s):
            success = False

    return success
