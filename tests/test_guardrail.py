"""Number guardrail: figures in agent answers must be backed by tool results (no LLM, no network)."""

import json

from real_basket.agents.guardrail import answer_figures, tool_values, unverified_figures, warning_text


def _messages(*results: dict) -> list:
    """Strands-style conversation: one toolUse / toolResult pair per result (MCP tools return JSON text)."""
    msgs = []
    for n, res in enumerate(results):
        msgs.append({"role": "assistant", "content": [{"toolUse": {"toolUseId": f"t{n}", "name": "x", "input": {}}}]})
        msgs.append({"role": "user", "content": [{"toolResult": {"toolUseId": f"t{n}", "status": "success",
                                                                 "content": [{"text": json.dumps(res)}]}}]})
    return msgs


TOOL = {"essential_yoy_pct": 2.93, "cpi_yoy_pct": 2.83, "deviation_pp": 0.11, "weights": {"housing_energy": 0.5231},
        "categories": [{"category": "mobility", "gap_pp": 0.94}], "rent_75m2_eur": 1234.5}


def test_figures_from_tools_pass_in_german_format_and_rounded():
    answer = ("Die Grundlebenshaltungskosten steigen um 2,93 % (VPI: 2,8 %), Abweichung +0,11 Prozentpunkte. "
              "Größter Treiber: Verkehr (+0,94 PP). Wohnen / Energie hat ein Gewicht von 52,3 %. "
              "Eine 75-m²-Wohnung kostet 1.234,50 €.")
    assert unverified_figures(answer, _messages(TOOL)) == []


def test_invented_or_derived_figures_are_flagged():
    answer = "Abweichung 0,10 PP (2,93 % minus 2,83 %), Lebensmittel +4,7 %."
    assert unverified_figures(answer, _messages(TOOL)) == ["0,10", "+4,7"]
    assert "0,10" in warning_text(["0,10"]) and warning_text([]) == ""


def test_dates_years_counts_and_pages_are_not_checked():
    answer = ("Stand 10/2026 (Basis 11/2024 = 100, EVS 2023), 15 Städte, 5 Gruppen, "
              "[Lebenshaltungskosten_2026_Deutschland_Euro_und_Index.pdf S. 3], 31.10.2026, 2026-10.")
    assert answer_figures(answer) == []


def test_numbers_from_the_question_are_allowed():
    assert unverified_figures("Mit 40 % Lebensmittel ergibt sich 2,93 %.", _messages(TOOL),
                              question="Was wäre bei 40 % Lebensmittel?") == []


def test_no_tool_results_means_every_figure_is_flagged():
    assert unverified_figures("Inflation 2,9 %", []) == ["2,9"]


def test_tool_values_reads_nested_json_and_plain_text():
    values = tool_values(_messages({"a": [{"b": 1.5}]}) + [
        {"role": "user", "content": [{"toolResult": {"content": [{"text": "max. Abweichung 0.003 Punkte"}]}}]}])
    assert {1.5, 0.003} <= values
