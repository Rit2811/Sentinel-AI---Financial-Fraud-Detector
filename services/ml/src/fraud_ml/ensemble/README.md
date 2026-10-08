# Ensemble Development Helpers

This separate development track contains numerical probability, calibration,
fusion, policy and reporting helpers. It is not the application's selected scorer.
The application uses the approved frozen sigmoid-calibrated Random Forest.

Legacy dataset-specific development/bundle entry points fail closed; supplying an
arbitrary artifact path cannot bypass their compatibility gates. Source pins and
feature order belong to `fraud_ml.data` and `fraud_ml.features`. Preserve separate
development artifacts; do not reuse them as a serving package or launch training
as an application setup step.
