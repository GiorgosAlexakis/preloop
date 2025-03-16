#!/usr/bin/env python3
"""Test file for pre-commit hooks."""

from typing import Any, Dict, Optional


def badly_formatted_function(x: int, y: int, z: Optional[str] = None) -> Dict[str, Any]:
    """This function is intentionally badly formatted to test pre-commit hooks.

    Args:
        x: First number
        y: Second number
        z: Optional string

    Returns:
        Dict with results
    """
    result = {"sum": x + y, "product": x * y}
    if z is not None:
        result["message"] = z
    return result


class BadlyFormattedClass:
    def __init__(self, name: str = "default"):
        self.name = name

    def do_something(self, input_value: int):
        print(f"Doing something with {input_value} in {self.name}")
        return input_value * 2


if __name__ == "__main__":
    test_func = badly_formatted_function(10, 20, "test")
    print(test_func)

    test_class = BadlyFormattedClass("test instance")
    test_class.do_something(42)
