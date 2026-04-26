import hashlib
import json
import mimetypes
import os
import shutil
import sys
import threading   # 新增：用于多线程并发锁
import time        # 新增：用于防手抖的时间限制
from datetime import datetime  # 新增：用于每日备份
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
RESULTS_DIR = ROOT / "label_results"
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".avi", ".mkv"}
LABEL_FILENAME = "labeled_with_tag.json"
GOOD_FILENAME = "good_only.json"
GOOD_WITH_SIZE_FILENAME = "good_with_object_size.json"
SCRIPT_FILENAME = "build_good_only.py"
OBJECT_SIZE_FIELD = "object_size"

# ---------------------------------------------------------
# 全局保护变量
# ---------------------------------------------------------
FILE_LOCK = threading.Lock()  # 文件读写锁：强制所有保存排队，防止并发写入导致文件清空
LAST_REQUEST_TIME = 0.0       # 记录上一次保存的时间戳
LAST_REQUEST_TAG = None       # 记录上一次保存的动作是 good 还是 bad


def resolve_user_path(raw_path: str) -> Path:
    text = (raw_path or "").strip().strip('"')
    if not text:
        raise ValueError("JSON 路径为空")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    return path


def resolve_video_path(raw_path: str, dataset_path: Path) -> Path:
    text = str(raw_path or "").strip().strip('"')
    if not text:
        raise ValueError("视频路径为空")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (dataset_path.parent / path).resolve()
    else:
        path = path.resolve()
    return path


def load_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def dump_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def safe_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._")
    return cleaned or "dataset"


def output_path_for_dataset(dataset_path: Path) -> Path:
    parent_name = safe_name(dataset_path.parent.name)
    base_name = safe_name(dataset_path.stem)
    bundle_dir = RESULTS_DIR / f"{parent_name}_{base_name}"
    return bundle_dir / LABEL_FILENAME


def build_output_bundle(dataset_path: Path):
    output_path = output_path_for_dataset(dataset_path)
    bundle_dir = output_path.parent
    good_path = bundle_dir / GOOD_FILENAME
    good_with_size_path = bundle_dir / GOOD_WITH_SIZE_FILENAME
    script_path = bundle_dir / SCRIPT_FILENAME
    return bundle_dir, output_path, good_path, good_with_size_path, script_path


def legacy_output_paths_for_dataset(dataset_path: Path):
    digest = hashlib.sha1(str(dataset_path).lower().encode("utf-8")).hexdigest()[:10]
    base = safe_name(dataset_path.stem)
    old_hash_bundle_file = RESULTS_DIR / f"{base}_{digest}" / LABEL_FILENAME
    old_flat_file = RESULTS_DIR / f"{base}_{digest}_labeled.json"
    return [old_hash_bundle_file, old_flat_file]


def build_good_only_data(labeled_data):
    good = []
    for row in labeled_data:
        if row.get("tag") == "good":
            item = dict(row)
            item.pop("tag", None)
            legacy_size = item.pop("good_size_tag", None)
            if legacy_size and OBJECT_SIZE_FIELD not in item:
                item[OBJECT_SIZE_FIELD] = legacy_size
            good.append(item)
    return good


def update_good_only_json(labeled_data, good_path: Path):
    dump_json(good_path, build_good_only_data(labeled_data))


def build_good_with_size_data(labeled_data):
    sized_good = []
    for row in labeled_data:
        if row.get("tag") != "good":
            continue
        size = normalize_object_size(row.get(OBJECT_SIZE_FIELD) or row.get("good_size_tag"))
        if size not in {"large", "small"}:
            continue
        item = dict(row)
        item.pop("tag", None)
        item.pop("good_size_tag", None)
        item[OBJECT_SIZE_FIELD] = size
        sized_good.append(item)
    return sized_good


def dataset_requires_object_size(items, dataset_path: Path):
    for row in items:
        if isinstance(row, dict) and requires_good_size_tag(row, dataset_path):
            return True
    return False


def update_derived_jsons(labeled_data, dataset_path: Path, good_path: Path, good_with_size_path: Path):
    update_good_only_json(labeled_data, good_path)
    if dataset_requires_object_size(labeled_data, dataset_path):
        dump_json(good_with_size_path, build_good_with_size_data(labeled_data))
    elif good_with_size_path.exists():
        good_with_size_path.unlink()


