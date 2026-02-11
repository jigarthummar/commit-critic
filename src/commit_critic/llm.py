import json
import sys
import textwrap
from openai import OpenAI
from .models import CommitInfo, CommitCritique
from .ui import styled, DIM, YELLOW, RED
from .config import load_config

ANALYSIS_SYSTEM = textwrap.dedent("""\
    You are a senior developer who reviews Git commit messages.
    You will receive a JSON array of commits. For EACH commit, return a JSON object with:
      - hash: the short hash (first 8 chars)
      - message: the original commit message (first line only)
      - score: integer 1-10
      - issue: (if score < 7) a short explanation of the problem
      - suggestion: (if score < 7) a concrete improved commit message
      - praise: (if score >= 7) why the commit message is good

    Scoring guide:
      1-2: meaningless ("wip", "fix", single word, emoji-only)
      3-4: too vague, no context ("fixed bug", "update")
      5-6: decent but could be clearer or lacks scope
      7-8: good — clear type/scope, describes *what* and *why*
      9-10: exemplary — conventional-commit style, concise, measurable impact

    Return ONLY a JSON array. No markdown fences, no commentary.
""")

WRITE_SYSTEM = textwrap.dedent("""\
    You are a senior developer helping write the perfect commit message.
    Given a `git diff --staged` output, produce a commit message following
    the Conventional Commits specification.

    ## Conventional Commits Rules

    The commit message MUST be structured as:
```
    <type>[optional scope]: <description>

    [optional body]

    [optional footer(s)]
```

    ### Types
    Choose the MOST appropriate type based on the primary intent of the change:

    - feat:     A new feature (correlates with MINOR in SemVer)
    - fix:      A bug fix (correlates with PATCH in SemVer)
    - docs:     Documentation only changes
    - style:    Changes that do not affect the meaning of the code
                (white-space, formatting, missing semi-colons, etc)
    - refactor: A code change that improves code structure without changing
                functionality (renaming, restructuring classes/methods,
                extracting functions, etc)
    - perf:     A code change that improves performance
    - test:     Adding missing tests or correcting existing tests
    - build:    Changes that affect the build system or external dependencies
    - ci:       Changes to CI configuration files and scripts
    - chore:    Other changes that don't modify src or test files
    - revert:   Reverts a previous commit

    ### Rules
    - The summary MUST be prefixed with a type (noun), followed by an OPTIONAL
      scope in parentheses, OPTIONAL `!` (for breaking changes), and a REQUIRED
      terminal colon and space. e.g., `feat(parser): add ability to parse arrays`
    - Use `feat` when the commit adds a new feature.
    - Use `fix` when the commit represents a bug fix.
    - A scope, if provided, MUST be a noun describing a section of the codebase
      surrounded by parentheses. e.g., `fix(parser):`
    - The description MUST immediately follow the colon and space. It is a short
      summary of the code changes.
    - Breaking changes MUST be indicated by appending `!` after the type/scope
      and before the colon, OR as a footer: `BREAKING CHANGE: <description>`.
      BREAKING CHANGE MUST be uppercase.
    - Types other than feat and fix are NOT case sensitive, but BREAKING CHANGE
      MUST always be uppercase.
    - For `revert` commits, the body SHOULD contain: `This reverts commit <hash>.`

    ### Body Guidelines
    CRITICAL: The body must ONLY contain significant, meaningful changes.
    - DO NOT mention "whitespace cleanup", "formatting", or "file ending" fixes.
    - DO NOT mention "cosmetic changes" or trivial reformatting.
    - If the change is only whitespace/formatting, return a summary but NO body.
    - Each bullet should describe one logical change concisely.

    ### Footer Guidelines
    - Footers follow git trailer format: `Token: value` or `Token #value`
    - Footer tokens MUST use `-` in place of whitespace (e.g., `Acked-by`),
      except for `BREAKING CHANGE` which may use a space.
    - Include a `BREAKING CHANGE:` footer when introducing breaking API changes
      (if not already indicated with `!` in the type/scope prefix).

    ## Output Format
    Return ONLY a JSON object with no markdown fences and no extra text:
    {
      "summary": "one-line summary in conventional-commit format",
      "body": ["bullet 1", "bullet 2", ...],
      "breaking_change": "description if applicable, otherwise null",
      "changes_detected": ["high-level description of each logical change"]
    }
""")


def get_openrouter_client():
    key, base_url, _ = load_config()
    if not key:
        # Should have been caught by validate_config, but just in case
        sys.exit(1)

    return OpenAI(
        base_url=base_url,
        api_key=key,
    )


def llm_analyze(client, commits: list[CommitInfo], model: str | None = None, batch_size: int = 25) -> list[CommitCritique]:
    """Send commits to LLM via OpenRouter in batches and return critiques."""
    if model is None:
        _, _, model = load_config()
        
    all_critiques: list[CommitCritique] = []
    batches = [commits[i:i + batch_size] for i in range(0, len(commits), batch_size)]

    for idx, batch in enumerate(batches):
        if len(batches) > 1:
            print(styled(f"  Analyzing batch {idx + 1}/{len(batches)} …", DIM))

        payload = json.dumps([
            {"hash": c.hash[:8], "message": c.message}
            for c in batch
        ], indent=2)

        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=10000,
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM},
                    {"role": "user", "content": payload},
                ],
            )
        except Exception as e:
            print(styled(f"  Error calling AI API: {e}", RED))
            continue

        text = resp.choices[0].message.content.strip()

        # Robustly parse — strip markdown fences if present
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:])
        if text.endswith("```"):
            text = "\n".join(text.splitlines()[:-1])

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            print(styled("  Warning: could not parse LLM response for a batch. Skipping.", YELLOW))
            continue

        for item in items:
            all_critiques.append(CommitCritique(
                hash=item.get("hash", ""),
                message=item.get("message", ""),
                score=int(item.get("score", 5)),
                issue=item.get("issue", ""),
                suggestion=item.get("suggestion", ""),
                praise=item.get("praise", ""),
            ))

    return all_critiques


def llm_write(client, diff: str, model: str | None = None) -> dict:
    """Ask LLM via OpenRouter to suggest a commit message based on staged diff."""
    if model is None:
        _, _, model = load_config()
        
    # Truncate very large diffs to stay within context limits
    max_diff_chars = 60_000
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n\n... [diff truncated] ..."

    user_msg = f"Here is the `git diff --staged`:\n```\n{diff}\n```"

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=10000,
            messages=[
                {"role": "system", "content": WRITE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        # For write mode, failing is critical, so we exit or return empty
        print(styled(f"Error calling AI API: {e}", RED))
        sys.exit(1)

    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:])
    if text.endswith("```"):
        text = "\n".join(text.splitlines()[:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(styled("Error: AI returned invalid JSON. Try again.", RED))
        sys.exit(1)
