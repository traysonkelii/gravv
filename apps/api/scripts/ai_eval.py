"""Runs tests/ai/cases/extraction.yaml against the configured LLM provider and prints precision and recall for
facts and tasks plus contact-match accuracy. The fake provider must score 100 percent; live providers must exceed
0.85 precision on facts and tasks before a prompt version ships (Section 11.6).

Usage: uv run python -m scripts.ai_eval   (LLM_PROVIDER from .env)"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from app.ai.extraction import CaptureExtraction
from app.ai.llm import get_llm_client
from app.ai.prompts import render

CANDIDATES = "\n".join(
    [
        "00000000-0000-4000-8000-0000000000a1 | Col. Michael Johnson | Space Force | Program Director",
        "00000000-0000-4000-8000-0000000000a5 | Dr. James Chen | NASA | Chief Scientist",
        "00000000-0000-4000-8000-0000000000a2 | Emily Rodriguez | Boeing | Contract Manager",
        "00000000-0000-4000-8000-0000000000a3 | Sarah Martinez | Lockheed Martin | VP Sales",
        "00000000-0000-4000-8000-0000000000a6 | Kevin Liu | TechCorp Solutions | CTO",
    ]
)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def fuzzy_in(expected: str, produced: list[str]) -> bool:
    e = norm(expected)
    return any(e in norm(p) or norm(p) in e for p in produced)


CASES_PATH = Path(__file__).resolve().parents[1] / "tests/ai/cases/extraction.yaml"


def load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(CASES_PATH.read_text())["cases"]  # type: ignore[no-any-return]


async def run(cases: list[dict[str, Any]]) -> int:
    llm = get_llm_client()
    tp = fp = fn = 0
    ttp = tfp = tfn = 0
    contact_ok = contact_total = 0
    failures: list[str] = []
    for case in cases:
        prompt = render(
            "extract",
            "v1",
            now="2026-09-28T14:30-04:00",
            timezone="America/New_York",
            user_name="Sarah Chen",
            user_role="Account Executive",
            selected_contact="none",
            existing_facts="\n".join(f"- {e}" for e in case.get("existing", [])) or "none",
            candidates=CANDIDATES,
            capture=case["capture"],
        )
        out: CaptureExtraction = (await llm.complete_structured(prompt=prompt, schema=CaptureExtraction)).value
        facts = [f.content for f in out.facts]
        tasks = [t.title for t in out.tasks]
        for e in case["facts"]:
            if fuzzy_in(e, facts):
                tp += 1
            else:
                fn += 1
                failures.append(f"{case['id']}: missing fact '{e}' in {facts}")
        for p in facts:
            if not any(fuzzy_in(e, [p]) for e in case["facts"]):
                fp += 1
                failures.append(f"{case['id']}: unexpected fact '{p}'")
        for e in case["tasks"]:
            if fuzzy_in(e, tasks):
                ttp += 1
            else:
                tfn += 1
                failures.append(f"{case['id']}: missing task '{e}' in {tasks}")
        for p in tasks:
            if not any(fuzzy_in(e, [p]) for e in case["tasks"]):
                tfp += 1
                failures.append(f"{case['id']}: unexpected task '{p}'")
        contact_total += 1
        got = out.contact_match.display_name if out.contact_match else None
        ok = got in case["expect_contact_in"] if "expect_contact_in" in case else got == case.get("expect_contact")
        if ok:
            contact_ok += 1
        else:
            failures.append(
                f"{case['id']}: contact {got!r} expected {case.get('expect_contact', case.get('expect_contact_in'))!r}"
            )
        if case.get("expect_kind") and out.interaction.kind.value != case["expect_kind"]:
            failures.append(f"{case['id']}: kind {out.interaction.kind.value} expected {case['expect_kind']}")
        if case.get("needs_review") and not out.needs_review:
            failures.append(f"{case['id']}: expected a needs_review note")
        if case.get("occurred_at_set") and out.interaction.occurred_at is None:
            failures.append(f"{case['id']}: expected occurred_at")
        if case.get("sentiment") and out.interaction.sentiment.value != case["sentiment"]:
            failures.append(f"{case['id']}: sentiment {out.interaction.sentiment.value} expected {case['sentiment']}")
        for m in case.get("mentioned", []):
            if not fuzzy_in(m, [p.name for p in out.mentioned_people]):
                failures.append(f"{case['id']}: missing mentioned person '{m}'")

    def pr(tp_: int, fp_: int, fn_: int) -> tuple[float, float]:
        p = tp_ / (tp_ + fp_) if tp_ + fp_ else 1.0
        r = tp_ / (tp_ + fn_) if tp_ + fn_ else 1.0
        return p, r

    fp_, fr_ = pr(tp, fp, fn)
    tp_, tr_ = pr(ttp, tfp, tfn)
    print(f"provider={llm.name} model={llm.model} cases={len(cases)}")
    print(f"facts     precision={fp_:.2f} recall={fr_:.2f}")
    print(f"tasks     precision={tp_:.2f} recall={tr_:.2f}")
    print(f"contact   accuracy={contact_ok / contact_total:.2f}")
    for f in failures:
        print("  -", f)
    threshold = 1.0 if llm.name == "fake" else 0.85
    ok = fp_ >= threshold and tp_ >= threshold and (llm.name != "fake" or not failures)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run(load_cases())))
