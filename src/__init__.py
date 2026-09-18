"""SWARMRoute package."""
import sys
import types

# Safeguard macOS Python 3.13 ARM64 C-extension conflicts
if "pyarrow" not in sys.modules:
    fake_pa = types.ModuleType("pyarrow")
    fake_pa.__version__ = "0.0.0"
    sys.modules["pyarrow"] = fake_pa

for _m in ("tensorflow", "keras", "tensorboard"):
    if _m not in sys.modules:
        sys.modules[_m] = None

try:
    import ortools
    from ortools.constraint_solver import pywrapcp
except ImportError:
    pass
