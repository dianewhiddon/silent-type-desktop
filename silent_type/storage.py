"""Resolve an installation's data folder independently of its launcher.

The optional, gitignored locator contains a path only. An environment override
remains available for isolated tests. Existing installs keep their original data
folder until explicitly configured; changing a locator does not move user data.
"""

import argparse
import json
import os
from pathlib import Path

LOCATOR = Path(__file__).resolve().parents[1] / "data-location.json"


def data_directory(name, locator=LOCATOR):
    override = os.environ.get("SILENT_TYPE_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif locator.exists():
        try:
            value = json.loads(locator.read_text(encoding="utf-8"))
            path = Path(value["data_directory"]).expanduser()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid data location file: {locator}") from exc
    else:
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / name
    if not path.is_absolute():
        raise ValueError("The data directory must be an absolute path.")
    return path


def configure(path, locator=LOCATOR):
    """Pin an explicitly selected folder; preserve its existing contents."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ValueError("The data directory must be an absolute path.")
    path.mkdir(parents=True, exist_ok=True)
    temporary = locator.with_suffix(".tmp")
    temporary.write_text(json.dumps({"data_directory": str(path)}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(locator)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    print("Data directory:", configure(args.data_dir))


if __name__ == "__main__":
    main()
