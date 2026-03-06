"""Twitter/X ingestor - monitors specific accounts for token signals."""
import asyncio
import logging
import os
from typing import List, Optional

from madapes.detection import detect_contract_addresses
from madapes.ingestion.base import BaseIngestor, IngestedSignal

logger = logging.getLogger(__name__)


class TwitterIngestor(BaseIngestor):
    """Twitter/X ingestor using tweepy for API v2 access.

    Monitors specific accounts by polling their recent tweets.
    Requires TWITTER_BEARER_TOKEN, TWITTER_ACCOUNTS in .env.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._poll_interval = int(os.getenv("TWITTER_POLL_INTERVAL", "120"))  # seconds
        self._accounts: List[str] = []
        self._seen_ids: set = set()
        self._client = None

    @property
    def platform_name(self) -> str:
        return "twitter"

    async def start(self):
        """Start polling Twitter accounts."""
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
        if not bearer_token:
            logger.warning("Twitter ingestor: TWITTER_BEARER_TOKEN not set - disabled")
            return

        accounts_str = os.getenv("TWITTER_ACCOUNTS", "").strip()
        if not accounts_str:
            logger.warning("Twitter ingestor: TWITTER_ACCOUNTS not set - disabled")
            return

        self._accounts = [a.strip().lstrip("@") for a in accounts_str.split(",") if a.strip()]
        if not self._accounts:
            return

        try:
            import tweepy
            self._client = tweepy.Client(bearer_token=bearer_token)
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info(f"Twitter ingestor started: watching {len(self._accounts)} account(s)")
        except ImportError:
            logger.warning("Twitter ingestor: tweepy not installed - disabled")

    async def stop(self):
        """Stop the polling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("Twitter ingestor stopped")

    async def _poll_loop(self):
        """Periodically poll monitored accounts for new tweets."""
        while self._running:
            try:
                for account in self._accounts:
                    await self._check_account(account)
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Twitter poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _check_account(self, username: str):
        """Check a single account for new tweets with contract addresses."""
        if not self._client:
            return

        try:
            # Get user ID
            user = self._client.get_user(username=username)
            if not user or not user.data:
                return
            user_id = user.data.id

            # Get recent tweets
            tweets = self._client.get_users_tweets(
                user_id,
                max_results=10,
                tweet_fields=["created_at", "text"],
            )
            if not tweets or not tweets.data:
                return

            for tweet in tweets.data:
                tweet_id = str(tweet.id)
                if tweet_id in self._seen_ids:
                    continue
                self._seen_ids.add(tweet_id)

                # Limit seen IDs cache size
                if len(self._seen_ids) > 5000:
                    self._seen_ids = set(list(self._seen_ids)[-2500:])

                text = tweet.text or ""
                contracts = detect_contract_addresses(text)
                if not contracts:
                    continue

                signal = IngestedSignal(
                    platform="twitter",
                    message_text=text,
                    message_id=tweet_id,
                    sender_id=str(user_id),
                    sender_name=f"@{username}",
                    source_name=f"twitter:{username}",
                    timestamp=tweet.created_at.isoformat() if tweet.created_at else None,
                    contract_addresses=contracts,
                    metadata={"tweet_url": f"https://twitter.com/{username}/status/{tweet_id}"},
                )
                await self.process_signal(signal)

        except Exception as e:
            logger.error(f"Twitter check error for @{username}: {e}")
