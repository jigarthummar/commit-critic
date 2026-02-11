import json
import sys
import textwrap
from openai import OpenAI
from .models import CommitInfo, CommitCritique
from .ui import styled, DIM, YELLOW, RED
from .config import load_config, LOG

ANALYSIS_SYSTEM = textwrap.dedent("""\
    You are a senior developer who reviews Git commit messages against the
    Conventional Commits specification.

    ## Conventional Commits Rules (Reference for Scoring)

    A valid commit message MUST be structured as:
```
    <type>[optional scope]: <description>

    [optional body]

    [optional footer(s)]
```

    ### Valid Types
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

    ### Rules to Check
    - The message MUST be prefixed with a valid type, followed by an OPTIONAL
      scope in parentheses, OPTIONAL `!` (for breaking changes), and a REQUIRED
      terminal colon and space. e.g., `feat(parser): add ability to parse arrays`
    - A scope, if provided, MUST be a noun describing a section of the codebase
      surrounded by parentheses. e.g., `fix(parser):`
    - The description MUST immediately follow the colon and space.
    - Breaking changes MUST be indicated by `!` after the type/scope before the
      colon, OR as a footer: `BREAKING CHANGE: <description>` (uppercase).
    - Footer tokens MUST use `-` in place of whitespace (e.g., `Acked-by`),
      except `BREAKING CHANGE` which may use a space.
    - For `revert` commits, the body SHOULD contain: `This reverts commit <hash>.`

    ## Scoring Guide

    Score each commit message 1-10 based on how well it follows the spec:

    1-2  : Meaningless — "wip", "fix", single word, emoji-only, no type prefix
            An empty, blank, or missing commit message MUST be scored 1-2.
    3-4  : Too vague, no context — "fixed bug", "update", "changes", missing
            type or has wrong format (e.g., `Fix bug` instead of `fix: ...`)
    5-6  : Decent but flawed — has a type but missing scope where one would
            help, description is vague, wrong type used (e.g., `fix` for a
            refactor), overly long summary, or body included but unhelpful
    7-8  : Good — correct type, clear scope, describes *what* changed and
            *why*, follows the colon-space format, appropriate length
    9-10 : Exemplary — fully conventional-commit compliant, concise, specific,
            measurable impact, correct type and scope, body/footer used
            appropriately when needed


    ## Task

    You will receive a JSON array of commits. For EACH commit, return a JSON
    object with:
      - hash:       the short hash (first 8 chars)
      - message:    the original commit message (first line only)
      - score:      integer 1-10
      - issue:      (if score < 7) a short explanation of what's wrong,
                    referencing the specific rule(s) violated
      - suggestion: (if score < 7) a concrete improved commit message that
                    follows the full Conventional Commits spec
      - praise:     (if score >= 7) why the commit message is good,
                    referencing which rules it follows well

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

        LOG.debug("LLM request batch %s: payload=%s", idx + 1, payload)

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
        LOG.debug("LLM response batch %s (raw): %s", idx + 1, text[:2000] + ("..." if len(text) > 2000 else ""))

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
            critique = CommitCritique(
                hash=item.get("hash", ""),
                message=item.get("message", ""),
                score=int(item.get("score", 0)),
                issue=item.get("issue", ""),
                suggestion=item.get("suggestion", ""),
                praise=item.get("praise", ""),
            )
            LOG.debug("Parsed critique: hash=%r message=%r score=%s", critique.hash, critique.message, critique.score)
            all_critiques.append(critique)

    return all_critiques


def llm_write(client, diff: str, model: str | None = None) -> dict:
    """Ask LLM via OpenRouter to suggest a commit message based on staged diff."""
    if model is None:
        _, _, model = load_config()
        
    # Truncate very large diffs to stay within context limits
    max_diff_chars = 100_000
    if len(diff) > max_diff_chars:
        print(styled(f"  Warning: Diff is too large ({len(diff)} chars). Truncating to {max_diff_chars} chars.", YELLOW))
        diff = diff[:max_diff_chars] + "\n\n... [diff truncated] ..."

    user_msg = f"Here is the `git diff --staged`:\n```\n{diff}\n```"

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=6000,
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
