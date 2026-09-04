import json
import logging
import os
from pathlib import Path

from http_client import session


EXPORT_API_URL = os.getenv(
    "FORTNITE_EXPORT_API_URL",
    "http://localhost:3849/api/v1/export",
).rstrip("?")
LOCCHUNK_NUMBERS = (10, 100, 13, 20, 29, 30, 32, 35, 40, 50, 70, 80, 85, 90)
LOCRES_PATHS = tuple(
    "FortniteGame/Content/Localization/"
    f"Fortnite_locchunk{number}/ja/Fortnite_locchunk{number}.locres"　
    for number in LOCCHUNK_NUMBERS
) + ("FortniteGame/Content/Localization/Fortnite/ja/Fortnite.locres",)
OUTPUT_PATH = Path(__file__).resolve().parent / "shared" / "cache" / "locres_ja.json"
LOGGER = logging.getLogger(__name__)


def merge_locres(target: dict, source: dict) -> None:
    for namespace, entries in source.items():
        if not isinstance(entries, dict):
            continue
        target.setdefault(namespace, {}).update(entries)


def main() -> None:
    data: dict = {}
    for locres_path in LOCRES_PATHS:
        try:
            response = session.get(
                EXPORT_API_URL,
                params={"path": locres_path},
                timeout=120,
            )
            response.raise_for_status()
            chunk_data = response.json()
            if not isinstance(chunk_data, dict):
                raise ValueError("APIの応答がJSONオブジェクトではありません")
        except Exception as exc:
            LOGGER.warning("取得失敗のためスキップ: %s (%s)", locres_path, exc)
            continue

        merge_locres(data, chunk_data)
        LOGGER.info("取得完了: %s", locres_path)

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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
