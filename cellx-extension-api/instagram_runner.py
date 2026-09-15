"""Bounded, visible Instagram workflow for the Windows portable edition."""
import os
import random
import re
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

STOP = threading.Event()
LOCK = threading.Lock()
COMMENT = "hello, I like your image"


def config(settings):
    low, high = int(settings.get("minPosts", 5)), int(settings.get("maxPosts", 8))
    if not 1 <= low <= high <= 8:
        raise ValueError("Post count must be between 1 and 8.")
    return low, high, settings.get("commentText", COMMENT)


def run(settings, execute=False):
    low, high, comment = config(settings)
    if not isinstance(comment, str) or not comment.strip() or len(comment) > 300:
        raise ValueError("Comment must contain 1 to 300 characters.")
    if not execute:
        return {"ok": True, "status": "success", "message": "Configuration checked. No browser actions performed.",
                "output": {"min_posts": low, "max_posts": high, "public_comment": comment, "executed": False}}
    if not LOCK.acquire(blocking=False):
        return {"ok": False, "status": "error", "message": "An Instagram workflow is already running."}
    STOP.clear()
    rows = []
    target = random.SystemRandom().randint(low, high)
    root = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "CellX" / "InstagramRunner"
    root.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 300

    def check(page):
        if STOP.is_set():
            raise RuntimeError("Stopped by user.")
        if time.monotonic() > deadline:
            raise RuntimeError("Five-minute run limit reached.")
        if not page.url.startswith("https://www.instagram.com/"):
            raise RuntimeError("Browser left Instagram. Run stopped.")
        if re.search(r"/challenge/|/checkpoint/", page.url):
            raise RuntimeError("Instagram requires account verification. Run stopped.")

    try:
        from playwright.sync_api import sync_playwright, expect
        with closing(sqlite3.connect(root / "actions.sqlite3")) as db, sync_playwright() as pw:
            db.execute("CREATE TABLE IF NOT EXISTS actions (post TEXT PRIMARY KEY, state TEXT NOT NULL)")
            context = pw.chromium.launch_persistent_context(str(root / "browser"), channel="msedge", headless=False)
            try:
                context.set_default_timeout(8000)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                # Login remains manual in this dedicated profile. No credentials are read or copied.
                while page.locator("article").count() == 0:
                    check(page)
                    STOP.wait(0.5)
                seen = set()
                empty_rounds = 0
                while len(rows) < target:
                    check(page)
                    found = False
                    for article in page.locator("article").all():
                        check(page)
                        post = article.locator('a[href^="/p/"]').first
                        if post.count() == 0:
                            continue
                        href = post.get_attribute("href") or ""
                        if not re.fullmatch(r"/p/[A-Za-z0-9_-]+/", href) or href in seen:
                            continue
                        seen.add(href)
                        if db.execute("SELECT 1 FROM actions WHERE post=?", (href,)).fetchone():
                            continue
                        found = True
                        article.scroll_into_view_if_needed()
                        if STOP.wait(2):
                            check(page)
                        result = {"post_url": "https://www.instagram.com" + href, "like": "pending", "comment": "pending"}
                        rows.append(result)
                        check(page)
                        like = article.get_by_role("button", name="Like", exact=True)
                        if like.count() == 1:
                            like.click()
                        expect(article.get_by_role("button", name="Unlike", exact=True)).to_be_visible()
                        result["like"] = "liked"
                        comments = article.get_by_role("button", name="Comment", exact=True)
                        if comments.count() != 1:
                            result["comment"] = "unavailable"
                            db.execute("INSERT OR REPLACE INTO actions VALUES (?,?)", (href, "comments_unavailable"))
                            db.commit()
                        else:
                            comments.click()
                            dialog = page.get_by_role("dialog")
                            box = dialog.get_by_role("textbox", name=re.compile(r"^Add a comment"))
                            expect(box).to_be_visible()
                            check(page)
                            box.fill(comment)
                            # Record before submit: an uncertain response must never trigger a duplicate comment.
                            db.execute("INSERT INTO actions VALUES (?,?)", (href, "submission_pending"))
                            db.commit()
                            check(page)
                            dialog.get_by_role("button", name="Post", exact=True).click()
                            expect(box).to_have_value("")
                            expect(dialog.get_by_text(comment, exact=True).last).to_be_visible()
                            result["comment"] = "posted"
                            db.execute("UPDATE actions SET state='posted' WHERE post=?", (href,))
                            db.commit()
                            page.get_by_role("button", name="Close", exact=True).click()
                        if len(rows) >= target:
                            break
                    if len(rows) >= target:
                        break
                    empty_rounds = 0 if found else empty_rounds + 1
                    if empty_rounds >= 12:
                        raise RuntimeError("No more eligible posts were found.")
                    page.mouse.wheel(0, 700)
                    STOP.wait(1)
                return {"ok": True, "status": "success", "message": "Instagram workflow finished and stopped.",
                        "output": {"requested": target, "processed": len(rows), "rows": rows, "executed": True}}
            finally:
                context.close()
    except ImportError:
        return {"ok": False, "status": "error", "message": "Install the portable browser dependencies first."}
    except Exception as exc:
        return {"ok": False, "status": "error", "message": str(exc)[:400],
                "output": {"requested": target, "processed": len(rows), "rows": rows, "stopped": True}}
    finally:
        LOCK.release()