def ensure_output_script(script_path: Path):
    content = """import json
from pathlib import Path

INPUT_FILE = Path("labeled_with_tag.json")
OUTPUT_FILE = Path("good_only.json")
OUTPUT_SIZE_FILE = Path("good_with_object_size.json")


def normalize_object_size(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    mapping = {
        "large": "large",
        "big": "large",
        "small": "small",
        "tiny": "small",
    }
    return mapping.get(text)


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(f"Missing {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    good = []
    sized_good = []
    for item in data:
        if item.get("tag") == "good":
            row = dict(item)
            row.pop("tag", None)
            if "good_size_tag" in row and "object_size" not in row:
                row["object_size"] = row.pop("good_size_tag")
            size = normalize_object_size(row.get("object_size"))
            if size:
                row["object_size"] = size
                sized_good.append(dict(row))
            good.append(row)
    OUTPUT_FILE.write_text(json.dumps(good, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_SIZE_FILE.write_text(json.dumps(sized_good, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(good)} items to {OUTPUT_FILE}")
    print(f"Wrote {len(sized_good)} items to {OUTPUT_SIZE_FILE}")


if __name__ == "__main__":
    main()
"""
    script_path.write_text(content, encoding="utf-8")


def merge_existing_tags(source_items, labeled_items):
    merged = [dict(item) for item in source_items]
    for idx, row in enumerate(labeled_items):
        if idx >= len(merged):
            break
        tag = row.get("tag")
        if tag in {"good", "bad"}:
            merged[idx]["tag"] = tag
        size = normalize_object_size(row.get(OBJECT_SIZE_FIELD) or row.get("good_size_tag"))
        if size:
            merged[idx][OBJECT_SIZE_FIELD] = size
    return merged


