# last30days — Deep Research Skill

External skill: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)

## What it does
Research any topic across 10+ platforms (Reddit, X, YouTube, TikTok, Instagram, Hacker News, Polymarket, Bluesky, Truth Social, web) from the last 30 days. AI synthesizes findings into grounded, cited briefings.

## Installation
Installed automatically by `install.sh --profile=full`:
```bash
git clone https://github.com/mvanhorn/last30days-skill.git ~/.claude/skills/last30days
```

## Required API keys
- `SCRAPECREATORS_API_KEY` (required — covers Reddit, TikTok, Instagram)

## Optional API keys
- `OPENAI_API_KEY` — synthesis quality
- `XAI_API_KEY` — X/Twitter search via Grok
- `BRAVE_API_KEY` — web search
- `OPENROUTER_API_KEY` or `PARALLEL_API_KEY` — alternative web search
- `BSKY_HANDLE` + `BSKY_APP_PASSWORD` — Bluesky
- `TRUTHSOCIAL_TOKEN` — Truth Social

## Usage
```
/last30days Claude Code tips
/last30days best project management tools --quick
/last30days X vs Y (comparison mode)
```

## Triggers
last30, last30days, research, deep research, what's trending, what people say about

## Version
Tracks upstream v2.9.5+. Updates via `cd ~/.claude/skills/last30days && git pull`.
