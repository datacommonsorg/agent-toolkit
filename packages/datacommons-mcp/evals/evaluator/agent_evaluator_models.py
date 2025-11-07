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
agent_evaluator_models.py

Defines Pydantic models for structuring and validating
agent evaluation examples, including expected tool use.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

logger = logging.getLogger("evals.evaluator." + __name__)

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


class EvaluationStep(BaseModel):
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


def load_evaluation_set(file_path: str) -> list[EvaluationStep]:
    """
    Loads and validates an evaluation set from a JSON file.
    """
    adapter = TypeAdapter(list[EvaluationStep])
    logger.info("Loading evaluation set from: %s", file_path)
    with open(file_path) as f:
        try:
            data = json.load(f)
            return adapter.validate_python(data)
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
