CREATE TABLE collection_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage IN ('repository_metadata', 'commits')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    requests_used BIGINT NOT NULL DEFAULT 0 CHECK (requests_used >= 0),
    records_processed BIGINT NOT NULL DEFAULT 0 CHECK (records_processed >= 0),
    error_summary TEXT,
    CONSTRAINT ck_collection_runs_finish_state CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status IN ('done', 'failed') AND finished_at IS NOT NULL)
    ),
    CONSTRAINT ck_collection_runs_finished_after_start
        CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- Supports per-repository collection history and completeness reporting.
CREATE INDEX idx_collection_runs_repo_started_at ON collection_runs (repo_id, started_at);

-- Supports finding pending failures by collection stage.
CREATE INDEX idx_collection_runs_stage_status ON collection_runs (stage, status);
