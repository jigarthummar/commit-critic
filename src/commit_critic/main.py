import argparse
import sys
import shutil
import textwrap

from .config import validate_config, load_config
from .git_ops import get_commits, clone_repo, get_staged_diff, run_git
from .llm import get_openrouter_client, llm_analyze, llm_write
from .models import RepoStats
from .ui import styled, print_analysis, print_write_suggestion, BOLD, YELLOW, DIM, RED, GREEN


def cmd_analyze(args) -> None:
    client = get_openrouter_client()
    tmp_dir: str | None = None
    cwd: str | None = None

    try:
        if args.url:
            try:
                tmp_dir = clone_repo(args.url)
                cwd = tmp_dir
            except RuntimeError as e:
                print(styled("Error: ", RED, BOLD) + str(e))
                return

        n = args.num
        print(styled(f"\nAnalyzing last {n} commits…\n", BOLD))
        commits = get_commits(n, cwd=cwd)

        if not commits:
            print(styled("No commits found.", YELLOW))
            return

        print(styled(f"  Found {len(commits)} commits. Sending to AI for review…", DIM))
        critiques = llm_analyze(client, commits)

        stats = RepoStats(
            total=len(critiques),
            avg_score=sum(c.score for c in critiques) / len(critiques) if critiques else 0,
            vague_count=sum(1 for c in critiques if c.score < 5),
            decent_count=sum(1 for c in critiques if 5 <= c.score < 7),
            one_word_count=sum(1 for c in critiques if len(c.message.split()) <= 1),
            good_count=sum(1 for c in critiques if c.score >= 7),
            critiques=critiques,
        )
        print_analysis(stats)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def cmd_write(args) -> None:
    client = get_openrouter_client()

    try:
        diff = get_staged_diff()
    except RuntimeError:
        print(styled("Error: ", RED, BOLD) + "Not inside a Git repository or git is not available.")
        sys.exit(1)

    if not diff:
        print(styled("No staged changes found.", YELLOW))
        print("Stage some files first:  git add <files>")
        sys.exit(1)

    data = llm_write(client, diff)
    print_write_suggestion(data)

    # Interactive accept / edit loop
    full_message = data["summary"]
    if data.get("body"):
        full_message += "\n\n" + "\n".join(f"- {b}" for b in data["body"])

    answer = input("Press Enter to accept, or type your own message (q to quit): ").strip()
    if answer.lower() == "q":
        print("Aborted.")
        return

    if answer:
        full_message = answer

    # Commit
    try:
        run_git(["commit", "-m", full_message])
        print(styled("\n✓ Committed!", GREEN, BOLD))
    except RuntimeError as e:
        print(styled(f"\nCommit failed: {e}", RED))


def main() -> None:
    # Validate env vars before doing anything
    validate_config()

    parser = argparse.ArgumentParser(
        description="AI Commit Message Critic — analyze & improve your Git commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s --analyze                   Review last 50 commits (current repo)
              %(prog)s --analyze -n 100            Review last 100 commits
              %(prog)s --analyze --url=<repo_url>  Review a remote repository
              %(prog)s --write                     Suggest a commit for staged changes
        """),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--analyze", action="store_true", help="Analyze existing commit history")
    group.add_argument("--write", action="store_true", help="Interactive commit message writer")

    parser.add_argument("--url", type=str, default=None,
                        help="Remote Git repo URL to analyze (used with --analyze)")
    parser.add_argument("-n", "--num", type=int, default=50,
                        help="Number of commits to analyze (default: 50)")

    args = parser.parse_args()

    if args.url and not args.analyze:
        parser.error("--url can only be used with --analyze")

    if args.analyze:
        cmd_analyze(args)
    else:
        cmd_write(args)

if __name__ == "__main__":
    main()
