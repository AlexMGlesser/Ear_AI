from pathlib import Path

RULES_PATH = Path("config/assistant_rules.md")


def load_rules_text() -> str:
    if not RULES_PATH.exists():
        return "Keep responses concise and safe."
    return RULES_PATH.read_text(encoding="utf-8").strip()


def build_system_prompt() -> str:
    rules = load_rules_text()
    return (
        "You are an earbud voice assistant. Follow the rules exactly.\n\n"
        f"Rules:\n{rules}"
    )
