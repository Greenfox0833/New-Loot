このフォルダに武器の AssetPathName を入れてから `python proto/run.py` を実行します。

別フォルダを指定して実行することもできます。
例: `python proto/run.py E:\path\to\proto`

使える入力形式:
- `*.txt`: 1行に1件
- `*.json`: `["/Path/A", "/Path/B"]` または `[{"AssetPathName":"..."}]`
- `*.csv`: `AssetPathName` 列つき、または1列目にパス

出力先:
- 画像: `proto/images`
- 名前キャッシュ: `proto/cache/asset_localize_cache.json`
- 画像キャッシュ: `proto/cache/icon_cache`
- 画像パスキャッシュ: `proto/cache/asset_icon_cache.json`

補足:
- 生成済み画像がある場合はスキップします。
- 既存の `config.py` / `tasks.py` / `cache.py` には依存しません。
