class MockRedis:
    def __init__(self):
        self.store = {}
    async def get(self, key):
        return self.store.get(key)
    async def setex(self, key, time, value):
        self.store[key] = value

redis_client = MockRedis()
