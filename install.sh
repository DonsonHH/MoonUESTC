#!/usr/bin/env bash
# MoonUESTC installer: configuration, initialization and health-checked startup.
set -Eeuo pipefail
umask 077
cd -- "$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASSUME_YES=0
SKIP_PULL=0
SKIP_ADMIN=0
usage() {
  cat <<'HELP'
Usage: bash install.sh [--yes] [--skip-pull] [--skip-admin]
  --yes         Reuse an existing .env without configuration prompts.
  --skip-pull   Use a locally loaded image (offline installation).
  --skip-admin  Leave first administrator initialization for a later CLI step.
No account passwords are accepted through arguments or environment variables.
HELP
}
fail() { printf '错误：%s\n' "$*" >&2; exit 1; }
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=1 ;;
    --skip-pull) SKIP_PULL=1 ;;
    --skip-admin) SKIP_ADMIN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; fail "未知参数：$arg" ;;
  esac
done
command -v docker >/dev/null 2>&1 || fail '未找到 Docker。请先通过 NAS 应用中心或 Docker 官方渠道安装。'
docker info >/dev/null 2>&1 || fail '无法访问 Docker。请检查服务是否启动及当前用户权限。'
docker compose version >/dev/null 2>&1 || fail '需要 Docker Compose v2。'
compose_help="$(docker compose up --help)"
[[ "$compose_help" == *--wait* ]] || fail '当前 Compose 不支持 --wait，请更新 Compose v2。'
if [[ ! -f .env ]]; then
  (( ASSUME_YES == 0 )) || fail '非交互安装需要现成的 .env，请参考 .env.example。'
  printf 'MoonUESTC v0.4.1 首次配置\n公网访问请使用已有 HTTPS 反向代理；局域网可使用私有 IP 的 HTTP。\n'
  read -r -p '主机后端端口 [8088]：' port
  port="${port:-8088}"
  [[ "$port" =~ ^[0-9]+$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || fail '端口应为 1–65535。'
  read -r -p '浏览器访问地址（如 http://192.168.1.10:8088 或 https://你的IP或域名:8443）：' public_url
  url_pattern='^https?://[A-Za-z0-9][A-Za-z0-9._:-]*/?$'
  [[ "$public_url" =~ $url_pattern ]] || fail '请输入不带路径、参数或空格的 HTTP/HTTPS 地址；IPv6 请手动填写 .env。'
  if [[ "$public_url" == https://* ]]; then
    bind_address=127.0.0.1; allow_http=0
  else
    bind_address=0.0.0.0; allow_http=1
  fi
  if (( EUID == 0 )); then uid=10001; gid=10001; else uid="$(id -u)"; gid="$(id -g)"; fi
  (
    set -o noclobber
    printf 'MOON_IMAGE=ghcr.io/horoscope963852/moonuestc:0.4.1\nPUID=%s\nPGID=%s\nMOON_PORT=%s\nMOON_BIND_ADDRESS=%s\nMOON_PUBLIC_URL=%s\nMOON_ALLOW_INSECURE_HTTP=%s\nMOON_DATA_DIR=./data\nMOON_CONFIG_DIR=./config\nCOMPOSE_PROJECT_NAME=moonuestc\n' "$uid" "$gid" "$port" "$bind_address" "$public_url" "$allow_http" > .env
  ) || fail '.env 已存在，未覆盖。'
  chmod 600 .env
fi
# Read plain dotenv values without executing the file as shell code.
get_setting() {
  local value
  value="$(sed -n "s/^$1=//p" .env | head -n 1)"
  value="${value%$'\r'}"
  if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; fi
  printf '%s' "${value:-$2}"
}
uid="$(get_setting PUID 10001)"; gid="$(get_setting PGID 10001)"
[[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] && (( 10#$uid > 0 && 10#$gid > 0 )) || fail 'PUID/PGID 应为非 root 的数字用户/组 ID。'
data_dir="$(get_setting MOON_DATA_DIR ./data)"; config_dir="$(get_setting MOON_CONFIG_DIR ./config)"
for directory in "$data_dir" "$config_dir"; do
  [[ "$directory" != / && "$directory" != . && "$directory" != .. && -n "$directory" ]] || fail '数据目录必须是本项目专用子目录。'
  mkdir -p -- "$directory"
  resolved="$(cd -- "$directory" && pwd -P)"
  [[ "$resolved" != / && "$resolved" != "$PWD" ]] || fail '拒绝将根目录或整个项目目录作为私有数据目录。'
done
if [[ -f "$data_dir/dashboard.sqlite3" ]]; then
  [[ "$(stat -c %u -- "$data_dir/dashboard.sqlite3")" == "$uid" ]] || fail '现有数据库所有者与 PUID 不符，请先按部署文档核对迁移权限。'
fi
if (( EUID == 0 )); then
  chown -- "$uid:$gid" "$data_dir" "$config_dir"
else
  [[ "$uid" == "$(id -u)" && "$gid" == "$(id -g)" ]] || fail '当前用户无法设置指定 PUID/PGID，请使用 sudo 或调整首次配置。'
fi
chmod 700 -- "$data_dir" "$config_dir"
dc() { docker compose "$@"; }
dc config --quiet
[[ "$(get_setting MOON_PUBLIC_URL '')" != *YOUR_* ]] || fail '请先填写真实的 MOON_PUBLIC_URL。'
if (( SKIP_PULL == 0 )); then
  printf '正在拉取发布镜像；现有服务继续运行。\n'
  dc pull moonuestc
fi
# Validate the origin before opening the service or changing stored accounts.
dc run --rm -T --no-deps --entrypoint python moonuestc -c 'import os; from moonuestc.web_app import normalize_origin; normalize_origin(os.environ.get("MOON_PUBLIC_URL"), os.environ.get("MOON_ALLOW_INSECURE_HTTP")=="1"); print("访问地址检查通过。")'
initialized="$(dc run --rm -T --no-deps --entrypoint python moonuestc -c 'import os; os.umask(0o077); from moonuestc.web_store import WebStore; print("ready" if WebStore("/data").initialized() else "new")')"
if [[ "$initialized" == new ]]; then
  if (( SKIP_ADMIN == 0 )); then
    [[ -t 0 ]] || fail '首次管理员需要交互终端。请在终端运行脚本，或稍后使用 init-admin。'
    printf '请创建本系统管理员，密码仅在终端交互输入。\n'
    dc run --rm --no-deps moonuestc init-admin
  else
    printf '尚未初始化管理员。稍后执行：docker compose run --rm moonuestc init-admin\n'
  fi
elif [[ "$initialized" != ready ]]; then
  fail '无法确认管理员初始化状态，未启动或替换服务。'
fi
previous="$(dc ps -q moonuestc)"
previous_image=''
if [[ -n "$previous" ]]; then
  previous_image="$(docker inspect --format '{{.Image}}' "$previous")"
  active_jobs="$(dc exec -T moonuestc python -c 'import sqlite3; db=sqlite3.connect("file:/data/dashboard.sqlite3?mode=ro",uri=True); print(db.execute("SELECT count(*) FROM web_jobs WHERE state IN (?,?)",("queued","running")).fetchone()[0])')"
  [[ "$active_jobs" == 0 ]] || fail '已有学校任务正在排队或执行，请完成后重试升级。'
fi
if ! dc up -d --no-build --wait --wait-timeout 60; then
  if [[ -n "$previous_image" ]]; then
    printf '新版本启动失败，正在恢复之前的镜像。\n' >&2
    MOON_IMAGE="$previous_image" docker compose up -d --no-build --wait --wait-timeout 60 || true
  fi
  fail '启动未通过健康检查，请查看 docker compose logs。'
fi
printf '\n服务已启动。访问：%s\n' "$(get_setting MOON_PUBLIC_URL '')"
printf '学校账号、可信浏览器指纹和位置请在网页中填写。保存账号后先运行只读诊断。\n'
