"""Pytest configuration and fixtures."""

import os

# Set USDA API key for tests before any imports
# This is required by config.py validation
os.environ.setdefault("USDA_API_KEY", "test-api-key-for-pytest")
