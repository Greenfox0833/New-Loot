import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from cache import enrich_summary_with_names
from config import (
    DO_HOTFIX,
    ENABLE_ICON_CACHE_PREWARM,
    ENABLE_IMAGE_CREATION,
    MAX_WORKERS,
    PATH_BR_DISCORD,
    PATH_LOOTDATA_DIR,
    PATH_LOOT_SUMMARY,
    PATH_LP_JSON,
    PATH_LT_JSON,
    PATH_MINLIST_JSON,
    PATH_REPO_DIR,
    PATH_VERSION_SAVE_DIR,
    PROFILE_NAME,
    VERSION_PREFIX,
)
from diff_loot_auto import run_latest_diff
from summary import build_br_lootdata_all_tgs, build_summary, load_rows
from tasks import prewarm_icon_cache, worker_task

def get_versioned_filename(prefix, save_dir):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = save_dir / f"{prefix}_{now}.json"
    return str(filename)

def main():
    br_discord = Path(PATH_BR_DISCORD)
    loot_summary_py = Path(PATH_LOOT_SUMMARY)
    version_save_dir = Path(PATH_VERSION_SAVE_DIR)
    lt_json_path = Path(PATH_LT_JSON)
    lp_json_path = Path(PATH_LP_JSON)
    minlist_path = Path(PATH_MINLIST_JSON)

    try:
        print("===== BR: pipeline start =====")

        if DO_HOTFIX:
            subprocess.run(
                [sys.executable, r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/LootPackage変更.py"],
                check=True,
            )
            subprocess.run(
                [sys.executable, r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/LootTier変更.py"],
                check=True,
            )
            print("✓ Hotfix 適用完了")

        rows_lt = load_rows(str(lt_json_path))
        rows_lp = load_rows(str(lp_json_path))
        summary = build_summary(rows_lt, rows_lp)
        try:
            enrich_summary_with_names(summary)
        except Exception:
            pass

        version_save_dir.mkdir(parents=True, exist_ok=True)
        versioned_filename = get_versioned_filename(VERSION_PREFIX, str(version_save_dir))
        Path(versioned_filename).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ まとめJSONを作成: {versioned_filename}")

        br_now = datetime.now().strftime("%Y-%m-%d_%H-%M")
        br_lootdata_dir = Path(PATH_LOOTDATA_DIR)
        br_lootdata_dir.mkdir(parents=True, exist_ok=True)
        br_out = br_lootdata_dir / f"BR_LootData_{br_now}.json"
        br_view = build_br_lootdata_all_tgs(summary)
        Path(br_out).write_text(json.dumps(br_view, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ BR_LootData を作成: {br_out}")

        subprocess.run(
            [sys.executable, str(loot_summary_py), "--scan", str(version_save_dir), "--diff-scan", str(version_save_dir)],
            check=True,
        )
        print("✅ LootSummary 実行完了（抽出→比較）")

        if ENABLE_ICON_CACHE_PREWARM:
            prewarm_icon_cache(summary)
            print("✅ アイコンキャッシュ プリウォーム完了")

        if ENABLE_IMAGE_CREATION:
            try:
                with open(minlist_path, "r", encoding="utf-8") as f:
                    min_items = json.load(f)
                if not isinstance(min_items, list) or not min_items:
                    print(f"[!] MinList が空です: {minlist_path}")
                    return
            except FileNotFoundError:
                print(f"[!] 見つかりません: {minlist_path}")
                return

            DEFAULT_TG = "MinList"
            DEFAULT_WL = "_FromMinList"
            tasks = []
            for rec in min_items:
                ap = (rec or {}).get("AssetPathName")
                if not ap:
                    continue
                from config import resolve_out_dir

                out_dir = resolve_out_dir(DEFAULT_TG, DEFAULT_WL)
                preferred = rec.get("LocalizedName")
                tasks.append((ap, out_dir, None, DEFAULT_TG, DEFAULT_WL, preferred))

            uniq, seen = [], set()
            from export_api import normalize_asset_path

            for ap, od, _txt, tg, wl, preferred in tasks:
                key = (normalize_asset_path(ap), od, tg, wl)
                if key not in seen:
                    seen.add(key)
                    uniq.append((ap, od, None, tg, wl, preferred))

            print(f"[i] 画像化タスク数: {len(uniq)}")

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futs = [ex.submit(worker_task, ap, od, None, tg, wl, preferred) for ap, od, _txt, tg, wl, preferred in uniq]
                for _ in as_completed(futs):
                    pass
            print("✅ 画像生成 完了（MinListベース）")
        else:
            print("ℹ️ ENABLE_IMAGE_CREATION=False のため画像生成はスキップ")

        try:
            diff_result = run_latest_diff(PROFILE_NAME)
            if diff_result is None:
                print("ℹ️ Loot diff: 変更なし（作成スキップ）")
            else:
                out_path, diff = diff_result
                print(
                    f"✅ Loot diff を作成: {out_path} "
                    f"(added={len(diff['added'])} removed={len(diff['removed'])} change={len(diff['change'])})"
                )
        except Exception as e:
            print("[!] Loot diff に失敗:", e)

    except Exception as e:
        print("[!] main 内でエラー:", e)

    finally:
        try:
            if br_discord.exists():
                subprocess.run([sys.executable, str(br_discord)], check=True)
                print("✓ BR_Discord 実行完了")
            else:
                print(f"ℹ️ BR_Discord が見つかりません: {br_discord}")
        except Exception as e:
            print("[!] BR_Discord 実行に失敗:", e)

        try:
            repo_dir = Path(PATH_REPO_DIR)
            subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
            msg = f"BR update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", msg], check=False)
            subprocess.run(["git", "-C", str(repo_dir), "push"], check=True)
            print("✓ GitHub Push 完了")
        except Exception as e:
            print("[!] GitHub Push に失敗:", e)

        print("===== BR: pipeline end =====")
