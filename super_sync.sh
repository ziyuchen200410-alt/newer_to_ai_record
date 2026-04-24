#!/bin/zsh

# --- 核心配置 ---
REMOTE_BRANCH="main"
MAX_FILE_SIZE_MB=50 # 预警阈值：超过 50MB 的文件将提醒，超过 100MB 将阻断推送

# --- 逻辑审计 1：预检环境与身份 ---
if [[ -z $(git config user.name) || -z $(git config user.email) ]]; then
    echo "❌ 错误：Git 身份未配置。请先执行 git config --global 指令。"
    exit 1
fi

# --- 逻辑审计 2：检测物理体积，防止同步变慢 ---
# 搜索当前目录下大于 100MB 的文件，排除 .git 目录
LARGE_FILES=$(find . -type f -not -path '*/.*' -size +100M)
if [[ -n "$LARGE_FILES" ]]; then
    echo "⚠️ 严厉警告：检测到以下文件超过 100MB，GitHub 将物理性拒绝此类推送："
    echo "$LARGE_FILES"
    echo "建议将其加入 .gitignore 或移出仓库后再同步。"
    exit 1
fi

# --- 逻辑审计 3：原子化提交 ---
echo "🔄 正在扫描变更并提交本地快照..."
git add .

# 检查是否有实际变更
if git diff --cached --quiet; then
    echo "ℹ️ 无文件要提交，干净的工作区。"
else
    git commit -m "Integrated medical project structure: $(date '+%Y-%m-%d %H:%M:%S')"
fi

# --- 逻辑审计 4：解决同步与变基冲突 ---
echo "🚀 正在从远程拉取并执行变基 (Rebase)..."
# 设置临时代理或网络优化以应对 SSL_ERROR_SYSCALL
git config --global http.postBuffer 524288000

if ! git pull origin $REMOTE_BRANCH --rebase; then
    echo "❌ 错误：自动变基失败。可能存在 README.md 冲突，请手动解决后执行 git rebase --continue。"
    exit 1
fi

# --- 逻辑审计 5：安全推送 ---
echo "⬆️ 正在物理推送至 GitHub..."
if git push origin $REMOTE_BRANCH; then
    echo "---"
    echo "✅ 逻辑闭环完成：record 文件夹已成功同步至 GitHub。"
else
    echo "❌ 错误：推送失败。请检查网络环境或 LibreSSL SSL_connect 状态。"
    exit 1
fi