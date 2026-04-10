"""
Supabase-backed cache for agent evaluation results.

Cache key: (agent_name, agent_version, scenario_id)
TTL: configurable, default 24 hours

If Supabase is unavailable the cache silently returns None (cache miss),
so the evaluation falls back to running the agent normally.
"""

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
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


class SupabaseResultCache:
    """
    Caches agent responses in Supabase so the same agent is not
    re-invoked for identical scenarios within the TTL window.

    Usage:
        cache = SupabaseResultCache(ttl_seconds=86400)
        responses = cache.get("MyAgent", "1.0", "scenario_001")
        if responses is None:
            responses = run_agent(...)
            cache.set("MyAgent", "1.0", "scenario_001", responses)
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        ttl_seconds: int = 86400,
    ):
        self._url = supabase_url or os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", "")
        self._key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY", "")
        self._ttl = ttl_seconds
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        if not self._url or not self._key:
            return
        try:
            from supabase import create_client
            self._client = create_client(self._url, self._key)
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get(
        self,
        agent_name: str,
        agent_version: str,
        scenario_id: str,
    ) -> Optional[List[AgentResponse]]:
        if not self._available or not self._client:
            return None
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            resp = (
                self._client.table("agent_eval_cache")
                .select("responses_json")
                .eq("agent_name", agent_name)
                .eq("agent_version", agent_version)
                .eq("scenario_id", scenario_id)
                .gt("expires_at", now_iso)
                .maybeSingle()
                .execute()
            )
            if resp.data:
                return _deserialize_responses(resp.data["responses_json"])
            return None
        except Exception:
            return None

    def set(
        self,
        agent_name: str,
        agent_version: str,
        scenario_id: str,
        responses: List[AgentResponse],
    ) -> bool:
        if not self._available or not self._client:
            return False
        try:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=self._ttl)
            serialized = json.loads(_serialize_responses(responses))
            self._client.table("agent_eval_cache").upsert(
                {
                    "agent_name": agent_name,
                    "agent_version": agent_version,
                    "scenario_id": scenario_id,
                    "responses_json": serialized,
                    "created_at": now.isoformat(),
                    "expires_at": expires.isoformat(),
                },
                on_conflict="agent_name,agent_version,scenario_id",
            ).execute()
            return True
        except Exception:
            return False

    def invalidate(self, agent_name: str, agent_version: str) -> bool:
        """Remove all cached entries for a specific agent version."""
        if not self._available or not self._client:
            return False
        try:
            self._client.table("agent_eval_cache").delete().eq(
                "agent_name", agent_name
            ).eq("agent_version", agent_version).execute()
            return True
        except Exception:
            return False

    def clear_expired(self) -> bool:
        """Remove all expired cache entries."""
        if not self._available or not self._client:
            return False
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._client.table("agent_eval_cache").delete().lt(
                "expires_at", now_iso
            ).execute()
            return True
        except Exception:
            return False


class SupabaseReportStore:
    """
    Persists the latest full EvaluationReport per agent in Supabase.
    On re-evaluation of the same agent name+version, we check here first
    and skip if a valid cached report exists.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self._url = supabase_url or os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", "")
        self._key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY", "")
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        if not self._url or not self._key:
            return
        try:
            from supabase import create_client
            self._client = create_client(self._url, self._key)
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get_report(self, agent_name: str, agent_version: str) -> Optional[dict]:
        if not self._available or not self._client:
            return None
        try:
            resp = (
                self._client.table("agent_eval_reports")
                .select("report_json, aggregated_score, deployable, created_at")
                .eq("agent_name", agent_name)
                .eq("agent_version", agent_version)
                .maybeSingle()
                .execute()
            )
            return resp.data or None
        except Exception:
            return None

    def save_report(self, agent_name: str, agent_version: str, report_dict: dict) -> bool:
        if not self._available or not self._client:
            return False
        try:
            self._client.table("agent_eval_reports").upsert(
                {
                    "agent_name": agent_name,
                    "agent_version": agent_version,
                    "report_json": report_dict,
                    "aggregated_score": report_dict.get("scores", {}).get("aggregated", 0.0),
                    "deployable": report_dict.get("deployable", False),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="agent_name,agent_version",
            ).execute()
            return True
        except Exception:
            return False
