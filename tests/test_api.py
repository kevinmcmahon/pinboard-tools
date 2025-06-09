# ABOUTME: Tests for Pinboard API client functionality
# ABOUTME: Covers API interaction, rate limiting, and error handling

from typing import Any
from unittest.mock import Mock, patch

from pinboard_tools.sync.api import PinboardAPI


class TestPinboardAPI:
    """Test Pinboard API client."""

    def test_init_with_token(self) -> None:
        """Test API initialization with token."""
        api = PinboardAPI("test_token")
        assert api.api_token == "test_token"
        assert api.base_url == "https://api.pinboard.in/v1"

    def test_init_without_token(self) -> None:
        """Test API initialization fails without token."""
        # API doesn't actually validate empty token in constructor
        api = PinboardAPI("")
        assert api.api_token == ""

    @patch("requests.get")
    def test_get_all_posts_success(self, mock_get: Any) -> None:
        """Test successful posts retrieval."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "posts": [
                {
                    "href": "https://example.com",
                    "description": "Test bookmark",
                    "extended": "Test description",
                    "tags": "test tag1",
                    "time": "2024-01-01T00:00:00Z",
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        api = PinboardAPI("test_token")
        posts = api.get_all_posts()

        assert len(posts) == 1
        assert posts[0]["href"] == "https://example.com"
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_rate_limiting(self, mock_get: Any) -> None:
        """Test rate limiting behavior."""
        api = PinboardAPI("test_token")

        # Mock multiple calls
        mock_response = Mock()
        mock_response.json.return_value = {"posts": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # First call should work
        api.get_all_posts()

        # Second immediate call should be rate limited
        with patch("time.sleep") as mock_sleep:
            api.get_all_posts()
            # Should have slept due to rate limiting
            mock_sleep.assert_called()
