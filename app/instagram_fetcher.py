"""
Instagram post fetching using Instaloader library.

Fetches Instagram post data (description, media) for recipe extraction.
Handles session management and provides clear error messages.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import instaloader

from app import config


class InstagramFetchError(Exception):
    """Raised when Instagram post cannot be fetched."""
    pass


@dataclass
class InstagramPost:
    """Holds Instagram post data for recipe extraction."""
    description: str
    media_urls: list[str]
    media_type: str  # 'photo', 'video', or 'carousel'
    shortcode: str
    has_owner_comments: bool = False  # Whether owner comments were included


class InstagramFetcher:
    """Fetches Instagram posts using Instaloader."""

    def __init__(self, session_file: str | None = None):
        """
        Initialize Instagram fetcher.

        Args:
            session_file: Path to Instaloader session file (optional)
        """
        print(f"session_file={session_file}")
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True
        )

        self.session_file = session_file or config.INSTAGRAM_SESSION_FILE
        self._load_session()

    def _load_session(self):
        """Load saved Instagram session if available."""
        if self.session_file and Path(self.session_file).exists():
            try:
                session_path = Path(self.session_file)

                # Extract username from session file name
                # Standard format: ~/.instaloader-session-USERNAME
                filename = session_path.name

                # Try different session file formats
                if filename.startswith('.instaloader-session-'):
                    username = filename.replace('.instaloader-session-', '')
                elif filename.startswith('instaloader-session-'):
                    username = filename.replace('instaloader-session-', '')
                elif '-' in filename:
                    # Extract everything after the last dash
                    username = filename.split('-')[-1]
                else:
                    # Filename is the username
                    username = filename.replace('.instaloader-session', '')

                if username:
                    print(f"[Instagram] Loading session for user: {username}")
                    self.loader.load_session_from_file(username, str(session_path))
                    print("[Instagram] Session loaded successfully!")

            except FileNotFoundError:
                print(f"[Instagram] Session file not found: {self.session_file}")
            except Exception as e:
                print(f"[Instagram] Session load failed: {type(e).__name__}: {str(e)}")
                print("[Instagram] Will attempt without authentication (may fail)")

    def _fetch_owner_comments(self, post) -> list[str]:
        """
        Fetch comments from the post owner.

        Args:
            post: Instaloader Post object

        Returns:
            List of comment texts from the post owner
        """
        owner_comments = []
        try:
            # Fetch up to 50 comments (to avoid rate limiting)
            comment_count = 0
            max_comments = 50

            for comment in post.get_comments():
                if comment_count >= max_comments:
                    break

                # Check if comment is from post owner
                if comment.owner.username == post.owner_username:
                    owner_comments.append(comment.text)

                comment_count += 1

        except Exception:
            # If we can't fetch comments (rate limit, login required, etc.),
            # just return empty list - we'll still have the caption
            pass

        return owner_comments

    def _extract_shortcode(self, url: str) -> str:
        """
        Extract Instagram shortcode from URL.

        Args:
            url: Instagram URL

        Returns:
            Shortcode string

        Raises:
            InstagramFetchError: If URL format is invalid
        """
        # Match patterns like:
        # https://www.instagram.com/p/ABC123/
        # https://instagram.com/p/ABC123
        # https://www.instagram.com/reel/ABC123/
        pattern = r'instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)'
        match = re.search(pattern, url)

        if not match:
            raise InstagramFetchError(
                "Invalid Instagram URL format. Expected format: "
                "https://www.instagram.com/p/SHORTCODE/ or "
                "https://www.instagram.com/reel/SHORTCODE/"
            )

        return match.group(1)

    def fetch_post(self, url: str) -> InstagramPost:
        """
        Fetch Instagram post data.

        Args:
            url: Instagram post or reel URL

        Returns:
            InstagramPost object with post data

        Raises:
            InstagramFetchError: If post cannot be fetched
        """
        try:
            shortcode = self._extract_shortcode(url)
        except InstagramFetchError:
            raise

        try:
            # Fetch post using shortcode
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)

            # Extract description (caption)
            caption = post.caption or ""

            # Fetch owner's comments (where full recipe often lives)
            owner_comments = self._fetch_owner_comments(post)

            # Combine caption + owner comments
            description_parts = []
            if caption:
                description_parts.append(caption)
            if owner_comments:
                description_parts.extend(owner_comments)

            description = "\n\n".join(description_parts)

            if not description:
                raise InstagramFetchError(
                    "Instagram post has no caption or owner comments with text. "
                    "Recipe must be in the post description or comments."
                )

            has_owner_comments = len(owner_comments) > 0

            # Extract media URLs and type
            media_urls = []
            media_type = 'photo'

            if post.typename == 'GraphVideo':
                media_type = 'video'
                media_urls.append(post.video_url)
            elif post.typename == 'GraphSidecar':
                media_type = 'carousel'
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        media_urls.append(node.video_url)
                    else:
                        media_urls.append(node.display_url)
            else:
                media_urls.append(post.url)

            return InstagramPost(
                description=description,
                media_urls=media_urls,
                media_type=media_type,
                shortcode=shortcode,
                has_owner_comments=has_owner_comments
            )

        except instaloader.exceptions.BadResponseException as e:
            # Instagram is blocking the request or post doesn't exist
            error_msg = str(e)
            raise InstagramFetchError(
                f"Instagram blocked the request or post is unavailable.\n"
                f"Error: {error_msg}\n\n"
                "This is very common - Instagram actively blocks automated access.\n\n"
                "AUTOMATED SOLUTION: Not reliably possible with current Instagram protections.\n"
                "Instagram will continue to block API access even with valid sessions.\n\n"
                "The only 100% reliable method is manual text paste."
            ) from e
        except instaloader.exceptions.LoginRequiredException as e:
            raise InstagramFetchError(
                "Instagram requires login to access this post. "
                "Your session may have expired.\n"
                "Try logging in again: instaloader --login=YOUR_USERNAME"
            ) from e
        except instaloader.exceptions.PrivateProfileNotFollowedException as e:
            raise InstagramFetchError(
                "This Instagram post is from a private account. "
                "You cannot import recipes from private accounts."
            ) from e
        except instaloader.exceptions.ConnectionException as e:
            error_msg = str(e)
            # Check if this is a 403 Forbidden error (Instagram blocking)
            if "403" in error_msg or "Forbidden" in error_msg:
                raise InstagramFetchError(
                    "Instagram blocked the request (403 Forbidden). This is very common!\n\n"
                    "🔧 SOLUTION 1 - Manual Paste (Easiest):\n"
                    "1. Visit the Instagram post in your browser\n"
                    "2. Copy the full post text (caption + any recipe comments)\n"
                    "3. Use the 'Import from Text' endpoint instead:\n"
                    "   POST /import-recipe-text with {\"text\": \"...\"}\n\n"
                    "🔧 SOLUTION 2 - Set Up Instagram Session (For Automatic Fetching):\n"
                    "1. Run: instaloader --login=YOUR_USERNAME\n"
                    "2. Set: export INSTAGRAM_SESSION_FILE=~/.instaloader-session-YOUR_USERNAME\n"
                    "3. Restart the app\n\n"
                    "The manual paste method works 100% of the time!"
                ) from e
            raise InstagramFetchError(
                f"Failed to connect to Instagram: {error_msg}. "
                "Please check your internet connection or try the manual paste fallback."
            ) from e
        except Exception as e:
            error_msg = str(e)
            # Also check for 403 in generic exceptions
            if "403" in error_msg or "Forbidden" in error_msg or "graphql" in error_msg.lower():
                raise InstagramFetchError(
                    "Instagram blocked the request (403 Forbidden). This is very common!\n\n"
                    "🔧 SOLUTION 1 - Manual Paste (Easiest):\n"
                    "1. Visit the Instagram post in your browser\n"
                    "2. Copy the full post text (caption + any recipe comments)\n"
                    "3. Use the 'Import from Text' endpoint instead:\n"
                    "   POST /import-recipe-text with {\"text\": \"...\"}\n\n"
                    "🔧 SOLUTION 2 - Set Up Instagram Session (For Automatic Fetching):\n"
                    "1. Run: instaloader --login=YOUR_USERNAME\n"
                    "2. Set: export INSTAGRAM_SESSION_FILE=~/.instaloader-session-YOUR_USERNAME\n"
                    "3. Restart the app\n\n"
                    "The manual paste method works 100% of the time!"
                ) from e
            raise InstagramFetchError(
                f"Unexpected error fetching Instagram post: {error_msg}. "
                "Please try the manual paste fallback."
            ) from e
