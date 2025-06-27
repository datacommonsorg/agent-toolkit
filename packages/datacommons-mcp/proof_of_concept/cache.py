import collections


class LruCache:
  """
  A simple implementation of an in-memory LRU cache.
  """

  def __init__(self, capacity: int):
    self.cache = collections.OrderedDict()
    self.capacity = capacity

  def get(self, key: str):
    """
    Retrieves an item from the cache and marks it as recently used.
    Returns None if the key is not found.
    """
    if key not in self.cache:
      return None
    else:
      self.cache.move_to_end(key)
      return self.cache[key]

  def put(self, key: str, value) -> None:
    """
    Adds an item to the cache. If the cache is full, the least
    recently used item is removed.
    """
    self.cache[key] = value
    self.cache.move_to_end(key)
    if len(self.cache) > self.capacity:
      self.cache.popitem(last=False) 