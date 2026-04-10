#!/usr/bin/env python3
"""
SEO morning brief — orchestrates Phase 1 subagents via the Claude Agent SDK.

Runs two agents in sequence:
  1. seo-gsc-analyst   → pulls GSC data for all 3 sites
  2. seo-site-crawler  → inventories MDX content on all 3 sites

Aggregates both findings into one markdown digest, saves it under
scripts/seo/reports/YYYY-MM-DD-morning.md, and pings Telegram via notify.py.

Usage:
  python3 scripts/seo/morning_brief.py
  python3 scripts/seo/morning_brief.py --site glow-coded      # single site
  python3 scripts/seo/morning_brief.py --skip-telegram        # dry run

Requirements:
  - Claude Code CLI logged in (`claude /login`) on this machine
  - claude-agent-sdk installed (`pip install claude-agent-sdk`)
  - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in env (or .env loaded)
  - GSC token at ~/.config/gsc-token.json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock
except ImportError:
    print(
        "ERROR: claude-agent-sdk not installed.\n"
        "  pip install claude-agent-sdk",
        file=sys.stderr,
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "scripts" / "seo" / "reports"
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify.py"


def _load_dotenv() -> None:
    """Load REPO_ROOT/.env into os.environ if present. Minimal parser."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


async def run_agent(agent_name: str, prompt: str, timeout_s: int = 180) -> str:
    """
    Invoke a project-level subagent and return its final text output.
    Uses setting_sources=["project"] to load .claude/agents/seo/*.md.
    """
    options = ClaudeAgentOptions(
        setting_sources=["project"],
        cwd=str(REPO_ROOT),
        allowed_tools=["Read", "Grep", "Glob", "Bash", "WebFetch"],
        permission_mode="bypassPermissions",
    )

    full_prompt = f"@{agent_name} {prompt}"
    chunks: list[str] = []
    result_text: str | None = None

    async def _drain() -> None:
        nonlocal result_text
        async for message in query(prompt=full_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                result_text = getattr(message, "result", None)
                return

    try:
        await asyncio.wait_for(_drain(), timeout=timeout_s)
    except asyncio.TimeoutError:
        chunks.append(f"\n\n⏱️ Agent {agent_name} timed out after {timeout_s}s.")

    return (result_text or "\n".join(chunks)).strip() or f"(no output from {agent_name})"


def notify_telegram(title: str, body: str, level: str = "report") -> None:
    if not NOTIFY_SCRIPT.exists():
        print(f"notify: {NOTIFY_SCRIPT} not found, skipping", file=sys.stderr)
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        print("notify: TELEGRAM_BOT_TOKEN/CHAT_ID not set, skipping", file=sys.stderr)
        return
    try:
        subprocess.run(
            [
                sys.executable,
                str(NOTIFY_SCRIPT),
                "--stdin",
                "--level", level,
                "--title", title,
            ],
            input=body,
            text=True,
            check=True,
            timeout=20,
        )
    except subprocess.CalledProcessError as e:
        print(f"notify: send failed ({e})", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("notify: send timed out", file=sys.stderr)


async def main_async(args: argparse.Namespace) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    site_scope = args.site or "all 3 sites (glow-coded.com, rooted-glow.com, mirai-skin.com)"

    gsc_prompt = (
        f"Run the standard brief for {site_scope}. "
        "Return the structured markdown blocks described in your spec. "
        "Skip any commentary."
    )
    crawler_prompt = (
        "Audit content inventory for cosmetics/, wellness/, and build-coded/. "
        "Return one markdown block per site with inventory, orphans, thin content, "
        "missing frontmatter, missing FAQ, and hub coverage. No recommendations."
    )

    print(f"[{today}] dispatching seo-gsc-analyst …")
    gsc_out = await run_agent("seo-gsc-analyst", gsc_prompt, timeout_s=240)

    print(f"[{today}] dispatching seo-site-crawler …")
    crawler_out = await run_agent("seo-site-crawler", crawler_prompt, timeout_s=240)

    digest = (
        f"# SEO morning brief · {today}\n\n"
        f"## GSC findings\n\n{gsc_out}\n\n"
        f"---\n\n"
        f"## Content inventory\n\n{crawler_out}\n"
    )

    report_file = REPORTS_DIR / f"{today}-morning.md"
    report_file.write_text(digest)
    print(f"[{today}] wrote {report_file.relative_to(REPO_ROOT)}")

    if not args.skip_telegram:
        short_summary = (
            f"GSC + content crawl complete for {site_scope}.\n"
            f"Full digest: scripts/seo/reports/{today}-morning.md"
        )
        notify_telegram(
            title=f"SEO morning brief · {today}",
            body=short_summary,
            level="report",
        )
        print(f"[{today}] telegram ping sent")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SEO morning brief.")
    parser.add_argument(
        "--site",
        choices=["glow-coded", "rooted-glow", "mirai-skin"],
        help="Limit analysis to a single site (default: all 3).",
    )
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Don't send the Telegram ping (useful for dry runs).",
    )
    args = parser.parse_args()

    _load_dotenv()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
