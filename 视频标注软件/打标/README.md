# Absolute JSON Label App

> This legacy README has encoding issues.
> Please use `README_CN.md` as the authoritative documentation.

一个纯前后端本地打标工具，专注做一件事：

- 前端输入一个 JSON 路径。
- 按 JSON 中的 `ref_video_path` / `src_video_path` 播放双视频并打标。
- 每次打标立即保存，支持断点续标。

本项目不包含视频转码逻辑，不修改原始数据集 JSON。

## 1. 环境要求

- Python 3.9+
- 浏览器（Chrome/Edge/Firefox 任一）
- 无第三方 Python 依赖（标准库即可）

## 2. 启动方式

在项目目录运行：

```bash
python app.py
```

默认监听：

- `http://127.0.0.1:8000`

可选环境变量：

- `LABEL_APP_HOST`，默认 `127.0.0.1`
- `LABEL_APP_PORT`，默认 `8000`

例如：

```bash
LABEL_APP_HOST=0.0.0.0 LABEL_APP_PORT=8000 python app.py
```

## 3. 前端怎么用

1. 打开前端页面。
2. 在右上角输入框填写 JSON 绝对路径。
3. 点击“加载”。
4. 使用键盘或按钮打标。

键盘快捷键：

- `Space`：播放/暂停
- `← / →`：上一条/下一条
- `G / B`：标为 good / bad 并立即保存
- `L / S`：在添加/移除任务中，标为 good 并分类为大物体/小物体
- `1 / 2 / 3 / 0`：切换 1x / 2x / 3x / 0.5x

界面会显示：

- 当前样本序号
- Ref/Src 的真实文件路径
- 当前结果文件路径与 Good 文件路径

## 4. 输入 JSON 格式

顶层必须是数组，每一项至少包含：

```json
[
  {
    "ref_video_path": "/abs/path/to/ref.mp4",
    "src_video_path": "/abs/path/to/src.mp4",
    "text": [
      "instruction 1",
      "instruction 2",
      "instruction 3",
      "instruction 4"
    ]
  }
]
```

说明：

- 推荐使用绝对路径。
- 如果写相对路径，会按“JSON 文件所在目录”进行解析。
- 指令优先读取 `text`（数组），也兼容 `instruction_1 ~ instruction_4`。
- 其他字段会原样保留，保存时只新增 `tag`。

## 5. 结果保存规则

每个输入 JSON 会对应一个独立目录：

- `label_results/<json父目录名>_<json文件名>/`

该目录固定包含 3 个文件：

- `labeled_with_tag.json`：完整结果，带 `tag: good/bad`
- 对于添加/移除任务中的 `good` 项，会额外包含 `object_size: large/small`
- `good_only.json`：仅保留 good 项，且移除 `tag`
- `build_good_only.py`：离线重建 `good_only.json` 的脚本

示例：

- 输入：`/root/work/.../人工打标/add_chunk_000_sample.json`
- 输出目录：`label_results/人工打标_add_chunk_000_sample/`

## 6. 断点续标

- 重新加载同一个 JSON 路径时，系统会自动读取对应结果目录下的 `labeled_with_tag.json`。
- 已有 `tag` 会自动回填，不会丢进度。
- 每次 `G/B` 打标后立即落盘，同时刷新 `good_only.json`。

## 7. 代理/前缀路径兼容

如果你是通过类似 `.../proxy/8000/` 的地址访问，当前版本会自动探测 API 基址。

- 页面状态栏会显示当前命中的 API 基址。
- 若加载失败，状态栏会带上实际请求的 API URL，便于排查。

## 8. 常见问题

`样本 0/0 且 404`：

- 通常是 JSON 路径不对或请求被代理前缀改写。
- 先确认输入的是“完整 JSON 文件路径”，不是目录。

`Ref/Src 显示 '-'`：

- 数据尚未加载成功，先看状态栏报错详情。

视频黑屏但路径存在：

- 多数是浏览器不支持该编码。
- 本项目不转码，需自行预处理成浏览器可播放编码（如 H.264）。

Windows 删除历史文件失败（WinError 5）：

- 是系统文件权限问题，不影响新的打标保存逻辑。
