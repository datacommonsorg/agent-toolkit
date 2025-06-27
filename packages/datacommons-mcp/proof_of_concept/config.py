# Copyright 2025 Google LLC.
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
