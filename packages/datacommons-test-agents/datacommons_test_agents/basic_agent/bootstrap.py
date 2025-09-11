# Load the agent from bootstrap.py to avoid error reading the DC_API_KEY from
# the environment in unit tests
from datacommons_test_agents.basic_agent import agent  # noqa: F401
