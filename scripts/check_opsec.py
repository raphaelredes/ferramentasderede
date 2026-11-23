#!/usr/bin/env python3
"""
Guardrail script to prevent leaking private domains, internal hostnames,
corporate subnets, developer workstation paths, or personal usernames into
public commits, builds, or CI runs.

Prohibited organization/person identifiers are stored strictly as SHA-256 hex
digests (lowercase) so that the guard script itself contains zero sensitive
plaintext tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import subprocess
import sys
from typing import Iterable, List, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".icns",
    ".woff", ".woff2", ".ttf", ".eot", ".svg",
    ".exe", ".dll", ".pyd", ".so", ".bin", ".zip", ".7z",
    ".pdf", ".sqlite", ".sqlite3", ".db", ".pyc",
}

SKIP_FILENAMES = {
    "package-lock.json",
}

# Lowercase SHA-256 digests of private corporate domains, org subwords,
# internal network prefixes, and colleague/workstation usernames.
BLOCKED_TOKEN_HASHES = {
    # Corporate forest domains
    "b456a3710fc99813d2408f0d00849e56d8e6ce7e0afcc0bfd2f01b6fb08632ef": "ORG_DOMAIN_0",
    "b05c8fb8bcc89b1b2dd2b95c807a7000d42cd6c39c992c5fd89f6e5e979dd58d": "ORG_DOMAIN_1",
    "26fd3e33060759671c0c061ac4837d25f8fc81f05405751550bdc341f727af2c": "ORG_DOMAIN_2",
    "26efcf0414e6c11ae5a200610cdafb91ba7c1a70449a70c46921244fc0f440b4": "ORG_DOMAIN_3",
    "e3f803e439df2e186dccf0e93a5d1d4e7a0ced8203549a8ef66975eb6497f26a": "ORG_DOMAIN_4",
    # Corporate org sub-tokens
    "4b1ed5795097354451564a9e7d7ef90b1c24dc6e82747622da47034f17b9ed74": "ORG_SUB_0",
    "94361fe5191d37144d260203d497d7df91b87e3bb3f5c028e9e3cce58404ad74": "ORG_SUB_1",
    "56b452758c339e7f9bc710862f4e51007bd17695b6d1875dae74dafa19cead65": "ORG_SUB_2",
    "40a98e819f346594ef85962e562278611f21adfebe052b6322afe80cb5b4fda8": "ORG_SUB_3",
    "e712ba1b39ab6744942d128253aa34fa57bf55bc5cb0bd9d503a725614e632b9": "ORG_SUB_4",
    # Workstation / colleague identifiers & internal SSID/asset prefix
    "567576d73784c9895ecc5154a6ef6bd3634ca8ce015143a6c66750920d518965": "WS_ACCOUNT",
    "00e48a815525529ba9d33f8761a167588fe00c47bc82f515cf791c482ed99ecc": "PRIV_USER_0",
    "232851c3072c529772dd3a5ebad2aef6179c354a307e2591437b615de1231e25": "PRIV_USER_1",
    "1cafc1dfdf9dcdccc39029b49d11e36aaa5d48d29d016de011357c38377dcf2e": "INTERNAL_SSID_PREFIX",
}

REGEX_RULES: List[Tuple[str, re.Pattern[str]]] = [
    (
        "PERSONAL_WIN_PATH",
        re.compile(
            r"[A-Za-z]:[\\/]+Users[\\/]+(?!(?:Public|SeuUsuario|Default|All Users)\b)[A-Za-z0-9._~-]+",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSONAL_POSIX_PATH",
        re.compile(
            r"/[A-Za-z]/Users/(?!(?:Public|SeuUsuario|Default)\b)[A-Za-z0-9._~-]+",
            re.IGNORECASE,
        ),
    ),
    (
        "CLAUDE_PROJECT_SLUG",
        re.compile(r"C--Users-[A-Za-z0-9._-]+", re.IGNORECASE),
    ),
    (
        "INTERNAL_ASSET_HOSTNAME",
        re.compile(r"\bADM-\d{3,6}\b", re.IGNORECASE),
    ),
    ("LEAKED_SUBNET_10_212", re.compile(r"\b10\.212\.\d{1,3}\.\d{1,3}\b")),
    ("LEAKED_SUBNET_10_10_38", re.compile(r"\b10\.10\.38\.\d{1,3}\b")),
    ("LEAKED_SUBNET_10_10_90", re.compile(r"\b10\.10\.90\.\d{1,3}\b")),
    ("LEAKED_SUBNET_10_200_5", re.compile(r"\b10\.200\.5\.\d{1,3}\b")),
]

TOKEN_RE = re.compile(r"[a-z0-9_~.-]+")
SPLIT_RE = re.compile(r"[._~-]+")


def _should_skip(rel_path: str) -> bool:
    p = pathlib.PurePosixPath(rel_path.replace("\\", "/"))
    if p.name in SKIP_FILENAMES:
        return True
    if p.suffix.lower() in SKIP_EXTENSIONS:
        return True
    return False


def _git_output(args: List[str]) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _iter_tracked_files() -> Iterable[Tuple[str, str]]:
    for rel_path in _git_output(["ls-files"]).splitlines():
        rel_path = rel_path.strip()
        if not rel_path or _should_skip(rel_path):
            continue
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue
        try:
            yield rel_path, full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def _iter_staged_files() -> Iterable[Tuple[str, str]]:
    staged = _git_output(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    ).splitlines()
    for rel_path in staged:
        rel_path = rel_path.strip()
        if not rel_path or _should_skip(rel_path):
            continue
        try:
            raw = subprocess.check_output(
                ["git", "show", f":{rel_path}"],
                cwd=REPO_ROOT,
            )
            yield rel_path, raw.decode("utf-8")
        except (subprocess.CalledProcessError, UnicodeDecodeError):
            continue


def scan_text(rel_path: str, text: str) -> List[Tuple[str, int, str]]:
    """Scan file contents for OPSEC violations without printing sensitive values."""
    violations: List[Tuple[str, int, str]] = []
    seen_on_line = set()

    for lineno, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for tok in TOKEN_RE.findall(low):
            candidates = {tok}
            for part in SPLIT_RE.split(tok):
                if part:
                    candidates.add(part)
            for candidate in candidates:
                digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                rule = BLOCKED_TOKEN_HASHES.get(digest)
                if rule:
                    key = (lineno, f"HASH:{rule}")
                    if key not in seen_on_line:
                        seen_on_line.add(key)
                        violations.append((rel_path, lineno, f"HASH:{rule}"))

        for rule_name, rx in REGEX_RULES:
            if rx.search(line):
                key = (lineno, f"REGEX:{rule_name}")
                if key not in seen_on_line:
                    seen_on_line.add(key)
                    violations.append((rel_path, lineno, f"REGEX:{rule_name}"))

    return violations


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that no private/local environment details leak into tracked or staged files."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan staged git index blobs instead of working-tree tracked files.",
    )
    args = parser.parse_args(argv)

    sources = _iter_staged_files() if args.staged else _iter_tracked_files()
    all_violations: List[Tuple[str, int, str]] = []
    scanned_count = 0

    for rel_path, content in sources:
        scanned_count += 1
        all_violations.extend(scan_text(rel_path, content))

    if all_violations:
        print(
            f"[OPSEC] FALHA: {len(all_violations)} ocorrencia(s) privada(s) detectada(s) em {scanned_count} arquivo(s):"
        )
        for rel_path, lineno, rule in all_violations:
            print(f"  - {rel_path}:{lineno} [{rule}]")
        return 1

    mode_label = "staged" if args.staged else "tracked"
    print(f"[OPSEC] OK: nenhuma informacao privada encontrada ({scanned_count} arquivos {mode_label}).")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
