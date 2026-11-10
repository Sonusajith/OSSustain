BEGIN;

INSERT INTO repositories (
    github_id,
    full_name,
    created_at,
    stars_at_selection,
    size_group,
    primary_language,
    archived,
    fork,
    selected_at,
    cohort_version
)
VALUES
    (910000001, 'ossustain-demo/steady-alpha', TIMESTAMPTZ '2019-01-01 00:00:00+00',
     1200, 'medium', 'Java', FALSE, FALSE, now(), 'dev-seed-v1'),
    (910000002, 'ossustain-demo/declining-beta', TIMESTAMPTZ '2018-06-01 00:00:00+00',
     850, 'small', 'Python', FALSE, FALSE, now(), 'dev-seed-v1'),
    (910000003, 'ossustain-demo/growing-gamma', TIMESTAMPTZ '2020-03-01 00:00:00+00',
     3200, 'medium', 'TypeScript', FALSE, FALSE, now(), 'dev-seed-v1')
ON CONFLICT (github_id) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    stars_at_selection = EXCLUDED.stars_at_selection,
    size_group = EXCLUDED.size_group,
    primary_language = EXCLUDED.primary_language,
    archived = EXCLUDED.archived,
    fork = EXCLUDED.fork,
    selected_at = EXCLUDED.selected_at,
    added_at = EXCLUDED.selected_at,
    cohort_version = EXCLUDED.cohort_version;

WITH demo_repositories AS (
    SELECT id, full_name
    FROM repositories
    WHERE github_id IN (910000001, 910000002, 910000003)
),
months AS (
    SELECT month_start,
           row_number() OVER (ORDER BY month_start) - 1 AS month_index
    FROM generate_series(
        date_trunc('month', now()) - INTERVAL '12 months',
        date_trunc('month', now()) - INTERVAL '1 month',
        INTERVAL '1 month'
    ) AS month_start
)
INSERT INTO repo_windows (
    repo_id,
    window_start,
    window_end,
    active_contributors,
    new_contributors,
    returning_contributors,
    contributor_gini,
    newcomer_retention_rate,
    median_issue_response_hours,
    median_pr_merge_hours,
    prs_opened,
    prs_merged,
    review_count,
    activity_score,
    activity_trend_slope,
    contributor_trend_slope
)
SELECT repository.id,
       months.month_start,
       months.month_start + INTERVAL '1 month',
       CASE
           WHEN repository.full_name LIKE '%steady-alpha' THEN 8
           WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(2, 16 - months.month_index)
           ELSE 3 + months.month_index
       END,
       1 + (months.month_index % 3),
       CASE
           WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(1, 8 - months.month_index)
           ELSE 3
       END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN 0.68 ELSE 0.42 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN 0.24 ELSE 0.62 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN 54 ELSE 20 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN 110 ELSE 48 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(2, 12 - months.month_index) ELSE 10 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(1, 8 - months.month_index) ELSE 7 END,
       CASE WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(3, 20 - months.month_index) ELSE 16 END,
       CASE
           WHEN repository.full_name LIKE '%steady-alpha' THEN 25
           WHEN repository.full_name LIKE '%declining-beta' THEN GREATEST(4, 30 - months.month_index * 2)
           ELSE 10 + months.month_index * 2
       END,
       CASE
           WHEN repository.full_name LIKE '%declining-beta' THEN -1.25
           WHEN repository.full_name LIKE '%growing-gamma' THEN 0.75
           ELSE 0.02
       END,
       CASE
           WHEN repository.full_name LIKE '%declining-beta' THEN -0.5
           WHEN repository.full_name LIKE '%growing-gamma' THEN 0.2
           ELSE 0.01
       END
FROM demo_repositories AS repository
CROSS JOIN months
ON CONFLICT (repo_id, window_end) DO UPDATE SET
    window_start = EXCLUDED.window_start,
    active_contributors = EXCLUDED.active_contributors,
    new_contributors = EXCLUDED.new_contributors,
    returning_contributors = EXCLUDED.returning_contributors,
    contributor_gini = EXCLUDED.contributor_gini,
    newcomer_retention_rate = EXCLUDED.newcomer_retention_rate,
    median_issue_response_hours = EXCLUDED.median_issue_response_hours,
    median_pr_merge_hours = EXCLUDED.median_pr_merge_hours,
    prs_opened = EXCLUDED.prs_opened,
    prs_merged = EXCLUDED.prs_merged,
    review_count = EXCLUDED.review_count,
    activity_score = EXCLUDED.activity_score,
    activity_trend_slope = EXCLUDED.activity_trend_slope,
    contributor_trend_slope = EXCLUDED.contributor_trend_slope;

WITH demo_windows AS (
    SELECT repo_window.id AS window_id,
           repository.full_name,
           repo_window.activity_score
    FROM repo_windows AS repo_window
    JOIN repositories AS repository ON repository.id = repo_window.repo_id
    WHERE repository.github_id IN (910000001, 910000002, 910000003)
)
INSERT INTO labels (
    window_id,
    horizon_days,
    future_activity_score,
    decline_ratio,
    is_decline,
    label_version
)
SELECT window_id,
       90,
       activity_score * CASE WHEN full_name LIKE '%declining-beta' THEN 0.4 ELSE 0.9 END,
       CASE WHEN full_name LIKE '%declining-beta' THEN 0.4 ELSE 0.9 END,
       full_name LIKE '%declining-beta',
       'dev-seed-v1'
