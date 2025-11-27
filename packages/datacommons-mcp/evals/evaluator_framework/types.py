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
types.py

Defines Pydantic models for structuring and validating
agent evaluation examples, including expected tool use.

"""

import json
import logging
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

logger = logging.getLogger("evals.evaluator_framework." + __name__)

# --- Model Definitions ---


class ToolCall(BaseModel):
    """
    Describes a single tool call by the agent.

    Attributes:
        tool_name: The name of the tool that should be called.
        tool_input: A dictionary of arguments passed to the tool.
                    Using dict[str, Any] for flexibility.
    """

    tool_name: str
    tool_input: dict[str, Any]


class ExpectedEvaluationStep(BaseModel):
    """
    Input format used for loading evaluation sets.

    Describes the expected behavior of the agent for a single query.

    Attributes:
        query: The user's input query string.
        expected_tool_use: A list of `ToolCall` models representing
                           the sequence of tools the agent is expected to use.
        reference: A ground-truth reference string for the final answer.
    """

    query: str
    expected_tool_use: list[ToolCall]
    reference: str


class AgentTurn(BaseModel):
    """
    Describes a single query-response evaluation example.

    Attributes:
        query: The user's input query string.
        tool_calls: A list of `ToolCall` models representing
                           the sequence of tools the agent should use.
        reference: A ground-truth reference string for the final answer.
    """

    query: str
    tool_calls: list[ToolCall]
    reference: str


class EvaluationScore(BaseModel):
    """Holds evaluation scores for different aspects of the agent's performance."""

    tool_call_score: float | None
    response_evaluation_score: float | None


class EvaluationResultRow(BaseModel):
    """Represents a single row in the evaluation results DataFrame."""

    took: float  # Time taken in seconds
    expected_agent_turn: AgentTurn
    actual_agent_turn: AgentTurn
    evaluation_score: EvaluationScore


class EvaluationDataFrameRow(BaseModel):
    """
    Represents a single row in the evaluation results DataFrame.

    This model is used to structure the data before it is converted to a pandas DataFrame.
    Fields with default values are calculated after the initial creation of the DataFrame.
    """

    # Status fields
    overall_eval_status: str | None = None
    overall_tool_eval_status: str | None = None
    tool_eval_status: str | None = None
    overall_response_eval_status: str | None = None
    response_eval_status: str | None = None

    # Score fields
    average_tool_call_score: float | None = None
    average_response_evaluation_score: float | None = None
    run_number: int | None = None

    # Threshold fields
    tool_call_score_threshold: float
    response_evaluation_score_threshold: float

    # Direct data from evaluation
    tool_call_score: float | None
    response_evaluation_score: float | None
    time_taken_seconds: float
    prompt: str
    expected_response: str
    actual_response: str
    expected_tool_calls: str  # JSON string
    actual_tool_calls: str  # JSON string


def load_expected_agent_turns(file_path: str) -> list[AgentTurn]:
    """
    Loads and validates an evaluation set from a JSON file.
    """
    adapter = TypeAdapter(list[ExpectedEvaluationStep])
    logger.info("Loading evaluation set from: %s", file_path)
    with open(file_path) as f:
        try:
            data = json.load(f)
            expected_evaluation_steps = adapter.validate_python(data)
            return [
                AgentTurn(
                    query=step.query,
                    tool_calls=step.expected_tool_use,
                    reference=step.reference,
                )
                for step in expected_evaluation_steps
            ]
        except FileNotFoundError:
            logger.error("Error: File not found at %s", file_path)
            return []
        except json.JSONDecodeError:
            logger.error(
                "Error: Failed to decode JSON. Check for syntax errors in %s", file_path
            )
            return []
        except ValidationError as e:
            logger.error("Error: Data in %s failed validation:\n%s", file_path, e)
            return []
