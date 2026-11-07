ALTER TABLE repositories
    ALTER COLUMN id SET GENERATED ALWAYS;

ALTER TABLE repositories
    ADD CONSTRAINT repositories_full_name_shape
        CHECK (full_name ~ '^[^/]+/[^/]+$'),
    ADD COLUMN owner TEXT GENERATED ALWAYS AS (split_part(full_name, '/', 1)) STORED NOT NULL,
    ADD COLUMN name TEXT GENERATED ALWAYS AS (split_part(full_name, '/', 2)) STORED NOT NULL,
    ADD COLUMN stars BIGINT GENERATED ALWAYS AS (stars_at_selection::BIGINT) STORED NOT NULL,
    ADD COLUMN github_created_at TIMESTAMPTZ GENERATED ALWAYS AS (created_at) STORED NOT NULL,
    ADD COLUMN cohort_version TEXT NOT NULL DEFAULT 'unassigned'
        CHECK (length(btrim(cohort_version)) > 0),
    ADD COLUMN is_active BOOLEAN GENERATED ALWAYS AS (NOT archived) STORED NOT NULL,
    ADD COLUMN added_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE repositories AS repository
SET cohort_version = COALESCE(
    (
        SELECT cohort.name
        FROM cohort_memberships AS membership
        JOIN cohorts AS cohort ON cohort.id = membership.cohort_id
        WHERE membership.repository_id = repository.id
        ORDER BY cohort.created_at DESC, cohort.id DESC
        LIMIT 1
    ),
    'unassigned'
),
added_at = selected_at;

CREATE TABLE contributors (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contributor_key TEXT NOT NULL UNIQUE
        CHECK (contributor_key ~ '^[0-9a-f]{64}$'),
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE commits (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    contributor_id BIGINT REFERENCES contributors(id) ON DELETE SET NULL,
    sha TEXT NOT NULL CHECK (length(btrim(sha)) > 0),
    committed_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_commits_repo_sha UNIQUE (repo_id, sha)
);

-- Supports chronological commit collection and repository history reads.
CREATE INDEX idx_commits_repo_committed_at ON commits (repo_id, committed_at);

CREATE TABLE issues (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_number BIGINT NOT NULL CHECK (github_number > 0),
    author_id BIGINT REFERENCES contributors(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    first_response_at TIMESTAMPTZ,
    CONSTRAINT uq_issues_repo_github_number UNIQUE (repo_id, github_number),
    CONSTRAINT ck_issues_closed_after_created
        CHECK (closed_at IS NULL OR closed_at >= created_at),
    CONSTRAINT ck_issues_response_after_created
        CHECK (first_response_at IS NULL OR first_response_at >= created_at)
);

-- Supports issue-window aggregation by repository and creation time.
CREATE INDEX idx_issues_repo_created_at ON issues (repo_id, created_at);

CREATE TABLE pull_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_number BIGINT NOT NULL CHECK (github_number > 0),
    author_id BIGINT REFERENCES contributors(id) ON DELETE SET NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'closed', 'merged')),
    created_at TIMESTAMPTZ NOT NULL,
    merged_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    first_response_at TIMESTAMPTZ,
    CONSTRAINT uq_pull_requests_repo_github_number UNIQUE (repo_id, github_number),
    CONSTRAINT ck_pull_requests_merged_after_created
        CHECK (merged_at IS NULL OR merged_at >= created_at),
    CONSTRAINT ck_pull_requests_closed_after_created
        CHECK (closed_at IS NULL OR closed_at >= created_at),
    CONSTRAINT ck_pull_requests_response_after_created
        CHECK (first_response_at IS NULL OR first_response_at >= created_at),
    CONSTRAINT ck_pull_requests_merged_state_has_timestamp
        CHECK (state <> 'merged' OR merged_at IS NOT NULL),
    CONSTRAINT ck_pull_requests_merge_before_close
        CHECK (merged_at IS NULL OR closed_at IS NULL OR merged_at <= closed_at)
);

-- Supports pull-request-window aggregation by repository and creation time.
CREATE INDEX idx_pull_requests_repo_created_at ON pull_requests (repo_id, created_at);

CREATE TABLE reviews (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    reviewer_id BIGINT REFERENCES contributors(id) ON DELETE SET NULL,
    state TEXT NOT NULL CHECK (
        state IN ('approved', 'changes_requested', 'commented', 'dismissed', 'pending')
    ),
    submitted_at TIMESTAMPTZ
);

