from httpx import AsyncClient
from thingy import NamesMixin, Thingy, classproperty


class BubbleThing(NamesMixin, Thingy):
    _base_url = None
    _headers = {}
    _typename = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = {
            key.replace(" ", "_"): value for key, value in self.__dict__.items()
        }

    @classmethod
    def configure(cls, base_url, token, headers=None):
        cls._base_url = base_url
        if headers is None:
            headers = {}
        cls._headers = headers
        cls._headers.setdefault("Authorization", f"Bearer {token}")

    @classproperty
    def base_url(cls):
        if cls._base_url:
            return cls._base_url
        raise AttributeError("Undefined base URL. Call configure().")

    @classproperty
    def typename(cls):
        return cls._typename or "_".join(cls.names)

    @classmethod
    async def get(cls, params=None):
        if params is None:
            params = {}

        async def _get_page(params):
            async with AsyncClient(base_url=cls.base_url) as client:
                response = await client.get(
                    f"/api/1.1/obj/{cls.typename}",
                    params=params,
                    headers=cls._headers,
                )
                response.raise_for_status()
            return response.json()["response"]

        params.setdefault("cursor", 0)
        while page := await _get_page(params):
            for bubble_object in page["results"]:
                yield cls(bubble_object)
            if not page["remaining"]:
                break
            params["cursor"] = page["cursor"] + page["count"]


configure = BubbleThing.configure


class User(BubbleThing):
    pass


__all__ = ("BubbleThing", "configure", "User")
