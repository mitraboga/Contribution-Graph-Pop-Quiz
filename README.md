# Contribution Graph Pop Quiz — Telegram Bot

A Telegram bot that quizzes users on their GitHub contribution graph. It pulls the public contributions SVG (no GitHub token required), generates multiple-choice questions, tracks score, and supports both polling and webhook deployment.

## Quick Start (Local / Polling)
1) Python 3.10+ (3.11 recommended)
2) Copy `.env.example` → `.env`, paste your BotFather token
3) Create venv & install:
```bash
python -m venv .venv
# Windows PowerShell:
. .venv/Scripts/activate
pip install -r requirements.txt
