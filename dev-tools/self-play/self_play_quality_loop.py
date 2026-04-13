import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME_SERVER_DIR = PROJECT_ROOT / "home-server"

os.chdir(HOME_SERVER_DIR)

if str(HOME_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(HOME_SERVER_DIR))

import websockets

from app.config import settings
from app.web_lookup import build_web_context, parse_lookup_items

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "that", "this", "there", "their",
    "your", "about", "into", "what", "when", "where", "which", "while", "would", "could", "should",
    "have", "has", "had", "will", "just", "more", "less", "than", "then", "also", "today", "latest",
    "current", "look", "lookup", "search", "internet", "online", "give", "one", "specific", "fact",
}

GENERIC_MARKERS = (
    "as of my last update",
    "i cannot verify",
    "for the most current information",
    "check sources",
    "no specific major announcements",
    "i am not sure",
    "i do not know",
    "one moment",
    "let me check",
    "give me a second",
)


@dataclass
class Scenario:
    scenario_id: str
    prompt: str
    requires_lookup: bool
    expected_contains: list[str]
    expected_not_contains: list[str]


@dataclass
class EvalResult:
    scenario_id: str
    prompt: str
    answer: str
    human_score: float
    factual_score: float
    overall_score: float
    notes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run recursive self-play quality tuning for Ear AI assistant rules."
    )
    parser.add_argument("--scenarios", default=str(Path(__file__).resolve().parent / "self_play_scenarios.json"))
    parser.add_argument("--report", default=str(HOME_SERVER_DIR / "logs" / "self_play_last_report.json"))
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--target", type=float, default=0.88)
    parser.add_argument("--ws-url", default="")
    parser.add_argument("--apply", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def load_scenarios(path: Path) -> list[Scenario]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[Scenario] = []
    for item in raw:
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        scenarios.append(
            Scenario(
                scenario_id=str(item.get("id") or "scenario"),
                prompt=prompt,
                requires_lookup=bool(item.get("requires_lookup", False)),
                expected_contains=[str(v).lower() for v in item.get("expected_contains", [])],
                expected_not_contains=[str(v).lower() for v in item.get("expected_not_contains", [])],
            )
        )
    return scenarios


def extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{4,}", text.lower())
    return {token for token in tokens if token not in STOPWORDS}


def is_error_answer(answer: str) -> bool:
    return answer.strip().lower().startswith("error:")


def evaluate_human_like(answer: str) -> tuple[float, list[str]]:
    if is_error_answer(answer):
        return 0.0, ["Backend/model error response."]

    score = 1.0
    notes: list[str] = []
    word_count = len(re.findall(r"\S+", answer))

    if word_count < 4:
        score -= 0.35
        notes.append("Too short to feel naturally conversational.")
    elif word_count > 55:
        score -= 0.30
        notes.append("Too long for concise earbud-style speech.")

    lower = answer.lower()
    if "http://" in lower or "https://" in lower:
        score -= 0.25
        notes.append("Includes raw URL text, which sounds robotic in speech.")
    if "\n-" in answer or answer.strip().startswith("-"):
        score -= 0.20
        notes.append("Uses list formatting instead of natural spoken style.")
    if any(marker in lower for marker in GENERIC_MARKERS):
        score -= 0.25
        notes.append("Contains generic filler language.")
    if not re.search(r"[.!?]$", answer.strip()):
        score -= 0.10
        notes.append("Missing clean spoken sentence ending.")

    return max(0.0, min(1.0, score)), notes


def evaluate_factual(answer: str, lookup_items: list[dict[str, str]], requires_lookup: bool) -> tuple[float, list[str]]:
    if is_error_answer(answer):
        return 0.0, ["No factual evaluation possible due to backend/model error."]

    if not requires_lookup:
        return 1.0, []

    if not lookup_items:
        lower = answer.lower()
        if "cannot verify" in lower or "could not retrieve" in lower or "not sure" in lower:
            return 0.9, ["No evidence available, answer was honest about limits."]
        return 0.2, ["No evidence available, but answer sounds confident."]

    notes: list[str] = []
    evidence_words = extract_keywords(" ".join(item.get("snippet", "") for item in lookup_items))
    answer_words = extract_keywords(answer)
    if not answer_words:
        return 0.25, ["No concrete factual content in answer."]

    overlap = len(answer_words.intersection(evidence_words)) / max(1, len(answer_words))
    score = 0.40 + min(0.55, overlap * 1.2)

    if overlap < 0.20:
        notes.append("Weak alignment between answer and retrieved source snippets.")
    else:
        notes.append("Good overlap with retrieved source snippets.")

    return max(0.0, min(1.0, score)), notes


def evaluate_expectations(answer: str, scenario: Scenario) -> tuple[float, list[str]]:
    if is_error_answer(answer):
        return 0.0, ["Expectation checks failed due to backend/model error."]

    score = 1.0
    notes: list[str] = []
    lower = answer.lower()
    for needle in scenario.expected_contains:
        if needle not in lower:
            score -= 0.30
            notes.append(f"Missing expected phrase: {needle}")
    for needle in scenario.expected_not_contains:
        if needle in lower:
            score -= 0.30
            notes.append(f"Contains forbidden phrase: {needle}")
    return max(0.0, min(1.0, score)), notes


def build_tuning_directives(results: list[EvalResult], existing: list[str]) -> list[str]:
    directives = list(existing)
    avg_human = mean(r.human_score for r in results)
    avg_factual = mean(r.factual_score for r in results)

    candidates: list[str] = []
    if avg_human < 0.82:
        candidates.append("Speak naturally in one or two short sentences with direct, human-like phrasing and no template-like intro.")
    if avg_factual < 0.82:
        candidates.append("For lookup-style questions, only state claims supported by lookup notes; if evidence is thin, explicitly say you cannot verify.")
    if any(is_error_answer(r.answer) for r in results):
        candidates.append("When backend tools fail, say clearly that LM Studio is unreachable and ask the user to check local model server status.")

    for candidate in candidates:
        if candidate not in directives:
            directives.append(candidate)
    return directives


def append_directives_to_rules(base_rules: str, directives: list[str]) -> str:
    if not directives:
        return base_rules
    marker = "\n\nSelf-Play Tuned Addendum:\n"
    cleaned = base_rules.split(marker, maxsplit=1)[0].rstrip()
    lines = "\n".join(f"- {directive}" for directive in directives)
    return f"{cleaned}{marker}{lines}\n"


def resolve_ws_url(arg_value: str) -> str:
    if arg_value.strip():
        return arg_value.strip()
    host = "127.0.0.1" if settings.host in {"0.0.0.0", "::"} else settings.host
    return f"ws://{host}:{settings.port}/ws/assistant"


async def ask_assistant(ws_url: str, prompt: str) -> str:
    payload = {
        "type": "user_utterance",
        "session_id": str(uuid.uuid4()),
        "text": prompt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps(payload))
        raw = await websocket.recv()

    response = json.loads(raw)
    if response.get("type") == "assistant_response":
        return str(response.get("text") or "")
    if response.get("type") == "error":
        return f"ERROR: {response.get('message') or 'unknown error'}"
    return "ERROR: unexpected response format"


async def run_iteration(scenarios: list[Scenario], ws_url: str) -> list[EvalResult]:
    results: list[EvalResult] = []
    for scenario in scenarios:
        lookup_items: list[dict[str, str]] = []
        if scenario.requires_lookup:
            web_context = await build_web_context(scenario.prompt)
            lookup_items = parse_lookup_items(web_context)

        answer = await ask_assistant(ws_url, scenario.prompt)
        human_score, human_notes = evaluate_human_like(answer)
        factual_score, factual_notes = evaluate_factual(answer, lookup_items, scenario.requires_lookup)
        expectation_score, expectation_notes = evaluate_expectations(answer, scenario)
        overall = max(0.0, min(1.0, (human_score * 0.35) + (factual_score * 0.45) + (expectation_score * 0.20)))
        results.append(
            EvalResult(
                scenario_id=scenario.scenario_id,
                prompt=scenario.prompt,
                answer=answer,
                human_score=human_score,
                factual_score=factual_score,
                overall_score=overall,
                notes=[*human_notes, *factual_notes, *expectation_notes],
            )
        )
    return results


def summarize_iteration(iteration: int, results: list[EvalResult]) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "avg_human_score": round(mean(r.human_score for r in results), 4),
        "avg_factual_score": round(mean(r.factual_score for r in results), 4),
        "avg_overall_score": round(mean(r.overall_score for r in results), 4),
        "error_count": sum(1 for r in results if is_error_answer(r.answer)),
        "results": [
            {
                "scenario_id": r.scenario_id,
                "prompt": r.prompt,
                "answer": r.answer,
                "human_score": round(r.human_score, 4),
                "factual_score": round(r.factual_score, 4),
                "overall_score": round(r.overall_score, 4),
                "notes": r.notes,
            }
            for r in results
        ],
    }


def apply_directives_to_rules(base_rules_path: Path, directives: list[str]) -> None:
    original = base_rules_path.read_text(encoding="utf-8").strip()
    base_rules_path.write_text(append_directives_to_rules(original, directives), encoding="utf-8")


async def main() -> int:
    args = parse_args()
    scenarios_path = Path(args.scenarios)
    report_path = Path(args.report)
    rules_path = HOME_SERVER_DIR / "config" / "assistant_rules.md"
    ws_url = resolve_ws_url(args.ws_url)

    if not scenarios_path.exists():
        print(f"ERROR: scenario file not found: {scenarios_path}")
        return 1

    scenarios = load_scenarios(scenarios_path)
    if not scenarios:
        print("ERROR: no valid scenarios in scenario file.")
        return 1

    base_rules = rules_path.read_text(encoding="utf-8").strip()
    original_rules = base_rules
    directives: list[str] = []

    history: list[dict[str, Any]] = []
    best_score = -1.0
    best_directives: list[str] = []
    best_rules = base_rules

    try:
        for iteration in range(1, args.iterations + 1):
            candidate_rules = append_directives_to_rules(base_rules, directives).strip() + "\n"
            rules_path.write_text(candidate_rules, encoding="utf-8")

            iteration_results = await run_iteration(scenarios, ws_url)
            summary = summarize_iteration(iteration, iteration_results)
            history.append(summary)

            avg = summary["avg_overall_score"]
            print(
                f"iteration={iteration} avg_overall={avg:.3f} "
                f"avg_human={summary['avg_human_score']:.3f} "
                f"avg_factual={summary['avg_factual_score']:.3f} errors={summary['error_count']}"
            )

            if avg > best_score:
                best_score = avg
                best_directives = list(directives)
                best_rules = candidate_rules

            scenario_floor = min(result.overall_score for result in iteration_results)
            if avg >= args.target and scenario_floor >= (args.target - 0.15):
                print(f"Reached target quality threshold ({args.target:.2f}).")
                best_directives = list(directives)
                best_rules = candidate_rules
                break

            new_directives = build_tuning_directives(iteration_results, directives)
            if new_directives == directives:
                print("No new tuning directives were generated; stopping early.")
                break
            directives = new_directives
    finally:
        if not args.apply:
            rules_path.write_text(original_rules + "\n", encoding="utf-8")

    final_report = {
        "target": args.target,
        "max_iterations": args.iterations,
        "best_score": round(best_score, 4),
        "best_directives": best_directives,
        "history": history,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(f"Wrote report to {report_path}")

    tuned_path = HOME_SERVER_DIR / "config" / "assistant_rules.tuned.md"
    tuned_path.write_text(best_rules.strip() + "\n", encoding="utf-8")
    print(f"Wrote tuned rules proposal to {tuned_path}")

    if args.apply:
        apply_directives_to_rules(rules_path, best_directives)
        print("Applied best directives to config/assistant_rules.md")
    else:
        print("Restored original rules because --no-apply was used")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
