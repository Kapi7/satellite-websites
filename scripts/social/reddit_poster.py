#!/usr/bin/env python3
"""
Reddit comment poster + reply checker using Playwright browser automation.
Finds relevant threads and posts AI-generated, context-aware comments.
Monitors replies to our comments and can generate AI responses.

Comment types:
  - "value": No links. Genuinely helpful advice to build karma/credibility.
  - "link":  Includes a link to an article. Use sparingly after building karma.

Usage:
    python3 reddit_poster.py --check            # Show pending posts
    python3 reddit_poster.py --run-due           # Post all due comments (up to daily limit)
    python3 reddit_poster.py --post 5            # Post specific entry by ID
    python3 reddit_poster.py --dry-run           # Simulate posting (shows generated comment)
    python3 reddit_poster.py --headed            # Run with visible browser
    python3 reddit_poster.py --login             # Log in and save session (CAPTCHA)
    python3 reddit_poster.py --stats             # Show schedule stats
    python3 reddit_poster.py --check-replies     # Check for replies to our posted comments
    python3 reddit_poster.py --check-replies --reply  # Also generate + post AI replies
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    REDDIT_USERNAME, REDDIT_PASSWORD,
    REDDIT_SCHEDULE, REDDIT_MAX_PER_DAY,
    BROWSER_STATE_DIR, DATA_DIR,
    BROWSER_ARGS, DELAY_SHORT, DELAY_MEDIUM, DELAY_LONG, DELAY_PAGE_LOAD,
    GEMINI_API_KEY,
)


# ── Utilities ─────────────────────────────────────────────────

def human_delay(delay_range):
    time.sleep(random.uniform(*delay_range))


def load_schedule():
    with open(REDDIT_SCHEDULE) as f:
        return json.load(f)


def save_schedule(schedule):
    with open(REDDIT_SCHEDULE, "w") as f:
        json.dump(schedule, f, indent=2)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "reddit.log", "a") as f:
        f.write(line + "\n")


def get_due_posts(schedule):
    today = datetime.now().date().isoformat()
    return [p for p in schedule if p["status"] == "pending" and p["scheduled_date"] <= today]


def show_status(schedule):
    pending = [p for p in schedule if p["status"] == "pending"]
    posted = [p for p in schedule if p["status"] == "posted"]
    failed = [p for p in schedule if p["status"] == "failed"]
    skipped = [p for p in schedule if p["status"] == "skipped"]
    due = get_due_posts(schedule)

    value_pending = [p for p in pending if p.get("comment_type", "link") == "value"]
    link_pending = [p for p in pending if p.get("comment_type", "link") == "link"]
    value_posted = [p for p in posted if p.get("comment_type", "link") == "value"]
    link_posted = [p for p in posted if p.get("comment_type", "link") == "link"]

    print(f"\nReddit Schedule Status")
    print(f"{'='*50}")
    print(f"Total: {len(schedule)} | Posted: {len(posted)} | Pending: {len(pending)} | Failed: {len(failed)} | Skipped: {len(skipped)}")
    print(f"\nBy type:")
    print(f"  Value (no link):  {len(value_posted)} posted / {len(value_pending)} pending")
    print(f"  Link (with URL):  {len(link_posted)} posted / {len(link_pending)} pending")
    print(f"\nDue today: {len(due)}")

    if due:
        print(f"\nDue posts:")
        for p in due[:10]:
            ctype = p.get("comment_type", "link")
            label = p.get("topic", p.get("article_title", ""))[:40]
            print(f"  #{p['id']} [{ctype}] r/{p['subreddit']} | {label}")

    if pending:
        next_p = min(pending, key=lambda x: x["scheduled_date"])
        ctype = next_p.get("comment_type", "link")
        print(f"\nNext scheduled: {next_p['scheduled_date']} [{ctype}] — r/{next_p['subreddit']}")


# ── Browser / Auth ────────────────────────────────────────────

def is_logged_in(page):
    try:
        user_link = page.locator(f'a[href*="/user/{REDDIT_USERNAME}"], span.user a').first
        if user_link.is_visible(timeout=3000):
            return True
        if page.locator('a[href*="logout"], form[action*="logout"]').first.is_visible(timeout=2000):
            return True
        return False
    except Exception:
        return False


def verify_session(page):
    log("Verifying Reddit session...")
    page.goto("https://old.reddit.com/")
    time.sleep(5)
    if is_logged_in(page):
        log("Session valid — logged in")
        return True
    log("Session expired — need to re-login")
    log("Run with --login flag to re-authenticate (CAPTCHA required)")
    return False


def manual_login(page):
    log("Opening Reddit login for manual authentication...")
    page.goto("https://www.reddit.com/login/")
    print("\nPlease complete in the browser:")
    print("1. Solve the CAPTCHA")
    print(f"2. Log in with username: {REDDIT_USERNAME}")
    print("3. Wait until you see the Reddit homepage")
    print("\nWaiting up to 3 minutes...")
    try:
        page.wait_for_url("https://www.reddit.com/", timeout=180000)
        log("Login successful!")
        return True
    except Exception:
        if "login" not in page.url and "reddit.com" in page.url:
            log("Login appears successful")
            return True
        log("Login timeout")
        return False


def launch_browser(pw, args):
    """Create browser + context + page, return (browser, context, page)."""
    BROWSER_STATE_DIR.mkdir(exist_ok=True)
    state_path = BROWSER_STATE_DIR / "reddit"
    state_file = state_path / "state.json"

    browser = pw.chromium.launch(
        headless=not args.headed and not args.login,
        args=BROWSER_ARGS,
    )
    context = browser.new_context(
        storage_state=str(state_file) if state_file.exists() else None,
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    page = context.new_page()
    return browser, context, page, state_path


def save_browser_state(context, state_path):
    state_path.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(state_path / "state.json"))


# ── Thread Finding / Scraping ─────────────────────────────────

def find_thread(page, subreddit, search_terms):
    log(f"Searching r/{subreddit} for relevant threads...")
    terms_list = [t.strip() for t in search_terms.split(",")]
    all_candidates = []

    for term in terms_list[:3]:
        search_url = f"https://old.reddit.com/r/{subreddit}/search?q={term.replace(' ', '+')}&restrict_sr=on&sort=new&t=month"
        page.goto(search_url)
        time.sleep(3)
        try:
            page.wait_for_selector('a[href*="/comments/"]', timeout=8000)
        except Exception:
            continue

        post_links = page.locator('a[href*="/comments/"]').all()
        for link in post_links[:10]:
            href = link.get_attribute("href") or ""
            title = (link.text_content() or "").strip()
            if "/comments/" in href and len(title) > 10 and "comment" not in title.lower():
                title_lower = title.lower()
                term_words = term.lower().split()
                match_score = sum(1 for w in term_words if w in title_lower)
                if match_score > 0 and href not in [c[0] for c in all_candidates]:
                    all_candidates.append((href, title, match_score))

    if not all_candidates:
        log(f"  No relevant threads found in r/{subreddit}")
        page.goto(f"https://old.reddit.com/r/{subreddit}/")
        time.sleep(3)
        help_thread = page.locator(
            'a[href*="/comments/"]:has-text("Help"), '
            'a[href*="/comments/"]:has-text("Question"), '
            'a[href*="/comments/"]:has-text("Daily"), '
            'a[href*="/comments/"]:has-text("Weekly")'
        ).first
        try:
            if help_thread.is_visible(timeout=3000):
                href = help_thread.get_attribute("href")
                title = help_thread.text_content().strip()
                if href and not href.startswith("http"):
                    href = f"https://old.reddit.com{href}"
                log(f"  Using help thread: {title[:50]}")
                return href, title
        except Exception:
            pass
        return None, None

    all_candidates.sort(key=lambda x: x[2], reverse=True)
    chosen = random.choice(all_candidates[:3])
    thread_url = chosen[0] if chosen[0].startswith("http") else f"https://old.reddit.com{chosen[0]}"
    log(f"  Found: {chosen[1][:60]}")
    log(f"  URL: {thread_url}")
    return thread_url, chosen[1]


def scrape_thread_content(page, thread_url):
    thread_url = thread_url.replace("www.reddit.com", "old.reddit.com")
    page.goto(thread_url)
    time.sleep(4)

    op_text = ""
    try:
        op_el = page.locator('.expando .usertext-body .md').first
        if op_el.is_visible(timeout=3000):
            op_text = op_el.text_content().strip()
    except Exception:
        pass

    existing_comments = []
    try:
        comment_els = page.locator('.comment .usertext-body .md').all()
        for c in comment_els[:5]:
            try:
                text = c.text_content().strip()
                if len(text) > 20:
                    existing_comments.append(text[:300])
            except Exception:
                pass
    except Exception:
        pass

    return op_text[:1500], existing_comments


# ── AI Comment Generation ─────────────────────────────────────

def generate_comment_ai(entry, thread_title, op_text, existing_comments):
    from google import genai

    comment_type = entry.get("comment_type", "link")
    topic = entry.get("topic", "")
    expertise = entry.get("expertise", "")
    subreddit = entry.get("subreddit", "")
    url = entry.get("url", "")
    length = entry.get("length", "medium")

    existing_context = ""
    if existing_comments:
        existing_context = "\n\nOther comments already posted (DON'T repeat these points):\n"
        for c in existing_comments[:3]:
            existing_context += f"- {c[:200]}\n"

    if comment_type == "value":
        link_instruction = "DO NOT include any links or URLs. This is a pure advice comment."
    else:
        link_instruction = (
            f"Include this link naturally in your comment: {url}\n"
            "Slip it in as something you found helpful or bookmarked, NOT as self-promotion.\n"
            'Example patterns: "found this breakdown really helpful: [url]" or "this guide covers it better than I can: [url]"\n'
            "Only use the link ONCE, near the end of the comment."
        )

    # Length-based instruction
    if length == "short":
        length_instruction = "Keep response to 2-3 sentences max. Be concise and punchy."
    elif length == "long":
        length_instruction = "Write a detailed 8-12 sentence response with specific examples and personal anecdotes."
    else:
        length_instruction = "Write 4-6 sentences. Enough detail to be helpful but not an essay."

    prompt = f"""You are a real Reddit user posting a helpful comment on r/{subreddit}.

