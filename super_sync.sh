#!/bin/bash

# --- 环境整理 ---
# 再次确保没有隐藏的嵌套 git
find . -mindepth 2 -name ".git" -exec rm -rf {} +

# 配置针对医学大项目的忽略清单
cat > .gitignore <<EOF
# 忽略 iCloud 产生的缓存
.DS_Store
.Trash/
# 忽略大文件
*.pt
*.pth
*.bin
# 忽略 LLaMA-Factory 的运行缓存
LLaMA-Factory/cache/
LLaMA-Factory/data/
EOF

# --- Git 同步逻辑 ---
if [ ! -d ".git" ]; then
    git init
    git remote add origin https://github.com/ziyuchen200410-alt/train-test.git
else
    git remote set-url origin https://github.com/ziyuchen200410-alt/train-test.git
fi

# 确保分支名为 main
git branch -M main

# 先同步远程（处理 README 等）
git pull origin main --rebase

# 提交并推送
git add .
git commit -m "Integrated medical project structure into record folder"
git push -u origin main

echo "✅ 整个 record 文件夹已同步至 GitHub。"
