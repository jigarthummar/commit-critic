## AI Commit Message Critic

A terminal tool that leverages LLMs (via OpenRouter) to analyze Git commit message quality and assist in writing better, Conventional Commit-style messages.

## Features

*   **Analyze Mode**: Review and score existing commits (local or remote) to identify vague or meaningless messages
*   **Write Mode**: Generate Conventional Commit messages based on your staged changes
*   **Configurable**: Uses OpenRouter to support various LLMs (defaults to Claude Sonnet 4.5)

## Requirements

*   Python 3.10+
*   [uv](https://docs.astral.sh/uv/) (recommended) or pip
*   Git installed and available in PATH
*   [OpenRouter](https://openrouter.ai/) API key

## Setup

### 1\. Clone the repository

```plaintext
git clone https://github.com/jigarthummar/commit-critic.git
cd commit-critic
```

### 2\. Create a virtual environment and install dependencies

```plaintext
uv venv   # or: python3 -m venv .venv (if you don't want to use uv)
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt  # or remove uv and just run pip command
```

### 3\. Configure environment

Copy `.env.example` to `.env`:

```plaintext
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:

```plaintext
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```

Get your API key from [OpenRouter](https://openrouter.ai/).

## Usage

### CLI options

| Option | Description |
| --- | --- |
| `--analyze` | Analyze existing commit history (last N commits in current or remote repo). |
| `--write` | Interactive commit message writer: suggest a Conventional Commit from staged changes. |
| `--url=<repo_url>` | Remote Git repo URL to analyze. Use only with `--analyze`. |
| `-n`, `--num <n>` | Number of commits to analyze (default: 50). Use only with `--analyze`. |

You must use either `--analyze` or `--write`; they are mutually exclusive.

### Analyze existing commits

Review the last 50 commits in the current repository:

```plaintext
uv run commit_critic.py --analyze    # or: python commit_critic.py --analyze
```

Review the last 100 commits:

```plaintext
uv run commit_critic.py --analyze -n 100    # or: python commit_critic.py --analyze -n 100
```

Review a remote GitHub repository:

```plaintext
uv run commit_critic.py --analyze --url="https://github.com/user/repo"    # or: python commit_critic.py --analyze --url="..."
```

### Write a new commit message

Stage your changes first, then let the AI suggest a message:

```plaintext
git add .
uv run commit_critic.py --write    # or: python commit_critic.py --write
```

The tool will:

1.  Analyze your staged diff
2.  Suggest a title and body following [Conventional Commits](https://www.conventionalcommits.org/)
3.  Allow you to **Accept** (Enter), **Edit**, or **Quit**

## Scoring System

The AI rates commit messages on a scale of 1–10:

| Score | Meaning | Examples |
| --- | --- | --- |
| **1–2** | Meaningless | "wip", "fix", emoji-only |
| **3–4** | Too vague | "fixed bug", "update logic" |
| **5–6** | Decent | Lacks context or clear scope |
| **7–8** | Good | Clear what/why, helpful scope |
| **9–10** | Exemplary | Perfect Conventional Commit style, concise, measurable impact |