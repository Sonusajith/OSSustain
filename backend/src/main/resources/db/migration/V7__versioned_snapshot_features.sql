CREATE TABLE feature_sets (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id),
    feature_set_hash TEXT NOT NULL CHECK (feature_set_hash ~ '^[0-9a-f]{64}$'),
    code_revision TEXT NOT NULL,
    config JSONB NOT NULL,
    summary JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_feature_sets_id_dataset UNIQUE (id, dataset_version_id),
    CONSTRAINT uq_feature_sets_dataset_hash UNIQUE (dataset_version_id, feature_set_hash)
);

ALTER TABLE snapshots
    ADD CONSTRAINT uq_snapshots_id_dataset UNIQUE (id, dataset_version_id);

CREATE TABLE feature_definitions (
    feature_set_id BIGINT NOT NULL REFERENCES feature_sets(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL CHECK (length(btrim(feature_name)) > 0),
    feature_group TEXT NOT NULL CHECK (feature_group IN
        ('activity', 'contributor_diversity', 'newcomer_retention', 'responsiveness')),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0),
    time_window TEXT NOT NULL CHECK (length(btrim(time_window)) > 0),
    missing_policy TEXT NOT NULL CHECK (length(btrim(missing_policy)) > 0),
    PRIMARY KEY (feature_set_id, feature_name)
);

CREATE TABLE snapshot_features (
    snapshot_id BIGINT NOT NULL,
    dataset_version_id BIGINT NOT NULL,
    feature_set_id BIGINT NOT NULL,
    features JSONB NOT NULL,
    missing_flags JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_id, feature_set_id),
    CONSTRAINT fk_snapshot_features_snapshot_dataset
        FOREIGN KEY (snapshot_id, dataset_version_id)
        REFERENCES snapshots (id, dataset_version_id) ON DELETE CASCADE,
    CONSTRAINT fk_snapshot_features_feature_set_dataset
        FOREIGN KEY (feature_set_id, dataset_version_id)
        REFERENCES feature_sets (id, dataset_version_id) ON DELETE CASCADE
);

CREATE TABLE repository_metrics_monthly (
    snapshot_id BIGINT NOT NULL,
    feature_set_id BIGINT NOT NULL,
    prediction_date DATE NOT NULL,
    metrics JSONB NOT NULL,
    completeness JSONB NOT NULL,
    PRIMARY KEY (snapshot_id, feature_set_id),
    CONSTRAINT fk_monthly_metrics_snapshot_features
        FOREIGN KEY (snapshot_id, feature_set_id)
        REFERENCES snapshot_features (snapshot_id, feature_set_id) ON DELETE CASCADE
);

CREATE INDEX idx_snapshot_features_feature_set ON snapshot_features (feature_set_id);
CREATE INDEX idx_monthly_metrics_prediction_date
    ON repository_metrics_monthly (feature_set_id, prediction_date);
