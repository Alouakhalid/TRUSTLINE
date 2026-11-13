"""Shared pytest configuration and sys.path resolution for supervisor test suite."""
import os
import sys
from pathlib import Path

supervisor_tests_dir = Path(__file__).resolve().parent
agents_dir = supervisor_tests_dir.parent.parent
ai_engine_dir = agents_dir.parent
root_dir = ai_engine_dir.parent

for p in (root_dir, ai_engine_dir, agents_dir):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)
