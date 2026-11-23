from ossustain_pipeline.on_demand import (
    MAX_GLOBAL_HOURLY_REQUESTS,
    MAX_JOB_REQUESTS,
    _mask_bounded_history_features,
    _MemoryCache,
)


def test_on_demand_request_budgets_match_approved_caps() -> None:
    assert MAX_JOB_REQUESTS == 300
    assert MAX_GLOBAL_HOURLY_REQUESTS == 1000


def test_bounded_history_does_not_claim_first_ever_contributors() -> None:
    features = {
        "new_contributors_90d": 4,
        "newcomer_retention_rate_90d": 0.5,
        "commits_90d": 12,
    }

    bounded = _mask_bounded_history_features(features)

    assert bounded["new_contributors_90d"] is None
    assert bounded["newcomer_retention_rate_90d"] is None
    assert bounded["commits_90d"] == 12
    assert features["new_contributors_90d"] == 4


def test_on_demand_cache_never_persists_event_responses() -> None:
    cache = _MemoryCache()
    assert cache.read("https://api.github.com/repos/example/project") is None
    assert cache.write("https://api.github.com/repos/example/project", None) is None
