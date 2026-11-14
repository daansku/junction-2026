"""LENS analysis package: trace sync, leaderboard aggregation, rule discovery, and insights."""
from __future__ import annotations

from .aggregate import build_leaderboard
from .claim_check import check_claims, validate_against_schema
from .compare import build_comparisons
from .insights import build_insights, generate_auto_proposals
from .rule_discovery import build_rules
from .sync import sync_runs

__all__ = [
    "build_comparisons",
    "build_insights",
    "build_leaderboard",
    "build_rules",
    "check_claims",
    "generate_auto_proposals",
    "sync_runs",
    "validate_against_schema",
]
