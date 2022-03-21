import json
import datetime

import httpx
from thingy import NamesMixin, Thingy, classproperty


class Join:
    def __init__(self, cursor_or_cls, key):
        if isinstance(cursor_or_cls, Cursor):
            self.cursor = cursor_or_cls
            self.getter = self.get_from_cursor
        else:
            self.getter = cursor_or_cls._get_by_id

        self.key = key
        self.cache = {}

    async def get_from_cursor(self, id):
        self.cursor.cache = True
        self.cursor.rewind()

        async for other in self.cursor:
            if other._id == id:
                return other

    async def get(self, id):
        if isinstance(id, list):
            return [await self.get(i) for i in id]

        other = self.cache.get(id)
        if not other:
            other = await self.getter(id)
        self.cache[id] = other
        return other

    async def __call__(self, thing):
        other_id = getattr(thing, self.key)
        if other_id:
            other = await self.get(other_id)
            setattr(thing, self.key, other)
        return thing


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, BubbleThing):
            return o.view("bubble")
        return json.JSONEncoder.default(self, o)


async def raise_for_status(response):
    response.raise_for_status()


class AsyncClient(httpx.AsyncClient):
    _json_encoder = JSONEncoder

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("event_hooks", {"response": [raise_for_status]})
        super().__init__(*args, **kwargs)

    @classmethod
    def _dump_params(cls, params):
        for key, value in params.items():
            if not isinstance(value, (str, int)):
                params[key] = json.dumps(value, cls=cls._json_encoder)

    async def request(self, *args, **kwargs):
        params = kwargs.get("params")
        if params:
            self._dump_params(params)

        if "json" in kwargs:
            content = kwargs.pop("json")
            kwargs["content"] = json.dumps(content, cls=self._json_encoder)
            headers = kwargs.get("headers")
            if headers is None:
                headers = {}
            kwargs["headers"] = headers | {"Content-Type": "application/json"}
        return await super().request(*args, **kwargs)


class Cursor:
    _json_encoder = JSONEncoder

    def __init__(self, cls, params, cache=False):
        self.cls = cls
        self.params = params
        self.index = self.params.get("cursor", 0)
        self.page = None
        self.joins = []
        self.cache = cache
        self.cached = []

    async def _get_page(self):
        self.params["cursor"] = self.index

        async with self.cls._get_client() as client:
            response = await client.get(
                f"/api/1.1/obj/{self.cls.typename}",
                params=self.params,
            )
        return response.json()["response"]

    @property
    def page_index(self):
        return self.index - self.page["cursor"]

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            bubble_object = self.cached[self.index]
        except IndexError:
            pass
        else:
            self.index += 1
            return bubble_object

        if not self.page or (self.page_index == self.page["count"]):
            limit = self.params.get("limit")
            if not limit or self.index < limit:
                self.page = await self._get_page()

        try:
            bubble_object = self.page["results"][self.page_index]
        except IndexError:
            raise StopAsyncIteration

        self.index += 1
        bubble_object = self.cls(bubble_object)

        for join in self.joins:
            await join(bubble_object)

        if self.cache:
            self.cached.append(bubble_object)
        return bubble_object

    async def count(self):
        if not self.page:
            self.page = await self._get_page()
        return self.page["cursor"] + self.page["count"] + self.page["remaining"]

    def rewind(self):
        self.index = 0

    def join(self, key, cursor_or_cls):
        join = Join(cursor_or_cls, key)
        self.joins.append(join)


class BubbleThing(NamesMixin, Thingy):
    _base_url = None
    _client_cls = AsyncClient
    _json_encoder = JSONEncoder
    _headers = {}
    _typename = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        __dict__ = {}
        includes = []

        for key, value in self.__dict__.items():
            alias = key.replace(" ", "_").lower()
            __dict__[alias] = value
            if key not in ("Modified Date", "Created Date", "Created By", "_id"):
                includes.append((alias, key))

        self.__dict__ = __dict__
        self.add_view("bubble", include=includes)

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
        return cls._typename or "".join(cls.names)

    @classmethod
    def _get_client(cls):
        return cls._client_cls(
            base_url=cls._base_url,
            headers=cls._headers,
        )

    @classmethod
    def get(cls, **params):
        return Cursor(cls, params)

    @classmethod
    async def _get_by_id(cls, id, **params):
        async with cls._get_client() as client:
            response = await client.get(
                f"/api/1.1/obj/{cls.typename}/{id}",
                params=params,
            )

        bubble_object = response.json()["response"]
        if bubble_object:
            return cls(bubble_object)

    @classmethod
    async def _get_first(cls, **params):
        params["limit"] = 1
        try:
            return await cls.get(**params).__anext__()
        except StopAsyncIteration:
            return None

    @classmethod
    async def get_one(cls, id=None, **params):
        if id:
            return await cls._get_by_id(id, **params)
        return await cls._get_first(**params)

    @classmethod
    async def count(cls, **params):
        params["limit"] = 1
        return await cls.get(**params).count()

    async def join(self, key, cursor_or_cls):
        return await Join(cursor_or_cls, key)(self)

    async def put(self, **params):
        async with self._get_client() as client:
            await client.put(
                f"/api/1.1/obj/{self.__class__.typename}/{self._id}",
                params=params,
                json=self,
            )
        return self

    async def post(self, **params):
        async with self._get_client() as client:
            response = await client.post(
                f"/api/1.1/obj/{self.__class__.typename}",
                params=params,
                json=self,
            )
            self._id = response.json()["id"]
        return self

    async def save(self, **params):
        if self._id:
            return self.put(**params)
        return self.post(**params)


configure = BubbleThing.configure


__all__ = ("BubbleThing", "configure")
