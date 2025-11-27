# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Agent Evaluator for the Google Agent Development Kit (ADK) Framework.

Given a set of evaluation cases, calculates metrics for tool calls and responses
across multiple runs.

Executes the evaluation and returns a `pandas.DataFrame` containing results,
scores (e.g., Jaccard, ROUGE-1), and overall status.

Usage:

```python
import asyncio
import pandas as pd
from evals.evaluator_framework.evaluator import AgentEvaluator

async def run_evaluation() -> pd.DataFrame:
    results_df = await AgentEvaluator.evaluate(
        agent_module="my_app.my_agent_module",
        eval_dataset_path="/data/general_adk_eval_set.json",
        num_runs=3,
    )
    return results_df
```
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from typing import Any

import pathlib
import pandas as pd
from google.adk.agents.base_agent import BaseAgent
from pydantic import BaseModel
from rouge_score import rouge_scorer

from evals.evaluator_framework.runner import AgentRunner
from evals.evaluator_framework.types import (
    AgentTurn,
    EvaluationDataFrameRow,
    EvaluationResultRow,
    EvaluationScore,
    load_expected_agent_turns,
)

logger = logging.getLogger("evals.evaluator_framework." + __name__)


# Constants for default runs and evaluation criteria
NUM_RUNS = 2


