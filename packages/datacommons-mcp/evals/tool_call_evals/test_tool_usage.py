import pathlib

import pandas as pd
import pytest

from evals.evaluator_framework.evaluator import AgentEvaluator
from evals.tool_call_evals.agent import create_agent
from evals.tool_call_evals.instructions import DATA_AVAILABILITY_INSTRUCTIONS

# --- Configuration ---
EVALS_DATA_DIR = pathlib.Path(__file__).parent / "data"
TEST_FILES = sorted(EVALS_DATA_DIR.glob("**/*.test.json"))
REPORT_OUTPUT_DIR = "reports/"
REPORT_OUTPUT_BASE_FILENAME = "evaluation-report"


# --- Test Class for Evaluation and Reporting ---
class TestAgentEvaluation:
    """
    A test suite that evaluates the agent across multiple datasets,
    collects results into pandas DataFrames, and generates a
    consolidated HTML report after all tests have completed.
    """

    # Class attribute to store DataFrames from all test runs
    all_results_dfs: list[pd.DataFrame] = []

    @pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: p.name)
    @pytest.mark.asyncio
    async def test_tool_agent(self, path: pathlib.Path) -> None:
        """
        Test the agent's ability via a session file, collect the
        resulting dataframe, and then perform assertions.
        """

        agent = create_agent(DATA_AVAILABILITY_INSTRUCTIONS)

        # 1. Run the evaluation and get the dataframe
        result_df = await AgentEvaluator.evaluate(
            agent=agent,
            eval_dataset_path=str(path),
            num_runs=2,
            tool_score_threshold=1,  # Requires an exact match of tool calls
            response_score_threshold=0.01,  # Low threshold for response evaluation
        )

        # Add the test file name as a column for context in the final report
        result_df["source_test_file"] = path.name

        # Reorder columns to put source_test_file first
        columns = result_df.columns.tolist()
        columns.remove("source_test_file")
        result_df = result_df[["source_test_file"] + columns]

        # 2. IMPORTANT: Collect the result *before* any assertions
        # This ensures the data is saved even if the test fails.
        TestAgentEvaluation.all_results_dfs.append(result_df)

        # 3. Perform assertions on the result
        # If an assertion fails, pytest will mark this specific test run as FAILED,
        # but the `result_df` is already collected and the other parameterized
        # runs will continue.
        assert not result_df.empty, (
            f"Evaluation returned an empty dataframe for {path.name}"
        )

        # Check if any evaluations failed
        if "overall_eval_status" in result_df.columns:
            failed_rows = result_df[result_df["overall_eval_status"] == "FAILED"]
            if not failed_rows.empty:
                # Count failures by metric type
                failure_summary = []

                if "tool_eval_status" in result_df.columns:
                    tool_failures = len(
                        failed_rows[failed_rows["tool_eval_status"] == "FAILED"]
                    )
                    if tool_failures > 0:
                        failure_summary.append(f"tool_eval: {tool_failures} failures")

                if "response_eval_status" in result_df.columns:
                    response_failures = len(
                        failed_rows[failed_rows["response_eval_status"] == "FAILED"]
                    )
                    if response_failures > 0:
                        failure_summary.append(
                            f"response_eval: {response_failures} failures"
                        )

                pytest.fail(
                    f"Evaluation FAILED for {path.name}.\n"
                    f"Failed metrics summary: {', '.join(failure_summary) if failure_summary else 'unknown failures'}\n"
                    f"Total failed evaluations: {len(failed_rows)}"
                )

    @classmethod
    def teardown_class(cls) -> None:
        """
        Pytest hook that runs once after all test methods in the class are done.
        Combines the output from all tests into the final report.
        """
        if not cls.all_results_dfs:
            print("\nNo DataFrames were collected to generate a report.")
            return

        print(
            f"\n📈 Combining {len(cls.all_results_dfs)} result(s) into a single report..."
        )

        # Combine all collected DataFrames into one large DataFrame
        final_report_df = pd.concat(cls.all_results_dfs, ignore_index=True)

        # Write the final DataFrame to a single, easy-to-read HTML file
        try:
            # Make report output directory if it doesn't exist
            pathlib.Path(REPORT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            # Write output path with a timestamp
            report_output_path = (
                pathlib.Path(REPORT_OUTPUT_DIR)
                / f"{REPORT_OUTPUT_BASE_FILENAME}-{pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')}.html"
            )
            AgentEvaluator.create_styled_html_report(
                final_report_df, report_output_path
            )
            print(f"✅ Report successfully generated at: {report_output_path}")
            # Write to CSV as well for easier data manipulation
            csv_path = report_output_path.with_suffix(".csv")
            final_report_df.to_csv(csv_path, index=False)
            print(f"✅ CSV report generated at: {csv_path}")
        except Exception as e:
            print(f"🔥 Failed to write HTML report: {e}")
