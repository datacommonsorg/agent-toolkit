"""
Configuration module for Data Commons clients.
Contains configuration settings for both base and custom Data Commons instances.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
DC_API_KEY = os.getenv('DC_API_KEY')
if not DC_API_KEY:
  raise ValueError("DC_API_KEY environment variable is required")

BASE_DC_CONFIG = {
    "base": {
        "api_key": DC_API_KEY,
        "sv_search_base_url": 'https://dev.datacommons.org',
        "idx": 'base_uae_mem'
    },
    "custom_dcs": []
}

CUSTOM_DC_CONFIG = {
    "base": {
        "api_key": DC_API_KEY,
        "sv_search_base_url": 'https://dev.datacommons.org',
        "idx": 'base_uae_mem'
    },
    "custom_dcs": [{
        "name": "ONE Data Commons",
        "base_url": "https://datacommons.one.org/core/api/v2/",
        "sv_search_base_url": 'https://datacommons.one.org',
        "idx": 'user_all_minilm_mem'
    }]
}

FEDERATED_DC_CONFIG = {
    "base": {
        "api_key": DC_API_KEY,
        "sv_search_base_url": 'https://dev.datacommons.org',
        "idx": 'base_uae_mem'
    },
    "custom_dcs": [{
        "name": "ONE Data Commons",
        "base_url": "https://datacommons.one.org/core/api/v2/",
        "sv_search_base_url": 'https://datacommons.one.org',
        "idx": 'user_all_minilm_mem'
    }, {
        "name": "TechSoup Data Commons",
        "base_url": "https://datacommons.techsoup.org/core/api/v2/",
        "sv_search_base_url": 'https://datacommons.techsoup.org',
        "idx": 'user_all_minilm_mem'
    }]
}
