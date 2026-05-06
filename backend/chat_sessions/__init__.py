__all__ = [
    "SessionFacade",
    "create_session_facade",
    "default_session_facade",
]


def __getattr__(name):
    if name in __all__:
        from .facade import (
            SessionFacade,
            create_session_facade,
            default_session_facade,
        )

        namespace = {
            "SessionFacade": SessionFacade,
            "create_session_facade": create_session_facade,
            "default_session_facade": default_session_facade,
        }
        return namespace[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
