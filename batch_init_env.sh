#!/usr/bin/env bash

# 将上面内容粘贴进去并保存
# source /etc/network_turbo
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/run_optimizer.sh
# ~/batch_init_env.sh 5 3 1
# 或者
# ~/batch_init_env.sh lude_100_150_hold5_fac3_num1
# 或者
# 切换conda 并初始化pip 环境
# while read h f n; do    ~/batch_init_env.sh "$h" "$f" "$n";  done < ~/batch_init_env_param.txt
# 跳过conda
# while read h f n; do    ~/batch_init_env.sh -n "$h" "$f" "$n";  done < ~/batch_init_env_param.txt
set -euo pipefail

# —— 先做 Git 协议层面优化 —— #
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000

# —— 配置区 —— #
BASE_DIR="/root/autodl-tmp"                                # 所有项目目录的根目录
REPO_URL="https://github.com/soulZhaoL/lude.git"                  # 仓库地址
PQ_SOURCE="/root/*.pq"                                     # .pq 文件来源
CONDA_BASE="$(conda info --base)"                          # conda 安装根目录
CONDA_PREFIX="lude_100_150"                                # conda 环境名前缀
# PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"   # pip 镜像地址
PIP_INDEX_URL="https://mirrors.cloud.tencent.com/pypi/simple/"   # pip 镜像地址
# ================ #

usage() {
  cat <<EOF
Usage:
  $0 [--skip-conda|-n] hold fac num
  $0 [--skip-conda|-n] lude_100_150_hold<hold>_fac<fac>_num<num>

Options:
  --skip-conda, -n   跳过 Conda 环境激活

Examples:
  # 激活环境（默认行为）
  $0 5 3 1
  # 跳过激活
  $0 --skip-conda 5 3 1
  $0 -n lude_100_150_hold5_fac3_num1
EOF
  exit 1
}

# ——— 参数预解析 ——— #
SKIP_CONDA=false
if [[ "${1-}" == "--skip-conda" || "${1-}" == "-n" ]]; then
  SKIP_CONDA=true
  shift
fi

# ——— 参数解析 ——— #
if [ $# -eq 3 ]; then
  HOLD="$1"; FAC="$2"; NUM="$3"
elif [ $# -eq 1 ] && [[ "$1" =~ hold([0-9]+)_fac([0-9]+)_num([0-9]+) ]]; then
  HOLD="${BASH_REMATCH[1]}"
  FAC="${BASH_REMATCH[2]}"
  NUM="${BASH_REMATCH[3]}"
else
  usage
fi

# ——— 路径设置 ——— #
DIR="${BASE_DIR}/lude_100_150_hold${HOLD}_fac${FAC}_num${NUM}"
REPO_DIR="${DIR}/lude"    # 仓库克隆到子目录
WORKDIR="${REPO_DIR}/src/lude/data"

echo "▶▶▶ 处理目标：${DIR}"
mkdir -p "${DIR}"

# ——— 克隆或拉取更新 ——— #
if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "→ 克隆仓库到：${REPO_DIR}"
  rm -rf "${REPO_DIR}"
  git clone "${REPO_URL}" "${REPO_DIR}"
else
  echo "→ 更新仓库：${REPO_DIR}"
  cd "${REPO_DIR}"
  git pull
fi

# ——— 复制 .pq 文件 —— #
echo "→ 复制 .pq 到：${WORKDIR}"
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"
cp ${PQ_SOURCE} "${WORKDIR}/"

# ——— Conda 环境激活 —— #
if [ "${SKIP_CONDA}" = false ]; then
  ENV_NAME="${CONDA_PREFIX}_hold${HOLD}_fac${FAC}_num${NUM}"
  echo "→ 激活 Conda 环境：${ENV_NAME}"
  # 确保 conda 初始化脚本已经加载
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "${ENV_NAME}"
  # 安装依赖
  echo "→ 安装 Python 依赖 requirements.txt"
  cd "${REPO_DIR}"
  pip install -r requirements.txt -i "${PIP_INDEX_URL}"
  
  # 以开发模式安装项目
  echo "→ 以开发模式安装项目"
  if [ -f "${REPO_DIR}/install_dev.sh" ]; then
    cd "${REPO_DIR}"
    chmod +x ./install_dev.sh
    ./install_dev.sh
  else
    echo "⚠️ 警告：找不到 install_dev.sh 脚本"
    # 尝试直接安装
    cd "${REPO_DIR}"
    python -m pip install -e .
  fi
else
  echo "→ 跳过 Conda 环境激活"
fi

echo "✅ 完成：${DIR}"