class AgentEvaluator:
    """An evaluator for Agents intended for helping with test cases."""

    @staticmethod
    async def evaluate(
        agent: BaseAgent,
        eval_dataset_path: str,
        num_runs: int = NUM_RUNS,
        tool_score_threshold: float = 1.0,
        response_score_threshold: float = 0.8,
    ) -> pd.DataFrame:
        """Evaluates an Agent and returns a DataFrame of results.

        Args:
          agent: The agent to evaluate.
          eval_dataset_path: Path to a single .test.json file containing the eval dataset.
          num_runs: Number of times to assess each entry in the eval dataset.

        Returns:
            A pandas DataFrame with evaluation results
        """

        # 1. Load the expected evaluation steps
        expected_agent_turns = load_expected_agent_turns(eval_dataset_path)

        # 2. Prepare evaluation tasks
        tasks = [
            AgentEvaluator._evaluate_run(
                agent=agent,
                expected_agent_turns=expected_agent_turns,
                run_index=run_index,
                num_runs=num_runs,
            )
            for run_index in range(num_runs)
        ]

        # 3. Run all evaluation runs in parallel
        logger.info(
            "Starting %d evaluation runs in parallel",
            len(tasks),
        )
        results_nested = await asyncio.gather(*tasks)
        # Flatten the list of lists
        evaluation_result_rows = [
            item for sublist in results_nested for item in sublist
        ]

        # 4. Return the evaluation results
        return AgentEvaluator._create_results_dataframe(
            evaluation_result_rows,
            tool_score_threshold=tool_score_threshold,
            response_score_threshold=response_score_threshold,
        )

    @staticmethod
    async def _evaluate_run(
        agent: BaseAgent,
        expected_agent_turns: list[AgentTurn],
        run_index: int,
        num_runs: int,
    ) -> list[EvaluationResultRow]:
        """Evaluates a single run (sequence of turns) for an agent."""
        # Initialize a new agent runner for this run to ensure isolation from other runs
        # but continuity within this run.
        agent_runner = AgentRunner(agent=agent)
        await agent_runner.initialize()

        results = []
        for turn_index, expected_agent_turn in enumerate(expected_agent_turns):
            logger.info(
                "Starting evaluation turn %d/%d (Run %d/%d) for query: %s",
                turn_index + 1,
                len(expected_agent_turns),
                run_index + 1,
                num_runs,
                expected_agent_turn.query[:50] + "..."
                if len(expected_agent_turn.query) > 50
                else expected_agent_turn.query,
            )

            start_time = time.perf_counter()
            actual_agent_turn = await agent_runner.run(expected_agent_turn.query)
            took = time.perf_counter() - start_time

            evaluation_score = AgentEvaluator._calculate_evaluation_score(
                expected_agent_turn=expected_agent_turn,
                actual_agent_turn=actual_agent_turn,
            )

            results.append(
                EvaluationResultRow(
                    took=took,
                    expected_agent_turn=expected_agent_turn,
                    actual_agent_turn=actual_agent_turn,
                    evaluation_score=evaluation_score,
                )
            )
        return results

    @staticmethod
    def create_styled_html_report(
        df: pd.DataFrame, output_path: pathlib.Path, pre_wrap_columns: list[str] = None
    ) -> None:
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

    @staticmethod
    def _calculate_evaluation_score(
        expected_agent_turn: AgentTurn,
        actual_agent_turn: AgentTurn,
    ) -> EvaluationScore:
        """Calculates the evaluation result based on expected and actual turns."""
        # Placeholder logic for calculating scores
        tool_call_score = AgentEvaluator.calculate_jaccard_similarity(
            expected=expected_agent_turn.tool_calls,
            actual=actual_agent_turn.tool_calls,
        )

        response_evaluation_score = AgentEvaluator._calculate_rouge_1_fmeasure_score(
            expected=expected_agent_turn.reference,
            actual=actual_agent_turn.reference,
        )

        return EvaluationScore(
            tool_call_score=tool_call_score,
            response_evaluation_score=response_evaluation_score,
        )

    @staticmethod
    def _create_results_dataframe(
        evaluation_result_rows: list[EvaluationResultRow],
        tool_score_threshold: float = 1.0,
        response_score_threshold: float = 0.8,
    ) -> pd.DataFrame:
        """
        Processes evaluation results into a pandas DataFrame.

        Returns:
            A pandas DataFrame containing detailed results for each invocation,
            augmented with the average score and overall status for its corresponding metric.
        """
        all_results_data = [
            {
                # Initialize statuses as None, we will calculate them after grouping
                "overall_eval_status": None,
                "overall_tool_eval_status": None,
                "tool_eval_status": None,
                "overall_response_eval_status": None,
                "response_eval_status": None,
                # Initialize scores & run_number as None, we will calculate them after grouping
                "average_tool_call_score": None,
                "average_response_evaluation_score": None,
                "run_number": None,
                # Direct data from evaluation
                "tool_call_score_threshold": tool_score_threshold,
                "response_evaluation_score_threshold": response_score_threshold,
                "tool_call_score": evaluation_result_row.evaluation_score.tool_call_score,
                "response_evaluation_score": evaluation_result_row.evaluation_score.response_evaluation_score,
                "time_taken_seconds": evaluation_result_row.took,
                "prompt": evaluation_result_row.expected_agent_turn.query,
                "expected_response": evaluation_result_row.expected_agent_turn.reference,
                "actual_response": evaluation_result_row.actual_agent_turn.reference,
                "expected_tool_calls": json.dumps(
                    [
                        o.model_dump()
                        for o in evaluation_result_row.expected_agent_turn.tool_calls
                    ],
                    indent=2,
                ),
                "actual_tool_calls": json.dumps(
                    [
                        o.model_dump()
                        for o in evaluation_result_row.actual_agent_turn.tool_calls
                    ],
                    indent=2,
                ),
            }
            for evaluation_result_row in evaluation_result_rows
        ]

        df = pd.DataFrame(all_results_data)

        # Calculate Group Averages
        # transform('mean') calculates the mean for the group and assigns it to every row in that group
        df["average_tool_call_score"] = df.groupby("prompt")[
            "tool_call_score"
        ].transform("mean")
        df["average_response_evaluation_score"] = df.groupby("prompt")[
            "response_evaluation_score"
        ].transform("mean")

        # Calculate Statuses based on the AVERAGES
        # Uses the logic: "PASSED" if average_score >= threshold else "FAILED"

        # Calculate Tool Status
        df["overall_tool_eval_status"] = df["average_tool_call_score"].apply(
            lambda x: "PASSED"
            if x is not None and x >= tool_score_threshold
            else "FAILED"
        )

        # Calculate Overall Response Status
        df["overall_response_eval_status"] = df[
            "average_response_evaluation_score"
        ].apply(
            lambda x: "PASSED"
            if x is not None and x >= response_score_threshold
            else "FAILED"
        )

        # Calculate Overall Status (PASSED only if both Tool and Response passed)
        df["overall_eval_status"] = df.apply(
            lambda row: "PASSED"
            if row["overall_tool_eval_status"] == "PASSED"
            and row["overall_response_eval_status"] == "PASSED"
            else "FAILED",
            axis=1,
        )

        # Calculate Individual Invocation Statuses
        df["tool_eval_status"] = df.apply(
            lambda row: "PASSED"
            if row["tool_call_score"] is not None
            and row["tool_call_score"] >= tool_score_threshold
            else "FAILED",
            axis=1,
        )
        df["response_eval_status"] = df.apply(
            lambda row: "PASSED"
            if row["response_evaluation_score"] is not None
            and row["response_evaluation_score"] >= response_score_threshold
            else "FAILED",
            axis=1,
        )

        # Calculate Run Number
        # cumcount() numbers the items in each group starting from 0 based on their original order
        df["run_number"] = df.groupby("prompt").cumcount()

        # Validate the final DataFrame against the Pydantic model
        # This ensures that all expected columns are present and have correct types
        # We convert to dict and replace NaN with None for Pydantic compatibility
        for row in df.where(pd.notnull(df), None).to_dict(orient="records"):
            EvaluationDataFrameRow.model_validate(row)

        return df

    @staticmethod
    def _freeze(obj: Any) -> Any:  # noqa: ANN401
        """
        Recursively freezes Pydantic models, dicts, and lists into hashable types.

        Handles:
        1. Pydantic Models: Converts to dict via model_dump(), then recurses.
        2. Dicts: Converts to frozenset (key-order independent).
        3. Lists: Converts to tuple.
        """
        if isinstance(obj, BaseModel):
            return AgentEvaluator._freeze(obj.model_dump())
        if isinstance(obj, dict):
            return frozenset((k, AgentEvaluator._freeze(v)) for k, v in obj.items())
        if isinstance(obj, list):
            return tuple(AgentEvaluator._freeze(x) for x in obj)
        return obj

    @staticmethod
    def calculate_jaccard_similarity(
        expected: list[BaseModel], actual: list[BaseModel]
    ) -> float:
        """
        Calculates Generalized Jaccard Similarity for a list of Pydantic models.

        Formula: J(A, B) = |A ∩ B| / |A ∪ B|

        The implementation leverages Pydantic's model_dump() for structural
        normalization, ensuring that nested models (like ToolCall) are compared
        by value, not by reference.

        Args:
            expected: List of ground-truth Pydantic models.
            actual: List of generated Pydantic models.

        Returns:
            float: 0.0 to 1.0 representing the similarity score.
        """
        if not expected and not actual:
            return 1.0

        # 1. Transform to hashable multisets
        c_expected = Counter(AgentEvaluator._freeze(x) for x in expected)
        c_actual = Counter(AgentEvaluator._freeze(x) for x in actual)

        # 2. Intersection (min counts) & Union (max counts)
        intersection = c_expected & c_actual
        union = c_expected | c_actual

        # 3. Score
        denominator = sum(union.values())
        return sum(intersection.values()) / denominator if denominator else 0.0

    @staticmethod
    def _calculate_rouge_1_fmeasure_score(expected: str, actual: str) -> float:
        """Calculates the ROUGE-1 f-measure score between a candidate and reference text.

        ROUGE-1 measures the overlap of unigrams (single words) between the
        candidate and reference texts. The score is broken down into:
        - Precision: The proportion of unigrams in the candidate that are also in the
        reference.
        - Recall: The proportion of unigrams in the reference that are also in the
        candidate.
        - F-measure: The harmonic mean of precision and recall.

        Args:
            candidate: The generated text to be evaluated.
            reference: The ground-truth text to compare against.

        Returns:
            The f-measure ROUGE-1 score as a float between 0 and 1.
        """
        scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)

        # The score method returns a dictionary where keys are the ROUGE types
        # and values are Score objects (tuples) with precision, recall, and fmeasure.
        scores = scorer.score(expected, actual)

        return scores["rouge1"].fmeasure
