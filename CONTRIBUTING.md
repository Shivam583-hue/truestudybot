# Contributing to Professor Moore

Thanks for your interest in contributing. Here's how to get started.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/professor-moore.git
   cd professor-moore
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `config.py` with your test bot token (see README)
5. Run the bot: `python bot.py`

## Development Guidelines

### Code Style

- No docstrings, type annotations on simple functions, or unnecessary abstractions
- Keep it simple. Three similar lines are better than a premature helper function.
- Follow the existing patterns in the codebase

### Image Generation

All visual output uses Pillow (PIL). If you're adding a new image:

- Match the existing color palette in the file you're working on (`BG_COLOR`, `ACCENT`, `TEXT_WHITE`, etc.)
- Use the `_font()` helper for all fonts
- Use `_wrap_text()` for any user-facing text that could overflow
- Make image height dynamic when content length varies
- Test with long names and edge cases

### Database

- All queries in `database.py` are scoped by `guild_id`
- Active sessions use `LIVE_DUR` for real-time duration calculation
- Add migrations in `init_db()` if altering existing tables

### Commands

- Every command should work as both `!prefix` and `/slash`
- Slash commands that generate images should use `defer()` + `followup.send()`
- Use `_make_view()` for Components V2 text responses

## Pull Requests

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test with a real Discord bot in a test server
4. Keep commits focused and messages short
5. Open a PR with a clear description of what changed and why

## Reporting Issues

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Bot logs if applicable

## Font Requirements

The bot requires these fonts installed on the system:
- Roboto family: Bold, Medium, Regular, Light, Black, Condensed
- Liberation Serif

On Arch Linux: `sudo pacman -S ttf-roboto ttf-liberation`
On Ubuntu/Debian: `sudo apt install fonts-roboto fonts-liberation`
