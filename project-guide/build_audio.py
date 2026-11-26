"""Compatibility entry point. The canonical reproducible build is build.py."""
from build import main

if __name__ == "__main__":
    raise SystemExit(main())
