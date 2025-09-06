import json
import re

# ここに Addrow をそのまま貼り付けて使う
ADDROW_TEXT = r'''
+DataTable=/Game/Athena/Playlists/Showdown/Tournament/OverrideLootPackagesData_Backup;TableUpdate;"[{\"Name\":\"WorldList.AthenaLoot.Weapon.Shotgun.23\",\"LootPackageID\":\"WorldList.AthenaLoot.Weapon.Shotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_ExplosiveBow_Athena_SR.WID_ExplosiveBow_Athena_SR\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaLoot.Weapon.HighShotgun.19\",\"LootPackageID\":\"WorldList.AthenaLoot.Weapon.HighShotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_ExplosiveBow_Athena_SR.WID_ExplosiveBow_Athena_SR\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaSupplyDrop.Weapon.Shotgun.05\",\"LootPackageID\":\"WorldList.AthenaSupplyDrop.Weapon.Shotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_ExplosiveBow_Athena_SR.WID_ExplosiveBow_Athena_SR\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaLoot.Weapon.Shotgun.05\",\"LootPackageID\":\"WorldList.AthenaLoot.Weapon.Shotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaLoot.Weapon.HighShotgun.05\",\"LootPackageID\":\"WorldList.AthenaLoot.Weapon.HighShotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.ApolloLoot.Weapon.HighShotgun.02\",\"LootPackageID\":\"WorldList.ApolloLoot.Weapon.HighShotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaSupplyDrop.Weapon.Shotgun.04\",\"LootPackageID\":\"WorldList.AthenaSupplyDrop.Weapon.Shotgun\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.FlopperHigh.Shell.03\",\"LootPackageID\":\"WorldList.FlopperHigh.Shell\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaBooty.Short.01\",\"LootPackageID\":\"WorldList.AthenaBooty.Short\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":1,\"MaxWorldLevel\":1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaBooty.Short.02\",\"LootPackageID\":\"WorldList.AthenaBooty.Short\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":2,\"MaxWorldLevel\":2,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.AthenaBooty.Short.03\",\"LootPackageID\":\"WorldList.AthenaBooty.Short\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":2,\"Y\":2},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Weapons/WID_Shotgun_Standard_Athena_SR_Ore_T03.WID_Shotgun_Standard_Athena_SR_Ore_T03\",\"PersistentLevel\":\"\",\"MinWorldLevel\":3,\"MaxWorldLevel\":3,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"}]"
'''.strip()


def extract_table_name(raw: str) -> str:
    """
    +DataTable=/path/AAA/BBB/Name;TableUpdate;... から Name を抽出
    見つからなければデフォルト名を返す
    """
    m = re.search(r'\+DataTable=.+?/([^/;]+);TableUpdate;', raw)
    return m.group(1) if m else "LootCurrentSeasonLootPackages_Client_Comp_Backup"


def extract_payload_text(raw: str) -> str:
    """
    Addrow の JSON 部分を堅牢に抽出して返す。
    1) ;TableUpdate;" .... " の中身を優先
    2) なければ [ ... ] ブロックを抽出
    抽出結果が \" を含む場合は「外側のJSON文字列」をデコードして本体を取り出す（二段階）
    """
    # まずは ;TableUpdate; の直後のクォートに囲まれたペイロード優先
    m = re.search(r';TableUpdate;\s*(["\'])(?P<payload>.*)(\1)\s*$', raw, re.DOTALL)
    if m:
        quoted_payload = m.group('payload')
        # ここは “JSON文字列” なので一度デコードして中身（実JSONテキスト）を取り出す
        # 例: "[{\"Name\":\"...\"}]"  ->  [{"Name":"..."}]
        try:
            # 外側の JSON 文字列としてパース（エスケープ解除）
            decoded_text = json.loads(m.group(1) + quoted_payload + m.group(1))
            return decoded_text
        except json.JSONDecodeError:
            # 失敗したら後段の [ ... ] 抽出へフォールバック
            pass

    # フォールバック： [ ... ] を直接抜き出す
    m2 = re.search(r'(\[.*\])', raw, re.DOTALL)
    if not m2:
        raise ValueError("JSON 部分（[ ... ]）を抽出できませんでした。")
    block = m2.group(1)

    # もし \" が含まれていたら、外側の文字列のエスケープが残っている可能性が高い
    if '\\"' in block:
        # block を “JSON 文字列” とみなしてデコードを試みる
        try:
            decoded_text = json.loads('"' + block.replace('\\', '\\\\').replace('"', '\\"') + '"')
            return decoded_text
        except json.JSONDecodeError:
            pass  # だめならそのまま返して次で失敗させる

    return block


def addrow_to_datatable(raw_text: str) -> str:
    """
    Addrow データを DataTable 形式の JSON テキストに変換して返す
    """
    table_name = extract_table_name(raw_text)
    payload_text = extract_payload_text(raw_text)

    try:
        rows = json.loads(payload_text)  # ここで最終的に JSON 配列へ
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON パース失敗: {e}\n--- 抽出テキスト ---\n{payload_text[:4000]}")

    if not isinstance(rows, list):
        raise ValueError("抽出した JSON は配列ではありません。")

    # Rows を { Name: row_obj } に組み替え
    rows_dict = {}
    for row in rows:
        name = row.get("Name")
        if not name:
            raise ValueError("行データに 'Name' がありません。")
        rows_dict[name] = row

    datatable = [
        {
            "Type": "DataTable",
            "Name": table_name,
            "Class": "UScriptClass'DataTable'",
            "Properties": {
                "RowStruct": {
                    "ObjectName": "Class'FortLootPackageData'",
                    "ObjectPath": "/Script/FortniteGame"
                }
            },
            "Rows": rows_dict
        }
    ]

    return json.dumps(datatable, indent=2, ensure_ascii=False)


def main():
    try:
        out = addrow_to_datatable(ADDROW_TEXT)
        print(out)
    except Exception as e:
        # 失敗時も原因が分かるようにメッセージを詳細表示
        print(f"⚠ 変換に失敗しました: {e}")


if __name__ == "__main__":
    main()
