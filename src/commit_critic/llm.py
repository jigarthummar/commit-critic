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
    Conventional Commits (type(scope): description) with an optional body of
    bullet points describing the key changes.

    Return ONLY a JSON object:
    {
      "summary": "one-line summary in conventional-commit format",
      "body": ["bullet 1", "bullet 2", ...],
      "changes_detected": ["high-level description of each logical change"]
    }
    No markdown fences. No extra text.
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
                max_tokens=4096,
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
            max_tokens=2048,
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
