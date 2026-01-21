import json
import re
import sys

# Paste AddRow line here, or pipe text into stdin.
ADDROW_TEXT = r'''
+DataTable=/DragonCartLoot/DataTables/DragonCartLootTierData_Client;AddRow;"{\"Name\":\"Loot_Specialist_Supply_Extra_01\",\"TierGroup\":\"Loot_Specialist_Supply_Extra\",\"Weight\":1,\"QuotaLevel\":\"Unlimited\",\"LootTier\":0,\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"StreakBreakerCurrency\":\"\",\"StreakBreakerPointsMin\":0,\"StreakBreakerPointsMax\":0,\"StreakBreakerPointsSpend\":0,\"LootPackage\":\"WorldPKG.Specialist.Supply.Extra.Loot\",\"LootPreviewPackage\":\"None\",\"NumLootPackageDropsRange\":{\"X\":1,\"Y\":1},\"LootPackageCategoryWeightArray\":[1,0,0,0,0,0,0,0,0,0,0],\"LootPackageCategoryMinArray\":[1,0,0,0,0,0,0,0,0,0,0],\"LootPackageCategoryMaxArray\":[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1],\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"bAllowBonusLootDrops\":true,\"bAvoidDuplicateLootDrops\":false,\"Annotation\":\"\",\"NumLootPackageDrops\":0,\"RequiredGameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredTag\":\"None\"}"
'''


def extract_table_name(raw: str) -> str:
    m = re.search(r'\+DataTable=.+?/([^/;]+);AddRow;', raw)
    return m.group(1) if m else "AthenaLootTierData_Client"


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


def _flatten_gameplay_tags(src):
    if isinstance(src, dict):
        tags = src.get("GameplayTags", [])
        return tags if isinstance(tags, list) else []
    if isinstance(src, list):
        return src
    return []


def normalize_addrow_object(obj: dict):
    row_key = obj.get("Name")
    if not row_key:
        raise ValueError("Row object missing 'Name'.")

    row = {
        "TierGroup": obj.get("TierGroup", ""),
        "Weight": obj.get("Weight", 0),
        "QuotaLevel": obj.get("QuotaLevel", "Unlimited"),
        "LootTier": obj.get("LootTier", 0),
        "MinWorldLevel": obj.get("MinWorldLevel", -1),
        "MaxWorldLevel": obj.get("MaxWorldLevel", -1),
        "StreakBreakerCurrency": obj.get("StreakBreakerCurrency", ""),
        "StreakBreakerPointsMin": obj.get("StreakBreakerPointsMin", 0),
        "StreakBreakerPointsMax": obj.get("StreakBreakerPointsMax", 0),
        "StreakBreakerPointsSpend": obj.get("StreakBreakerPointsSpend", 0),
        "LootPackage": obj.get("LootPackage", ""),
        "LootPreviewPackage": obj.get("LootPreviewPackage", "None"),
        "NumLootPackageDropsRange": obj.get("NumLootPackageDropsRange", {"X": 1, "Y": 1}),
        "LootPackageCategoryWeightArray": obj.get("LootPackageCategoryWeightArray", []),
        "LootPackageCategoryMinArray": obj.get("LootPackageCategoryMinArray", []),
        "LootPackageCategoryMaxArray": obj.get("LootPackageCategoryMaxArray", []),
        "GameplayTags": _flatten_gameplay_tags(obj.get("GameplayTags", [])),
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
        "bAllowBonusLootDrops": obj.get("bAllowBonusLootDrops", True),
        "bAvoidDuplicateLootDrops": obj.get("bAvoidDuplicateLootDrops", False),
        "Annotation": obj.get("Annotation", ""),
        "NumLootPackageDrops": obj.get("NumLootPackageDrops", 0),
        "RequiredGameplayTags": _flatten_gameplay_tags(obj.get("RequiredGameplayTags", [])),
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
                    "ObjectName": "Class'FortLootTierData'",
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
