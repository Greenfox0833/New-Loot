import json
import os
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
COMMON_DIR = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.append(str(COMMON_DIR))
os.environ.setdefault("SYSTEM_PROFILE", "BR_Comp_Test")

from cache import enrich_summary_with_names
from summary import build_schema_v2, build_summary, load_rows, validate_schema_v2


def main():
    rows_lt = load_rows(str(BASE_DIR / "input" / "AthenaLootTierData_Client__final.json"))
    rows_lp = load_rows(str(BASE_DIR / "input" / "AthenaLootPackages_Client__final.json"))
    legacy = build_summary(rows_lt, rows_lp)
    enrich_summary_with_names(legacy)
    payload = build_schema_v2(legacy, rows_lp)
    errors = validate_schema_v2(payload)

    output_dir = BASE_DIR / "output" / "schema_v2"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = output_dir / f"BR_Comp_TEST_schema_v2_{stamp}.json"
    validation_path = output_dir / f"BR_Comp_TEST_schema_v2_{stamp}.validation.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    validation_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")

    packages = [
        package
        for table in payload["lootTables"].values()
        for group in table["lootGroups"]
        for package in group["packages"]
    ]
    stats = {
        "output": str(output_path.resolve()),
        "validation": str(validation_path.resolve()),
        "gameTableCount": len(payload["lootTables"]),
        "lootGroupCount": sum(len(table["lootGroups"]) for table in payload["lootTables"].values()),
        "packageCount": len(packages),
        "itemCount": sum(len(package["items"]) for package in packages),
        "resolvedListCount": sum(package["resolved"] for package in packages),
        "unresolvedListCount": sum(not package["resolved"] for package in packages),
        "intentionalEmptyListCount": sum(package["isEmpty"] for package in packages),
        "warningCount": len(payload["warnings"]),
        "validationErrorCount": len(errors),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
