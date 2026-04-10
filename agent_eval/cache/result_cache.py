"""
JSON file-backed cache for agent evaluation results.

Cache key: (agent_name, agent_version, scenario_id)
TTL: configurable, default 24 hours

Cache directory: CACHE_DIR env var or ./.agent_eval_cache
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from agent_eval.core.base import AgentResponse


def _serialize_responses(responses: List[AgentResponse]) -> str:
    items = []
    for r in responses:
        items.append({
            "output": r.output,
            "reasoning_trace": r.reasoning_trace,
            "tool_calls": r.tool_calls,
            "token_usage": r.token_usage,
            "latency": r.latency,
            "error": r.error,
        })
    return json.dumps(items)


def _deserialize_responses(data) -> List[AgentResponse]:
    if isinstance(data, str):
        items = json.loads(data)
    else:
        items = data
    result = []
    for item in items:
        result.append(AgentResponse(
            output=item.get("output", ""),
            reasoning_trace=item.get("reasoning_trace"),
            tool_calls=item.get("tool_calls", []),
            token_usage=item.get("token_usage", {}),
            latency=float(item.get("latency", 0.0)),
            error=item.get("error"),
        ))
    return result


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", value)


class SupabaseResultCache:
    """
    Caches agent responses in JSON files so the same agent is not
    re-invoked for identical scenarios within the TTL window.

    Cache directory structure:
        <cache_dir>/responses/<agent_name>/<agent_version>/<scenario_id>.json

    Usage:
        cache = SupabaseResultCache(ttl_seconds=86400)
        responses = cache.get("MyAgent", "1.0", "scenario_001")
        if responses is None:
            responses = run_agent(...)
            cache.set("MyAgent", "1.0", "scenario_001", responses)
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        ttl_seconds: int = 86400,
        **kwargs,
    ):
        self._cache_dir = cache_dir or os.getenv("CACHE_DIR", ".agent_eval_cache")
        self._responses_dir = os.path.join(self._cache_dir, "responses")
        self._ttl = ttl_seconds
        self._available = True
        try:
            os.makedirs(self._responses_dir, exist_ok=True)
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _entry_path(self, agent_name: str, agent_version: str, scenario_id: str) -> str:
        agent_dir = os.path.join(
            self._responses_dir,
            _safe_filename(agent_name),
            _safe_filename(agent_version),
        )
        os.makedirs(agent_dir, exist_ok=True)
        return os.path.join(agent_dir, f"{_safe_filename(scenario_id)}.json")

    def get(
        self,
        agent_name: str,
        agent_version: str,
        scenario_id: str,
    ) -> Optional[List[AgentResponse]]:
        if not self._available:
            return None
        try:
            path = self._entry_path(agent_name, agent_version, scenario_id)
            if not os.path.exists(path):
                return None
            with open(path, "r") as f:
                entry = json.load(f)
            expires_at = datetime.fromisoformat(entry["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                os.remove(path)
                return None
            return _deserialize_responses(entry["responses_json"])
        except Exception:
            return None

    def set(
        self,
        agent_name: str,
        agent_version: str,
        scenario_id: str,
        responses: List[AgentResponse],
    ) -> bool:
        if not self._available:
            return False
        try:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=self._ttl)
            entry = {
                "agent_name": agent_name,
                "agent_version": agent_version,
                "scenario_id": scenario_id,
                "responses_json": json.loads(_serialize_responses(responses)),
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
            }
            path = self._entry_path(agent_name, agent_version, scenario_id)
            with open(path, "w") as f:
                json.dump(entry, f, indent=2)
            return True
        except Exception:
            return False

    def invalidate(self, agent_name: str, agent_version: str) -> bool:
        """Remove all cached entries for a specific agent version."""
        if not self._available:
            return False
        try:
            agent_dir = os.path.join(
                self._responses_dir,
                _safe_filename(agent_name),
                _safe_filename(agent_version),
            )
            if not os.path.isdir(agent_dir):
                return True
            for fname in os.listdir(agent_dir):
                if fname.endswith(".json"):
                    os.remove(os.path.join(agent_dir, fname))
            return True
        except Exception:
            return False

    def clear_expired(self) -> bool:
        """Remove all expired cache entries."""
        if not self._available:
            return False
        try:
            now = datetime.now(timezone.utc)
            for root, _, files in os.walk(self._responses_dir):
                for fname in files:
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r") as f:
                            entry = json.load(f)
                        expires_at = datetime.fromisoformat(entry["expires_at"])
                        if now > expires_at:
                            os.remove(fpath)
                    except Exception:
                        pass
            return True
        except Exception:
            return False


class SupabaseReportStore:
    """
    Persists the latest full EvaluationReport per agent in JSON files.

    File path: <cache_dir>/reports/<agent_name>_<agent_version>.json
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        self._cache_dir = cache_dir or os.getenv("CACHE_DIR", ".agent_eval_cache")
        self._reports_dir = os.path.join(self._cache_dir, "reports")
        self._available = True
        try:
            os.makedirs(self._reports_dir, exist_ok=True)
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _report_path(self, agent_name: str, agent_version: str) -> str:
        fname = f"{_safe_filename(agent_name)}_{_safe_filename(agent_version)}.json"
        return os.path.join(self._reports_dir, fname)

    def get_report(self, agent_name: str, agent_version: str) -> Optional[dict]:
        if not self._available:
            return None
        try:
            path = self._report_path(agent_name, agent_version)
            if not os.path.exists(path):
                return None
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def save_report(self, agent_name: str, agent_version: str, report_dict: dict) -> bool:
        if not self._available:
            return False
        try:
            entry = {
                "agent_name": agent_name,
                "agent_version": agent_version,
                "report_json": report_dict,
                "aggregated_score": report_dict.get("scores", {}).get("aggregated", 0.0),
                "deployable": report_dict.get("deployable", False),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            path = self._report_path(agent_name, agent_version)
            with open(path, "w") as f:
                json.dump(entry, f, indent=2)
            return True
        except Exception:
            return False
