# AGENTS.md

This file defines how AI coding agents (Codex, Copilot agents, etc.) should work in this repository.

Agents should follow these rules to ensure changes remain safe, reproducible, and easy to review.

---

# Project Overview

This is a Python project using a modern toolchain:

Python environment: uv  
Package layout: src/  
Testing: pytest  
Linting: ruff  
Typing: pyright  
Editor: VS Code  

Repository layout:

src/
  codenames_llm/
    __init__.py
    __main__.py

tests/

pyproject.toml
README.md
AGENTS.md

---

# Running the Project

Run the application: