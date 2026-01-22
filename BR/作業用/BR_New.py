from pathlib import Path
import os
import sys

base_dir = Path(__file__).resolve().parent
system_update_dir = base_dir.parent.parent / "System Update" / "BR"
system_update_common = base_dir.parent.parent / "System Update"
if str(system_update_dir) not in sys.path:
    sys.path.insert(0, str(system_update_dir))
if str(system_update_common) not in sys.path:
    sys.path.insert(0, str(system_update_common))

if os.getenv("BR_INTERACTIVE") is None:
    os.environ["BR_INTERACTIVE"] = "1"

from pipeline import main

if __name__ == "__main__":
    main()
