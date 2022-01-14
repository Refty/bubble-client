from httpx import AsyncClient
from thingy import NamesMixin, Thingy, classproperty


class Cursor:
    def __init__(self, cls, params):
        self.cls = cls
        self.params = params
        self.index = self.params.get("cursor", 0)
        self.page = None

    async def _get_page(self):
        self.params["cursor"] = self.index

        async with AsyncClient(base_url=self.cls.base_url) as client:
            response = await client.get(
                f"/api/1.1/obj/{self.cls.typename}",
                params=self.params,
                headers=self.cls._headers,
            )
            response.raise_for_status()
        return response.json()["response"]

    @property
    def page_index(self):
        return self.index - self.page["cursor"]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.page or self.page_index == self.page["count"]:
            self.page = await self._get_page()

        try:
            bubble_object = self.page["results"][self.page_index]
        except IndexError:
            raise StopAsyncIteration

        self.index += 1
        return self.cls(bubble_object)


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
        if token:
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
    def get(cls, **params):
        return Cursor(cls, params)


configure = BubbleThing.configure


__all__ = ("BubbleThing", "configure")
