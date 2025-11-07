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
A custom fork of the google.adk.evaluation.agent_evaluator.

This version is modified to return evaluation results as a pandas.DataFrame
instead of running assertions directly. This enables the test runner to
collect, aggregate, and generate persistent reports (e.g., HTML, CSV)
from the results.

Based off of https://github.com/google/adk-python/blob/8b3ed059c24903e8aca0a09d9d503b48af7df850/src/google/adk/evaluation/agent_evaluator.py
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import statistics
import time

import pandas as pd
from google.adk.agents.base_agent import BaseAgent
from google.adk.evaluation.constants import MISSING_EVAL_DEPENDENCIES_MESSAGE
from google.adk.evaluation.eval_case import IntermediateData, Invocation
from google.adk.evaluation.eval_metrics import (
    EvalMetric,
    EvalMetricResult,
    PrebuiltMetrics,
)
from google.adk.evaluation.eval_result import EvalCaseResult
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_sets_manager import EvalSetsManager
from google.adk.evaluation.in_memory_eval_sets_manager import InMemoryEvalSetsManager
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.utils.context_utils import Aclosing
from google.genai import types as genai_types
from pydantic import BaseModel
from rouge_score import rouge_scorer

from evals.evaluator.agent_evaluator_models import (
    EvaluationStep,
    ToolCall,
    load_evaluation_set,
)

logger = logging.getLogger("evals.evaluator." + __name__)


# Constants for default runs and evaluation criteria
NUM_RUNS = 2

TOOL_TRAJECTORY_SCORE_KEY = PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE.value
# This evaluation is not very stable.
# This is always optional unless explicitly specified.
RESPONSE_EVALUATION_SCORE_KEY = PrebuiltMetrics.RESPONSE_EVALUATION_SCORE.value
RESPONSE_MATCH_SCORE_KEY = PrebuiltMetrics.RESPONSE_MATCH_SCORE.value
SAFETY_V1_KEY = PrebuiltMetrics.SAFETY_V1.value

ALLOWED_CRITERIA = [
    TOOL_TRAJECTORY_SCORE_KEY,
    RESPONSE_EVALUATION_SCORE_KEY,
    RESPONSE_MATCH_SCORE_KEY,
    SAFETY_V1_KEY,
]

QUERY_COLUMN = "query"
REFERENCE_COLUMN = "reference"
EXPECTED_TOOL_USE_COLUMN = "expected_tool_use"


DEFAULT_CRITERIA = {
    TOOL_TRAJECTORY_SCORE_KEY: 1.0,  # 1-point scale; 1.0 is perfect.
    RESPONSE_MATCH_SCORE_KEY: 0.8,  # Rouge-1 text match; 0.8 is default.
}


def load_json(file_path: str) -> dict | list:
    with open(file_path) as f:
        return json.load(f)


class _EvalMetricResultWithInvocation(BaseModel):
    """EvalMetricResult along with both actual and expected invocation.

    This is class is intentionally marked as private and is created for
    convenience.
    """

    actual_invocation: Invocation
    expected_invocation: Invocation
    eval_metric_result: EvalMetricResult


class EvaluationScore(BaseModel):
    """Holds evaluation scores for different aspects of the agent's performance."""

    tool_call_score: float | None
    response_evaluation_score: float | None


class EvaluationResultRow(BaseModel):
    """Represents a single row in the evaluation results DataFrame."""

    took: float  # Time taken in seconds
    expected_evaluation_step: EvaluationStep
    actual_evaluation_step: EvaluationStep
    evaluation_score: EvaluationScore


class AgentTurn(BaseModel):
    """Represents a single turn in an agent conversation."""

    user_input: str
    agent_response: str
    tool_calls: list[genai_types.FunctionCall]


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
        agent_turn = AgentTurn(
            user_input=query,
            agent_response=final_response_text,
            tool_calls=tool_calls,
        )
        logger.info("Agent Turn Completed: %s", agent_turn.model_dump_json(indent=4))
        return agent_turn


