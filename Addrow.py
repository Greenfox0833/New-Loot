import json
import re

# ここに Addrow をそのまま貼り付けて使う
ADDROW_TEXT = r'''
+DataTable=/LootCurrentSeason/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp_Backup;TableUpdate;"[{\"Name\":\"AthenaHighConsumablesRare.09\",\"LootPackageID\":\"WorldList.AthenaHighConsumablesRare\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":2,\"Y\":2},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/Game/Athena/Items/Consumables/ShockwaveGrenade/Athena_ShockGrenade.Athena_ShockGrenade\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"},{\"Name\":\"WorldList.FlopperDefault.Consumables.02\",\"LootPackageID\":\"WorldList.FlopperDefault.Consumables\",\"Weight\":0,\"NamedWeightMult\":\"None\",\"PotentialNamedWeights\":[],\"CountRange\":{\"X\":1,\"Y\":1},\"LootPackageCategory\":0,\"GameplayTags\":{\"GameplayTags\":[],\"ParentTags\":[]},\"RequiredLootGroupTag\":{\"TagName\":\"None\"},\"RequiredTagQuery\":{\"TokenStreamVersion\":0,\"TagDictionary\":[],\"QueryTokenStream\":[],\"UserDescription\":\"\",\"AutoDescription\":\"\"},\"LootPackageCall\":\"\",\"ItemDefinition\":\"/WildEstateConsumables/Gameplay/BrickSail/WID_Athena_BrickSail_Zero.WID_Athena_BrickSail_Zero\",\"PersistentLevel\":\"\",\"MinWorldLevel\":-1,\"MaxWorldLevel\":-1,\"bAllowBonusDrops\":true,\"Annotation\":\"\",\"DurabilityPercentageOverride\":1,\"Count\":0,\"RequiredTag\":\"None\"}]"
'''

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
