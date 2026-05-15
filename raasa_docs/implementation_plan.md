# Implementation Plan: Learned Risk Model (Isolation Forest)

We are starting Phase 3 of the RAASA roadmap. The goal is to move from a static, manually-weighted risk formula (`Risk = w1*cpu + w2*mem + w3*proc + w4*net`) to a dynamic, unsupervised **Learned Risk Model**. We will use `scikit-learn`'s `IsolationForest` to assess the likelihood of a feature vector being an anomaly.

## progress Tracking

- [x] **Configuration Updates**
  - [x] Add `scikit-learn` and `joblib` (for model persistence) to `requirements.txt`.
  - [x] Add a new config block in `config.yaml` to specify `model_path` and `use_ml_model`.
  - [x] Update `AppConfig` logic in `raasa/core/config.py`.

- [x] **ML Training Pipeline**
  - [x] Create `raasa/ml/train_iforest.py` to extract benign vectors and train the model.
  - [x] Train initial model on 398 benign records from existing logs.
  - [x] Persist model to `raasa/models/iforest_latest.pkl`.

- [x] **Risk Assessment Engine**
  - [x] Update `RiskAssessor` in `raasa/core/risk_model.py` to load the Joblib model.
  - [x] Implement ML-based risk calculation using `decision_function`.
  - [x] Ensure graceful fallback to linear weights if model loading fails.

- [x] **Controller Integration**
  - [x] Update `raasa/core/app.py` to pass ML configuration to `RiskAssessor`.

- [ ] **Validation & Verification**
  - [ ] Implement `tests/test_learned_model.py` to verify ML path behavior.
  - [ ] Run comparison experiment: Linear vs ML on `network_test` scenario.
  - [ ] Update performance claims in research documentation.

## User Review Required

> [!NOTE]
> All core technical components of the ML transition are now **complete**. We have successfully transitioned from a static heuristic to a learning model.

## Proposed Changes

### Configuration Updates [COMPLETE]
- Add `scikit-learn` and `joblib` (for model persistence) to `requirements.txt`.
- Add a new config block in `config.yaml` to specify `model_path: "raasa/models/iforest.pkl"` and `use_ml_model: true`.

### ML Training Pipeline [COMPLETE]
#### [NEW] `raasa/ml/train_iforest.py`
- Integrated log extraction and `IsolationForest` training.
- Successfully generated `iforest_latest.pkl`.

### Risk Assessment Engine [COMPLETE]
#### [MODIFY] `raasa/core/risk_model.py`
- Implemented `RiskAssessor` updates for ML scoring.

### Experiment Extension [IN PROGRESS]
#### [NEW] `tests/test_learned_model.py`
- Add unit tests verifying that `RiskAssessor` behaves gracefully.

## Open Questions

> [!NOTE]
> There are no remaining open questions for the implementation phase. We are moving into validation.

## Verification Plan

### Automated Tests
- [x] Install dependencies via `pip install -r requirements.txt`.
- [ ] Run `pytest tests/` entirely, including new ML-specific tests.

### Manual Verification
- [x] Execute `python -m raasa.ml.train_iforest` to generate the model.
- [ ] Execute `python -m raasa.experiments.run_experiment --mode raasa --scenario network_test` to verify detection performance.
