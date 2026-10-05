"""python -m campusfree <子命令>"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
