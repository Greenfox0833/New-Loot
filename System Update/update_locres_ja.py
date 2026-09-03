import json
import os
from pathlib import Path

from http_client import session


LOCRES_API_URL = os.getenv(
    "FORTNITE_LOCRES_API_URL",
    "http://localhost:3849/api/v1/export/locres?lang=ja",
)
OUTPUT_PATH = Path(__file__).resolve().parent / "shared" / "cache" / "locres_ja.json"


def main() -> None:
    response = session.get(LOCRES_API_URL, timeout=120)
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("locres APIの応答がJSONオブジェクトではありません。")

    entry_count = sum(
        len(value)
        for value in data.values()
        if isinstance(value, dict)
    )
    if entry_count == 0:
        raise ValueError("locres APIの応答にローカライズ項目がありません。")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(OUTPUT_PATH)
    print(f"保存完了: {OUTPUT_PATH}")
    print(f"ローカライズ件数: {entry_count}")


if __name__ == "__main__":
    main()
