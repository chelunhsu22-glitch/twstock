#!/usr/bin/env bash
# 把產生的資料存回儲存庫；若遠端有新提交，以本次產生的資料為準，避免衝突
set -e
MSG="$1"
git config user.name "github-actions"
git config user.email "github-actions@users.noreply.github.com"
for i in 1 2 3 4 5; do
  tar czf /tmp/gen.tgz data docs/data 2>/dev/null || tar czf /tmp/gen.tgz data
  git fetch -q origin main
  git reset -q --hard origin/main
  rm -rf data docs/data
  tar xzf /tmp/gen.tgz
  git add -A data docs/data
  if git diff --cached --quiet; then echo "沒有變更"; exit 0; fi
  git commit -qm "$MSG"
  if git push -q origin HEAD:main; then echo "已存檔：$MSG"; exit 0; fi
  echo "推送失敗，重試 $i"; sleep 10
done
exit 1