THREAD TITLE: {thread_title}

OP'S POST: {op_text if op_text else "(no body text, just the title)"}
{existing_context}

YOUR EXPERTISE: {expertise if expertise else topic}

RULES — follow these EXACTLY:
1. Write in casual, lowercase reddit style. no capitalization at start of sentences. use "lol", "tbh", "ngl", etc sparingly and naturally
2. Sound like a real person sharing their experience, NOT an expert giving a lecture
3. Reference the OP's specific situation/question directly. Don't be generic.
4. Include specific product names, numbers, or personal anecdotes where relevant
5. Vary paragraph length. Some short sentences. Some longer ones.
6. {link_instruction}
7. Do NOT start with "great question", "this is a great question", "I had the same issue", or any canned opener. Jump right into the substance.
8. Do NOT use bullet points with asterisks. Use plain text, dashes, or just paragraph breaks.
9. {length_instruction}
10. Do NOT use markdown formatting (no bold, no headers). Plain text only.
11. Add a UNIQUE angle or insight that the existing comments haven't covered.
12. Sound slightly imperfect — like a real person typing quickly. An occasional informal phrasing is good.
13. NEVER mention "AI", "generated", or anything that hints this isn't a real person.
14. Do NOT use "Here's" as an opener.
15. Do NOT end with "hope this helps" or "good luck" or any generic closer. Just end naturally after your last point.
16. Do NOT start with "hey!" or greetings. Jump right into substance.
17. Avoid exclamation marks. Use periods. Real reddit users don't use exclamation marks constantly.

