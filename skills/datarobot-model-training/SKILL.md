---
name: datarobot-model-training
description: Comprehensive guidance for training models in DataRobot, including project creation, AutoML configuration, feature engineering, and model selection. Use when training models, creating AutoML projects, or selecting models in DataRobot.
---

# DataRobot Model Training Skill

This skill provides guidance for the complete model training workflow in DataRobot, from project creation through model selection and validation.

## Quick Start

**Most common use case**: Create a project and train models

1. **Create or reuse a Use Case**: ask the user if they have an existing Use Case ID to reuse (`dr.UseCase.get(use_case_id)`); otherwise create a new one (`dr.UseCase.create(name)`). Every project needs one linked in Workbench
2. **Upload dataset**: `upload_dataset(file_path, dataset_name, use_case_id)` to upload training data, associated with the Use Case
3. **Create project**: `create_project(dataset_id, project_name, target_column, use_case_id)` to create new project, associated with the same Use Case
4. **Start training**: `start_automl(project_id, mode)` to begin AutoML training

**Example**: "Create a new project under a 'Sales Forecasting' Use Case with sales_data.csv, set 'revenue' as target, and start Quick AutoML training"

## When to use this skill

Use this skill when you need to:
- Create new DataRobot projects
- Upload training datasets
- Configure AutoML experiments
- Monitor training progress
- Select and compare models
- Understand feature engineering results
- Export trained models

## Key capabilities

### 1. Project Management

- Create new projects with appropriate settings
- Upload datasets (CSV, Parquet, database connections)
- Configure project settings (target, partitioning, time series)
- Manage multiple projects and experiments

### 2. AutoML Configuration

- Set training modes (Quick, Manual, Comprehensive)
- Configure feature engineering options
- Set time limits and resource constraints
- Choose algorithms and model types

### 3. Training Execution

- Start AutoML training runs
- Monitor training progress
- Handle training errors and warnings
- Pause/resume training if needed

### 4. Model Analysis

- Compare model performance metrics
- Review feature importance
- Analyze model insights and explanations
- Select best models for deployment

## Workflow examples

### Example 1: Create and train a new project

**User request**: "Create a new project using my sales_data.csv file, predict 'revenue' as the target, and start AutoML training."

**Agent workflow**:
1. Upload the dataset to DataRobot
2. Create a new project with the dataset
3. Set 'revenue' as the target variable
4. Configure project settings (detect partitioning, handle time series if needed)
5. Start AutoML training with appropriate mode
6. Monitor training progress
7. Report when training completes with top model metrics

### Example 2: Configure advanced training options

**User request**: "Train a model with time series settings: datetime column 'date', series ID 'store_id', forecast window 1-7 days."

**Agent workflow**:
1. Create project with time series configuration
2. Set datetime column and series ID columns
3. Configure forecast window (1-7 days)
4. Set appropriate time series validation
5. Start training with time series-aware algorithms
6. Monitor progress and report results

## Using DataRobot SDK

This skill guides you to use the DataRobot Python SDK directly. Install the SDK if needed:

```bash
pip install datarobot
```

### Key SDK Operations

Use these DataRobot SDK methods for model training:

**Use Cases** (organize related datasets/projects/deployments under one entity):
- `dr.UseCase.create(name, description=None)` - Create a new Use Case
- `dr.UseCase.get(use_case_id)` - Retrieve an existing Use Case (reuse instead of creating a new one)
- `use_case.add(entity=project_or_dataset)` - Attach an already-created project or dataset to a Use Case

**Projects**:
- `dr.Project.create_from_dataset(dataset_id, project_name, use_case=use_case)` - Create project, linked to a Use Case
- `dr.Project.get(project_id)` - Get project details
- `dr.Project.list()` - List all projects
- `project.set_target(target_column)` - Set target variable

**Training**:
- `project.start(autopilot_on=True)` - Start AutoML training
- `project.get_status()` - Check training status
- `dr.Model.list(project_id)` - List trained models
- `dr.Model.get(model_id)` - Get model details

**Model Analysis**:
- `model.get_metrics()` - Get performance metrics
- `model.get_feature_impact()` - Get feature importance