CREATE TABLE collection_progress (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL
        CHECK (resource_type IN ('commits', 'issues', 'pull_requests', 'reviews')),
    cursor TEXT,
    last_page BIGINT CHECK (last_page IS NULL OR last_page >= 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
    requests_used BIGINT NOT NULL DEFAULT 0 CHECK (requests_used >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_collection_progress_repo_resource UNIQUE (repo_id, resource_type)
);

CREATE TABLE repo_windows (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repo_id BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    active_contributors BIGINT CHECK (active_contributors IS NULL OR active_contributors >= 0),
    new_contributors BIGINT CHECK (new_contributors IS NULL OR new_contributors >= 0),
    returning_contributors BIGINT
        CHECK (returning_contributors IS NULL OR returning_contributors >= 0),
    contributor_gini NUMERIC(6, 5)
        CHECK (contributor_gini IS NULL OR contributor_gini BETWEEN 0 AND 1),
    newcomer_retention_rate NUMERIC(6, 5)
        CHECK (newcomer_retention_rate IS NULL OR newcomer_retention_rate BETWEEN 0 AND 1),
    median_issue_response_hours NUMERIC(14, 4)
        CHECK (median_issue_response_hours IS NULL OR median_issue_response_hours >= 0),
    median_pr_merge_hours NUMERIC(14, 4)
        CHECK (median_pr_merge_hours IS NULL OR median_pr_merge_hours >= 0),
    prs_opened BIGINT CHECK (prs_opened IS NULL OR prs_opened >= 0),
    prs_merged BIGINT CHECK (prs_merged IS NULL OR prs_merged >= 0),
    review_count BIGINT CHECK (review_count IS NULL OR review_count >= 0),
    activity_score NUMERIC(18, 6)
        CHECK (activity_score IS NULL OR activity_score >= 0),
    activity_trend_slope NUMERIC(18, 8),
    contributor_trend_slope NUMERIC(18, 8),
    CONSTRAINT ck_repo_windows_end_after_start CHECK (window_end > window_start)
);

-- Enforces one window end per repository and supports repository window-history lookups.
CREATE UNIQUE INDEX uq_repo_windows_repo_end ON repo_windows (repo_id, window_end);

CREATE TABLE labels (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    window_id BIGINT NOT NULL UNIQUE REFERENCES repo_windows(id) ON DELETE CASCADE,
    horizon_days INTEGER NOT NULL CHECK (horizon_days > 0),
    future_activity_score NUMERIC(18, 6) NOT NULL CHECK (future_activity_score >= 0),
    decline_ratio NUMERIC(18, 8) NOT NULL CHECK (decline_ratio >= 0),
    is_decline BOOLEAN NOT NULL,
    label_version TEXT NOT NULL CHECK (length(btrim(label_version)) > 0)
);

CREATE TABLE model_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name TEXT NOT NULL CHECK (
        model_name IN ('baseline', 'logistic_regression', 'random_forest', 'gradient_boosting')
    ),
    model_version TEXT NOT NULL CHECK (length(btrim(model_version)) > 0),
    train_start TIMESTAMPTZ NOT NULL,
    train_end TIMESTAMPTZ NOT NULL,
    test_start TIMESTAMPTZ NOT NULL,
    test_end TIMESTAMPTZ NOT NULL,
    pr_auc NUMERIC(6, 5) CHECK (pr_auc IS NULL OR pr_auc BETWEEN 0 AND 1),
    roc_auc NUMERIC(6, 5) CHECK (roc_auc IS NULL OR roc_auc BETWEEN 0 AND 1),
    precision NUMERIC(6, 5) CHECK (precision IS NULL OR precision BETWEEN 0 AND 1),
    recall NUMERIC(6, 5) CHECK (recall IS NULL OR recall BETWEEN 0 AND 1),
    f1 NUMERIC(6, 5) CHECK (f1 IS NULL OR f1 BETWEEN 0 AND 1),
    params JSONB NOT NULL DEFAULT '{}'::JSONB,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_model_runs_name_version UNIQUE (model_name, model_version),
    CONSTRAINT ck_model_runs_train_range CHECK (train_end >= train_start),
    CONSTRAINT ck_model_runs_test_range CHECK (test_end >= test_start),
    CONSTRAINT ck_model_runs_temporal_split CHECK (train_end <= test_start)
);

CREATE UNIQUE INDEX uq_model_runs_single_primary
    ON model_runs (is_primary)
    WHERE is_primary;

CREATE TABLE predictions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id BIGINT NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    window_id BIGINT NOT NULL REFERENCES repo_windows(id) ON DELETE CASCADE,
    risk_score NUMERIC(5, 4) NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_predictions_model_window UNIQUE (model_run_id, window_id)
);

-- Supports finding predictions for a repository window across model runs.
CREATE INDEX idx_predictions_window_id ON predictions (window_id);

-- The unique index on (prediction_id, rank) supports lookups by prediction_id.
CREATE TABLE risk_indicators (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id BIGINT NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL CHECK (length(btrim(feature_name)) > 0),
    direction TEXT NOT NULL CHECK (direction IN ('increases_risk', 'decreases_risk')),
    weight NUMERIC(18, 8) NOT NULL CHECK (weight >= 0),
    rank INTEGER NOT NULL CHECK (rank > 0),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0)
);

-- Enforces one indicator per prediction rank and supports lookups by prediction_id.
CREATE UNIQUE INDEX uq_risk_indicators_prediction_rank
    ON risk_indicators (prediction_id, rank);

CREATE VIEW v_repo_latest_risk AS
SELECT repository.id AS repo_id,
       repository.full_name,
       latest.window_end,
       latest.risk_score,
       latest.risk_level
FROM repositories AS repository
JOIN LATERAL (
    SELECT repo_window.window_end,
           prediction.risk_score,
           prediction.risk_level
    FROM model_runs AS model_run
    JOIN predictions AS prediction ON prediction.model_run_id = model_run.id
    JOIN repo_windows AS repo_window ON repo_window.id = prediction.window_id
    WHERE model_run.is_primary
      AND repo_window.repo_id = repository.id
    ORDER BY repo_window.window_end DESC, prediction.created_at DESC, prediction.id DESC
    LIMIT 1
) AS latest ON TRUE;
