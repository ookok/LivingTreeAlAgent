"""json_utils — drop-in orjson replacement for stdlib json.

All LivingTree modules must use this instead of `import json` or `from livingtree.serialization.json_utils import _json_dumps, _json_loads`.
orjson is 12x faster than stdlib json.

Usage:
    from livingtree.serialization.json_utils import _json_dumps, _json_loads
    from livingtree.serialization.json_utils import _json_dump, _json_load

    s = _json_dumps({"key": "value"})             # pretty-printed str
    s = _json_dumps({"key": "value"}, indent=True)  # same as above
    obj = _json_loads(s)                           # parse str/bytes → object
    _json_dump(obj, path)                          # write JSON to file
    obj = _json_load(path)                         # read JSON from file
"""

from __future__ import annotations

from pathlib import Path

import orjson

JSONDecodeError = orjson.JSONDecodeError


def _json_dumps(obj: object, *, indent: bool = True) -> str:
    """Serialize object to JSON string. indent=True for pretty-printing."""
    option = orjson.OPT_INDENT_2 if indent else 0
    return orjson.dumps(obj, option=option).decode()


def _json_loads(data: str | bytes) -> object:
    """Parse JSON string or bytes → Python object."""
    return orjson.loads(data)


def _json_dump(obj: object, path: str | Path) -> None:
    """Write object as pretty-printed JSON to file."""
    Path(path).write_bytes(orjson.dumps(obj, option=orjson.OPT_INDENT_2))


def _json_load(path: str | Path) -> object:
    """Read and parse JSON from file."""
    return orjson.loads(Path(path).read_bytes())


__all__ = ["_json_dumps", "_json_loads", "_json_dump", "_json_load", "JSONDecodeError"]
