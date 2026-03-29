# DAG Plan Authoring

This guide shows how to author SAIDA plans using the execution DAG contract introduced in `0.3.0`.

## Core Rules

- every step is a node
- every declared input ref is directional
- cycles are not allowed
- every output ref must be produced once
- `final_output_ref` should point at the output you want surfaced as the primary result

## Main Contracts

- `AnalysisPlan.inputs`: named plan-level inputs such as `primary_dataset`
- `PlanStep.inputs`: explicit references to plan inputs or earlier step outputs
- `PlanStep.outputs`: typed output declarations for the step
- `PlanStep.output_refs`: stable output ids for result and dependency lookup
- `AnalysisPlan.final_output_ref`: the final artifact to surface as the primary result

## Recommended Artifact Kinds

- `dataset`
- `frame`
- `series`
- `scalar`
- `verification`

Pandas remains the low-level payload representation, but plans should reason in terms of typed artifacts and refs rather than raw DataFrame plumbing.

## Simple Single-Step Plan

```python
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Count all rows.",
    inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
    final_output_ref="row_count",
    steps=[
        PlanStep(
            step_id="row_count",
            tool_family="duckdb",
            action="row_count",
            method_id="row_count",
            family="aggregation_grouping",
            parameters={},
            description="Count all rows.",
            inputs=[
                StepInputRef(
                    input_id="dataset_input",
                    source_type="plan_input",
                    ref="primary_dataset",
                    expected_kind="dataset",
                )
            ],
            output_refs=["row_count"],
            outputs=[
                StepOutputSpec(
                    output_id="row_count",
                    kind="scalar",
                    logical_shape="scalar",
                    physical_shape="scalar",
                )
            ],
        )
    ],
)
```

## Chained Two-Step Plan

```python
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Count rows, then consume that output in a second step.",
    inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
    final_output_ref="numeric_summary_table",
    steps=[
        PlanStep(
            step_id="row_count",
            tool_family="duckdb",
            action="row_count",
            method_id="row_count",
            family="aggregation_grouping",
            parameters={},
            description="Count all rows.",
            inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset")],
            output_refs=["row_count_value"],
            outputs=[StepOutputSpec(output_id="row_count_value", kind="scalar", logical_shape="scalar")],
        ),
        PlanStep(
            step_id="numeric_summary",
            tool_family="stats",
            action="numeric_summary",
            method_id="numeric_summary",
            family="diagnostic_workflows",
            parameters={},
            description="Consume the earlier output before producing the final table.",
            inputs=[StepInputRef(input_id="count_input", source_type="step_output", ref="row_count_value")],
            output_refs=["numeric_summary_table"],
            outputs=[StepOutputSpec(output_id="numeric_summary_table", kind="frame", logical_shape="table")],
        ),
    ],
)
```

## Prompt-Generated Plans

`PromptAnalysisFrontend.plan(...)` now emits graph-valid plans by construction:

- dataset input refs are attached automatically
- output refs and output specs are inferred when the registry can do so safely
- `final_output_ref` is set during plan finalization

This keeps prompt generation and authored plans on the same execution contract.

## Migration Notes

- existing single-step authored plans still execute
- the engine binds missing dataset inputs and output refs for backward compatibility
- new authored plans should prefer explicit `inputs`, `outputs`, and `final_output_ref`
