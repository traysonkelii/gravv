"""Versioned prompt templates. A template file has a system part and a user part split by a marker line;
placeholders look like {{ name }} and are replaced verbatim (no expression evaluation)."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
SPLIT = "\n===USER===\n"
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    @property
    def id(self) -> str:
        return f"{self.name}:{self.version}"


@lru_cache
def _load(name: str, version: str) -> tuple[str, str]:
    raw = (PROMPTS_DIR / name / f"{version}.md").read_text()
    system, user = raw.split(SPLIT, 1)
    return system.strip(), user.strip()


def render(name: str, version: str = "v1", **variables: str) -> Prompt:
    system, user = _load(name, version)

    def sub(text: str) -> str:
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in variables:
                raise KeyError(f"prompt {name}:{version} is missing variable {key}")
            return variables[key]

        return _PLACEHOLDER.sub(repl, text)

    return Prompt(name=name, version=version, system=sub(system), user=sub(user))
