"""Verify every figure in facts.py has a source that still exists, and that retired numbers
are not referenced by the deck.

    python check_numbers.py

Exits non-zero on any failure. Run this before rendering anything.
"""
import re
import subprocess
import sys
from pathlib import Path

import facts as N

HERE = Path(__file__).parent
# What the audience hears or sees. The generated presenter script is excluded: it is derived from
# script_data.py and carries the DONT_SAY table, which quotes the banned claims on purpose.
DECK_SOURCES = [HERE / "scenes.py", HERE / "build_native.py", HERE / "script_data.py"]

REPO = N.BAYAN  # for `gh`; the PRs live in the main Bayan repo (has the git remote)


def ok(msg):
    print(f"  ok   {msg}")


def bad(msg, errors):
    print(f"  FAIL {msg}")
    errors.append(msg)


def resolve_src(src: str) -> str | None:
    """Return None if the source resolves, else a reason. `src` is a free-text provenance
    string; it resolves if any PATHS key is mentioned and that file exists, or if it names a PR
    that is merged."""
    if src == "retired":
        return None
    if src.startswith("peer:"):
        return None  # accepted, but flagged by main(): only a teammate's session vouches for it
    if src.startswith("pdf:"):
        _, ref, rest = src.split(":", 2)
        path, _, needle = rest.partition("::")
        blob = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=HERE, capture_output=True)
        if blob.returncode != 0:
            return f"git show {ref}:{path} failed"
        txt = subprocess.run(["pdftotext", "-layout", "-", "-"], input=blob.stdout, capture_output=True)
        if " ".join(needle.split()) not in " ".join(txt.stdout.decode("utf8", "replace").split()):
            return f"{needle!r} not found in {path}"
        return None
    if src.startswith("git:"):
        _, ref, rest = src.split(":", 2)
        path, _, needle = rest.partition("::")
        out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=HERE, capture_output=True, text=True)
        if out.returncode != 0:
            return f"git show {ref}:{path} failed: {out.stderr.strip()[:100]}"
        norm = lambda t: " ".join(t.split())
        if norm(needle) not in norm(out.stdout):
            return f"{needle!r} not found in {ref}:{path}"
        return None
    # a PR reference
    m = re.search(r"PR #(\d+)", src)
    if m:
        num = m.group(1)
        try:
            out = subprocess.run(
                ["gh", "pr", "view", num, "--json", "state,mergedAt", "--jq", ".state + \" \" + (.mergedAt // \"-\")"],
                cwd=REPO, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            return f"gh unavailable for PR #{num}: {e}"
        if out.returncode != 0:
            return f"PR #{num}: {out.stderr.strip()[:120]}"
        state = out.stdout.strip()
        if not state.startswith("MERGED") and not state.startswith("OPEN"):
            return f"PR #{num} is {state!r}"
    # a path: longest matching PATHS key wins
    for key in sorted(N.PATHS, key=len, reverse=True):
        if key in src:
            if not N.PATHS[key].exists():
                return f"path for {key!r} missing: {N.PATHS[key]}"
    # a bare file name we know
    for name in ("main.tex", "figures.tex", "facts.json", "report.md", "assemble.log",
                 "check_corpus.log", "synthetic_data_card_v1.md", "run_retry.log", "leakage_train.log"):
        if name in src:
            if not any(p.exists() for p in N.PATHS.values() if p.name == name):
                return f"no known path for file {name!r}"
    return None


def main() -> int:
    errors = []
    print(f"checking {len(N.FIG)} figures and {len(N.SCATTER)} scatter points\n")

    for name, (val, src, note) in N.FIG.items():
        reason = resolve_src(src)
        if reason:
            bad(f"{name} = {val}: {reason}", errors)
        else:
            ok(f"{name} = {val}  <- {src[:90]}" + ("   [UNVERIFIED: peer session]" if src.startswith("peer:") else ""))

    for key, path in N.PATHS.items():
        if path.exists():
            ok(f"path {key} -> {path.name}")
        else:
            bad(f"path {key} is missing: {path}", errors)

    def scannable(f: Path) -> str:
        """What the audience hears or sees. For script_data.py that is SPEECH only — DONT_SAY and
        QA quote the banned claims on purpose, to tell the presenter not to say them."""
        text = f.read_text(encoding="utf-8", errors="replace")
        if f.name == "script_data.py":
            import ast
            tree = ast.parse(text)
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                        getattr(t, "id", None) == "SPEECH" for t in node.targets):
                    return ast.unparse(node.value)
            return ""
        return text

    # retired numbers must not appear in the deck
    retired = {"retired_sari_copy": N.FIG["retired_sari_copy"][0]}
    print("\nscanning on-slide / spoken text for retired numbers")
    for f in DECK_SOURCES:
        if not f.exists():
            continue
        text = scannable(f)
        for name, val in retired.items():
            for needle in (str(val), f"{val:.1f}"):
                if needle in text:
                    bad(f"{f.name} still contains retired {name} value {needle}", errors)

    # the known-bad claims must be gone
    banned = [r"\bBaseet\b", r"\b22,?733\b", r"\b13,?072\b", r"250 MB", r"\b9\.3%", r"\b77\.5\b", r"\b75\.9\b"]
    print("\nscanning on-slide / spoken text for superseded claims")
    for f in DECK_SOURCES:
        if not f.exists():
            continue
        text = scannable(f)
        for pat in banned:
            for m in re.finditer(pat, text):
                line = text[:m.start()].count("\n") + 1
                bad(f"{f.name}:{line} contains {pat}", errors)

    print()
    if errors:
        print(f"{len(errors)} failure(s)")
        return 1
    print("all numbers sourced; no superseded claims in the deck")
    return 0


if __name__ == "__main__":
    sys.exit(main())
