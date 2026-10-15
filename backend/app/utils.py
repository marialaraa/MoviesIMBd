from flask import request


class BadRequest(ValueError):
    pass


def is_valid(value, cast):
    try:
        cast(value)
        return True
    except ValueError:
        return False


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def positive_int(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    if not is_valid(raw, int) or int(raw) < 1:
        raise BadRequest(f"'{name}' must be a positive integer")
    return int(raw)
