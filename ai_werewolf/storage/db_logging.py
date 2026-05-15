from typing import Any

from sqlmodel import Session


def database_label_for_bind(bind: Any) -> str:
    engine = getattr(bind, "engine", bind)
    url = getattr(engine, "url", None)
    if url is None:
        return type(bind).__name__

    render_as_string = getattr(url, "render_as_string", None)
    if callable(render_as_string):
        return render_as_string(hide_password=True)
    return str(url)


def database_label_for_session(session: Session) -> str:
    try:
        return database_label_for_bind(session.get_bind())
    except Exception as exc:
        return f"unknown({type(exc).__name__})"
