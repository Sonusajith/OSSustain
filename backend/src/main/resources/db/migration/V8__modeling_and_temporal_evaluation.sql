CREATE TABLE model_versions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    feature_set_id BIGINT NOT NULL,
    feature_set_name TEXT NOT NULL CHECK (feature_set_name IN ('activity_only', 'extended')),
    algorithm TEXT NOT NULL CHECK (algorithm IN (
        'threshold_baseline', 'logistic_regression', 'random_forest', 'gradient_boosting'
    )),
    params JSONB NOT NULL,
    params_hash TEXT NOT NULL CHECK (params_hash ~ '^[0-9a-f]{64}$'),
    seed INTEGER NOT NULL CHECK (seed >= 0),
    label_config JSONB NOT NULL,
    training_config JSONB NOT NULL,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    code_revision TEXT NOT NULL,
    artifact_path TEXT,
    validation_threshold DOUBLE PRECISION NOT NULL
        CHECK (validation_threshold BETWEEN 0 AND 1),
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_model_versions_feature_set_dataset
        FOREIGN KEY (feature_set_id, dataset_version_id)
        REFERENCES feature_sets (id, dataset_version_id) ON DELETE CASCADE,
    CONSTRAINT uq_model_versions_id_dataset UNIQUE (id, dataset_version_id),
    CONSTRAINT uq_model_versions_configuration
        UNIQUE (dataset_version_id, feature_set_id, feature_set_name, algorithm, params_hash)
);

CREATE UNIQUE INDEX uq_model_versions_selected_per_feature_set
    ON model_versions (dataset_version_id, feature_set_id, feature_set_name)
    WHERE is_selected;

CREATE TABLE evaluation_results (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_version_id BIGINT NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    split TEXT NOT NULL CHECK (split IN ('train', 'validation', 'test')),
    stratum TEXT NOT NULL CHECK (stratum IN ('overall', 'small', 'medium', 'large')),
    metric TEXT NOT NULL CHECK (length(btrim(metric)) > 0),
    value DOUBLE PRECISION,
    ci_low DOUBLE PRECISION,
    ci_high DOUBLE PRECISION,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    CONSTRAINT uq_evaluation_results_key
        UNIQUE (model_version_id, split, stratum, metric),
    CONSTRAINT ck_evaluation_results_finite CHECK (
        (value IS NULL OR value NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8))
        AND (ci_low IS NULL OR ci_low NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8))
        AND (ci_high IS NULL OR ci_high NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8))
    ),
    CONSTRAINT ck_evaluation_results_ci CHECK (
        (ci_low IS NULL AND ci_high IS NULL) OR
        (ci_low IS NOT NULL AND ci_high IS NOT NULL AND ci_low <= ci_high)
    )
);

CREATE INDEX idx_evaluation_results_split_stratum
    ON evaluation_results (split, stratum, metric);

CREATE TABLE feature_importances (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_version_id BIGINT NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    method TEXT NOT NULL CHECK (method IN ('validation_permutation', 'standardized_coefficient')),
    feature_name TEXT NOT NULL CHECK (length(btrim(feature_name)) > 0),
    value DOUBLE PRECISION NOT NULL,
    rank INTEGER NOT NULL CHECK (rank > 0),
    CONSTRAINT uq_feature_importances_key UNIQUE (model_version_id, method, feature_name),
    CONSTRAINT ck_feature_importances_finite CHECK (
        value NOT IN ('Infinity'::float8, '-Infinity'::float8, 'NaN'::float8)
    )
);

CREATE INDEX idx_feature_importances_model_rank
    ON feature_importances (model_version_id, method, rank);

ALTER TABLE predictions
    ALTER COLUMN model_run_id DROP NOT NULL,
    ALTER COLUMN window_id DROP NOT NULL,
    ADD COLUMN model_version_id BIGINT,
    ADD COLUMN snapshot_id BIGINT,
    ADD COLUMN dataset_version_id BIGINT,
    ADD CONSTRAINT fk_predictions_model_version_dataset
        FOREIGN KEY (model_version_id, dataset_version_id)
        REFERENCES model_versions (id, dataset_version_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_predictions_snapshot_dataset
        FOREIGN KEY (snapshot_id, dataset_version_id)
        REFERENCES snapshots (id, dataset_version_id) ON DELETE CASCADE,
    ADD CONSTRAINT ck_predictions_one_model_reference CHECK (
        (model_run_id IS NOT NULL AND window_id IS NOT NULL
            AND model_version_id IS NULL AND snapshot_id IS NULL AND dataset_version_id IS NULL)
        OR (model_run_id IS NULL AND window_id IS NULL
            AND model_version_id IS NOT NULL AND snapshot_id IS NOT NULL
            AND dataset_version_id IS NOT NULL)
    );

CREATE UNIQUE INDEX uq_predictions_model_version_window
    ON predictions (model_version_id, snapshot_id)
    WHERE model_version_id IS NOT NULL;
