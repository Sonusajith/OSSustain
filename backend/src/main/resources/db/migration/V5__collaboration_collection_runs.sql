ALTER TABLE collection_runs
    DROP CONSTRAINT collection_runs_stage_check;

ALTER TABLE collection_runs
    ADD CONSTRAINT collection_runs_stage_check
        CHECK (stage IN (
            'repository_metadata',
            'commits',
            'pull_requests',
            'reviews',
            'issues',
            'responses',
            'validation'
        ));

-- GitHub review IDs make review upserts idempotent across collector reruns.
ALTER TABLE reviews
    ADD COLUMN github_id BIGINT;

CREATE UNIQUE INDEX uq_reviews_pull_request_github_id
    ON reviews (pull_request_id, github_id)
    WHERE github_id IS NOT NULL;
