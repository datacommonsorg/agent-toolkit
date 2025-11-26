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
from evals.evaluator.agent_evaluator import AgentEvaluator

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

import importlib
import json
import logging
import time
from collections import Counter
from typing import Any

import pandas as pd
from google.adk.agents.base_agent import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types as genai_types
from pydantic import BaseModel
from rouge_score import rouge_scorer

from evals.evaluator.agent_evaluator_models import (
    AgentTurn,
    EvaluationResultRow,
    EvaluationScore,
    ToolCall,
    load_expected_agent_turns,
)

logger = logging.getLogger("evals.evaluator." + __name__)


# Constants for default runs and evaluation criteria
NUM_RUNS = 2


def load_json(file_path: str) -> dict | list:
    """Loads a JSON file and returns its content."""
    with open(file_path) as f:
        return json.load(f)


class AgentRunner:
    """A placeholder class for running an agent."""

    def __init__(self, agent: BaseAgent) -> None:
        self.app_name = "datacommons_app"
        self.user_id = "user_1"
        self.session_id = "session_001"
        self.session_service = InMemorySessionService()
        self.session: Session | None = None
        self.runner: Runner | None = None
        self.agent = agent

    async def initialize(self) -> None:
        """Initializes the agent runner by creating a session."""
        self.session = await self.session_service.create_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.session_id,
        )

        self.runner = Runner(
            agent=self.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )

    async def run(self, query: str) -> genai_types.Content:
        """Runs the agent with the given query and returns the response content."""
        # Ensure session & runner exist
        if not self.session or not self.runner:
            raise ValueError(
                "Session and/or runner not initialized. Call initialize() first."
            )

        # Prepare the user's message in ADK format
        content = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])

        final_response_text = "Agent did not produce a final response."  # Default

        # Iterate through events to capture tool calls and final response
        tool_calls: list[genai_types.FunctionCall] = []
        async for event in self.runner.run_async(
            user_id=self.user_id, session_id=self.session_id, new_message=content
        ):
            # Filter events to only those authored by the agent
            if event.author != self.agent.name:
                continue
            tool_calls.extend(event.get_function_calls())

            # Key Concept: is_final_response() marks the concluding message for the turn.
            if event.is_final_response():
                if event.content and event.content.parts:
                    # Assuming text response in the first part
                    final_response_text = event.content.parts[0].text
                elif (
                    event.actions and event.actions.escalate
                ):  # Handle potential errors/escalations
                    final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                # Add more checks here if needed (e.g., specific error codes)
                break  # Stop processing events once the final response is found

        actual_agent_turn = AgentTurn(
            query=query,
            tool_calls=[
                ToolCall(tool_name=func.name, tool_input=func.args)
                for func in tool_calls
            ],
            reference=final_response_text,
        )
        logger.info(
            "Agent Turn Completed: %s", actual_agent_turn.model_dump_json(indent=4)
        )
        return actual_agent_turn


class AgentEvaluator:
    """An evaluator for Agents, mainly intended for helping with test cases."""

    @staticmethod
    async def evaluate_eval_set(
        agent_module: str,
        expected_agent_turns: list[AgentTurn],
        num_runs: int = NUM_RUNS,
        tool_score_threshold: float = 1.0,
        response_score_threshold: float = 0.8,
    ) -> pd.DataFrame:
        """Evaluates an agent using the given EvalSet.

        Returns a pandas DataFrame with the evaluation results.

        Args:
          agent_module: Path to the Python module from which the agent will be dynamically loaded. The system looks for and instantiates the object named `root_agent` inside this module.
          expected_agent_turns: List of AgentTurns containing the queries to execute within the session and their expected tool calls.
          num_runs: Number of times all entries in the eval dataset should be
            assessed.
          tool_score_threshold: Threshold for tool call evaluation.
          response_score_threshold: Threshold for response evaluation.
        Returns:
            A pandas DataFrame with evaluation results
        """
        # 1. Load the agent
        agent_for_eval = AgentEvaluator._get_agent_for_eval(module_name=agent_module)
        agent_runner = AgentRunner(agent=agent_for_eval)
        await agent_runner.initialize()

        # 2. Run the evaluation steps
        evaluation_result_rows: list[EvaluationResultRow] = []
        for run_index in range(num_runs):
            logger.info("Starting evaluation run %d/%d", run_index + 1, num_runs)
            for expected_agent_turn in expected_agent_turns:
                start_time = time.perf_counter()
                actual_agent_turn = await agent_runner.run(expected_agent_turn.query)
                evaluation_score = AgentEvaluator._calculate_evaluation_score(
                    expected_agent_turn=expected_agent_turn,
                    actual_agent_turn=actual_agent_turn,
                )
                took = time.perf_counter() - start_time
                evalution_result_row = EvaluationResultRow(
                    took=took,
                    expected_agent_turn=expected_agent_turn,
                    actual_agent_turn=actual_agent_turn,
                    evaluation_score=evaluation_score,
                )
                evaluation_result_rows.append(evalution_result_row)
            agent_runner.runner.close()

        return AgentEvaluator._create_results_dataframe(
            evaluation_result_rows,
            tool_score_threshold=tool_score_threshold,
            response_score_threshold=response_score_threshold,
        )

    @staticmethod
    async def evaluate(
        agent_module: str,
        eval_dataset_path: str,
        num_runs: int = NUM_RUNS,
        tool_score_threshold: float = 1.0,
        response_score_threshold: float = 0.8,
    ) -> pd.DataFrame:
        """Evaluates an Agent and returns a DataFrame of results.

        Args:
          agent_module: The path to python module that contains the agent's definition.
          eval_dataset_path: Path to a single .test.json file containing the eval dataset.
          num_runs: Number of times to assess each entry in the eval dataset.

        Returns:
            A pandas DataFrame with evaluation results
        """

        # 1. Load the expected evaluation steps
        expected_agent_turns = load_expected_agent_turns(eval_dataset_path)

        # 2. Run the evaluation & return the results DataFrame
        return await AgentEvaluator.evaluate_eval_set(
            agent_module=agent_module,
            expected_agent_turns=expected_agent_turns,
            num_runs=num_runs,
            tool_score_threshold=tool_score_threshold,
            response_score_threshold=response_score_threshold,
        )

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
    def _get_agent_for_eval(module_name: str) -> BaseAgent:
        module_path = f"{module_name}"
        agent_module = importlib.import_module(module_path)
        return agent_module.agent.root_agent

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
                "tool_call_score_threshold": tool_score_threshold,
                "response_evaluation_score_threshold": response_score_threshold,
                "run_number": None,
                # Direct data from evaluation
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
