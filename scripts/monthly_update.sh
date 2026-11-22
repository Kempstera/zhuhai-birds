#!/bin/sh
# 定时入口：给 launchd 调用，也可以手工执行。
#
# 真正的逻辑全在 auto_update.py。这一层只干三件事，都是 launchd 环境下才需要的：
#   1. 补 PATH —— launchd 给的环境只有 /usr/bin:/bin:/usr/sbin:/sbin，node 找不到；
#   2. 找一个装了 jinja2 的 python3 —— 写死版本号会在 WorkBuddy 升级后失效；
#   3. 加锁 —— 手工触发撞上定时任务时，两次部署会互相覆盖产物。
#
# 手工用法：
#   sh scripts/monthly_update.sh            # 该更新就更新
#   sh scripts/monthly_update.sh --dry      # 只看构建和校验
#   sh scripts/monthly_update.sh --force    # 强制重建

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LOG=/var/tmp/zhuhai-birds-auto-update.log
LOCK=/var/tmp/zhuhai-birds-auto-update.lock

if ! mkdir "$LOCK" 2>/dev/null; then
  # 锁超过 30 分钟当作上次崩溃的残留（正常一次跑不到 2 分钟）
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已有任务在跑，本次跳过。" >> "$LOG"
    exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="${LANG:-zh_CN.UTF-8}"

PY=""
for c in "$HOME/.workbuddy/binaries/python/versions/"*/bin/python3 \
         /usr/local/bin/python3 /usr/bin/python3; do
  [ -x "$c" ] || continue
  if "$c" -c "import jinja2" 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 找不到带 jinja2 的 python3，已放弃。" >> "$LOG"
  exit 1
fi

cd "$PROJ" || exit 1
"$PY" "$PROJ/scripts/auto_update.py" "$@"
exit $?
