import pathlib

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator

parent_path = pathlib.Path(__file__).parent


@pytest.mark.asyncio
async def test_basic_agent() -> None:
    """Test the agent's basic ability via a session file."""
    await AgentEvaluator.evaluate(
        agent_module="datacommons_test_agents.basic_agent.bootstrap",
        eval_dataset_file_path_or_dir=str(parent_path / "data"),
        num_runs=2,
    )
