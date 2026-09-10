import sys
# Prevent pyarrow from registering duplicate C++ protobuf descriptors that conflict with OR-Tools on ARM64
if "pyarrow" not in sys.modules:
    sys.modules["pyarrow"] = None
