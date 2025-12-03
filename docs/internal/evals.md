# Running Evaluations

The `packages/datacommons-mcp/evals/` directory contains evaluation tests for the Data Commons MCP server. These tests are built using the [Google Agent Development Kit (ADK)](https://github.com/google/adk-python/).

## Evaluation Framework

The goal of these tests is to make sure the agent works correctly. We compare what the agent does against a "ground truth" dataset to see if it's right.

### Core Objectives

*   **Intent Resolution:** Check if the agent understands what the user is asking and picks the right tool.
*   **Parameter Extraction:** Check if the agent pulls out the correct details (like dates, place IDs, and variable IDs) from the user's question.
*   **Regression Testing:** Ensure that changes to tool descriptions do not negatively impact the LLM's ability to correctly understand and use the tools.

## Scoring

We rate the agent's performance using two main scores:

1.  **Tool Call Score:** This checks if the agent called the right tool with the exact right arguments.
    *   **Score 1.0 (Pass):** The tool call matches the expectation exactly.
    *   **Score < 1.0 (Fail):** Any difference in the tool name or arguments.

2.  **Response Evaluation Score:** This checks the quality of the agent's final text response (if a reference answer is provided).
    *   We use a **ROUGE-1 F1 score**.
    *   **What this means:** ROUGE-1 counts how many words in the agent's answer overlap with the words in the reference answer. A higher score means more overlap.

## Test Data Structure

The tests are defined in JSON files in `packages/datacommons-mcp/evals/tool_call_evals/data/`.

### Schema

```json
{
  "query": "What is the population (dcid=Count_Person) of California??",
  "expected_tool_use": [
    {
      "tool_name": "get_observations",
      "tool_input": {
        "date": "latest",
        "place_dcid": "geoId/06",
        "variable_dcid": "Count_Person"
      }
    }
  ],
  "reference": "A data analyst could use this data to identify the most recent population"
}
```

*   `query`: The question we ask the agent.
*   `expected_tool_use`: The tool calls we expect the agent to make. The agent must match the tool name and inputs exactly to pass.
*   `reference`: (Optional) A correct answer text, used if we want to check the quality of the agent's final response.

## Execution

### Environment Configuration

You need these environment variables to run the tests:

```bash
export DC_API_KEY="<your-dc-key>"      # https://apikeys.datacommons.org/
export GEMINI_API_KEY="<your-key>"     # https://aistudio.google.com/app/apikey
```

### Local Runner

Run the tests using `uv` to make sure all dependencies are installed:

```bash
# Run from the root of the repo
uv run --extra test pytest -k "eval"
```

### CI/CD Integration

We run these tests automatically on GitHub Actions (in `.github/workflows/secure-evals.yaml`) whenever code changes in `packages/datacommons-mcp/` or `evals/`. This checks that new code doesn't break the `main` branch.

## Adding New Evals

To add new tests:

1.  Go to `packages/datacommons-mcp/evals/tool_call_evals/data/`.
2.  Choose an appropriate directory for your test, or create a new one.
3.  Create a new `.test.json` file in that directory, or add to an existing one.
4.  Add your test cases using the JSON format above.
5.  The test runner (`test_tools.py`) will automatically find and run your new tests.

## Reporting

The test runner saves reports in the `reports/` directory.

### Artifacts
*   **HTML Report:** `evaluation-report-<timestamp>.html` (Easy to read, with colors)
*   **CSV Report:** `evaluation-report-<timestamp>.csv` (Raw data for analysis)

### Report Schema

Here are the columns included in the report:

| Column | Description |
| :--- | :--- |
| `source_test_file` | The JSON file containing the test case. |
| `overall_eval_status` | Did the test pass or fail? |
| `overall_tool_eval_status` | Aggregate pass/fail status for tool calls across runs. |
| `tool_eval_status` | Pass/fail status for the tool call in this specific run. |
| `overall_response_eval_status` | Aggregate pass/fail status for the response across runs. |
| `response_eval_status` | Pass/fail status for the response in this specific run. |
| `average_tool_call_score` | Average tool score across all runs for this case. |
| `average_response_evaluation_score` | Average response score (ROUGE-1) across all runs. |
| `tool_call_score_threshold` | Minimum score required to pass tool evaluation (usually 1.0). |
| `response_evaluation_score_threshold` | Minimum score required to pass response evaluation. |
| `run_number` | The iteration number of the test run. |
| `tool_call_score` | Score for this specific run (1.0 = exact match, 0.0 = mismatch). |
| `response_evaluation_score` | ROUGE-1 F1 score for the response in this run. |
| `time_taken_seconds` | How long the test took to run. |
| `prompt` | The input question sent to the agent. |
| `expected_response` | The reference answer from the JSON. |
| `actual_response` | The answer generated by the agent. |
| `expected_tool_calls` | The tool calls defined in the "ground truth". |
| `actual_tool_calls` | The tool calls actually made by the agent.
