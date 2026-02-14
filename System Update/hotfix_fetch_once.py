import json
import re
import subprocess
import sys
from pathlib import Path

PY = sys.executable
BASE_DIR = Path(__file__).resolve().parent
LOCAL_OUTDIR = BASE_DIR / "cloudstorage_system"
LOCAL_HOTFIX_INI = BASE_DIR / "Hotfix.ini"
LOCAL_CHANGED_TABLES = BASE_DIR / "changed_tables.json"
LOCAL_NOOP_MESSAGE = BASE_DIR / "_hotfix_noop_message.cmd"

HOTFIX_FETCH = [
    PY,
    r"E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix取得.py",
    "--outdir",
    str(LOCAL_OUTDIR),
    "--hotfix-out",
    str(LOCAL_HOTFIX_INI),
    "--changed-tables-out",
    str(LOCAL_CHANGED_TABLES),
    # 401時に呼ばれても副作用なしで即終了させる
    "--message",
    str(LOCAL_NOOP_MESSAGE),
]

TOKEN_REFRESH_CMD = [
    PY,
    r"E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Token.py",
]

ALL_TOKENS_PATH = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/ALL_tokens.json")


def load_client_token() -> str | None:
    if not ALL_TOKENS_PATH.exists():
        return None
    try:
        data = json.loads(ALL_TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[HOTFIX-ONCE] ALL_tokens.json 読み込み失敗: {e}", file=sys.stderr)
        return None

    token = (
        data.get("eg1account_token")
        or data.get("EG1account_token")
        or data.get("account_token")
        or data.get("client_token")
    )
    if token:
        return token
    return None


def align_client_token_with_preferred() -> bool:
    """
    Hotfix取得.py が client_token を固定参照するため、
    実利用トークン(eg1/account)を client_token に同期して 401 を避ける。
    """
    if not ALL_TOKENS_PATH.exists():
        return False
    try:
        data = json.loads(ALL_TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[HOTFIX-ONCE] ALL_tokens.json 読み込み失敗: {e}", file=sys.stderr)
        return False

    preferred = (
        data.get("eg1account_token")
        or data.get("EG1account_token")
        or data.get("account_token")
        or data.get("client_token")
    )
    if not preferred:
        return False

    if data.get("client_token") == preferred:
        return True

    data["client_token"] = preferred
    try:
        ALL_TOKENS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[HOTFIX-ONCE] ALL_tokens.json 更新失敗: {e}", file=sys.stderr)
        return False

    print("[HOTFIX-ONCE] client_token を有効トークンに同期しました。")
    return True


def run_token_refresh() -> bool:
    print("[HOTFIX-ONCE] Token.py を1回だけ実行してキーを再取得します。")
    p = subprocess.run(TOKEN_REFRESH_CMD, text=True)
    if p.returncode != 0:
        print(f"[HOTFIX-ONCE] Token.py 失敗 rc={p.returncode}", file=sys.stderr)
        return False
    return True


def run_hotfix_fetch() -> subprocess.CompletedProcess[str]:
    print("[HOTFIX-ONCE] Hotfix取得.py を実行します。")
    return subprocess.run(HOTFIX_FETCH, text=True, capture_output=True)


def parse_saved_counts(out: str) -> tuple[int, int] | None:
    m = re.search(r"完了:\s*(\d+)\s*/\s*(\d+)\s*件\s*保存", out)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def is_token_related_failure(rc: int, out: str, err: str) -> bool:
    blob = f"{out}\n{err}"
    if rc in (10, 12):
        return True
    token_markers = [
        "client_token が取得できませんでした",
        "アカウントトークンが取得できませんでした",
        "401",
        "Unauthorized",
    ]
    return any(m in blob for m in token_markers)


def main() -> int:
    refreshed_once = False
    LOCAL_NOOP_MESSAGE.write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")

    if not load_client_token():
        if not run_token_refresh():
            print("[HOTFIX-ONCE] キー再取得に失敗したため終了します。", file=sys.stderr)
            return 1
        refreshed_once = True
        if not load_client_token():
            print("[HOTFIX-ONCE] 再取得後もキーが見つからないため終了します。", file=sys.stderr)
            return 1

    if not align_client_token_with_preferred():
        print("[HOTFIX-ONCE] 有効トークンを準備できないため終了します。", file=sys.stderr)
        return 1

    first = run_hotfix_fetch()
    sys.stdout.write(first.stdout)
    sys.stderr.write(first.stderr)
    first_counts = parse_saved_counts(first.stdout)
    first_zero_saved = bool(first_counts and first_counts[0] == 0 and first_counts[1] > 0)
    if first.returncode in (0, 100) and not first_zero_saved:
        print(f"[HOTFIX-ONCE] 完了 rc={first.returncode}")
        return 0

    if refreshed_once:
        print(
            f"[HOTFIX-ONCE] すでにキー再取得済みのため再試行せず終了 rc={first.returncode}",
            file=sys.stderr,
        )
        return first.returncode

    if not is_token_related_failure(first.returncode, first.stdout, first.stderr):
        print(f"[HOTFIX-ONCE] トークン関連ではない失敗 rc={first.returncode}", file=sys.stderr)
        return first.returncode

    if not run_token_refresh():
        print("[HOTFIX-ONCE] キー再取得に失敗したため終了します。", file=sys.stderr)
        return first.returncode
    refreshed_once = True

    if not load_client_token():
        print("[HOTFIX-ONCE] 再取得後もキーが見つからないため終了します。", file=sys.stderr)
        return first.returncode
    if not align_client_token_with_preferred():
        print("[HOTFIX-ONCE] 再取得後に有効トークンを準備できませんでした。", file=sys.stderr)
        return first.returncode

    print("[HOTFIX-ONCE] Hotfix取得を1回だけ再試行します。")
    second = run_hotfix_fetch()
    sys.stdout.write(second.stdout)
    sys.stderr.write(second.stderr)
    second_counts = parse_saved_counts(second.stdout)
    second_zero_saved = bool(second_counts and second_counts[0] == 0 and second_counts[1] > 0)
    if second.returncode in (0, 100) and not second_zero_saved:
        print(f"[HOTFIX-ONCE] 完了 rc={second.returncode}")
        return 0

    print(f"[HOTFIX-ONCE] 再試行後も失敗 rc={second.returncode}", file=sys.stderr)
    return second.returncode


if __name__ == "__main__":
    raise SystemExit(main())