FROM demo_windows
ON CONFLICT (window_id) DO UPDATE SET
    horizon_days = EXCLUDED.horizon_days,
    future_activity_score = EXCLUDED.future_activity_score,
    decline_ratio = EXCLUDED.decline_ratio,
    is_decline = EXCLUDED.is_decline,
    label_version = EXCLUDED.label_version;

INSERT INTO model_runs (
    model_name,
    model_version,
    train_start,
    train_end,
    test_start,
    test_end,
    pr_auc,
    roc_auc,
    precision,
    recall,
    f1,
    params,
    is_primary
)
VALUES (
    'baseline',
    'dev-seed-v1',
    date_trunc('month', now()) - INTERVAL '36 months',
    date_trunc('month', now()) - INTERVAL '15 months',
    date_trunc('month', now()) - INTERVAL '12 months',
    date_trunc('month', now()) - INTERVAL '1 day',
    0.61,
    0.67,
    0.58,
    0.64,
    0.61,
    '{"seed":"dev_seed.sql","synthetic":true}'::JSONB,
    TRUE
)
ON CONFLICT (model_name, model_version) DO UPDATE SET
    train_start = EXCLUDED.train_start,
    train_end = EXCLUDED.train_end,
    test_start = EXCLUDED.test_start,
    test_end = EXCLUDED.test_end,
    pr_auc = EXCLUDED.pr_auc,
    roc_auc = EXCLUDED.roc_auc,
    precision = EXCLUDED.precision,
    recall = EXCLUDED.recall,
    f1 = EXCLUDED.f1,
    params = EXCLUDED.params,
    is_primary = EXCLUDED.is_primary,
    created_at = now();

WITH demo_windows AS (
    SELECT repo_window.id AS window_id,
           repository.full_name,
           repo_window.window_end
    FROM repo_windows AS repo_window
    JOIN repositories AS repository ON repository.id = repo_window.repo_id
    WHERE repository.github_id IN (910000001, 910000002, 910000003)
),
primary_model AS (
    SELECT id
    FROM model_runs
    WHERE model_name = 'baseline' AND model_version = 'dev-seed-v1'
)
INSERT INTO predictions (model_run_id, window_id, risk_score, risk_level)
SELECT primary_model.id,
       demo_windows.window_id,
       CASE
           WHEN demo_windows.full_name LIKE '%declining-beta'
               THEN LEAST(0.95, 0.72 + (EXTRACT(MONTH FROM demo_windows.window_end)::INTEGER % 10) / 100.0)
           WHEN demo_windows.full_name LIKE '%growing-gamma'
               THEN 0.38
           ELSE 0.16
       END,
       CASE
           WHEN demo_windows.full_name LIKE '%declining-beta' THEN 'high'
           WHEN demo_windows.full_name LIKE '%growing-gamma' THEN 'medium'
           ELSE 'low'
       END
FROM demo_windows
CROSS JOIN primary_model
ON CONFLICT (model_run_id, window_id) DO UPDATE SET
    risk_score = EXCLUDED.risk_score,
    risk_level = EXCLUDED.risk_level,
    created_at = now();

WITH demo_predictions AS (
    SELECT prediction.id AS prediction_id,
           repository.full_name,
           prediction.risk_score
    FROM predictions AS prediction
    JOIN model_runs AS model_run ON model_run.id = prediction.model_run_id
    JOIN repo_windows AS repo_window ON repo_window.id = prediction.window_id
    JOIN repositories AS repository ON repository.id = repo_window.repo_id
    WHERE model_run.model_name = 'baseline'
      AND model_run.model_version = 'dev-seed-v1'
      AND repository.github_id IN (910000001, 910000002, 910000003)
),
indicators AS (
    SELECT prediction_id,
           full_name,
           risk_score,
           1 AS rank,
           'activity_trend_slope' AS feature_name,
           CASE WHEN full_name LIKE '%declining-beta'
                THEN 'increases_risk' ELSE 'decreases_risk' END AS direction,
           'Synthetic activity-trend indicator for development seed data.' AS description
    FROM demo_predictions
    UNION ALL
    SELECT prediction_id,
           full_name,
           risk_score,
           2 AS rank,
           'active_contributors' AS feature_name,
           CASE WHEN full_name LIKE '%declining-beta'
                THEN 'increases_risk' ELSE 'decreases_risk' END AS direction,
           'Synthetic contributor-count indicator for development seed data.' AS description
    FROM demo_predictions
)
INSERT INTO risk_indicators (prediction_id, feature_name, direction, weight, rank, description)
SELECT prediction_id, feature_name, direction, risk_score, rank, description
FROM indicators
ON CONFLICT (prediction_id, rank) DO UPDATE SET
    feature_name = EXCLUDED.feature_name,
    direction = EXCLUDED.direction,
    weight = EXCLUDED.weight,
    description = EXCLUDED.description;

COMMIT;
