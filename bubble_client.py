from httpx import AsyncClient
from thingy import NamesMixin, Thingy, classproperty


class Cursor:
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

    def rewind(self):
        self.index = 0

    def join(self, key, cursor_or_other_cls, **params):
        if not isinstance(cursor_or_other_cls, Cursor):
            cursor_or_other_cls = Cursor(cursor_or_other_cls, params, cache=True)
        self.joins[key] = cursor_or_other_cls
        return self


class BubbleThing(NamesMixin, Thingy):
    _base_url = None
    _headers = {}
    _typename = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = {
            key.replace(" ", "_").lower(): value for key, value in self.__dict__.items()
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
        return cls._typename or "".join(cls.names)

    @classmethod
    def get(cls, **params):
        return Cursor(cls, params)

    @classmethod
    async def _get_by_id(cls, id, **params):
        async with AsyncClient(base_url=cls.base_url) as client:
            response = await client.get(
                f"/api/1.1/obj/{cls.typename}/{id}",
                params=params,
                headers=cls._headers,
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


configure = BubbleThing.configure


__all__ = ("BubbleThing", "configure")
