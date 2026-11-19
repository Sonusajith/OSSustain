ALTER TABLE model_versions
    ADD COLUMN risk_low_cutoff DOUBLE PRECISION,
    ADD COLUMN risk_high_cutoff DOUBLE PRECISION,
    ADD CONSTRAINT ck_model_versions_risk_cutoffs CHECK (
        (risk_low_cutoff IS NULL AND risk_high_cutoff IS NULL)
        OR (risk_low_cutoff IS NOT NULL AND risk_high_cutoff IS NOT NULL
            AND risk_low_cutoff BETWEEN 0 AND 1
            AND risk_high_cutoff BETWEEN risk_low_cutoff AND 1)
    );

ALTER TABLE predictions
    ADD COLUMN prediction_date DATE,
    ADD COLUMN limitation_flags JSONB NOT NULL DEFAULT '[]'::JSONB;

CREATE TABLE prediction_outcomes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_version_id BIGINT NOT NULL,
    dataset_version_id BIGINT NOT NULL,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    snapshot_id BIGINT,
    prediction_id BIGINT REFERENCES predictions(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('predicted', 'skipped')),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_prediction_outcomes_model_dataset
        FOREIGN KEY (model_version_id, dataset_version_id)
        REFERENCES model_versions (id, dataset_version_id) ON DELETE CASCADE,
    CONSTRAINT fk_prediction_outcomes_snapshot_dataset
        FOREIGN KEY (snapshot_id, dataset_version_id)
        REFERENCES snapshots (id, dataset_version_id) ON DELETE CASCADE,
    CONSTRAINT uq_prediction_outcomes_model_repo UNIQUE (model_version_id, repo_id),
    CONSTRAINT ck_prediction_outcomes_result CHECK (
        (status = 'predicted' AND snapshot_id IS NOT NULL AND prediction_id IS NOT NULL
            AND reason IS NULL)
        OR (status = 'skipped' AND prediction_id IS NULL AND reason IS NOT NULL
            AND length(btrim(reason)) > 0)
    )
);

CREATE TABLE prediction_explanations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id BIGINT NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL CHECK (length(btrim(feature_name)) > 0),
    feature_value DOUBLE PRECISION,
    reference_value DOUBLE PRECISION,
    probability_delta DOUBLE PRECISION NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('increases_risk', 'decreases_risk', 'neutral')),
    rank INTEGER NOT NULL CHECK (rank > 0),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0),
    CONSTRAINT uq_prediction_explanations_rank UNIQUE (prediction_id, rank),
    CONSTRAINT uq_prediction_explanations_feature UNIQUE (prediction_id, feature_name),
    CONSTRAINT ck_prediction_explanations_finite CHECK (
        probability_delta NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8)
        AND (feature_value IS NULL OR feature_value NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8))
        AND (reference_value IS NULL OR reference_value NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8))
    )
);

CREATE INDEX idx_prediction_explanations_prediction_rank
    ON prediction_explanations (prediction_id, rank);
CREATE INDEX idx_prediction_outcomes_dataset_status
    ON prediction_outcomes (dataset_version_id, status);
