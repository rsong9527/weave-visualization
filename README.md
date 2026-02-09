# vits-simple-api 项目分析与复现指南

## 这玩意是啥？

[vits-simple-api](https://github.com/Artrajz/vits-simple-api) 是一个基于 VITS（Variational Inference with adversarial learning for end-to-end Text-to-Speech）的**语音合成 HTTP API 服务**。

简单来说：**你给它一段文字，它还你一段语音**。

### 核心能力

| 功能 | 说明 |
|------|------|
| VITS 文本转语音 | 输入文字，输出语音音频 |
| VITS 语音转换 | 把 A 的声音转换成 B 的声音 |
| Bert-VITS2 | 更高质量的中日英多语言 TTS |
| GPT-SoVITS | 少样本语音克隆，只需几秒参考音频 |
| W2V2-VITS | 带情感控制的语音合成（兴奋/低语等） |
| HuBert-soft VITS | 基于 HuBert 的语音转换 |
| 多模型加载 | 同时加载多个不同的语音模型 |
| 自动语言识别 | 自动检测输入文本的语言 |
| 长文本处理 | 自动切分长文本分段合成 |
| GPU 加速 | 支持 CUDA GPU 加速推理 |
| 流式输出 | 支持 MP3 格式的流式音频响应 |
| SSML 支持 | 支持语音合成标记语言（开发中） |

### 技术栈

- **后端框架**: Flask (Python 3.10)
- **深度学习**: PyTorch
- **模型类型**: VITS / Bert-VITS2 / GPT-SoVITS / W2V2-VITS / HuBert-VITS
- **部署方式**: Docker / 虚拟环境 / Windows 部署包
- **API 协议**: RESTful HTTP API
- **Stars**: 1040+ | **Forks**: 135+ | **License**: AGPL-3.0

## 项目架构

```
vits-simple-api/
├── app.py                  # Flask 主入口，注册蓝图、调度器
├── config.py               # 配置管理（Pydantic 模型），生成 config.yaml
├── contants.py             # 模型类型常量定义
├── manager/
│   ├── ModelManager.py     # 模型加载/卸载管理器
│   ├── TTSManager.py       # TTS 推理管理器（核心调度）
│   ├── model_handler.py    # 模型处理器
│   └── observer.py         # 观察者模式
├── tts_app/
│   ├── voice_api/views.py  # REST API 路由定义（核心 API）
│   ├── admin/              # 管理后台（模型加载/卸载）
│   ├── auth/               # 登录认证
│   ├── frontend/           # Web 前端界面
│   ├── templates/          # HTML 模板
│   └── static/             # 静态资源 (CSS/JS)
├── vits/                   # VITS 模型实现
├── bert_vits2/             # Bert-VITS2 模型实现
├── gpt_sovits/             # GPT-SoVITS 模型实现
├── utils/                  # 工具函数（语言分类、数据处理等）
├── module/                 # 辅助模块（多音字、G2PW）
├── data/                   # 数据目录
│   ├── models/             # 语音模型存放目录
│   ├── bert/               # BERT 模型（多语言）
│   ├── emotional/          # 情感模型
│   └── hubert/             # HuBert 模型
├── Dockerfile              # Docker 构建文件
├── docker-compose-gpu.yaml # GPU 版 Docker Compose
└── requirements.txt        # Python 依赖
```

## API 接口一览

服务默认运行在 `http://localhost:23456`。

### 基础接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/voice/speakers` | 获取所有已加载的说话人列表 |
| GET/POST | `/voice/default_parameter` | 获取默认参数配置 |
| GET/POST | `/voice/check` | 检查指定模型和说话人是否可用 |

### TTS 语音合成接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/voice/vits?text=你好&id=0` | VITS 文本转语音 |
| GET/POST | `/voice/w2v2-vits?text=你好&id=0&emotion=111` | W2V2-VITS 带情感的语音合成 |
| GET/POST | `/voice/bert-vits2?text=你好&id=0` | Bert-VITS2 语音合成 |
| GET/POST | `/voice/gpt-sovits?text=你好&id=0` | GPT-SoVITS 语音合成 |
| POST | `/voice/hubert-vits` | HuBert 语音转换（需上传音频） |
| POST | `/voice/conversion` | VITS 声音转换 |
| POST | `/voice/ssml` | SSML 语音合成 |
| GET/POST | `/voice/reading` | 朗读模式（旁白+对话双角色） |

### 通用参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | string | - | 要合成的文本 |
| `id` | int | 0 | 说话人 ID |
| `format` | string | wav | 输出音频格式 (wav/mp3/ogg/silk/flac) |
| `lang` | string | auto | 语言 (auto/zh/ja/en/ko/mix) |
| `length` | float | 1.0 | 语速控制 (>1 慢, <1 快) |
| `noise` | float | 0.33 | 噪声系数 |
| `noisew` | float | 0.4 | 噪声权重 |
| `segment_size` | int | 50 | 长文本分段大小 |
| `streaming` | bool | false | 是否使用流式输出 (仅 MP3) |

## 复现方式

### 方式一：Docker 部署（推荐）

最简单的方式，使用本仓库提供的 `docker-compose.yml`：

```bash
# 1. 创建数据目录
mkdir -p data/models

# 2. 启动服务 (CPU 版本)
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 访问 Web 界面
# http://localhost:23456
# 管理后台: http://localhost:23456/admin
```

如果有 NVIDIA GPU：

```bash
# GPU 版本
docker-compose -f docker-compose-gpu.yml up -d
```

### 方式二：本地虚拟环境部署

```bash
# 1. 克隆项目
git clone https://github.com/Artrajz/vits-simple-api.git
cd vits-simple-api

# 2. 创建 Python 3.10 虚拟环境
python3.10 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 如果有 NVIDIA GPU，安装 GPU 版 PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cu118

# 5. 启动服务
python app.py

# 首次启动会自动生成 config.yaml 配置文件
# 默认自动加载 data/models/ 下的所有模型
```

### 方式三：使用安装脚本（Linux Docker）

```bash
bash -c "$(wget -O- https://raw.githubusercontent.com/Artrajz/vits-simple-api/main/vits-simple-api-installer-latest.sh)"
```

## 模型获取

服务启动后需要放入语音模型才能使用。模型放在 `data/models/` 目录下。

### VITS 模型

VITS 模型通常包含两个文件：
- `G_xxx.pth` - 生成器权重
- `config.json` - 模型配置

可以从以下来源获取预训练模型：
- [Hugging Face - VITS models](https://huggingface.co/models?search=vits)
- 各种开源 VITS 项目的 Release 页面

### Bert-VITS2 模型

- [Bert-VITS2 官方仓库](https://github.com/Stardust-minus/Bert-VITS2)
- 需要额外下载对应语言的 BERT 模型放入 `data/bert/` 目录

### GPT-SoVITS 模型

- [GPT-SoVITS 官方仓库](https://github.com/RVC-Boss/GPT-SoVITS)
- 需要两个文件：`*.pth`（VITS 权重）和 `*.ckpt`（GPT 权重）

## API 调用示例

启动服务后，可以使用 `api_examples.py` 测试 API：

```bash
python api_examples.py
```

或者直接用 curl：

```bash
# 获取说话人列表
curl http://localhost:23456/voice/speakers

# VITS 文本转语音
curl "http://localhost:23456/voice/vits?text=你好世界&id=0" --output hello.wav

# Bert-VITS2 文本转语音
curl "http://localhost:23456/voice/bert-vits2?text=这是一个测试&id=0&lang=zh" --output test.wav

# GPT-SoVITS 文本转语音
curl "http://localhost:23456/voice/gpt-sovits?text=你好&id=0&lang=zh" --output gpt_hello.wav
```

## 在线体验

不想本地部署？可以直接试试在线 Demo：

- **Hugging Face Space**: https://huggingface.co/spaces/Artrajz/vits-simple-api
- **Colab Notebook**: https://colab.research.google.com/drive/1uBkMy0UjLE3C1zvxZ7NPPc3K74v4B6zw

示例 URL：
- 中日混合: `https://artrajz-vits-simple-api.hf.space/voice/vits?text=你好,こんにちは&id=164`
- 英文: `https://artrajz-vits-simple-api.hf.space/voice/vits?text=Difficult the first time, easy the second.&id=4`

## 配置说明

首次启动后会生成 `config.yaml`，关键配置项：

```yaml
# HTTP 服务配置
http_service:
  host: 0.0.0.0
  port: 23456
  debug: false

# 系统配置
system:
  device: cuda          # 推理设备: cuda / cpu / mps
  cache_audio: false    # 是否缓存生成的音频
  api_key_enabled: false # 是否启用 API Key 认证
  is_admin_enabled: true # 是否启用管理后台

# 模型配置
tts_model_config:
  models_dir: models    # 模型目录（相对于 data/）
  auto_load: true       # 自动加载所有模型
  tts_models: []        # 手动指定模型列表

# 管理员账号（首次启动自动生成随机用户名密码）
admin:
  username: xxxxxxxx
  password: xxxxxxxxxxxxxxxx
```

## 注意事项

1. **Python 版本**: 推荐 Python 3.10，其他版本可能存在兼容性问题
2. **GPU 显存**: 加载多个模型需要较大显存，建议 >= 4GB VRAM
3. **依赖安装**: 部分依赖（如 `pyopenjtalk`）可能需要系统级别的编译工具
4. **模型文件**: 模型文件通常较大（几百 MB 到几 GB），需要预先下载
5. **BERT 模型**: Bert-VITS2 需要对应语言的 BERT 模型，首次加载会自动下载
6. **安全性**: 如果暴露到公网，建议关闭管理后台（`is_admin_enabled: false`）并启用 API Key

## 参考链接

- [vits-simple-api GitHub](https://github.com/Artrajz/vits-simple-api)
- [VITS 论文](https://arxiv.org/abs/2106.06103)
- [Bert-VITS2](https://github.com/Stardust-minus/Bert-VITS2)
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
- [Docker Hub](https://hub.docker.com/r/artrajz/vits-simple-api)