Write the comment now. Output ONLY the comment text, nothing else."""

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    comment = response.text.strip()
    comment = comment.replace("**", "").replace("##", "").replace("# ", "")
    comment = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', comment)
    comment = comment.replace("~~", "")
    if comment.startswith('"') and comment.endswith('"'):
        comment = comment[1:-1]
    if comment.startswith("'") and comment.endswith("'"):
        comment = comment[1:-1]
    return comment


def generate_reply_ai(our_comment, reply_text, reply_author, thread_title, subreddit):
    """Generate a natural reply to someone who responded to our comment."""
    from google import genai

    prompt = f"""You are a real Reddit user on r/{subreddit}. Someone replied to your comment and you need to respond naturally.

THREAD: {thread_title}

YOUR ORIGINAL COMMENT:
{our_comment[:500]}

REPLY FROM u/{reply_author}:
{reply_text}

RULES:
1. Write in casual, lowercase reddit style. Sound like the same person who wrote the original comment.
2. Keep it SHORT — 1-3 sentences max. Reddit replies are brief.
3. If they asked a question, answer it directly. If they agreed, acknowledge briefly. If they disagreed, respond respectfully.
4. DO NOT include any links or URLs.
5. No markdown formatting. No bold, no headers. Plain text only.
6. Don't be defensive or argumentative. Be chill.
7. No "hey!" greetings, no "hope this helps" closers. Just respond naturally.
8. Avoid exclamation marks. Use periods.
9. NEVER mention "AI", "generated", or anything that hints this isn't a real person.

