# Phase 4 Data Collection and Quality

## Dataset version

- Cohort: `ossustain-public-repositories-v1`
- Cohort configuration hash: `f7098f8826eb12e0ab9672020a1dea4334e70c0f88b282977b00016ceacfa5e8`
- Observation window: 2022-01-01 through 2025-12-31
- Repositories processed: 50 of 50
- Collection stages failed: 0

The version is identified by the cohort name, configuration hash, and observation window. Detailed machine-readable reports are generated locally at `pipeline/data/reports/phase4-full.json` and `pipeline/data/reports/phase4-validation.json`; those reports and collected records are ignored by Git.

## Collected data

| Record type | Count |
|---|---:|
| Pull requests | 2,659 |
| Reviews | 2,285 |
| Non-PR issues | 17,647 |
| Commits (Phase 3) | 55,206 |

All collection stages completed. Validation marks 46 repositories complete and retains four with quality flags for review.

## Request use

| Budget category | Used across collection | Approved cap |
|---|---:|---:|
| Pull requests, reviews, and responses | 7,919 | 12,500 |
| Non-PR issues and responses | 5,090 | 25,000 |

The request counter is kept in the local append-only ledger under `%LOCALAPPDATA%/ossustain/` and reconciled with database run history. It is not committed.

## First-response coverage

| Data type | Has first response | Missing first response | Missing rate |
|---|---:|---:|---:|
| Pull requests | 1,124 of 2,659 | 1,535 | 57.7% |
| Non-PR issues | 3,775 of 17,647 | 13,872 | 78.6% |

Missing first responses are represented as null. They are not filled with estimates.

## Quality flags

- `protobuf-net/protobuf-net`: 239 collected issues versus 238 in the frozen screen (+1).
- `longitachi/ZLPhotoBrowser`: 42 collected pull requests versus 43 in the frozen screen (-1).
- `kubernetes/client-go`: no pull requests or issues; the frozen screen also counted zero for both.
- `hoochanlon/hamuleite`: no pull requests or issues; the frozen screen also counted zero for both.

The two one-record differences remain flagged because the screening counts and final collection do not agree. No collection stage failed, and no repository was removed from the cohort.

## Reproduction

With PostgreSQL running and the local `.env` values configured, run:

```powershell
$env:PYTHONPATH = 'pipeline/src'
.venv/Scripts/python.exe -m ossustain_pipeline.cli --config pipeline/config.example.yaml collect-collaboration --report pipeline/data/reports/phase4-full.json
.venv/Scripts/python.exe -m ossustain_pipeline.cli --config pipeline/config.example.yaml validate --report pipeline/data/reports/phase4-validation.json
```

The validation command compares each repository's collected PR and issue counts with the frozen Phase 4 screening counts and reports first-response missingness and insufficient-data flags.
