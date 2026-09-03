import json
import os
import subprocess
import sys
import time
import traceback
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMMON_DIR = BASE_DIR.parent
PROJECT_ROOT = COMMON_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(COMMON_DIR) not in sys.path:
    sys.path.append(str(COMMON_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

WEB_LOOTPOOL_NAME = "Juno_Tabasco_LootPool.json"

# Ensure child scripts use Juno_Tabasco profile
os.environ["SYSTEM_PROFILE"] = "Juno_Tabasco"

from cache import build_item_metadata_index, enrich_summary_with_names, upsert_item_metadata_file
from config import (
    DO_HOTFIX,
    ENABLE_ICON_CACHE_PREWARM,
    ENABLE_IMAGE_CREATION,
    LOG_EVERY,
    LOG_LEVEL,
    MAX_WORKERS,
    PATH_LOOTDATA_DIR,
    PATH_LOOT_SUMMARY,
    PATH_LP_JSON,
    PATH_LT_JSON,
    PATH_MINLIST_JSON,
    PATH_REPO_DIR,
    PATH_HOTFIX_LP,
    PATH_HOTFIX_LT,
    PATH_VERSION_SAVE_DIR,
    PROFILE_NAME,
    VERSION_PREFIX,
)
from diff_loot_auto import get_web_lootpool_path, run_diff_data
from new_item_images import copy_new_item_images
from summary import build_br_lootdata_all_tgs, build_summary, load_rows
from tasks import prewarm_icon_cache, worker_task


def _setup_logger():
    log_dir = Path(__file__).resolve().parent / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pipeline_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    logger = logging.getLogger("pipeline_Juno_Tabasco")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("log file: %s", log_path)
    return logger

def get_versioned_filename(prefix, save_dir):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = save_dir / f"{prefix}_{now}.json"
    return str(filename)

def main():
    logger = _setup_logger()
    loot_summary_py = Path(PATH_LOOT_SUMMARY)
    version_save_dir = Path(PATH_VERSION_SAVE_DIR)
    lt_json_path = Path(PATH_LT_JSON)
    lp_json_path = Path(PATH_LP_JSON)
    minlist_path = Path(PATH_MINLIST_JSON)

    try:
        logger.info("===== Juno_Tabasco: pipeline start =====")
        logger.info("paths: lt=%s lp=%s minlist=%s", lt_json_path, lp_json_path, minlist_path)
        logger.info("output: summary=%s lootdata=%s", version_save_dir, PATH_LOOTDATA_DIR)
        logger.info("flags: hotfix=%s prewarm=%s image=%s workers=%s", DO_HOTFIX, ENABLE_ICON_CACHE_PREWARM, ENABLE_IMAGE_CREATION, MAX_WORKERS)

        if DO_HOTFIX:
            logger.info("hotfix start: %s", PATH_HOTFIX_LP)
            hotfix_start = time.time()
            res_lp = subprocess.run(
                [sys.executable, str(Path(PATH_HOTFIX_LP))],
                check=True,
                capture_output=True,
                text=True,
            )
            if res_lp.stdout:
                logger.info("hotfix lp stdout: %s", res_lp.stdout.strip())
            if res_lp.stderr:
                logger.warning("hotfix lp stderr: %s", res_lp.stderr.strip())

            logger.info("hotfix start: %s", PATH_HOTFIX_LT)
            res_lt = subprocess.run(
                [sys.executable, str(Path(PATH_HOTFIX_LT))],
                check=True,
                capture_output=True,
                text=True,
            )
            if res_lt.stdout:
                logger.info("hotfix lt stdout: %s", res_lt.stdout.strip())
            if res_lt.stderr:
                logger.warning("hotfix lt stderr: %s", res_lt.stderr.strip())

            logger.info("✓ Hotfix 適用完了 (%.2fs)", time.time() - hotfix_start)

        t0 = time.time()
        logger.info("load lt: %s", lt_json_path)
        rows_lt = load_rows(str(lt_json_path))
        logger.info("load lp: %s", lp_json_path)
        rows_lp = load_rows(str(lp_json_path))
        logger.info("load done (%.2fs)", time.time() - t0)

        logger.info("build summary start")
        t0 = time.time()
        summary = build_summary(rows_lt, rows_lp)
        logger.info("build summary done (%.2fs)", time.time() - t0)
        try:
            logger.info("enrich summary with names start")
            t0 = time.time()
            enrich_summary_with_names(summary)
            logger.info("enrich summary done (%.2fs)", time.time() - t0)
        except Exception:
            logger.warning("enrich summary failed: %s", traceback.format_exc().strip())

        version_save_dir.mkdir(parents=True, exist_ok=True)
        versioned_filename = get_versioned_filename(VERSION_PREFIX, str(version_save_dir))
        Path(versioned_filename).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("✅ まとめJSONを作成: %s", versioned_filename)

        logger.info("build item metadata start")
        t0 = time.time()
        item_metadata_filename = COMMON_DIR / "shared" / "cache" / "item_metadata.json"
        upsert_item_metadata_file(str(item_metadata_filename), PROFILE_NAME, build_item_metadata_index(summary))
        logger.info("✅ アイテム名・説明・タグJSONを更新: %s (%.2fs)", item_metadata_filename, time.time() - t0)

        br_now = datetime.now().strftime("%Y-%m-%d_%H-%M")
        br_lootdata_dir = Path(PATH_LOOTDATA_DIR)
        br_lootdata_dir.mkdir(parents=True, exist_ok=True)
        br_out = br_lootdata_dir / f"{PROFILE_NAME}_LootData_{br_now}.json"
        logger.info("build BR_LootData start")
        t0 = time.time()
        br_view = build_br_lootdata_all_tgs(summary)
        logger.info("build BR_LootData done (%.2fs)", time.time() - t0)
        Path(br_out).write_text(json.dumps(br_view, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("✅ BR_LootData を作成: %s", br_out)
        # Gitで共有されているWeb公開データを、今回の差分比較元として保持する。
        previous_web_data = None
        try:
            web_out = get_web_lootpool_path(PROFILE_NAME, WEB_LOOTPOOL_NAME)
            if web_out.exists():
                previous_web_data = json.loads(web_out.read_text(encoding="utf-8-sig"))
            web_out.parent.mkdir(parents=True, exist_ok=True)
            web_out.write_text(json.dumps(br_view, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("✅ Web LootPool を更新: %s", web_out)
        except Exception:
            logger.warning("Web LootPool 更新に失敗: %s", traceback.format_exc().strip())

        logger.info("LootSummary start: %s", loot_summary_py)
        t0 = time.time()
        res_sum = subprocess.run(
            [sys.executable, str(loot_summary_py), "--scan", str(version_save_dir), "--diff-scan", str(version_save_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        if res_sum.stdout:
            logger.info("LootSummary stdout: %s", res_sum.stdout.strip())
        if res_sum.stderr:
            logger.warning("LootSummary stderr: %s", res_sum.stderr.strip())
        logger.info("✅ LootSummary 実行完了（抽出→比較） (%.2fs)", time.time() - t0)

        if ENABLE_ICON_CACHE_PREWARM:
            logger.info("prewarm start")
            t0 = time.time()
            prewarm_icon_cache(summary)
            logger.info("✅ アイコンキャッシュ プリウォーム完了 (%.2fs)", time.time() - t0)

        if ENABLE_IMAGE_CREATION:
            try:
                with open(minlist_path, "r", encoding="utf-8") as f:
                    min_items = json.load(f)
                if not isinstance(min_items, list) or not min_items:
                    logger.warning("MinList が空です: %s", minlist_path)
                    return
            except FileNotFoundError:
                logger.warning("MinList が見つかりません: %s", minlist_path)
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

            logger.info("画像化タスク数: %s", len(uniq))

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futs = [ex.submit(worker_task, ap, od, None, tg, wl, preferred) for ap, od, _txt, tg, wl, preferred in uniq]
                done = 0
                total = len(futs)
                for fut in as_completed(futs):
                    done += 1
                    try:
                        fut.result()
                    except Exception:
                        logger.warning("worker failed: %s", traceback.format_exc().strip())
                    if done == 1 or done % max(1, LOG_EVERY) == 0 or done == total:
                        logger.info("画像生成 進捗: %s/%s", done, total)
            logger.info("✅ 画像生成 完了（MinListベース）")
        else:
            logger.info("ℹ️ ENABLE_IMAGE_CREATION=False のため画像生成はスキップ")

        try:
            diff_result = run_diff_data(PROFILE_NAME, previous_web_data, br_view)
            if diff_result is None:
                logger.info("✅ Loot diff: 変更なし（作成スキップ）")
            else:
                out_path, diff = diff_result
                logger.info(
                    "✅ Loot diff を作成: %s (added=%s removed=%s change=%s)",
                    out_path,
                    len(diff["added"]),
                    len(diff["removed"]),
                    len(diff["change"]),
                )

                from config import resolve_out_dir

                new_item_dir, copied_count, missing_count = copy_new_item_images(
                    PROFILE_NAME,
                    diff,
                    Path(resolve_out_dir("MinList", "_FromMinList")),
                    minlist_path,
                )
                if copied_count > 0 and new_item_dir is not None:
                    logger.info("✅ AddedItems 画像を保存: %s (copied=%s missing=%s)", new_item_dir, copied_count, missing_count)
                else:
                    logger.info("ℹ️ AddedItems 画像の追加対象なし (copied=%s missing=%s)", copied_count, missing_count)
        except Exception:
            logger.warning("Loot diff に失敗: %s", traceback.format_exc().strip())
    except Exception as e:
        logger.error("[!] main 内でエラー: %s", e)
        logger.error(traceback.format_exc().strip())

    finally:

        try:
            repo_dir = Path(PATH_REPO_DIR)
            logger.info("git add: %s", repo_dir)
            subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True, capture_output=True, text=True)
            msg = f"Juno_Tabasco update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            res_commit = subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", msg], check=False, capture_output=True, text=True)
            if res_commit.stdout:
                logger.info("git commit stdout: %s", res_commit.stdout.strip())
            if res_commit.stderr:
                logger.warning("git commit stderr: %s", res_commit.stderr.strip())
            res_push = subprocess.run(["git", "-C", str(repo_dir), "push"], check=True, capture_output=True, text=True)
            if res_push.stdout:
                logger.info("git push stdout: %s", res_push.stdout.strip())
            if res_push.stderr:
                logger.warning("git push stderr: %s", res_push.stderr.strip())
            logger.info("✓ GitHub Push 完了")
        except Exception as e:
            logger.warning("[!] GitHub Push に失敗: %s", e)
            logger.warning(traceback.format_exc().strip())

        logger.info("===== Juno_Tabasco: pipeline end =====")


if __name__ == "__main__":
    main()
