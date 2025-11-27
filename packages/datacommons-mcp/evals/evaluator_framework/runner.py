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
Runs an ADK agent in a session.

Example usage:

runner = AgentRunner(agent)
await runner.initialize()
response = await runner.run("Hello, how are you?")
print(response)
"""

import logging

import google.genai.types as genai_types
from google.adk.agents.base_agent import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session

from evals.evaluator_framework.types import AgentTurn, ToolCall

logger = logging.getLogger("evals.evaluator_framework." + __name__)


class AgentRunner:
    """Runs an ADK agent in a session."""

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
