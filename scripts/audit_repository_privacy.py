from __future__ import annotations

import re
import subprocess
from pathlib import Path


MAX_TEXT_SIZE = 2_000_000
SELF_PATH = "scripts/audit_repository_privacy.py"

SECRET_RULES = {
    "private_key_block": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.IGNORECASE,
    ),
    "bearer_token": re.compile(
        r"authorization\s*[:=]\s*['\"]?bearer\s+\S+",
        re.IGNORECASE,
    ),
    "credential_assignment": re.compile(
        r"(?:api[_-]?key|access[_-]?token|secret|password|passwd)"
        r"\s*[:=]\s*['\"][^'\"]{4,}['\"]",
        re.IGNORECASE,
    ),
}

MACHINE_RULES = {
    "mini_pc_ip": re.compile(r"192\.168\.137\.2"),
    "local_username": re.compile(r"\b(?:sdkad|syed)\b", re.IGNORECASE),
    "windows_worker_path": re.compile(
        r"C:\\AI_Worker",
        re.IGNORECASE,
    ),
    "wsl_home_path": re.compile(
        r"/home/(?:sdkad|syed)(?:/|\b)",
        re.IGNORECASE,
    ),
}


def git_candidate_files() -> list[str]:
    output = subprocess.check_output(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return sorted(set(output.splitlines()))


def read_candidate(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_TEXT_SIZE:
            return None
        data = path.read_bytes()
    except OSError:
        return None

    if b"\x00" in data:
        return None

    return data.decode("utf-8", errors="replace")


def matching_rules(text: str, rules: dict[str, re.Pattern]) -> list[str]:
    return [name for name, pattern in rules.items() if pattern.search(text)]


def main() -> None:
    secret_matches: dict[str, list[str]] = {}
    machine_matches: dict[str, list[str]] = {}
    skipped: list[str] = []
    candidates = git_candidate_files()

    for filename in candidates:
        normalized = Path(filename).as_posix()
        if normalized == SELF_PATH:
            continue

        text = read_candidate(Path(filename))
        if text is None:
            skipped.append(normalized)
            continue

        secret_rules = matching_rules(text, SECRET_RULES)
        machine_rules = matching_rules(text, MACHINE_RULES)

        if secret_rules:
            secret_matches[normalized] = secret_rules
        if machine_rules:
            machine_matches[normalized] = machine_rules

    print("Repository privacy audit")
    print(f"Candidate files: {len(candidates)}")
    print(f"Binary, inaccessible, or large files skipped: {len(skipped)}")

    print("\nPotential secret files:")
    if secret_matches:
        for filename, rules in secret_matches.items():
            print(f"- {filename}: {', '.join(rules)}")
    else:
        print("- none")

    print("\nMachine-specific files:")
    if machine_matches:
        for filename, rules in machine_matches.items():
            print(f"- {filename}: {', '.join(rules)}")
    else:
        print("- none")

    print("\nSkipped files:")
    if skipped:
        for filename in skipped:
            print(f"- {filename}")
    else:
        print("- none")


if __name__ == "__main__":
    main()
