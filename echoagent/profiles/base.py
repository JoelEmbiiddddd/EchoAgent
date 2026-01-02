from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from echoagent.profiles.models import Profile


class ToolAgentOutput(BaseModel):
    """Standard output for all tool agents"""
    output: str
    sources: list[str] = Field(default_factory=list)


def load_all_profiles():
    """Load all Profile instances from the profiles package.

    Returns:
        Dict with shortened keys (e.g., "observe" instead of "observe_profile")
        Each profile has a _key attribute added for automatic name derivation
    """
    import importlib
    import inspect
    from pathlib import Path

    profiles = {}
    package_path = Path(__file__).parent

    # Recursively find all .py files in the profiles directory
    for py_file in package_path.rglob('*.py'):
        if py_file.name == 'base.py' or py_file.name.startswith('_'):
            continue

        # Convert file path to module name (need to find 'echoagent' root)
        # Go up from current file: profiles/base.py -> profiles -> echoagent
        echoagent_root = package_path.parent
        relative_path = py_file.relative_to(echoagent_root)
        module_name = 'echoagent.' + str(relative_path.with_suffix('')).replace('/', '.')

        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Profile) and not name.startswith('_'):
                    # Strip "_profile" suffix from key for cleaner access
                    key = name.replace('_profile', '') if name.endswith('_profile') else name
                    # Add _key attribute to profile for automatic name derivation
                    obj._key = key
                    profiles[key] = obj
        except Exception as e:
            print(f"Error loading profile: {module_name}")
            raise e

    return profiles
