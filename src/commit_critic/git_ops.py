import subprocess
import tempfile
from .models import CommitInfo
from .ui import styled, DIM

def run_git(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=cwd,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def get_commits(n: int = 50, cwd: str | None = None) -> list[CommitInfo]:
    """Return last *n* commits from the repo at *cwd*."""
    # Use null byte as separator to avoid collision
    sep = "%x00"
    fmt = f"%H%n%an%n%ai%n%B{sep}"
    log = run_git(["log", f"-{n}", f"--pretty=format:{fmt}"], cwd=cwd)
    commits = []
    # Strip the final separator if present and split
    blocks = log.strip(sep).split(sep)
    
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 4:
            continue
        commits.append(CommitInfo(
            hash=lines[0].strip(),
            author=lines[1].strip(),
            date=lines[2].strip(),
            message="\n".join(lines[3:]).strip(),
        ))
    return commits


def get_staged_diff(cwd: str | None = None) -> str:
    return run_git(["diff", "--staged"], cwd=cwd)


def clone_repo(url: str) -> str:
    """Shallow-clone *url* into a temp directory; return its path."""
    tmp = tempfile.mkdtemp(prefix="commit_critic_")
    print(styled(f"Cloning {url} …", DIM))
    try:
        subprocess.run(
            ["git", "clone", "--bare", "--filter=blob:none", url, tmp],
            check=True, capture_output=True, text=True, timeout=300,
        )
        return tmp
    except subprocess.TimeoutExpired:
        # Clean up the partial directory
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"Cloning timed out (over 5 minutes). The repository might be too large or the network is slow.")
    except subprocess.CalledProcessError as e:
        # Clean up the empty/partial directory
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        
        # Parse error for better messages
        err_msg = e.stderr.lower()
        if "authentication failed" in err_msg or "permission denied" in err_msg:
            raise RuntimeError(f"Authentication failed for {url}.\n"
                               f"If this is a private repo, try cloning it manually first and run without --url.")
        elif "repository not found" in err_msg or "could not read from remote" in err_msg:
             raise RuntimeError(f"Repository not found or not accessible: {url}")
        else:
            raise RuntimeError(f"Git clone failed:\n{e.stderr.strip()}")
