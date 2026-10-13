"""A link type's `from` / `to` may name an object type, an interface, or a list of either."""


def names_of(value):
    return list(value) if isinstance(value, list) else [value]


def describe(value):
    return ", ".join(names_of(value))


def valid_side(value, object_types, interfaces):
    names = names_of(value)
    return bool(names) and all(isinstance(n, str) and (n in object_types or n in interfaces) for n in names)


def matches(value, object_type, object_types):
    """True when object_type is one of the named types or implements one of the named interfaces."""
    implements = (object_types.get(object_type) or {}).get("implements", [])
    return any(name == object_type or name in implements for name in names_of(value))
