import json
import re
import sys

# Paste AddRow line here, or pipe text into stdin.
ADDROW_TEXT = r'''
+DataTable=/DragonCartLoot/DataTables/DragonCartLootPackages_Client;AddRow;"{\"Name\":\"WorldPKG.Specialist.Supply.Extra.Loot.01\",\"LootPackageID\":\"WorldPKG.Specialist.Supply.Extra.Loot\",\"Weight\":1,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"WorldList.Ammo.Random\",\"ItemDefinition\":\"None\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"}"
'''


def extract_table_name(raw: str) -> str:
    m = re.search(r'\+DataTable=.+?/([^/;]+);AddRow;', raw)
    return m.group(1) if m else "AthenaLootPackages_Client"


def extract_payload_text(raw: str) -> str:
    m = re.search(r';AddRow;\s*(["\'])(?P<payload>.*)(\1)\s*$', raw, re.DOTALL)
    if m:
        quoted_payload = m.group('payload')
        try:
            return json.loads(m.group(1) + quoted_payload + m.group(1))
        except json.JSONDecodeError:
            pass

    m2 = re.search(r'(\{.*\})', raw, re.DOTALL)
    if not m2:
        raise ValueError("JSON object not found in AddRow text.")
    block = m2.group(1)

    if '\\"' in block:
        try:
            decoded_text = json.loads('"' + block.replace('\\', '\\\\').replace('"', '\\"') + '"')
            return decoded_text
        except json.JSONDecodeError:
            pass

    return block


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _flatten_gameplay_tags(src):
    if isinstance(src, dict):
        tags = src.get("GameplayTags", [])
        return tags if isinstance(tags, list) else []
    if isinstance(src, list):
        return src
    return []


def _normalize_item_definition(itemdef):
    if isinstance(itemdef, dict):
        return {
            "AssetPathName": itemdef.get("AssetPathName", ""),
            "SubPathString": itemdef.get("SubPathString", ""),
        }
    if isinstance(itemdef, str):
        if not itemdef or itemdef == "None":
            return {"AssetPathName": "", "SubPathString": ""}
        return {"AssetPathName": itemdef, "SubPathString": ""}
    return {"AssetPathName": "", "SubPathString": ""}


def normalize_addrow_object(obj: dict):
    row_key = obj.get("Name")
    if not row_key:
        raise ValueError("Row object missing 'Name'.")

    row = {
        "LootPackageID": obj.get("LootPackageID", ""),
        "Weight": _to_float(obj.get("Weight", 0.0), 0.0),
        "NamedWeightMult": obj.get("NamedWeightMult", "None"),
        "PotentialNamedWeights": obj.get("PotentialNamedWeights", []),
        "CountRange": obj.get("CountRange", {"X": 1, "Y": 1}),
        "LootPackageCategory": obj.get("LootPackageCategory", 0),
        "GameplayTags": _flatten_gameplay_tags(obj.get("GameplayTags", [])),
        "RequiredLootGroupTag": obj.get("RequiredLootGroupTag", {"TagName": "None"}),
        "RequiredTagQuery": obj.get(
            "RequiredTagQuery",
            {
                "TokenStreamVersion": 0,
                "TagDictionary": [],
                "QueryTokenStream": [],
                "UserDescription": "",
                "AutoDescription": "",
            },
        ),
        "LootPackageCall": obj.get("LootPackageCall", ""),
        "ItemDefinition": _normalize_item_definition(obj.get("ItemDefinition", "")),
        "PersistentLevel": obj.get("PersistentLevel", ""),
        "MinWorldLevel": obj.get("MinWorldLevel", -1),
        "MaxWorldLevel": obj.get("MaxWorldLevel", -1),
        "bAllowBonusDrops": obj.get("bAllowBonusDrops", True),
        "Annotation": obj.get("Annotation", ""),
        "DurabilityPercentageOverride": _to_float(
            obj.get("DurabilityPercentageOverride", 1.0), 1.0
        ),
    }
    return row_key, row


def addrow_to_datatable(raw_text: str) -> str:
    table_name = extract_table_name(raw_text)
    payload_text = extract_payload_text(raw_text)

    try:
        obj = json.loads(payload_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}\n--- payload ---\n{payload_text[:4000]}")

    if isinstance(obj, list):
        if not obj:
            raise ValueError("Payload is an empty list.")
        obj = obj[0]
    if not isinstance(obj, dict):
        raise ValueError("Payload is not a JSON object.")

    row_key, row = normalize_addrow_object(obj)
    datatable = [
        {
            "Type": "DataTable",
            "Name": table_name,
            "Class": "UScriptClass'DataTable'",
            "Flags": "RF_Public | RF_Standalone | RF_Transactional | RF_WasLoaded | RF_LoadCompleted",
            "Properties": {
                "RowStruct": {
                    "ObjectName": "Class'FortLootPackageData'",
                    "ObjectPath": "/Script/FortniteGame",
                }
            },
            "Rows": {row_key: row},
        }
    ]

    return json.dumps(datatable, indent=2, ensure_ascii=True)


def main():
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        raw = ADDROW_TEXT
    try:
        out = addrow_to_datatable(raw)
        print(out)
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
