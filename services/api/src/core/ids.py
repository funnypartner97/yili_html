from uuid import uuid7


def new_id() -> str:
    return str(uuid7())
