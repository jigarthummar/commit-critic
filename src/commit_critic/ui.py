# ──────────────────────────────────────────────
# ANSI helpers
# ──────────────────────────────────────────────
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
RULE = "━" * 48


def styled(text: str, *codes: str) -> str:
    return "".join(codes) + text + RESET

def print_analysis(stats) -> None:
    bad = [c for c in stats.critiques if c.score < 7]
    good = [c for c in stats.critiques if c.score >= 7]

    # ── Bad commits ──
    if bad:
        print()
        print(styled(RULE, RED))
        print(styled("💩 COMMITS THAT NEED WORK", RED, BOLD))
        print(styled(RULE, RED))
        for c in sorted(bad, key=lambda x: x.score):
            print()
            trunc = c.message.splitlines()[0][:80]
            print(f'  Commit: {styled(f"{trunc!r}", YELLOW)}')
            color = RED if c.score <= 3 else YELLOW
            print(f"  Score:  {styled(f'{c.score}/10', color, BOLD)}")
            if c.issue:
                print(f"  Issue:  {c.issue}")
            if c.suggestion:
                print(f"  Better: {styled(c.suggestion, GREEN)}")

    # ── Good commits ──
    if good:
        print()
        print(styled(RULE, GREEN))
        print(styled("💎 WELL-WRITTEN COMMITS", GREEN, BOLD))
        print(styled(RULE, GREEN))
        for c in sorted(good, key=lambda x: -x.score)[:10]:
            print()
            trunc = c.message.splitlines()[0][:80]
            print(f'  Commit: {styled(f"{trunc!r}", CYAN)}')
            print(f"  Score:  {styled(f'{c.score}/10', GREEN, BOLD)}")
            if c.praise:
                print(f"  Why:    {c.praise}")

    # ── Stats ──
    print()
    print(styled(RULE, MAGENTA))
    print(styled("📊 YOUR STATS", MAGENTA, BOLD))
    print(styled(RULE, MAGENTA))
    print(f"  Total commits analyzed : {stats.total}")
    print(f"  Average score          : {styled(f'{stats.avg_score:.1f}/10', BOLD)}")
    pct_vague = (stats.vague_count / stats.total * 100) if stats.total else 0
    pct_one = (stats.one_word_count / stats.total * 100) if stats.total else 0
    pct_good = (stats.good_count / stats.total * 100) if stats.total else 0
    print(f"  Vague commits          : {stats.vague_count} ({pct_vague:.0f}%)")
    print(f"  One-word commits       : {stats.one_word_count} ({pct_one:.0f}%)")
    print(f"  Good commits (≥7)      : {stats.good_count} ({pct_good:.0f}%)")
    print()


def print_write_suggestion(data: dict) -> None:
    print()
    print(styled("Analyzing staged changes…", DIM))
    print()

    if data.get("changes_detected"):
        print(styled("Changes detected:", BOLD))
        for ch in data["changes_detected"]:
            print(f"  • {ch}")
        print()

    print(styled("Suggested commit message:", BOLD))
    print(styled(RULE, CYAN))
    print(styled(data["summary"], CYAN, BOLD))
    if data.get("body"):
        print()
        for b in data["body"]:
            print(f"  - {b}")
    print(styled(RULE, CYAN))
    print()
