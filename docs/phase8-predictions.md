# Phase 8 predictions and explanations

## Model selection and traceability

`predict` first considers only the model marked selected within each feature
family. It chooses the highest validation PR-AUC across those candidates; ties
are resolved by model-version ID. The test split is never queried for this
choice. Prediction rows retain the model version, dataset version, snapshot,
prediction date, probability, and risk category. The selected model's validation
PR-AUC and F1 decision threshold remain in the model evaluation records.

The category boundaries are the inclusive one-third and two-thirds quantiles of
the selected model's validation probabilities. Scores at or below the first
boundary are `low`, scores above it and at or below the second are `medium`, and
scores above the second are `high`. Tied scores can leave a category empty. The
cutoffs are persisted on `model_versions` and copied into the local run report.
They place new scores relative to the validation-score distribution; they are
not policy thresholds or calibrated probabilities of future decline. The model's
calibration evaluation is documented in [Phase 7 results](phase7-modeling.md).

## Cohort coverage and limitations

For each repository in the dataset's cohort, the pipeline selects the latest
snapshot that belongs to that dataset and feature set. A snapshot can be used
when its future label is incomplete because inference does not need an observed
outcome. A repository without a snapshot or a feature record is recorded as
`skipped` with a reason in `prediction_outcomes`. Every generated prediction
stores limitation flags for low reference activity and missing model inputs.

## Per-prediction indicators

`explain` takes the stored prediction's feature values and replaces one input at
a time with that feature's median among labeled validation snapshots. The signed
change in model probability is ranked by absolute size; up to five indicators
are persisted. Positive changes are described as associated with a higher model
risk score, and negative changes as associated with a lower score. This is a
local model comparison, not a causal effect. Missing inputs are imputed by the
saved training pipeline and are visible through the prediction's limitation
flags; a feature without a validation reference value is omitted from indicators.

Both commands are idempotent for the same model and snapshot. Reports are local
JSON files under ignored `pipeline/data/reports/` by default.

## Dataset 1 run

The local run selected model version 3 (Random Forest, activity-only), which had
the highest validation PR-AUC among the family-selected models (0.6470). Its
validation-derived category cutoffs were 0.4445 and 0.6041. All 50 cohort
repositories received a prediction for their latest snapshot; none were skipped.
All 50 predictions received three activity-feature indicators (150 rows total),
and rerunning both stages preserved the same 50 predictions and 150 indicator
rows. Forty-four predictions carry a low-activity limitation flag. The local
run report records each probability, category, snapshot, date, and flag.
