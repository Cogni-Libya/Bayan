"""The yes/no questions every scoring-mode candidate answers (Jev, JevEmbed, Qwen in scoring mode)."""
QUESTIONS = {
    "same": "Does the rewrite keep exactly the same meaning as the original: every fact, claim and qualifier "
            "preserved, and nothing added, removed, negated or changed? Rephrasing, simpler words and splitting "
            "into shorter sentences are allowed.",
    "added": "Does the rewrite state any fact, detail or claim that the original does not state?",
    "missing": "Is any fact, detail or qualifier from the original missing from the rewrite?",
    "contradict": "Does the rewrite contradict the original or reverse any of its claims (for example a negation, "
                  "a different number, swapped roles, or a statement turned into a question)?",
}


def combine(p):
    """One pass score: the pair passes only if it passes every question."""
    return min(p["same"], 1 - p["added"], 1 - p["missing"], 1 - p["contradict"])
