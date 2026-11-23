CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_full_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    client_ip_hash TEXT NOT NULL CHECK (client_ip_hash ~ '^[0-9a-f]{64}$'),
    requests_used INTEGER NOT NULL DEFAULT 0 CHECK (requests_used BETWEEN 0 AND 300),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 3),
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    lease_until TIMESTAMPTZ,
    CONSTRAINT ck_analysis_jobs_repository CHECK (repository_full_name ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
);

CREATE INDEX idx_analysis_jobs_queue ON analysis_jobs (created_at)
    WHERE status = 'queued';
CREATE UNIQUE INDEX uq_analysis_jobs_repository_active ON analysis_jobs (lower(repository_full_name))
    WHERE status IN ('queued', 'running');
CREATE INDEX idx_analysis_jobs_ip_rate ON analysis_jobs (client_ip_hash, created_at);
CREATE INDEX idx_analysis_jobs_expiry ON analysis_jobs (finished_at)
    WHERE status IN ('succeeded', 'failed');

CREATE TABLE analysis_results (
    job_id UUID PRIMARY KEY REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    repository_full_name TEXT NOT NULL,
    model_version_id BIGINT NOT NULL REFERENCES model_versions(id),
    probability DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    risk_category TEXT NOT NULL CHECK (risk_category IN ('low', 'medium', 'high')),
    prediction_date DATE NOT NULL,
    feature_set_name TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    limitation_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    features JSONB NOT NULL,
    indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
    request_count INTEGER NOT NULL CHECK (request_count BETWEEN 1 AND 300),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE on_demand_api_requests (
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_on_demand_api_requests_time ON on_demand_api_requests (requested_at);