def normalize_object_size(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    mapping = {
        "large": "large",
        "big": "large",
        "大": "large",
        "大物体": "large",
        "small": "small",
        "tiny": "small",
        "小": "small",
        "小物体": "small",
    }
    return mapping.get(text)


def requires_good_size_tag(item, dataset_path: Path):
    blob = " ".join(
        [
            str(dataset_path).lower(),
            str(item.get("ref_video_path", "")).lower(),
            str(item.get("src_video_path", "")).lower(),
            str(item.get("raw_task_type", "")).lower(),
            str(item.get("edit_type", "")).lower(),
        ]
    )

    add_tokens = ["\\add\\", "/add/", "add_", "_add", "object addition", "addition"]
    delete_tokens = ["\\delete\\", "/delete/", "delete_", "_delete", "object removal", "removal", "deletion"]
    return any(token in blob for token in add_tokens + delete_tokens)


def row_is_completed(row, dataset_path: Path):
    tag = row.get("tag")
    if tag == "bad":
        return True
    if tag != "good":
        return False
    if requires_good_size_tag(row, dataset_path):
        return normalize_object_size(row.get(OBJECT_SIZE_FIELD)) in {"large", "small"}
    return True


def first_unlabeled_index(items, dataset_path: Path):
    for idx, row in enumerate(items):
        if not row_is_completed(row, dataset_path):
            return idx
    return max(len(items) - 1, 0)


def completed_count(items, dataset_path: Path):
    return sum(1 for row in items if row_is_completed(row, dataset_path))


def extract_instructions(item):
    if isinstance(item.get("text"), list):
        values = [str(x).strip() for x in item["text"] if str(x).strip()]
        if values:
            return values[:4]

    candidates = []
    for key in ("instruction_1", "instruction_2", "instruction_3", "instruction_4"):
        value = item.get(key)
        if value is not None and str(value).strip():
            candidates.append(str(value).strip())
    if candidates:
        return candidates[:4]

    fallback = item.get("instruction") or item.get("prompt")
    if fallback is not None and str(fallback).strip():
        return [str(fallback).strip()]
    return []


def parse_byte_range(range_header: str, file_size: int):
    if not range_header:
        return None
    if not range_header.startswith("bytes="):
        return "invalid"
    value = range_header[len("bytes=") :].strip()
    if "," in value or "-" not in value:
        return "invalid"
    start_raw, end_raw = value.split("-", 1)
    try:
        if start_raw == "":
            if end_raw == "":
                return "invalid"
            length = int(end_raw)
            if length <= 0:
                return "invalid"
            start = max(file_size - length, 0)
            end = file_size - 1
        else:
            start = int(start_raw)
            end = file_size - 1 if end_raw == "" else int(end_raw)
        if start < 0 or end < 0 or start > end or start >= file_size:
            return "invalid"
        end = min(end, file_size - 1)
        return start, end
    except ValueError:
        return "invalid"


class AppHandler(SimpleHTTPRequestHandler):
    @staticmethod
    def route_matches(path: str, endpoint: str) -> bool:
        clean = (path or "").rstrip("/")
        return clean == endpoint or clean.endswith(endpoint)

    @staticmethod
    def looks_like_prefixed_index(path: str) -> bool:
        return (path or "").endswith("/")

    def end_headers(self):
        parsed = urlparse(getattr(self, "path", "") or "")
        suffix = Path(parsed.path).suffix.lower()
        if parsed.path == "/" or suffix in {".html", ".js", ".css"}:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        parsed = urlparse(path)
        clean = parsed.path.lstrip("/")
        if clean == "":
            clean = "index.html"
        else:
            candidate = STATIC_DIR / clean
            if not candidate.exists() and "/" in clean:
                tail = clean.split("/")[-1]
                tail_candidate = STATIC_DIR / tail
                if tail_candidate.exists():
                    clean = tail
        return str((STATIC_DIR / clean).resolve())

    def guess_type(self, path):
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type or "application/octet-stream"

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_video_file(self, video_path: Path, head_only: bool):
        file_size = video_path.stat().st_size
        byte_range = parse_byte_range(self.headers.get("Range", ""), file_size)
        if byte_range == "invalid":
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return

        mime_type = mimetypes.guess_type(str(video_path))[0] or "application/octet-stream"
        if byte_range is None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if head_only:
                return
            with video_path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        start, end = byte_range
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        if head_only:
            return

        remaining = length
        with video_path.open("rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def handle_video(self, query: str, head_only: bool):
        params = parse_qs(query)
        raw_path = params.get("path", [None])[0]
        if not raw_path:
            return self.send_json({"error": "缺少视频路径参数 path"}, HTTPStatus.BAD_REQUEST)
        try:
            video_path = resolve_user_path(unquote(raw_path))
        except Exception as exc:
            return self.send_json({"error": f"视频路径无效: {exc}"}, HTTPStatus.BAD_REQUEST)

        if not video_path.exists() or not video_path.is_file():
            return self.send_json({"error": f"视频不存在: {video_path}"}, HTTPStatus.NOT_FOUND)
        return self.send_video_file(video_path, head_only=head_only)

    def handle_dataset(self, query: str):
        params = parse_qs(query)
        raw_path = params.get("path", [None])[0]
        if not raw_path:
            return self.send_json({"error": "缺少数据集路径参数 path"}, HTTPStatus.BAD_REQUEST)

        try:
            dataset_path = resolve_user_path(unquote(raw_path))
        except Exception as exc:
            return self.send_json({"error": f"JSON 路径无效: {exc}"}, HTTPStatus.BAD_REQUEST)

        if not dataset_path.exists() or not dataset_path.is_file():
            return self.send_json({"error": f"JSON 文件不存在: {dataset_path}"}, HTTPStatus.NOT_FOUND)

        try:
            source_items = load_json(dataset_path)
        except Exception as exc:
            return self.send_json({"error": f"读取 JSON 失败: {exc}"}, HTTPStatus.BAD_REQUEST)

        if not isinstance(source_items, list):
            return self.send_json({"error": "JSON 顶层必须是数组(list)"}, HTTPStatus.BAD_REQUEST)

        bundle_dir, output_path, good_path, good_with_size_path, script_path = build_output_bundle(dataset_path)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        ensure_output_script(script_path)
        
        # 修复读取历史数据崩溃时不报错的 Bug
        if output_path.exists():
            try:
                labeled = load_json(output_path)
                source_items = merge_existing_tags(source_items, labeled)
            except Exception as e:
                print(f"❌ 读取历史记录失败，文件可能已损坏，报错: {e}")
        else:
            for legacy_path in legacy_output_paths_for_dataset(dataset_path):
                if legacy_path.exists():
                    try:
                        labeled = load_json(legacy_path)
                        source_items = merge_existing_tags(source_items, labeled)
                        break
                    except Exception:
                        continue

        update_derived_jsons(source_items, dataset_path, good_path, good_with_size_path)

        normalized = []
        for idx, item in enumerate(source_items):
            if not isinstance(item, dict):
                return self.send_json({"error": f"第 {idx + 1} 条不是对象(dict)"}, HTTPStatus.BAD_REQUEST)

            if "ref_video_path" not in item or "src_video_path" not in item:
                return self.send_json(
                    {"error": f"第 {idx + 1} 条缺少 ref_video_path 或 src_video_path"},
                    HTTPStatus.BAD_REQUEST,
                )

            try:
                ref_abs = resolve_video_path(item.get("ref_video_path"), dataset_path)
                src_abs = resolve_video_path(item.get("src_video_path"), dataset_path)
            except Exception as exc:
                return self.send_json({"error": f"第 {idx + 1} 条视频路径无效: {exc}"}, HTTPStatus.BAD_REQUEST)

            row = dict(item)
            row["instructions"] = extract_instructions(item)
            row["ref_video_path"] = str(ref_abs)
            row["src_video_path"] = str(src_abs)
            row["ref_video_url"] = "api/video?path=" + quote(str(ref_abs), safe=":/\\._-")
            row["src_video_url"] = "api/video?path=" + quote(str(src_abs), safe=":/\\._-")
            row["ref_video_exists"] = ref_abs.exists()
            row["src_video_exists"] = src_abs.exists()
            
            # --- 恢复掩码图（diff）生成逻辑 ---
                         # --- 核心逻辑更正：掩码检索优先级 ---
            diff_folder = src_abs.parent.with_name("diff")
            
            # --- 核心修改：掩码图（diff）检索逻辑 ---
            # 不要用 src_abs.stem，改用 ref_abs.stem
            mask_abs = src_abs.parent.with_name("diff") / f"{ref_abs.stem}.jpg"

            # 增加一个兼容性判断（万一某些旧掩码还是以 src 命名的）
            if not mask_abs.exists():
                mask_abs = src_abs.parent.with_name("diff") / f"{src_abs.stem}.jpg"

            row["mask_url"] = "api/video?path=" + quote(str(mask_abs), safe=":/\\._-")
            row["mask_exists"] = mask_abs.exists()
            # ----------------------------------
            
            row[OBJECT_SIZE_FIELD] = normalize_object_size(row.get(OBJECT_SIZE_FIELD) or row.get("good_size_tag"))
            row["requires_good_size_tag"] = requires_good_size_tag(row, dataset_path)
            normalized.append(row)

        return self.send_json(
            {
                "dataset_path": str(dataset_path),
                "output_path": str(output_path),
                "output_dir": str(output_path.parent),
                "good_path": str(good_path),
                "good_with_size_path": str(good_with_size_path) if good_with_size_path.exists() else "",
                "script_path": str(script_path),
                "items": normalized,
                "total": len(normalized),
                "completed": completed_count(normalized, dataset_path),
                "next_index": first_unlabeled_index(normalized, dataset_path),
            }
        )

    def handle_save_label(self):
        global LAST_REQUEST_TIME, LAST_REQUEST_TAG
        
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            dataset_path = resolve_user_path(payload.get("dataset_path"))
            index = int(payload.get("index"))
            tag = str(payload.get("tag")).lower()
            object_size = normalize_object_size(payload.get(OBJECT_SIZE_FIELD) or payload.get("good_size_tag"))
        except Exception as exc:
            return self.send_json({"error": f"请求格式错误: {exc}"}, HTTPStatus.BAD_REQUEST)

        if tag not in {"good", "bad"}:
            return self.send_json({"error": "tag 只能是 good 或 bad"}, HTTPStatus.BAD_REQUEST)
        if not dataset_path.exists():
            return self.send_json({"error": f"JSON 不存在: {dataset_path}"}, HTTPStatus.NOT_FOUND)

        # -----------------------------------------------------------------
        # 1. 防手抖限制 (0.15秒)
        # -----------------------------------------------------------------
        current_time = time.time()
        is_g_then_ls = (
            tag == "good" and 
            object_size in {"large", "small"} and 
            LAST_REQUEST_TAG == "good"
        )
        
        if not is_g_then_ls and (current_time - LAST_REQUEST_TIME < 0.15):
            return self.send_json(
                {"error": "操作太快啦！为防止数据覆盖请间隔 0.15 秒再按"}, 
                HTTPStatus.TOO_MANY_REQUESTS
            )
            
        LAST_REQUEST_TIME = current_time
        LAST_REQUEST_TAG = tag

        # -----------------------------------------------------------------
        # 2. 全局文件锁保护写入
        # -----------------------------------------------------------------
        with FILE_LOCK:
            try:
                source_items = load_json(dataset_path)
                if not isinstance(source_items, list):
                    raise ValueError("JSON 顶层必须是数组(list)")
                bundle_dir, output_path, good_path, good_with_size_path, script_path = build_output_bundle(dataset_path)
                bundle_dir.mkdir(parents=True, exist_ok=True)
                ensure_output_script(script_path)
                
                if output_path.exists():
                    try:
                        labeled = load_json(output_path)
                        source_items = merge_existing_tags(source_items, labeled)
                    except Exception as e:
                        # 强拦截：文件损坏不允许继续存，防止清空数据
                        raise RuntimeError(f"历史记录文件损坏，已拦截保存防止清空数据！报错: {e}")
                else:
                    for legacy_path in legacy_output_paths_for_dataset(dataset_path):
                        if legacy_path.exists():
                            try:
                                labeled = load_json(legacy_path)
                                source_items = merge_existing_tags(source_items, labeled)
                                break
                            except Exception:
                                continue

                if index < 0 or index >= len(source_items):
                    return self.send_json({"error": "index 超出范围"}, HTTPStatus.BAD_REQUEST)

                row = dict(source_items[index])
                if tag == "good" and requires_good_size_tag(row, dataset_path):
                    if object_size not in {"large", "small"}:
                        return self.send_json(
                            {"error": "当前样本属于添加/移除任务，good 标签必须选择 object_size=large 或 small"},
                            HTTPStatus.BAD_REQUEST,
                        )
                row["tag"] = tag
                if tag == "bad":
                    row.pop(OBJECT_SIZE_FIELD, None)
                    row.pop("good_size_tag", None)
                elif object_size in {"large", "small"}:
                    row[OBJECT_SIZE_FIELD] = object_size
                source_items[index] = row
                
                # -----------------------------------------------------------------
                # 3. 写入前的双重自动备份
                # -----------------------------------------------------------------
                if output_path.exists():
                    try:
                        bak_path = output_path.with_name(output_path.name + ".bak")
                        shutil.copy2(output_path, bak_path)
                        
                        backup_dir = output_path.parent / "backups"
                        backup_dir.mkdir(exist_ok=True)
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        daily_backup_path = backup_dir / f"labeled_{today_str}.json"
                        shutil.copy2(output_path, daily_backup_path)
                    except Exception as e:
                        print(f"⚠️ 自动备份遇到权限或IO小问题，不影响主线: {e}")

                dump_json(output_path, source_items)
                update_derived_jsons(source_items, dataset_path, good_path, good_with_size_path)

                return self.send_json(
                    {
                        "ok": True,
                        "output_path": str(output_path),
                        "output_dir": str(output_path.parent),
                        "good_path": str(good_path),
                        "good_with_size_path": str(good_with_size_path) if good_with_size_path.exists() else "",
                        "script_path": str(script_path),
                        "completed": completed_count(source_items, dataset_path),
                        "next_index": first_unlabeled_index(source_items, dataset_path),
                    }
                )
            except Exception as exc:
                return self.send_json({"error": f"保存失败: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if self.route_matches(parsed.path, "/api/video"):
            return self.handle_video(parsed.query, head_only=True)
        return super().do_HEAD()

    def do_GET(self):
        parsed = urlparse(self.path)
        if self.route_matches(parsed.path, "/api/dataset"):
            return self.handle_dataset(parsed.query)
        if self.route_matches(parsed.path, "/api/video"):
            return self.handle_video(parsed.query, head_only=False)
        if self.route_matches(parsed.path, "/api/health"):
            return self.send_json({"ok": True})
        if parsed.path == "/" or self.looks_like_prefixed_index(parsed.path):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if self.route_matches(parsed.path, "/api/save-label"):
            return self.handle_save_label()
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API")


def main():
    host = os.environ.get("LABEL_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("LABEL_APP_PORT", "8000"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Label app started: http://{host}:{port}")
    print(f"Results dir: {RESULTS_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()