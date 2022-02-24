import json
from datetime import datetime

import httpx
from thingy import NamesMixin, Thingy, classproperty


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class AsyncClient(httpx.AsyncClient):
    _json_encoder = JSONEncoder

    async def request(self, *args, **kwargs):
        if "json" in kwargs:
            json = kwargs.pop("json")
            kwargs["content"] = self._json_encoder.dumps(json)
            kwargs.setdefault("headers", {})
            kwargs["headers"]["Content-Type"] = "application/json"
        return await super().request(*args, **kwargs)


class Cursor:
    _json_encoder = JSONEncoder

    def __init__(self, cls, params, cache=False):
        self.cls = cls
        self.params = params
        self.index = self.params.get("cursor", 0)
        self.page = None
        self.joins = {}
        self.cache = cache
        self.cached = []

    async def _get_page(self):
        self.params["cursor"] = self.index

        async with self.cls._get_client() as client:
            response = await client.get(
                f"/api/1.1/obj/{self.cls.typename}",
                params=self.params,
            )
            response.raise_for_status()
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

        if not self.page or self.page_index == self.page["count"]:
            self.page = await self._get_page()

        try:
            bubble_object = self.page["results"][self.page_index]
        except IndexError:
            raise StopAsyncIteration

        self.index += 1
        bubble_object = self.cls(bubble_object)

        for key, cursor in self.joins.items():
            await bubble_object.join(key, cursor)

        if self.cache:
            self.cached.append(bubble_object)
        return bubble_object

    async def count(self):
        if not self.page:
            self.page = await self._get_page()
        return self.page["cursor"] + self.page["count"] + self.page["remaining"]

    def rewind(self):
        self.index = 0

    def join(self, key, cursor_or_other_cls, **params):
        if not isinstance(cursor_or_other_cls, Cursor):
            cursor_or_other_cls = Cursor(cursor_or_other_cls, params, cache=True)
        self.joins[key] = cursor_or_other_cls
        return self


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
    def _dump_params(cls, params):
        for key, value in params.items():
            if not isinstance(value, str):
                params[key] = json.dumps(value, cls=cls._json_encoder)

    @classmethod
    def get(cls, **params):
        cls._dump_params(params)
        return Cursor(cls, params)

    @classmethod
    async def _get_by_id(cls, id, **params):
        cls._dump_params(params)
        async with cls._get_client() as client:
            response = await client.get(
                f"/api/1.1/obj/{cls.typename}/{id}",
                params=params,
            )
            response.raise_for_status()

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

    async def _join_by_cursor(self, key, cursor):
        other_id_or_ids = getattr(self, key)
        if not other_id_or_ids:
            return
        cursor.cache = True

        # TODO: fill with None when we can't find an id and guarantee the original order
        if isinstance(other_id_or_ids, list):
            others = []
            async for other in cursor:
                for index, other_id in enumerate(other_id_or_ids):
                    if other._id == other_id:
                        cursor.rewind()
                        others.append(other)
                        other_id_or_ids.pop(index)
                        break
                if len(other_id_or_ids) == 0:
                    break
            setattr(self, key, others)
            return
        else:
            async for other in cursor:
                if other._id == other_id_or_ids:
                    cursor.rewind()
                    setattr(self, key, other)
                    break
            else:
                setattr(self, key, None)

    async def _join_by_cls(self, key, other_cls, **params):
        other_id_or_ids = getattr(self, key)
        if not other_id_or_ids:
            return

        # TODO: use a constraint and filter on the ids instead
        if isinstance(other_id_or_ids, list):
            others = []
            async for other_id in other_id_or_ids:
                other = other_cls._get_by_id(other_id, **params)
                others.append(other)
            setattr(self, key, others)
        else:
            other = await other_cls._get_by_id(other_id, **params)
            setattr(self, key, other)

    async def join(self, key, cursor_or_other_cls, **params):
        if isinstance(cursor_or_other_cls, Cursor):
            return await self._join_by_cursor(key, cursor_or_other_cls)
        else:
            return await self._join_by_cls(key, cursor_or_other_cls, **params)

    async def put(self, **params):
        self._dump_params(params)
        async with self._get_client() as client:
            response = await client.put(
                f"/api/1.1/obj/{self.__class__.typename}/{self._id}",
                params=params,
                json=self.view("bubble"),
            )
            response.raise_for_status()
        return self

    async def post(self, **params):
        self._dump_params(params)
        async with self._get_client() as client:
            response = await client.post(
                f"/api/1.1/obj/{self.__class__.typename}",
                params=params,
                json=self.view("bubble"),
            )
            response.raise_for_status()
            self._id = response.json()["id"]
        return self

    async def save(self, **params):
        if self._id:
            return self.put(**params)
        return self.post(**params)


configure = BubbleThing.configure


__all__ = ("BubbleThing", "configure")
