# Changelog

All notable changes to DataRobot agent skills are tracked here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
version numbers track the shared plugin version maintained across
`.claude-plugin/`, `.cursor-plugin/plugin.json`, and `gemini-extension.json`.

Each entry should be prefixed with the affected skill folder name (for example,
`` `datarobot-predictions`: ... ``) so it's easy to scan what changed per skill.

## [Unreleased]

- `datarobot-setup`: Broaden trigger to cover credential failures; add env var and auth validity checks to pre-flight.

### Added
- `datarobot-workload-api`: New skill covering the DataRobot Workload API end-to-end — running containers as managed services, replica/autoscaling settings, CPU/GPU compute bundles, credential injection, diagnosing stuck or crash-looping workloads (`CrashLoopBackOff` / `ImagePullBackOff` / `OOMKilled` / probe failures / `exec format error` on linux/amd64), pulling logs / OpenTelemetry traces / metrics / service stats, the artifact dev → lock → production rollout flow with zero-downtime rolling replacement, and org-admin-set scaling limits (`maxConcurrentWorkloads`, `maxWorkloadReplicas` — returns HTTP 403 with a structured detail message when exceeded). Modal organization with one SKILL.md covering four user intents (create/configure, diagnose, observe, artifact lifecycle), five runnable scripts in `scripts/` (`wait_for_running.py`, `diagnose_workload.py`, `wait_for_build.py`, `wait_for_replacement.py`, `check_limits.py`), and deep content in `references/` (status vocabulary, common error patterns, OpenAPI schema reference, full lifecycle code paths). Examples use `httpx`.
- `tests/integration/test_workload_api_limits.py`: spec-conformance test that fetches the published public OpenAPI spec and asserts the `maxConcurrentWorkloads` / `maxWorkloadReplicas` fields exist on the `OrganizationRetrieve` / `OrganizationUserResponse` / `UserRetrieveResponse` schemas. Skips cleanly when offline so it doesn't break CI without network. Catches future drift between the skill's documented field names and the spec.

### Changed
- `datarobot-model-explainability`: Correct SHAP export guidance for `datarobot.insights.ShapMatrix` (in-memory `matrix`/`columns` or classmethod `get_as_dataframe`/`get_as_csv`); fix `compute_shap_matrix.py` `--output` export; fix anomaly assessment date-range example to use `get_explanations()` instead of `get_latest_explanations()`; fix Model diagnostics examples (`get_confusion_chart`, `get_feature_effect`); document insights diagnostics (`RocCurve`, `LiftChart`, `ConfusionMatrix`); correct documented SHAP caveats for blenders, the >1000-feature limit, `ShapImpact` source support, logit-link probability conversion, XEMP contribution wording, XEMP routing guidance, and XEMP `max_explanations` limit; raise the documented minimum SDK version to `datarobot>=3.6.0` when referencing `ShapDistributions`.

## [1.3.1] - 2026-06-02

- `datarobot-setup`: Corrected issues with setup commands.

## [1.3.0] - 2026-05-27

- `datarobot-model-explainability`: Updated SHAP guidance to use the current `datarobot.insights` APIs, added data slice and anomaly assessment coverage, added SHAP and XEMP reference docs, and added a `compute_shap_matrix.py` helper script.

## [1.2.0] - 2026-05-20

First tracked release. Skills included:

- `datarobot-agent-assist`
- `datarobot-app-framework-cicd`
- `datarobot-data-preparation`
- `datarobot-external-agent-monitoring`
- `datarobot-feature-engineering`
- `datarobot-model-deployment`
- `datarobot-model-explainability`
- `datarobot-model-monitoring`
- `datarobot-model-training`
- `datarobot-predictions`
- `datarobot-setup`