class AgentEvaluator:
    """An evaluator for Agents, mainly intended for helping with test cases."""

    @staticmethod
    def find_config_for_test_file(test_file: str) -> dict[str, float]:
        """Find the test_config.json file in the same folder as the test file."""
        test_folder = os.path.dirname(test_file)
        config_path = os.path.join(test_folder, "test_config.json")
        if os.path.exists(config_path):
            config_data = load_json(config_path)
            if "criteria" in config_data and isinstance(config_data["criteria"], dict):
                return config_data["criteria"]
            raise ValueError(
                f"Invalid format for test_config.json at {config_path}. Expected a"
                " 'criteria' dictionary."
            )
        return DEFAULT_CRITERIA

    @staticmethod
    async def evaluate_eval_set(
        agent_module: str,
        evaluation_steps: list[EvaluationStep],
        criteria: dict[str, float],
        num_runs: int = NUM_RUNS,
    ) -> pd.DataFrame:
        """Evaluates an agent using the given EvalSet.

        Returns a pandas DataFrame with the evaluation results.

        Args:
          agent_module: The path to python module that contains the definition of
            the agent. There is convention in place here, where the code is going to
            look for 'root_agent' in the loaded module.
          eval_set: The eval set.
          criteria: Evauation criterias, a dictionary of metric names to their
            respective thresholds.
          num_runs: Number of times all entries in the eval dataset should be
            assessed.
        """
        # 1. Load the agent
        agent_for_eval = AgentEvaluator._get_agent_for_eval(module_name=agent_module)
        agent_runner = AgentRunner(agent=agent_for_eval)
        await agent_runner.initialize()
        print("!!!! WOOF")
        print("evaluation_steps=", evaluation_steps)

        # 2. Run the evaluation steps
        evaluation_result_rows: list[EvaluationResultRow] = []
        for step in evaluation_steps:
            start_time = time.perf_counter
            agent_turn = await agent_runner.run(step.query)
            actual_evaluation_step = AgentEvaluator._agent_turn_to_evaluation_step(
                agent_turn
            )
            print("!!!!!!!!!!! step=", step)
            print("!!!!!!!!!! agent_turn=", agent_turn)
            print("!!!!!!!!!! actual_evaluation_step=", actual_evaluation_step)
            evaluation_score = AgentEvaluator._calculate_evaluation_score(
                expected_evaluation_step=step,
                actual_evaluation_step=actual_evaluation_step,
            )
            took = time.perf_counter() - start_time()
            evalution_result_row = EvaluationResultRow(
                took=took,
                expected_evaluation_step=step,
                actual_evaluation_step=actual_evaluation_step,
                evaluation_score=evaluation_score,
            )
            evaluation_result_rows.append(evalution_result_row)

        agent_runner.runner.close()

        """
        if False:
            eval_metrics = [
                EvalMetric(metric_name=n, threshold=t) for n, t in criteria.items()
            ]

            # Step 1: Perform evals, basically inferencing and evaluation of metrics
            eval_results_by_eval_id = await AgentEvaluator._get_eval_results_by_eval_id(
                agent_for_eval=agent_for_eval,
                eval_set=eval_set,
                eval_metrics=eval_metrics,
                num_runs=num_runs,
            )

            # Step 2: Post-process the results
            for eval_results_per_eval_id in eval_results_by_eval_id.values():
                eval_metric_results = (
                    AgentEvaluator._get_eval_metric_results_with_invocation(
                        eval_results_per_eval_id
                    )
                )

        df = pd.DataFrame()
        return df
        """

        return AgentEvaluator._create_results_dataframe(
            evaluation_result_rows, num_runs
        )

    @staticmethod
    async def evaluate(
        agent_module: str,
        eval_dataset_path: str,
        num_runs: int = NUM_RUNS,
    ) -> pd.DataFrame:
        """Evaluates an Agent and returns a DataFrame of results.

        Args:
          agent_module: The path to python module that contains the agent's definition.
          eval_dataset_file_path_or_dir: Path to a single .test.json file or a
            directory to be explored for all .test.json files.
          num_runs: Number of times to assess each entry in the eval dataset.
          agent_name: The name of the agent.
          initial_session_file: File with initial session state for all evals.

        Returns:
            A pandas DataFrame with evaluation results
        """

        # 1. Gather all test files from the given path
        criteria = AgentEvaluator.find_config_for_test_file(eval_dataset_path)
        evaluation_steps = load_evaluation_set(eval_dataset_path)
        print("!!!!! evaluation_steps=", evaluation_steps)

        # 2. Capture the DataFrame returned by `evaluate_eval_set`
        return await AgentEvaluator.evaluate_eval_set(
            agent_module=agent_module,
            evaluation_steps=evaluation_steps,
            criteria=criteria,
            num_runs=num_runs,
        )

    @staticmethod
    def _calculate_evaluation_score(
        expected_evaluation_step: EvaluationStep,
        actual_evaluation_step: EvaluationStep,
    ) -> EvaluationScore:
        """Calculates the evaluation result based on expected and actual turns."""
        # Placeholder logic for calculating scores
        tool_call_score = 1.0  # Assume perfect score for tool calls

        response_evaluation_score = AgentEvaluator._calculate_rouge_1_fmeasure_score(
            expected=expected_evaluation_step.reference,
            actual=actual_evaluation_step.reference,
        )

        return EvaluationScore(
            tool_call_score=tool_call_score,
            response_evaluation_score=response_evaluation_score,
        )

    @staticmethod
    def _convert_content_to_text(content: genai_types.Content | None) -> str:
        if content and content.parts:
            return "\n".join([p.text for p in content.parts if p.text])

        return ""

    @staticmethod
    def _convert_tool_calls_to_text(
        intermediate_data: IntermediateData | None,
    ) -> str:
        if intermediate_data and intermediate_data.tool_uses:
            formatted_tools = [
                f"Tool: {tool.name}\nArgs: {tool.args}"
                for tool in intermediate_data.tool_uses
            ]

            return "\n\n".join(formatted_tools)

        return ""

    @staticmethod
    def _get_agent_for_eval(module_name: str) -> BaseAgent:
        module_path = f"{module_name}"
        agent_module = importlib.import_module(module_path)
        return agent_module.agent.root_agent

    @staticmethod
    def _get_eval_sets_manager(app_name: str, eval_set: EvalSet) -> EvalSetsManager:
        eval_sets_manager = InMemoryEvalSetsManager()

        eval_sets_manager.create_eval_set(
            app_name=app_name, eval_set_id=eval_set.eval_set_id
        )
        for eval_case in eval_set.eval_cases:
            eval_sets_manager.add_eval_case(
                app_name=app_name,
                eval_set_id=eval_set.eval_set_id,
                eval_case=eval_case,
            )

        return eval_sets_manager

    @staticmethod
    async def _get_eval_results_by_eval_id(
        agent_for_eval: BaseAgent,
        eval_set: EvalSet,
        eval_metrics: list[EvalMetric],
        num_runs: int,
    ) -> dict[str, list[EvalCaseResult]]:
        """Returns EvalCaseResults grouped by eval case id.

        The grouping happens because of the "num_runs" argument, where for any value
        greater than 1, we would have generated inferences num_runs times and so
        by extension we would have evaluated metrics on each of those inferences.
        """
        try:
            from google.adk.evaluation.base_eval_service import (
                EvaluateConfig,
                EvaluateRequest,
                InferenceConfig,
                InferenceRequest,
            )
            from google.adk.evaluation.local_eval_service import LocalEvalService
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(MISSING_EVAL_DEPENDENCIES_MESSAGE) from e

        # It is okay to pick up this dummy name.
        app_name = "test_app"
        eval_service = LocalEvalService(
            root_agent=agent_for_eval,
            eval_sets_manager=AgentEvaluator._get_eval_sets_manager(
                app_name=app_name, eval_set=eval_set
            ),
        )

        inference_requests = [
            InferenceRequest(
                app_name=app_name,
                eval_set_id=eval_set.eval_set_id,
                inference_config=InferenceConfig(),
            )
        ] * num_runs  # Repeat inference request num_runs times.

        # Generate inferences
        inference_results = []
        for inference_request in inference_requests:
            async with Aclosing(
                eval_service.perform_inference(inference_request=inference_request)
            ) as agen:
                async for inference_result in agen:
                    inference_results.extend([inference_result])

        # Evaluate metrics
        # As we perform more than one run for an eval case, we collect eval results
        # by eval id.
        eval_results_by_eval_id: dict[str, list[EvalCaseResult]] = {}
        evaluate_request = EvaluateRequest(
            inference_results=inference_results,
            evaluate_config=EvaluateConfig(eval_metrics=eval_metrics),
        )
        async with Aclosing(
            eval_service.evaluate(evaluate_request=evaluate_request)
        ) as agen:
            async for eval_result in agen:
                eval_id = eval_result.eval_id
                if eval_id not in eval_results_by_eval_id:
                    eval_results_by_eval_id[eval_id] = []

                eval_results_by_eval_id[eval_id].append(eval_result)

        return eval_results_by_eval_id

    @staticmethod
    def _get_eval_metric_results_with_invocation(
        eval_results_per_eval_id: list[EvalCaseResult],
    ) -> dict[str, list[_EvalMetricResultWithInvocation]]:
        """Returns _EvalMetricResultWithInvocation grouped by metric.

        EvalCaseResult contain results for each metric per invocation.

        This method flips it around and returns a structure that groups metric
        results per invocation by eval metric.

        This is a convenience function.
        """
        eval_metric_results: dict[str, list[_EvalMetricResultWithInvocation]] = {}

        # Go over the EvalCaseResult one by one, do note that at this stage all
        # EvalCaseResult belong to the same eval id.
        for eval_case_result in eval_results_per_eval_id:
            # For the given eval_case_result, we go over metric results for each
            # invocation. Do note that a single eval case can have more than one
            # invocation and for each invocation there could be more than on eval
            # metrics that were evaluated.
            for (
                eval_metrics_per_invocation
            ) in eval_case_result.eval_metric_result_per_invocation:
                # Go over each eval_metric_result for an invocation.
                for (
                    eval_metric_result
                ) in eval_metrics_per_invocation.eval_metric_results:
                    metric_name = eval_metric_result.metric_name
                    if metric_name not in eval_metric_results:
                        eval_metric_results[metric_name] = []

                    actual_invocation = eval_metrics_per_invocation.actual_invocation
                    expected_invocation = (
                        eval_metrics_per_invocation.expected_invocation
                    )

                    eval_metric_results[metric_name].append(
                        _EvalMetricResultWithInvocation(
                            actual_invocation=actual_invocation,
                            expected_invocation=expected_invocation,
                            eval_metric_result=eval_metric_result,
                        )
                    )
        return eval_metric_results

    @staticmethod
    def _create_results_dataframe(
        evaluation_result_rows: list[EvaluationResultRow],
        tool_score_threshold: float = 1.0,
        response_score_threshold: float = 0.8,
        num_runs: int = NUM_RUNS,
    ) -> pd.DataFrame:
        """
        Processes evaluation results into a pandas DataFrame.

        Returns:
            A pandas DataFrame containing detailed results for each invocation,
            augmented with the average score and overall status for its corresponding metric.
        """
        all_results_data = []
        for evaluation_result_row in evaluation_result_rows:
            # todo: calculate average score
            # if scores:
            #    average_score = statistics.mean(scores)
            #    # Use .value if EvalStatus is an Enum
            #    overall_eval_status = (
            #        "PASSED" if average_score >= threshold else "FAILED"
            #    )
            # else:
            #    average_score = None  # Or float('nan')
            #    overall_eval_status = "NOT_EVALUATED"

            # Use .value for enums to get the string representation
            tool_eval_status = (
                "PASSED"
                if (
                    evaluation_result_row.evaluation_score.tool_call_score is not None
                    and evaluation_result_row.evaluation_score.tool_call_score
                    >= tool_score_threshold
                )
                else "FAILED"
            )

            response_eval_status = (
                "PASSED"
                if (
                    evaluation_result_row.evaluation_score.response_evaluation_score
                    is not None
                    and evaluation_result_row.evaluation_score.response_evaluation_score
                    >= response_score_threshold
                )
                else "FAILED"
            )

            overall_eval_status = (
                "PASSED"
                if tool_eval_status == "PASSED" and response_eval_status == "PASSED"
                else "FAILED"
            )

            all_results_data.append(
                {
                    "overall_eval_status": overall_eval_status,
                    "tool_eval_status": tool_eval_status,
                    "tool_call_score": evaluation_result_row.evaluation_score.tool_call_score,
                    "response_eval_status": response_eval_status,
                    "response_evaluation_score": evaluation_result_row.evaluation_score.response_evaluation_score,
                    "time_taken_seconds": evaluation_result_row.took,
                    # "average_score": average_score,
                    # "line_score": per_invocation_result.eval_metric_result.score,
                    # "threshold": threshold,
                    # "invocation_number": (invocation_idx + 1) % num_runs,
                    "prompt": evaluation_result_row.expected_evaluation_step.query,
                    "expected_response": evaluation_result_row.expected_evaluation_step.reference,
                    "actual_response": evaluation_result_row.actual_evaluation_step.reference,
                    "expected_tool_calls": json.dumps(
                        [
                            o.model_dump()
                            for o in evaluation_result_row.expected_evaluation_step.tool_calls
                        ],
                        indent=2,
                    ),
                    "actual_tool_calls": json.dumps(
                        [
                            o.model_dump()
                            for o in evaluation_result_row.actual_evaluation_step.tool_calls
                        ],
                        indent=2,
                    ),
                }
            )

        if not all_results_data:
            return pd.DataFrame()  # Return an empty DataFrame if no results

        # 4. Create the final DataFrame and return it
        return pd.DataFrame(all_results_data)

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

    @staticmethod
    def _agent_turn_to_evaluation_step(agent_turn: AgentTurn) -> EvaluationStep:
        """Converts an AgentTurn to an EvaluationStep."""
        return EvaluationStep(
            query=agent_turn.user_input,
            tool_calls=[
                ToolCall(tool_name=func.name, tool_input=func.args)
                for func in agent_turn.tool_calls
            ],
            reference=agent_turn.agent_response,
        )
