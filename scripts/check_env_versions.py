"""Quick environment sanity check for the collector UI.

Run with the active virtualenv to confirm the installed versions match
requirements.txt (especially SQLAlchemy and typing_extensions for Python 3.13).
"""
from importlib import metadata

PACKAGES = [
    "sqlalchemy",
    "typing_extensions",
    "fastapi",
    "uvicorn",
    "pymodbus",
]


def get_version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "<not installed>"


def main() -> None:
    for pkg in PACKAGES:
        print(f"{pkg} = {get_version(pkg)}")


if __name__ == "__main__":
    main()
