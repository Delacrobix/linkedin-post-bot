"""LinkedIn Post Bot that fetches articles and posts them to LinkedIn."""

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import requests

from post_generator import PostGenerationError, generate_linkedin_post

# Configuration
BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "published.db"
BACKUP_DIR = BASE_DIR / "backups"
LINKEDIN_API_URL = "https://api.linkedin.com/v2/ugcPosts"
MIN_PUBLISH_DATE = datetime(2025, 12, 11, tzinfo=timezone.utc)


def init_db() -> None:
    """Initialize database and create table if not exists."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS published_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            linkedin_post_id TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


def backup_db() -> None:
    """Create a backup of the database before modifications."""
    if not DB_FILE.exists():
        return

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"published_{timestamp}.db"
    shutil.copy2(DB_FILE, backup_file)
    print(f"Backup created: {backup_file.name}")

    # Keep only last 5 backups
    backups = sorted(BACKUP_DIR.glob("published_*.db"), reverse=True)
    for old_backup in backups[5:]:
        old_backup.unlink()


def get_published_urls() -> set[str]:
    """Get set of already published article URLs."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT url FROM published_articles")
    urls = {row[0] for row in cursor.fetchall()}
    conn.close()
    return urls


def save_published_article(url: str, title: str, linkedin_post_id: str) -> None:
    """Save a published article to the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO published_articles (url, title, linkedin_post_id) VALUES (?, ?, ?)",
        (url, title, linkedin_post_id),
    )
    conn.commit()
    conn.close()


def parse_publish_date(date_str: str) -> datetime | None:
    """Parse ISO 8601 date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_articles(api_url: str) -> list[dict]:
    """Fetch articles from the articles API."""
    response = requests.get(api_url, params={"size": 10, "page": 1})
    response.raise_for_status()
    data = response.json()
    return data.get("articles", [])


def get_linkedin_user_id(access_token: str) -> str:
    """Get the authenticated user's LinkedIn ID."""
    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()["sub"]


def post_to_linkedin(
    access_token: str, user_id: str, text: str, article_url: str
) -> dict:
    """Post content to LinkedIn."""
    payload = {
        "author": f"urn:li:person:{user_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "originalUrl": article_url,
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    response = requests.post(
        LINKEDIN_API_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def create_post_text(article: dict) -> str:
    """Generate post text for an article using AI."""
    title = article.get("title", "")
    description = article.get("description", "")
    body = article.get("body", "")

    post_text = generate_linkedin_post(title, description, body)

    return post_text  # LinkedIn limit is ~3000 chars


def main():
    # Load configuration from environment
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    articles_api_url = os.environ.get("ARTICLES_API_URL")

    if not access_token:
        print("Error: LINKEDIN_ACCESS_TOKEN not set")
        return 1

    if not articles_api_url:
        print("Error: ARTICLES_API_URL not set")
        return 1

    # Initialize database
    init_db()

    # Load published articles
    published_urls = get_published_urls()
    print(f"Already published: {len(published_urls)} articles")

    # Fetch new articles
    print(f"Fetching articles from {articles_api_url}...")
    articles = fetch_articles(articles_api_url)

    # Find unpublished articles (published after MIN_PUBLISH_DATE)
    new_articles = []
    for a in articles:
        if a.get("link") in published_urls:
            continue
        pub_date = parse_publish_date(a.get("publishedAt", ""))

        if pub_date and pub_date >= MIN_PUBLISH_DATE:
            new_articles.append(a)

    print(f"New articles to publish: {len(new_articles)}")

    if not new_articles:
        print("No new articles to publish")
        return 0

    user_id = get_linkedin_user_id(access_token)

    # Post the most recent new article
    article = new_articles[0]
    print(f"Publishing: {article.get('title')}")

    # Generate post text with error handling
    try:
        post_text = create_post_text(article)
    except PostGenerationError as e:
        print(f"Error generating post text: {e}")
        print("Aborting to prevent publishing invalid content")
        return 1

    print("Generated post text:", post_text)
    print(f"Post text length: {len(post_text)} characters")

    article_url = article.get("link", "")

    result = post_to_linkedin(access_token, user_id, post_text, article_url)
    linkedin_post_id = result.get("id", "")
    print(f"Posted successfully! ID: {linkedin_post_id}")

    # Backup and save to database
    backup_db()
    save_published_article(article_url, article.get("title"), linkedin_post_id)
    print("Saved to database")

    return 0


if __name__ == "__main__":
    exit(main())
