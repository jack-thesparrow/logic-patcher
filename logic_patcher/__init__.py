# logic_patcher/__init__.py

try:
    from importlib.metadata import version as _v
    __version__ = _v("logic-patcher")
except Exception:
    __version__ = "1.0.0"
__app_name__     = "logic-patcher"
__author__       = "Rahul Tudu"
__github_owner__ = "jack-thesparrow"
__github_repo__  = "logic-patcher"
