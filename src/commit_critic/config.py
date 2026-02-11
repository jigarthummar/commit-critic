import os
import sys
import logging
import dotenv
from .ui import styled, RED, BOLD

LOG = logging.getLogger("commit_critic")


def load_config():
    dotenv.load_dotenv()
    
    # We can validate here or just return values
    key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
    
    return key, base_url, model


def setup_logging(verbose: bool = False) -> None:
    """Enable debug logging when COMMIT_CRITIC_DEBUG=1 or --verbose."""
    level = logging.DEBUG if (verbose or os.getenv("COMMIT_CRITIC_DEBUG")) else logging.WARNING
    LOG.setLevel(level)
    if level == logging.DEBUG and not LOG.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(logging.DEBUG)
        LOG.addHandler(h)


def validate_config():
    key, _, _ = load_config()
    if not key:
        print(styled("Error: ", RED, BOLD) + "OPENROUTER_API_KEY environment variable is not set.")
        print("  Create a .env file with OPENROUTER_API_KEY=sk-or-...")
        sys.exit(1)