Write the reply now. Output ONLY the reply text, nothing else."""

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    reply = response.text.strip()
    reply = reply.replace("**", "").replace("##", "").replace("# ", "")
    reply = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', reply)
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]
    return reply


def generate_comment(entry, thread_title, op_text="", existing_comments=None):
    if existing_comments is None:
        existing_comments = []
    comment = entry.get("comment", "")
    if comment:
        return comment
    if not GEMINI_API_KEY:
        log("ERROR: GEMINI_API_KEY not set. Cannot generate comments.")
        return None
    return generate_comment_ai(entry, thread_title, op_text, existing_comments)


# ── Posting ───────────────────────────────────────────────────

def post_comment(page, thread_url, comment_text, dry_run=False):
    thread_url = thread_url.replace("www.reddit.com", "old.reddit.com")
    log(f"Opening thread: {thread_url[:60]}...")

    if dry_run:
        log(f"  [DRY RUN] Would post comment ({len(comment_text)} chars):")
        print(f"\n{'─'*50}")
        print(comment_text)
        print(f"{'─'*50}\n")
        return True

    try:
        page.goto(thread_url)
        time.sleep(5)
        comment_box = page.locator('textarea[name="text"]').first
        if not comment_box.is_visible(timeout=10000):
            log("  Could not find comment box")
            page.screenshot(path=str(DATA_DIR / "reddit-no-commentbox.png"))
            return False

        log("  Found comment box")
        comment_box.click()
        human_delay(DELAY_SHORT)
        comment_box.fill(comment_text)
        human_delay(DELAY_MEDIUM)
        page.screenshot(path=str(DATA_DIR / "reddit-before-submit.png"))
        submit_btn = page.locator('button[type="submit"]:has-text("save")').first
        submit_btn.click()
        human_delay(DELAY_LONG)
        time.sleep(5)
        page.screenshot(path=str(DATA_DIR / "reddit-after-submit.png"))
        log("  Comment posted successfully")
        return True

    except Exception as e:
        log(f"  Comment failed: {e}")
        try:
            page.screenshot(path=str(DATA_DIR / "reddit-error.png"))
        except Exception:
            pass
        return False


def post_reply(page, reply_text, reply_button_locator, dry_run=False):
    """Post a reply to a specific comment using old.reddit.com."""
    if dry_run:
        log(f"  [DRY RUN] Would post reply ({len(reply_text)} chars):")
        print(f"    {'─'*46}")
        for line in reply_text.split('\n'):
            print(f"    {line}")
        print(f"    {'─'*46}")
        return True

    try:
        reply_button_locator.click()
        human_delay(DELAY_MEDIUM)

        # Find the reply textarea that just appeared
        reply_box = reply_button_locator.locator('..').locator('..').locator('..').locator('textarea[name="text"]').first
        if not reply_box.is_visible(timeout=5000):
            # Try broader search within the comment's child area
            reply_box = reply_button_locator.locator('xpath=ancestor::div[contains(@class,"comment")]').locator('textarea[name="text"]').last
        if not reply_box.is_visible(timeout=5000):
            log("  Could not find reply textarea")
            return False

        reply_box.fill(reply_text)
        human_delay(DELAY_SHORT)
        save_btn = reply_box.locator('..').locator('button[type="submit"]:has-text("save")').first
        save_btn.click()
        human_delay(DELAY_LONG)
        time.sleep(3)
        log("  Reply posted successfully")
        return True

    except Exception as e:
        log(f"  Reply failed: {e}")
        return False


# ── Reply Checker ─────────────────────────────────────────────

def check_replies(page, schedule, do_reply=False, dry_run=False):
    """Check all posted comments for new replies."""
    posted = [e for e in schedule if e["status"] == "posted" and e.get("thread_url")]

    if not posted:
        log("No posted comments to check")
        return

    log(f"Checking replies on {len(posted)} posted comment(s)...")

    replies_file = DATA_DIR / "reddit_replies.json"
    if replies_file.exists():
        with open(replies_file) as f:
            known_replies = json.load(f)
    else:
        known_replies = {}

    total_new = 0

    for entry in posted:
        entry_id = str(entry["id"])
        thread_url = entry["thread_url"].replace("www.reddit.com", "old.reddit.com")
        our_comment_text = entry.get("generated_comment", entry.get("comment", ""))

        log(f"\n  #{entry['id']} r/{entry['subreddit']} — {entry.get('topic', entry.get('article_title', ''))[:40]}")
        log(f"    Thread: {thread_url[:70]}")

        try:
            page.goto(thread_url)
            time.sleep(4)

            # Find our comment by looking for our username
            our_comments = page.locator(f'.comment .author[href*="/user/{REDDIT_USERNAME}"]').all()

            if not our_comments:
                log(f"    Could not find our comment (may have been removed)")
                entry_known = known_replies.get(entry_id, {})
                entry_known["status"] = "comment_not_found"
                known_replies[entry_id] = entry_known
                continue

            log(f"    Found {len(our_comments)} comment(s) by us")

            # For each of our comments, find child/reply comments
            for our_author_el in our_comments:
                # Navigate up to the .comment div, then find child .comment divs
                our_comment_div = our_author_el.locator('xpath=ancestor::div[contains(@class,"comment")][1]')

                # Get our comment's score
                try:
                    score_el = our_comment_div.locator('.score.unvoted').first
                    score_text = score_el.get_attribute("title") or score_el.text_content() or ""
                    log(f"    Our comment score: {score_text}")
                except Exception:
                    pass

                # Find direct child comments (replies to us)
                child_comments = our_comment_div.locator('> .child .comment').all()

                if not child_comments:
                    log(f"    No replies yet")
                    continue

                log(f"    Found {len(child_comments)} reply/replies")

                if entry_id not in known_replies:
                    known_replies[entry_id] = {"replies": [], "replied_to": []}

                for child in child_comments:
                    try:
                        reply_author_el = child.locator('.author').first
                        reply_author = reply_author_el.text_content().strip() if reply_author_el else "unknown"

                        reply_body_el = child.locator('.usertext-body .md').first
                        reply_text = reply_body_el.text_content().strip() if reply_body_el else ""

                        reply_score_el = child.locator('.score.unvoted').first
                        reply_score = ""
                        try:
                            reply_score = reply_score_el.get_attribute("title") or reply_score_el.text_content() or ""
                        except Exception:
                            pass

                        if not reply_text or reply_author == REDDIT_USERNAME:
                            continue

                        # Check if we've already seen this reply
                        reply_key = f"{reply_author}:{reply_text[:50]}"
                        seen_keys = [r.get("key", "") for r in known_replies[entry_id].get("replies", [])]

                        if reply_key in seen_keys:
                            continue

                        total_new += 1
                        reply_data = {
                            "key": reply_key,
                            "author": reply_author,
                            "text": reply_text[:500],
                            "score": reply_score,
                            "found_at": datetime.now().isoformat(),
                        }
                        known_replies[entry_id]["replies"].append(reply_data)

                        print(f"\n    {'─'*46}")
                        print(f"    NEW REPLY from u/{reply_author} (score: {reply_score}):")
                        for line in reply_text[:300].split('\n'):
                            print(f"      {line}")
                        print(f"    {'─'*46}")

                        # Generate and post a reply if requested
                        if do_reply and reply_key not in known_replies[entry_id].get("replied_to", []):
                            thread_title = entry.get("thread_title", entry.get("topic", ""))
                            subreddit = entry["subreddit"]

                            ai_reply = generate_reply_ai(
                                our_comment_text, reply_text, reply_author,
                                thread_title, subreddit
                            )

                            if ai_reply:
                                log(f"    Generated reply ({len(ai_reply)} chars)")

                                # Find the reply button for this specific child comment
                                reply_btn = child.locator('a:has-text("reply")').first

                                if dry_run:
                                    print(f"    [DRY RUN] Would reply:")
                                    print(f"      {ai_reply}")
                                    known_replies[entry_id].setdefault("replied_to", []).append(reply_key)
                                else:
                                    success = post_reply(page, ai_reply, reply_btn, dry_run=False)
                                    if success:
                                        known_replies[entry_id].setdefault("replied_to", []).append(reply_key)
                                        reply_data["our_reply"] = ai_reply
                                        human_delay(DELAY_LONG)

                    except Exception as e:
                        log(f"    Error processing reply: {e}")
                        continue

        except Exception as e:
            log(f"    Error checking thread: {e}")
            continue

        # Save after each thread
        with open(replies_file, "w") as f:
            json.dump(known_replies, f, indent=2)

        # Delay between threads
        if entry != posted[-1]:
            time.sleep(random.uniform(3, 6))

    log(f"\nDone. Found {total_new} new reply/replies across {len(posted)} threads.")

    # Save final state
    with open(replies_file, "w") as f:
        json.dump(known_replies, f, indent=2)


# ── Main Flows ────────────────────────────────────────────────

def run_poster(args):
    from playwright.sync_api import sync_playwright

    schedule = load_schedule()

    if args.check:
        show_status(schedule)
        return

    if not REDDIT_USERNAME or not REDDIT_PASSWORD:
        print("Error: REDDIT_USERNAME and REDDIT_PASSWORD must be set in .env")
        sys.exit(1)

    # Determine which posts to make
    if args.login:
        posts_to_make = []
    elif args.post:
        posts_to_make = [p for p in schedule if p["id"] == args.post]
        if not posts_to_make:
            print(f"Post #{args.post} not found")
            sys.exit(1)
    elif args.run_due:
        posts_to_make = get_due_posts(schedule)[:REDDIT_MAX_PER_DAY]
        if not posts_to_make and not args.login:
            log("No posts due today")
            return
    else:
        print("Specify --check, --run-due, --post N, or --login")
        sys.exit(1)

    with sync_playwright() as pw:
        browser, context, page, state_path = launch_browser(pw, args)

        if args.login:
            if not manual_login(page):
                browser.close()
                sys.exit(1)
            save_browser_state(context, state_path)
            log("Session saved. You can now run without --login")
            browser.close()
            return

        if not verify_session(page):
            browser.close()
            sys.exit(1)
        save_browser_state(context, state_path)

        if not posts_to_make:
            log("No posts to make")
            browser.close()
            return

        log(f"Processing {len(posts_to_make)} post(s)...")
        posted_count = 0

        for entry in posts_to_make:
            search_terms = entry.get("search_terms", "")
            thread_url, thread_title = find_thread(page, entry["subreddit"], search_terms)

            if not thread_url:
                log(f"  No thread found for #{entry['id']}, skipping")
                for e in schedule:
                    if e["id"] == entry["id"]:
                        e["status"] = "skipped"
                        e["skip_reason"] = "no_thread_found"
                        break
                save_schedule(schedule)
                continue

            op_text, existing_comments = scrape_thread_content(page, thread_url)
            log(f"  Thread context: {len(op_text)} chars OP, {len(existing_comments)} existing comments")

            comment = generate_comment(entry, thread_title or "", op_text, existing_comments)
            if not comment:
                log(f"  Failed to generate comment for #{entry['id']}")
                continue

            log(f"  Generated comment: {len(comment)} chars")
            success = post_comment(page, thread_url, comment, dry_run=args.dry_run)

            for e in schedule:
                if e["id"] == entry["id"]:
                    if args.dry_run:
                        break
                    e["status"] = "posted" if success else "failed"
                    e["posted_at"] = datetime.now().isoformat()
                    e["thread_url"] = thread_url
                    e["thread_title"] = thread_title
                    e["generated_comment"] = comment
                    break

            if success:
                posted_count += 1
            if not args.dry_run:
                save_schedule(schedule)

            if entry != posts_to_make[-1]:
                delay = random.uniform(120, 300)
                log(f"Waiting {delay:.0f}s before next post...")
                time.sleep(delay)

        save_browser_state(context, state_path)
        browser.close()
        log(f"Done. Posted: {posted_count}/{len(posts_to_make)}")


def run_reply_checker(args):
    from playwright.sync_api import sync_playwright

    schedule = load_schedule()

    if not REDDIT_USERNAME or not REDDIT_PASSWORD:
        print("Error: REDDIT_USERNAME and REDDIT_PASSWORD must be set in .env")
        sys.exit(1)

    with sync_playwright() as pw:
        browser, context, page, state_path = launch_browser(pw, args)

        if not verify_session(page):
            browser.close()
            sys.exit(1)
        save_browser_state(context, state_path)

        check_replies(page, schedule, do_reply=args.reply, dry_run=args.dry_run)

        save_browser_state(context, state_path)
        browser.close()


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reddit comment poster + reply checker")
    parser.add_argument("--check", action="store_true", help="Show schedule status")
    parser.add_argument("--run-due", action="store_true", help="Post all due comments")
    parser.add_argument("--post", type=int, help="Post specific entry by ID")
    parser.add_argument("--dry-run", action="store_true", help="Simulate posting")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--login", action="store_true", help="Manual login only (solve CAPTCHA)")
    parser.add_argument("--stats", action="store_true", help="Show schedule stats")
    parser.add_argument("--check-replies", action="store_true", help="Check for replies to our comments")
    parser.add_argument("--reply", action="store_true", help="Auto-reply to new replies (use with --check-replies)")
    args = parser.parse_args()

    if args.stats:
        schedule = load_schedule()
        show_status(schedule)
        return

    if args.check_replies:
        run_reply_checker(args)
        return

    if not any([args.check, args.run_due, args.post, args.login]):
        parser.print_help()
        sys.exit(1)

    run_poster(args)


if __name__ == "__main__":
    main()
