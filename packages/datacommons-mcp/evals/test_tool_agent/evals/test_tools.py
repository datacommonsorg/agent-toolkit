import pathlib

import pandas as pd
import pytest

# Assuming this is the correct import path for your evaluator
from evals.evaluator.agent_evaluator import AgentEvaluator

# --- Configuration ---
GET_OBSERVATIONS_DATA_DIR = pathlib.Path(__file__).parent / "data/get_observations"
TEST_FILES = sorted(GET_OBSERVATIONS_DATA_DIR.glob("*.test.json"))
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

        # 1. Run the evaluation and get the dataframe
        # This assumes your `evaluate` function now returns a pandas DataFrame.
        result_df = await AgentEvaluator.evaluate(
            agent_module="evals.test_tool_agent.bootstrap",
            eval_dataset_path=str(path),
            num_runs=2,
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
        This is the perfect place to generate the final report.
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
            create_styled_html_report(final_report_df, report_output_path)
            print(f"✅ Report successfully generated at: {report_output_path}")
            # Write to CSV as well for easier data manipulation
            csv_path = report_output_path.with_suffix(".csv")
            final_report_df.to_csv(csv_path, index=False)
            print(f"✅ CSV report generated at: {csv_path}")
        except Exception as e:
            print(f"🔥 Failed to write HTML report: {e}")


def create_styled_html_report(
    df: pd.DataFrame, output_path: pathlib.Path, pre_wrap_columns: list[str] = None
):
    """
    Applies CSS styling to the results DataFrame and saves it as an HTML file.

    Args:
        df: The DataFrame to style and save
        output_path: Path where the HTML file should be saved
        pre_wrap_columns: List of column names to wrap in <pre> tags.
                         Defaults to ['expected_tool_calls', 'actual_tool_calls']
    """
    if pre_wrap_columns is None:
        pre_wrap_columns = ["expected_tool_calls", "actual_tool_calls"]

    print("🎨 Applying styles to the report...")

    # Define a function to color the 'overall_eval_status' column
    def style_status(series: pd.Series) -> list[str]:
        styles = []
        for value in series:
            if value == "PASSED":
                styles.append("background-color: #d4edda; color: #155724;")  # Green
            elif value == "FAILED":
                styles.append("background-color: #f8d7da; color: #721c24;")  # Red
            else:
                styles.append("")  # Default
        return styles

    # Define a function to wrap tool call columns in <pre> tags
    def wrap_in_pre(val):
        if pd.isna(val) or val == "":
            return val
        return f'<pre style="white-space: pre-wrap; font-family: monospace; font-size: 12px; margin: 0; padding: 4px; background-color: #f8f9fa; border-radius: 3px;">{val}</pre>'

    try:
        # Create format dictionary with numeric formatting and pre-wrap columns
        format_dict = {
            "average_tool_call_score": "{:.3f}",
            "average_response_evaluation_score": "{:.3f}",
            "tool_call_score": "{:.3f}",
            "response_evaluation_score": "{:.3f}",
            "tool_call_score_threshold": "{:.3f}",
            "response_evaluation_score_threshold": "{:.3f}",
            "time_taken_seconds": "{:.3f}",
        }

        # Add pre-wrap formatting for specified columns
        for col in pre_wrap_columns:
            if col in df.columns:
                format_dict[col] = wrap_in_pre

        # Apply styles using the .style accessor
        styled_df = (
            df.style.apply(
                style_status,
                subset=[
                    "overall_eval_status",
                    "overall_tool_eval_status",
                    "overall_response_eval_status",
                    "tool_eval_status",
                    "response_eval_status",
                ],
            )
            .format(format_dict)
            .bar(
                subset=[
                    "average_tool_call_score",
                    "average_response_evaluation_score",
                    "tool_call_score",
                    "response_evaluation_score",
                ],
                vmin=0,
                vmax=1.0,
                align="zero",
                color="#5bc0de",
            )
            .set_properties(
                **{
                    "font-family": "Helvetica, Arial, sans-serif",
                    "border": "1px solid #ddd",
                    "padding": "8px",
                }
            )
            .set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("background-color", "#f2f2f2"),
                            ("font-weight", "bold"),
                            ("text-align", "left"),
                        ],
                    },
                    {
                        "selector": "tr:nth-child(even)",
                        "props": [("background-color", "#f9f9f9")],
                    },
                    {
                        "selector": "tr:hover",
                        "props": [("background-color", "#eef5ff")],
                    },
                ]
            )
        )

        # Write the styled DataFrame to an HTML file
        styled_df.to_html(output_path, index=False, escape=False)
        print(f"✅ Styled report successfully generated at: {output_path}")

    except Exception as e:
        print(f"🔥 Failed to write styled HTML report: {e}")
        # Fallback to the unstyled version
        df.to_html(output_path, index=False, border=1)
        print(f"✅ Unstyled fallback report generated at: {output_path}")
