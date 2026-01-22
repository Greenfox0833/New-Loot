BR.py 分割版 説明書

場所
  BR/作業用/BR.py
  BR/作業用/SyStem Update/ (分割済みモジュール一式)

概要
  BR.py はエントリ専用の薄いスクリプトです。
  実行本体は SyStem Update/pipeline.py の main() です。

実行方法
  1) BR/作業用/BR.py を実行
  2) pipeline の流れに沿って処理が進行
  3) 起動時にパス入力のプロンプトが出る（空Enterで既定値）

プロファイル
  System Update/<PROFILE>/config.py を作ると、その設定で上書きできます。
  例: SYSTEM_PROFILE=BR_Comp

BASE_PATH / SEASON_PATH 複数対応
  - BASE_PATHS と SEASON_PATHS を最大10個まで設定可能
  - AUTO_RESOLVE_PATHS=True で自動解決を有効化
  - 例: BASE_PATHS = ["E:/フォートナイト/Picture/Loot Pool", "E:/Fmodel/Exports"]
        SEASON_PATHS = ["TEST4/New Loot"]

実行順番（pipeline の流れ）
  1) Hotfix 実行 (LootPackage変更.py / LootTier変更.py)
  2) LT/LP 読み込み → summary 作成
  3) summary を保存 (versioned JSON)
  4) BR_LootData を生成・保存
  5) LootSummary.py 実行 (抽出→比較)
  6) MinList 読み込み → 画像タスク作成
  7) 画像生成 (並列)
  8) Discord 送信 (BR_Discor.py)
  9) Git add/commit/push

フォルダ構成と役割
  config.py      : 設定値・パス・定数・フラグ
  utils.py       : 小さな共通関数(as_floatなど)
  http_client.py : HTTP セッション/Retry 設定
  export_api.py  : Export API 呼び出し・正規化・ローカライズ
  cache.py       : レアリティ/ローカライズ/アイコンのキャッシュ
  image_tools.py : 画像生成(カード合成/ステータス描画)
  summary.py     : LT/LP から summary を作る処理 + LootData 生成
  tasks.py       : 画像タスク化/worker/プリウォーム
  pipeline.py    : main() / 実行フロー(Hotfix→summary→画像→Discord→Git)

よく触る設定
  config.py の RUN_MODE / RUN_OPTIONS / OUTPUT_BASE_DIR など

RUN_MODE の意味
  pipeline : JSON作成 → アイコンDL(プリウォーム) → 画像生成
  images   : JSON作成 → 画像生成
  prewarm  : JSON作成 → アイコンDLのみ
  json     : JSON作成のみ
  dryrun   : 何もしない

注意
  - パスは環境依存です。必要なら config.py で変更してください。
  - BR.py は SyStem Update を sys.path に追加してから pipeline を呼びます。
  - 対話入力を無効にする場合は環境変数 BR_INTERACTIVE=0 を設定してください。
