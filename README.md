[Bubble.io]: https://bubble.io/

Bubble-Client
=============

[![PyPI](https://img.shields.io/pypi/v/bubble-client.svg)](https://pypi.org/project/bubble-client)
[![License](https://img.shields.io/github/license/Refty/bubble-client)](LICENSE)
[![Code style](https://img.shields.io/badge/code%20style-black-black)](https://github.com/ambv/black)

Python client for the [Bubble.io][] APIs

Installation
------------

```shell
pip install bubble-client
```

Examples
--------

* Get users (or any Bubble thing, really):

```python
>>> from bubble_client import configure, BubbleThing
>>> configure(base_url=..., token=...)

>>> class User(BubbleThing):
...     pass

>>> async for user in User.get():
...     print(user)
User({'name': 'Dr. Jekyll', ...})
User({'name': 'Mr. Hyde', ...})

>>> user.name
'Mr. Hyde'
```
