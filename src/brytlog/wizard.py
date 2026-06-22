import getpass
import sys
from dataclasses import dataclass
from . import config, summarizer
from .summarizer import summarize_crash


@dataclass
class WizardConfig:
    """Configuration returned from the setup wizard."""
    provider: str
    model: str
    api_key: str
    api_base_url: str
    system_prompt: str
    temperature: float
    max_output: int
    save_report: bool
    max_input: int

def run_setup_wizard(is_onboarding: bool = False) -> WizardConfig:
    """Interactive wizard for core configuration onboarding."""
    # Load existing config to merge
    current_config = config.load_user_config()

    if is_onboarding:
        print("\nWelcome to brytlog! Quick setup and you're good to go.")
        print("(You can change these and advanced settings anytime by typing `brytlog --config`)\n")
    else:
        print("\n--- brytlog configuration ---")

    print("Which LLM provider would you like to use?")
    print("1. Google (Gemini via Google AI Studio)")
    print("2. OpenAI (ChatGPT)")
    print("3. Anthropic (Claude)")
    print("4. Grok (xAI)")
    print("5. Ollama (Local)")
    print("6. Custom (OpenAI-compatible)")

    provider_map = {
        "1": "google", "2": "openai", "3": "anthropic",
        "4": "grok", "5": "ollama", "6": "custom"
    }

    provider_default_choice = next(
        (k for k, v in provider_map.items() if v == current_config.get("provider")),
        None
    )

    choice = ""
    prompt_suffix = f" (default {provider_default_choice})" if provider_default_choice else ""
    while choice not in provider_map:
        choice = input(f"Select your provider [1-6]{prompt_suffix}: ").strip()
        if not choice and provider_default_choice:
            choice = provider_default_choice

    provider = provider_map[choice]

    # Selected mid-2026 cheap-fast-good models
    default_models = {
        "google": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5",
        "grok": "grok-4-fast",
        "ollama": "llama3.2",
        "custom": "your-custom-model"
    }

    suggested_model = current_config.get("model") or default_models[provider]
    print(f"\nModel of choice (e.g. {suggested_model}):")

    if current_config.get("model"):
        prompt = f"Press Enter to use '{suggested_model}', or type your own: "
    else:
        prompt = "Enter model name: "

    model = input(prompt).strip()
    if not model and current_config.get("model"):
        model = suggested_model
    elif not model:
        # If no default exists and they press enter, we must force a choice or use the suggestion
        model = suggested_model

    api_key = current_config.get("api_key", "")
    if provider != "ollama":
        print(f"\nPlease enter your {provider.capitalize()} API Key:")
        if api_key:
            print(f"(Current: {api_key[:4]}...{api_key[-4:]})")
            prompt = "API Key (press Enter to keep current): "
        else:
            prompt = "API Key: "
        new_api_key = getpass.getpass(prompt).strip()
        if new_api_key:
            api_key = new_api_key

    api_base_url = current_config.get("api_base_url", "")
    if provider == "custom":
        print("\nPlease enter your Custom API Base URL (e.g. http://localhost:1234/v1):")
        print("(Note: Standard 'Authorization: Bearer' header will be used. Azure/Vertex not currently supported)")
        if api_base_url:
            print(f"(Current: {api_base_url})")
        new_url = input("Base URL (press Enter to keep current): ").strip()
        if new_url:
            api_base_url = new_url

    # Credentials verification
    if provider != "ollama":
        print("\nVerifying credentials...")
        test_result = summarize_crash(
            command="echo 'verification'",
            output="verification",
            provider=provider,
            model=model,
            api_key=api_key,
            api_base_url=api_base_url,
            system_prompt="You are a connection tester. Respond with only the word 'OK'.",
            max_output=20
        )
        is_error = "API Error" in test_result or "failed" in test_result.lower() or "No API_KEY" in test_result

        if is_error:
            print(f"❌ Verification failed:\n{test_result}")
            print("\nConfiguration NOT saved. Please check your credentials and try again.")
            sys.exit(1)
        else:
            print("✅ Credentials verified.")

    # Update and save to ~/.brytlog.json
    final_data = {
        "provider": provider,
        "model": model,
        "temperature": current_config.get("temperature", 0.2),
        "api_key": api_key,
        "api_base_url": api_base_url,
        "max_input": current_config.get("max_input", 4000),
        "max_output": current_config.get("max_output", 1000),
        "system_prompt": current_config.get("system_prompt", summarizer.DEFAULT_SYSTEM_PROMPT.strip()),
        "save_report": current_config.get("save_report", True),
    }

    config.save_user_config(final_data)

    print("\n✅ All set! (configuration saved to ~/.brytlog.json)")
    if not is_onboarding:
        print("You're ready to use brytlog.\n")

    return WizardConfig(
        provider=final_data["provider"],
        model=final_data["model"],
        api_key=final_data["api_key"],
        api_base_url=final_data["api_base_url"],
        system_prompt=final_data["system_prompt"],
        temperature=final_data["temperature"],
        max_output=final_data["max_output"],
        save_report=final_data["save_report"],
        max_input=final_data["max_input"]
    )
