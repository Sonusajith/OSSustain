ALTER TABLE prediction_explanations
    ADD COLUMN method TEXT NOT NULL DEFAULT 'local_substitution',
    ADD CONSTRAINT ck_prediction_explanations_method
        CHECK (method IN ('shap', 'local_substitution'));
