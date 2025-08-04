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

import collections


class LruCache:
    """
    A simple implementation of an in-memory LRU cache.
    """

    def __init__(self, capacity: int) -> None:
        self.cache = collections.OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> set[str]:
        """
        Retrieves an item from the cache and marks it as recently used.
        Returns None if the key is not found.
        """
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: set[str]) -> None:
        """
        Adds an item to the cache. If the cache is full, the least
        recently used item is removed.
        """
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
