#!/bin/bash
# vits-simple-api 一键安装脚本
# 支持 Docker 部署和本地虚拟环境部署
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   vits-simple-api 安装脚本${NC}"
echo -e "${BLUE}   语音合成 HTTP API 服务${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# 检测系统环境
check_environment() {
    echo -e "${YELLOW}[检测环境]${NC}"
    
    # 检测操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="other"
    fi
    echo -e "  操作系统: ${GREEN}${OS}${NC}"
    
    # 检测 Docker
    if command -v docker &> /dev/null; then
        DOCKER_AVAILABLE=true
        echo -e "  Docker: ${GREEN}已安装${NC}"
    else
        DOCKER_AVAILABLE=false
        echo -e "  Docker: ${RED}未安装${NC}"
    fi
    
    # 检测 GPU
    if command -v nvidia-smi &> /dev/null; then
        GPU_AVAILABLE=true
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        echo -e "  GPU: ${GREEN}${GPU_INFO}${NC}"
    else
        GPU_AVAILABLE=false
        echo -e "  GPU: ${YELLOW}未检测到 NVIDIA GPU（将使用 CPU 模式）${NC}"
    fi
    
    # 检测 Python
    if command -v python3.10 &> /dev/null; then
        PYTHON_CMD="python3.10"
        PYTHON_AVAILABLE=true
    elif command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        PYTHON_CMD="python3"
        PYTHON_AVAILABLE=true
    else
        PYTHON_AVAILABLE=false
    fi
    
    if [ "$PYTHON_AVAILABLE" = true ]; then
        echo -e "  Python: ${GREEN}$($PYTHON_CMD --version)${NC}"
    else
        echo -e "  Python: ${RED}未安装${NC}"
    fi
    
    echo ""
}

# Docker 部署
deploy_docker() {
    echo -e "${BLUE}[Docker 部署]${NC}"
    
    # 创建目录
    mkdir -p data/models data/bert data/emotional data/hubert logs
    echo -e "  ${GREEN}已创建数据目录${NC}"
    
    # 选择 GPU/CPU 版本
    if [ "$GPU_AVAILABLE" = true ]; then
        echo -e "  ${YELLOW}检测到 GPU，使用 GPU 版本${NC}"
        COMPOSE_FILE="docker-compose-gpu.yml"
    else
        echo -e "  ${YELLOW}使用 CPU 版本${NC}"
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # 拉取镜像
    echo -e "  ${YELLOW}拉取 Docker 镜像...${NC}"
    docker-compose -f "$COMPOSE_FILE" pull
    
    # 启动服务
    echo -e "  ${YELLOW}启动服务...${NC}"
    docker-compose -f "$COMPOSE_FILE" up -d
    
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  部署完成！${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo -e "  Web 界面:   ${BLUE}http://localhost:23456${NC}"
    echo -e "  管理后台:   ${BLUE}http://localhost:23456/admin${NC}"
    echo -e "  API 端点:   ${BLUE}http://localhost:23456/voice/speakers${NC}"
    echo ""
    echo -e "  ${YELLOW}注意: 需要将语音模型放入 data/models/ 目录${NC}"
    echo -e "  ${YELLOW}管理员账号密码请查看 config.yaml 文件${NC}"
    echo ""
    echo -e "  查看日志: ${BLUE}docker-compose -f $COMPOSE_FILE logs -f${NC}"
    echo -e "  停止服务: ${BLUE}docker-compose -f $COMPOSE_FILE down${NC}"
}

# 本地部署
deploy_local() {
    echo -e "${BLUE}[本地虚拟环境部署]${NC}"
    
    if [ "$PYTHON_AVAILABLE" = false ]; then
        echo -e "${RED}错误: 未找到 Python。请安装 Python 3.10${NC}"
        exit 1
    fi
    
    # 克隆项目
    if [ ! -d "vits-simple-api" ]; then
        echo -e "  ${YELLOW}克隆 vits-simple-api 仓库...${NC}"
        git clone https://github.com/Artrajz/vits-simple-api.git
    else
        echo -e "  ${GREEN}vits-simple-api 目录已存在，跳过克隆${NC}"
    fi
    
    cd vits-simple-api
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        echo -e "  ${YELLOW}创建虚拟环境...${NC}"
        $PYTHON_CMD -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 安装依赖
    echo -e "  ${YELLOW}安装 Python 依赖（可能需要几分钟）...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # 如果有 GPU，安装 GPU 版 PyTorch
    if [ "$GPU_AVAILABLE" = true ]; then
        echo -e "  ${YELLOW}安装 GPU 版 PyTorch...${NC}"
        pip install torch --index-url https://download.pytorch.org/whl/cu118
    fi
    
    # 创建数据目录
    mkdir -p data/models
    
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  安装完成！${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo -e "  启动命令:"
    echo -e "    ${BLUE}cd vits-simple-api${NC}"
    echo -e "    ${BLUE}source venv/bin/activate${NC}"
    echo -e "    ${BLUE}python app.py${NC}"
    echo ""
    echo -e "  ${YELLOW}注意: 需要将语音模型放入 data/models/ 目录${NC}"
}

# 主流程
check_environment

echo "请选择部署方式:"
echo "  1) Docker 部署 (推荐)"
echo "  2) 本地虚拟环境部署"
echo "  3) 仅创建目录结构（不安装）"
echo ""

read -p "请输入选项 [1/2/3]: " choice

case $choice in
    1)
        if [ "$DOCKER_AVAILABLE" = false ]; then
            echo -e "${RED}Docker 未安装，请先安装 Docker${NC}"
            echo -e "安装命令: ${BLUE}curl -fsSL https://get.docker.com | sh${NC}"
            exit 1
        fi
        deploy_docker
        ;;
    2)
        deploy_local
        ;;
    3)
        mkdir -p data/models data/bert data/emotional data/hubert logs
        echo -e "${GREEN}目录结构已创建${NC}"
        echo -e "  data/models/     - 放入语音模型"
        echo -e "  data/bert/       - 放入 BERT 模型（Bert-VITS2 需要）"
        echo -e "  data/emotional/  - 放入情感模型"
        echo -e "  data/hubert/     - 放入 HuBert 模型"
        echo -e "  logs/            - 日志目录"
        ;;
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac
