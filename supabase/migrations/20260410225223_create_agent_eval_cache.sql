/*
  # Agent Evaluation Cache Tables

  ## Purpose
  Store evaluation results per agent so repeated evaluations of the same agent
  can be served from cache without re-running all tests.

  ## New Tables

  ### agent_eval_cache
  - Stores the serialized list of AgentResponse objects per agent+scenario combination
  - Cache key = agent_name + agent_version + scenario_id
  - TTL-based expiration via expires_at column

  ### agent_eval_reports
  - Stores full EvaluationReport JSON per agent evaluation run
  - Keyed by agent_name + agent_version
  - Used to return latest report without re-running evaluation

  ## Security
  - RLS enabled on all tables
  - Service role key used server-side (Python backend), no direct user auth needed
  - Policies allow service role full access

  ## Notes
  1. agent_name + agent_version + scenario_id forms the unique cache key
  2. expires_at defaults to 24h from creation; cache is invalidated after that
  3. Full report stored in agent_eval_reports for quick lookup by agent identity
*/

CREATE TABLE IF NOT EXISTS agent_eval_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  agent_version text NOT NULL DEFAULT '1.0',
  scenario_id text NOT NULL,
  responses_json jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
  UNIQUE (agent_name, agent_version, scenario_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_cache_lookup
  ON agent_eval_cache (agent_name, agent_version, scenario_id);

CREATE INDEX IF NOT EXISTS idx_eval_cache_expiry
  ON agent_eval_cache (expires_at);

ALTER TABLE agent_eval_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can read cache"
  ON agent_eval_cache
  FOR SELECT
  TO service_role
  USING (true);

CREATE POLICY "Service role can insert cache"
  ON agent_eval_cache
  FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY "Service role can update cache"
  ON agent_eval_cache
  FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role can delete cache"
  ON agent_eval_cache
  FOR DELETE
  TO service_role
  USING (true);


CREATE TABLE IF NOT EXISTS agent_eval_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name text NOT NULL,
  agent_version text NOT NULL DEFAULT '1.0',
  report_json jsonb NOT NULL DEFAULT '{}',
  aggregated_score float NOT NULL DEFAULT 0.0,
  deployable boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agent_name, agent_version)
);

CREATE INDEX IF NOT EXISTS idx_eval_reports_agent
  ON agent_eval_reports (agent_name, agent_version);

ALTER TABLE agent_eval_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can read reports"
  ON agent_eval_reports
  FOR SELECT
  TO service_role
  USING (true);

CREATE POLICY "Service role can insert reports"
  ON agent_eval_reports
  FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY "Service role can update reports"
  ON agent_eval_reports
  FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role can delete reports"
  ON agent_eval_reports
  FOR DELETE
  TO service_role
  USING (true);
