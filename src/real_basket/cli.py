"""Minimal CLI to test the agent without the UI: `poetry run real-basket-cli "your question"`."""

import sys

from real_basket.agents.orchestrator import create_orchestrator


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Steigen die Grundlebenshaltungskosten schneller als die Inflation?"
    print(create_orchestrator()(prompt))


if __name__ == "__main__":
    main()
