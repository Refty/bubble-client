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
User({'name': 'Beatrix Emery', ...})
User({'name': 'Dr. Jekyll', ...})

>>> user.name
'Dr. Jekyll'
```

* Change values:

```python
>>> user.name = "Mr. Hyde"
>>> await user.save()
>>> user.name
'Mr. Hyde'
```

* Count users:

```python
>>> User.count()
2
```

* Add a new user:

```python
>>> user = User(name="Sir Charles Emery")
>>> await user.save()
>>> User.count()
3
```

* Search!

```python
>>> constraints = [{'key': 'name', 'constraint_type': 'equals', 'value': 'Mr. Hyde'}]

>>> pet = await Pet.get_one(constraints=constraints)
>>> pet.name
'Mr. Hyde'
```

* Join stuff!

```python
>>> class Pet(BubbleThing):
...     pass

>>> pet = await pet.get_one()
>>> await pet.join("created_by", User)

>>> pet.type
'dog'
>>> pet.created_by
User({'name': 'Mr. Hyde', ...})
>>> pet.created_by.name
'Mr. Hyde'
```

* Also works on cursors!

```python
>>> async for pet in Pet.get().join("created_by", User):
...     print(pet)
Pet({'type': 'dog', 'created_by': User({'name': 'Mr. Hyde', ...}), ...})
Pet({'type': 'donkey', 'created_by': User({'name': 'Beatrix Emery', ...}), ...})
```

* Delete stuff!

```python
>>> constraints = [{"key": "name", "constraint_type": "equals", "value": "Beatrix Emery"}]
>>> pet = await Project.get_one(constraints=constraints)
>>> await pet.delete()
```

Tips
----

* Use `asyncio.run(main())` if you are getting a `SyntaxError` (it means that you can't use
  async/await in the main body of a Python code).
* Avoid using dashes in table names (Python object names can't have a dash).
* The base URL doesn't need the `/api/1.1/obj` part.
