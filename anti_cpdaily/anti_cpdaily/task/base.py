from httpx import AsyncClient, Client


class BaseTask:
    def __init__(self):
        pass

    def run(self, root: str, client: Client) -> bool:
        pass


class AsyncBaseTask:
    def __init__(self):
        pass

    async def run(self, client: AsyncClient) -> bool:
        pass
    