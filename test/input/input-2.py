import math

def f_to_c(f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    x = f - 32.0
    return x * 5 / 9

def c_to_f(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    x = c * 9 / 5
    return x + 32.0

TEST_VALUES = [-459.67, -273.15, 0.0, 32.0, 42.0, 273.15, 100.0, 212.0, 373.15]

def test_conversions() -> None:
    for t in TEST_VALUES:
        assert_round_trip(t)

def assert_round_trip(t: float) -> None:
    # Round-trip Fahrenheit through Celsius:
    assert math.isclose(t, f_to_c(c_to_f(t))), f"{t} F -> C -> F failed!"
    # Round-trip Celsius through Fahrenheit:
    assert math.isclose(t, c_to_f(f_to_c(t))), f"{t} C -> F -> C failed!"

if __name__ == "__main__":
    test_conversions()
