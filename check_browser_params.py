import inspect
from browser_use import Browser
sig = inspect.signature(Browser.__init__)
print("Browser.__init__ signature:")
for k, v in sig.parameters.items():
    if k == "self":
        continue
    default = v.default if v.default is not inspect.Parameter.empty else "(required)"
    print(f"  {k}: {default}")
