## 🔍 AI Commit Message Critic

A terminal tool that uses Claude to analyze Git commit message quality and help you write better commits.

## Setup

```plaintext
pip install -r requirements.txt
export OPENROUTER_API_KEY="sk-ant-..."
```

## Usage

### Analyze mode — review existing commits

```plaintext
# Analyze last 50 commits in the current repo
python commit_critic.py --analyze

# Analyze last 100 commits
python commit_critic.py --analyze -n 100

# Analyze a remote repository
python commit_critic.py --analyze --url="https://github.com/user/repo"
```

### Write mode — interactive commit writer

```plaintext
# Stage your changes first
git add .

# Let AI suggest a commit message
python commit_critic.py --write
```

The tool will analyze your staged diff, detect the logical changes, and suggest a  
Conventional Commit–style message. Press **Enter** to accept, type your own, or **q** to quit.

## What it scores

| Score | Meaning |
| --- | --- |
| 1–2 | Meaningless — "wip", "fix", single word |
| 3–4 | Too vague — "fixed bug", "update" |
| 5–6 | Decent but unclear scope or missing _why_ |
| 7–8 | Good — clear type/scope, describes what & why |
| 9–10 | Exemplary — conventional commit, concise, measurable impact |

## Requirements

*   Python 3.10+
*   Git
*   An [Anthropic API key](https://console.anthropic.com/)