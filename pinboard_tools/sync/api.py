# ABOUTME: Pinboard API client with rate limiting and error handling
# ABOUTME: Provides functions for interacting with the Pinboard.in API

import time
from datetime import datetime
from typing import Any

import requests


class PinboardAPIError(Exception):
    """Custom exception for Pinboard API errors"""

    pass


# API rate limiting constants
PINBOARD_RATE_LIMIT_SECONDS = 3.0
RATE_LIMIT_BUFFER = 0.1


class PinboardAPI:
    """Pinboard API client with rate limiting"""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.pinboard.in/v1"
        self.last_request_time = 0.0
        self.min_request_interval = PINBOARD_RATE_LIMIT_SECONDS + RATE_LIMIT_BUFFER

    def _rate_limit(self) -> None:
        """Ensure we don't exceed API rate limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        """Make API request with rate limiting and error handling"""
        self._rate_limit()

        if params is None:
            params = {}
        params["auth_token"] = self.api_token
        params["format"] = "json"

        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": "pin-tags/0.1.0", "Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:  # Too Many Requests
                print("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            raise PinboardAPIError(f"HTTP error: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise PinboardAPIError(f"Connection error: {e}") from e
        except requests.exceptions.Timeout as e:
            raise PinboardAPIError(f"Request timeout: {e}") from e
        except requests.exceptions.RequestException as e:
            raise PinboardAPIError(f"API request failed: {e}") from e

    def get_all_posts(
        self,
        tag: str | None = None,
        start: int = 0,
        results: int = -1,
        fromdt: datetime | None = None,
        todt: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get all posts, optionally filtered"""
        params = {}
        if tag:
            params["tag"] = tag
        if start > 0:
            params["start"] = str(start)
        if results > 0:
            params["results"] = str(results)
        if fromdt:
            params["fromdt"] = fromdt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if todt:
            params["todt"] = todt.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._make_request("posts/all", params)
        if isinstance(data, dict):
            posts = data.get("posts", [])
            return posts if isinstance(posts, list) else []
        return data if isinstance(data, list) else []

    def get_recent_posts(
        self, count: int = 15, tag: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent posts"""
        params = {"count": str(count)}
        if tag:
            params["tag"] = tag

        data = self._make_request("posts/recent", params)
        if isinstance(data, dict):
            posts = data.get("posts", [])
            return posts if isinstance(posts, list) else []
        return []

    def add_post(
        self,
        url: str,
        description: str,
        extended: str = "",
        tags: str = "",
        dt: datetime | None = None,
        replace: str = "yes",
        shared: str = "yes",
        toread: str = "no",
    ) -> bool:
        """Add a new bookmark"""
        params = {
            "url": url,
            "description": description,
            "extended": extended,
            "tags": tags,
            "replace": replace,
            "shared": shared,
            "toread": toread,
        }

        if dt:
            params["dt"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = self._make_request("posts/add", params)
        if isinstance(result, dict):
            return result.get("result_code") == "done"
        return False

    def delete_post(self, url: str) -> bool:
        """Delete a bookmark"""
        params = {"url": url}
        result = self._make_request("posts/delete", params)
        if isinstance(result, dict):
            return result.get("result_code") == "done"
        return False

    def get_post(
        self,
        url: str | None = None,
        urls: list[str] | None = None,
        meta: str = "yes",
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get one or more posts by URL"""
        params = {"meta": meta}
        if url:
            params["url"] = url
        elif urls:
            params["url"] = " ".join(urls[:100])  # API limit
        if tag:
            params["tag"] = tag

        data = self._make_request("posts/get", params)
        if isinstance(data, dict):
            posts = data.get("posts", [])
            return posts if isinstance(posts, list) else []
        return []

    def get_last_update(self) -> datetime:
        """Get time of last update"""
        data = self._make_request("posts/update")
        return datetime.fromisoformat(data["update_time"].replace("Z", "+00:00"))

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with counts"""
        data = self._make_request("tags/get")
        if isinstance(data, dict):
            return data
        return {}