See the [Common Patterns](#common-patterns) section below for complete examples.

## Helper Scripts

This skill includes executable helper scripts that Claude can run directly:

- `scripts/create_project.py` - Create a new project from a dataset, optionally linked to a Use Case
- `scripts/start_training.py` - Start AutoML training
- `scripts/list_models.py` - List trained models with metrics

The `datarobot-data-preparation` skill's `scripts/upload_dataset.py` accepts the same optional `use_case_id` argument for linking an uploaded dataset to a Use Case.

**Usage example**:
```bash
# Create (or reuse) a Use Case first
python -c "import datarobot as dr; print(dr.UseCase.create(name='Sales Prediction').id)"

# Upload dataset, linked to the Use Case
python ../datarobot-data-preparation/scripts/upload_dataset.py sales_data.csv "Sales Data" use_case_456

# Create project and set target, linked to the same Use Case
python scripts/create_project.py dataset_123 "Sales Prediction" revenue use_case_456

# Start training
python scripts/start_training.py project_456 Quick

# List models
python scripts/list_models.py project_456 AUC
```

Claude can run these scripts directly or use them as reference when writing code.

## Best practices

1. **Data preparation**: Ensure data is clean and properly formatted before upload
2. **Use Cases**: Every project needs a linked Use Case in Workbench. Resolve one up front — reuse an existing `use_case_id` via `dr.UseCase.get(use_case_id)`, or create a new one via `dr.UseCase.create(name)` — and pass it to both `Dataset.create_from_file` (`use_cases=[...]`) and `Project.create_from_dataset` (`use_case=...`) so the project lands under the intended Use Case rather than a default one
3. **Target selection**: Choose appropriate target variable (avoid leakage)
4. **Partitioning**: Use proper partitioning for time-aware or grouped data
5. **Feature engineering**: Let AutoML handle feature engineering, but review results
6. **Model selection**: Compare multiple models, not just the top performer
7. **Validation**: Review validation strategy and ensure it matches your use case

## Common patterns

### Pattern 1: Standard classification/regression
```python
import datarobot as dr
import os

# Initialize client
client = dr.Client(
    token=os.getenv("DATAROBOT_API_TOKEN"), endpoint=os.getenv("DATAROBOT_ENDPOINT")
)

# Reuse an existing Use Case if the user gave us one, otherwise create a new one
existing_use_case_id = os.getenv("DATAROBOT_USE_CASE_ID")  # or ask the user for it
use_case = (
    dr.UseCase.get(existing_use_case_id)
    if existing_use_case_id
    else dr.UseCase.create(name="Sales Prediction")
)

# Upload dataset
dataset = dr.Dataset.create_from_file(
    file_path="training_data.csv", name="Sales Data", use_cases=[use_case]
)

# Create project
project = dr.Project.create_from_dataset(
    dataset_id=dataset.id, project_name="Sales Prediction", use_case=use_case
)

# Set target
project.set_target(target="revenue", mode=dr.AUTOPILOT_MODE.QUICK)

# Start AutoML (Quick mode)
project.start(autopilot_on=True, max_wait=3600)

# Monitor training
while project.get_status()["status"] not in ["complete", "error"]:
    import time

    time.sleep(30)
    project.get_status()

# Get trained models
models = dr.Model.list(project.id)
best_model = max(models, key=lambda m: m.metrics.get("AUC", 0))
print(f"Best model: {best_model.id}, AUC: {best_model.metrics.get('AUC')}")
```

### Pattern 2: Time series forecasting
```python
import datarobot as dr
import os

# Reuse an existing Use Case if the user gave us one, otherwise create a new one
existing_use_case_id = os.getenv("DATAROBOT_USE_CASE_ID")  # or ask the user for it
use_case = (
    dr.UseCase.get(existing_use_case_id)
    if existing_use_case_id
    else dr.UseCase.create(name="Sales Forecast")
)

# Upload dataset
dataset = dr.Dataset.create_from_file(
    "sales_data.csv", "Sales Forecast Data", use_cases=[use_case]
)

# Create project
project = dr.Project.create_from_dataset(
    dataset_id=dataset.id, project_name="Sales Forecast", use_case=use_case
)

# Configure time series settings
project.set_target(
    target="sales",
    mode=dr.AUTOPILOT_MODE.COMPREHENSIVE,
    partitioning_method=dr.PARTITIONING_METHOD.DATETIME,
    datetime_partition_column="date",
    multiseries_id_columns=["store_id"],
    forecast_window_start=1,
    forecast_window_end=7,
)

# Start training
project.start(autopilot_on=True, max_wait=7200)

# Wait for completion and get results
project.wait_for_completion()
models = dr.Model.list(project.id)
```

## Model selection criteria

When selecting models, consider:

- **Performance metrics**: Accuracy, AUC, RMSE, MAPE (depending on problem type)
- **Prediction speed**: Important for real-time deployments
- **Interpretability**: Some models are more explainable
- **Feature requirements**: Some models need specific feature types
- **Deployment constraints**: Consider model size and resource requirements

## Error handling

Common errors and solutions:

- **Dataset upload failures**: Check file format, size limits, encoding
- **"Dataset does not contain enough rows"**: DataRobot requires a minimum of 20 rows to create a project from a dataset — sample/demo data must meet this
- **Target errors**: Ensure target column exists and has appropriate values
- **Training failures**: Check data quality, feature types, missing values
- **Timeout errors**: Adjust time limits or use Quick mode for initial exploration

## SDK Setup

### Install DataRobot SDK

```bash
pip install datarobot
```

### Initialize Client

```python
import datarobot as dr
import os

client = dr.Client(
    token=os.getenv("DATAROBOT_API_TOKEN"),
    endpoint=os.getenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com"),
)
```

## Resources

- [DataRobot Python SDK Documentation](https://datarobot-public-api-client.readthedocs-hosted.com/)
- [DataRobot AutoML Documentation](https://docs.datarobot.com/en/docs/modeling/index.html)
- [General Modeling Documentation – Time Series](https://docs.datarobot.com/en/docs/modeling/index.html)
- [General Modeling Documentation – Feature Engineering](https://docs.datarobot.com/en/docs/modeling/index.html)

