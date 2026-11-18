-- Research snapshots are versioned independently of the V3 dashboard/dev-seed windows.
CREATE TABLE dataset_versions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_hash TEXT NOT NULL UNIQUE CHECK (version_hash ~ '^[0-9a-f]{64}$'),
    cohort_name TEXT NOT NULL,
    config JSONB NOT NULL,
    source_hash TEXT NOT NULL CHECK (source_hash ~ '^[0-9a-f]{64}$'),
    code_revision TEXT NOT NULL,
    summary JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id),
    repo_id BIGINT NOT NULL REFERENCES repositories(id),
    prediction_date DATE NOT NULL,
    reference_start DATE NOT NULL,
    future_end DATE NOT NULL,
    observed_until DATE NOT NULL,
    reference_activity INTEGER NOT NULL CHECK (reference_activity >= 0),
    future_activity INTEGER CHECK (future_activity >= 0),
    label BOOLEAN,
    label_status TEXT NOT NULL CHECK (label_status IN
        ('labeled', 'low_reference_activity', 'incomplete_future')),
    split TEXT NOT NULL CHECK (split IN ('train', 'validation', 'test', 'purged', 'unassigned')),
    CONSTRAINT uq_snapshots_version_repo_date
        UNIQUE (dataset_version_id, repo_id, prediction_date),
    CONSTRAINT ck_snapshots_windows CHECK
        (reference_start < prediction_date AND future_end > prediction_date),
    CONSTRAINT ck_snapshots_label_status CHECK (
        (label_status = 'labeled' AND label IS NOT NULL AND future_activity IS NOT NULL
            AND future_end <= observed_until)
        OR (label_status = 'low_reference_activity' AND label IS NULL
            AND future_activity IS NOT NULL AND future_end <= observed_until)
        OR (label_status = 'incomplete_future' AND label IS NULL
            AND future_activity IS NULL AND future_end > observed_until)
    )
);

CREATE INDEX idx_snapshots_version_split ON snapshots (dataset_version_id, split, label_status);
CREATE INDEX idx_snapshots_repo_date ON snapshots (repo_id, prediction_date);
