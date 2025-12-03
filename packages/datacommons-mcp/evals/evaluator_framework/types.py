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
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

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


class ReportColumnTag(str, Enum):
    """
    Used to apply styles to html cells for the given value in the DataFrame.
    """

    STYLE = "style"  # Applies a style tag (or render logic) to the html cell.
    FORMATTED_STRING = "formatted_string"  # Formats numerical value with a given format string (F-string).


class ReportStyleType(str, Enum):
    """Formatting values for the ColumnTag.STYLE ('style') tag."""

    STATUS = "status"  # CSS: Green/Red background depending on value
    SCORE = "score"  # CSS: Blue data bar with width based on float value from 0 to 1.0
    PREFORMATTED = "preformatted"  # HTML: <pre> tag wrapping


class ReportStyleMixin:
    """
    Mixin to select column styles and formatting for a report.
    """

    @classmethod
    def get_columns_by_style(cls, style_type: ReportStyleType) -> list[str]:
        """Specific helper to get columns for a specific style enum."""
        return [
            name
            for name, field in cls.model_fields.items()
            if field.json_schema_extra
            and field.json_schema_extra.get(ReportColumnTag.STYLE) == style_type
        ]

    @classmethod
    def get_format_map(cls) -> dict[str, str]:
        """Returns a dict of {column_name: format_string} for Pandas styling."""
        result = {}
        for name, field in cls.model_fields.items():
            if field.json_schema_extra:
                val = field.json_schema_extra.get(ReportColumnTag.FORMATTED_STRING)
                if val:
                    result[name] = val
        return result


# Metric scores are styled with a score bar and formatted to 3 decimal places.
MetricScore = Annotated[
    float | None,
    Field(
        json_schema_extra={
            ReportColumnTag.STYLE: ReportStyleType.SCORE,
            ReportColumnTag.FORMATTED_STRING: "{:.3f}",
        }
    ),
]

# Float values are formatted to 3 decimal places.
FormattedFloat = Annotated[
    float | None, Field(json_schema_extra={ReportColumnTag.FORMATTED_STRING: "{:.3f}"})
]

# A string representing a pass/fail status, styled in green for "pass" and red for "fail".
StatusLabel = Annotated[
    str | None, Field(json_schema_extra={ReportColumnTag.STYLE: ReportStyleType.STATUS})
]

# Large text blobs that need <pre> wrapping in HTML
PreformattedText = Annotated[
    str, Field(json_schema_extra={ReportColumnTag.STYLE: ReportStyleType.PREFORMATTED})
]


class EvaluationDataFrameRow(ReportStyleMixin, BaseModel):
    """
    Represents a single row in the evaluation results DataFrame.

    This model is used to structure the data before it is converted to a pandas DataFrame.
    Fields with default values are calculated after the initial creation of the DataFrame.
    """

    # Status fields
    overall_eval_status: StatusLabel = None
    overall_tool_eval_status: StatusLabel = None
    tool_eval_status: StatusLabel = None
    overall_response_eval_status: StatusLabel = None
    response_eval_status: StatusLabel = None

    # Score fields
    average_tool_call_score: MetricScore = None
    average_response_evaluation_score: MetricScore = None
    run_number: int | None = None

    # Threshold fields
    tool_call_score_threshold: FormattedFloat = None
    response_evaluation_score_threshold: FormattedFloat = None

    # Direct data from evaluation
    tool_call_score: MetricScore = None
    response_evaluation_score: MetricScore = None
    time_taken_seconds: FormattedFloat = None
    prompt: str
    expected_response: str
    actual_response: str
    expected_tool_calls: PreformattedText
    actual_tool_calls: PreformattedText


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
