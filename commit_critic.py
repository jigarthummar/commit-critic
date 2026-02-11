#!/usr/bin/env python3
"""
AI Commit Message Critic — Analyze commit quality & write better commits.
Entry point script.
"""
import sys
import os

# Add 'src' to sys.path so we can import the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from commit_critic.main import main

if __name__ == "__main__":
    main()


# Just wated to test the commit critic