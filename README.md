# Weave Word Frequency Analysis Demo / 中文 LLM 评测可视化

[English](#english) | [中文](#中文)

---

## English

This project demonstrates how to use **Weave** and **W&B** for conversation word frequency analysis, LLM evaluation, and visualization.

Inspired by [wandb/llm-leaderboard](https://github.com/wandb/llm-leaderboard) (Nejumi Leaderboard 4 - Japanese LLM evaluation), this project extends the concept to **Chinese LLM evaluation**.

### Features

1. Track LLM conversations with Weave
2. English text tokenization + word frequency
3. **Chinese text tokenization (jieba) + word frequency**
4. W&B visualization (tables + charts)
5. Weave Evaluation integration
6. **Chinese LLM Leaderboard design (referencing Nejumi)**

### Why a Chinese Version?

The [Nejumi Leaderboard](https://github.com/wandb/llm-leaderboard) evaluates LLMs on Japanese tasks using benchmarks like Jaster, MT-bench (JP), JBBQ, etc. A Chinese version is meaningful because:

- **Language specificity**: Chinese has unique NLP challenges (word segmentation, no spaces, etc.)
- **Different benchmarks**: Chinese needs C-Eval, CMMLU, SuperCLUE instead of Japanese-specific ones
- **Ecosystem demand**: Many Chinese LLMs (Qwen, DeepSeek, ChatGLM, Yi, Baichuan) need unified evaluation
- **Safety/Alignment**: Chinese-specific safety and bias evaluation dimensions
- **W&B integration**: Reuse the proven Weave + W&B infrastructure from Nejumi

### Quick Start

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Configure W&B API Key

```bash
export WANDB_API_KEY=your_api_key_here
```

#### 3. Run English Word Frequency Analysis

```bash
python weave_word_frequency.py
```

#### 4. Run Chinese Word Frequency Analysis

```bash
python weave_word_frequency_zh.py
```

#### 5. Run Chinese LLM Evaluation

```bash
python weave_evaluation_demo_zh.py
```

#### 6. Run Chinese LLM Leaderboard Design Demo

```bash
python llm_leaderboard_zh_design.py
```

### File Descriptions

| File | Description |
|------|-------------|
| `weave_word_frequency.py` | English word frequency analysis + Weave tracing |
| `weave_word_frequency_zh.py` | **Chinese word frequency analysis (jieba) + Weave tracing** |
| `weave_evaluation_demo.py` | English Weave Evaluation with multiple scorers |
| `weave_evaluation_demo_zh.py` | **Chinese Weave Evaluation with Chinese benchmarks** |
| `weave_frequency_as_evaluation.py` | Conversation topic analysis as Evaluation |
| `weave_with_wandb_workspace.py` | Weave + W&B Workspace integration demo |
| `llm_leaderboard_zh_design.py` | **Chinese LLM Leaderboard design document** |
| `requirements.txt` | Python dependencies |

### Evaluation Taxonomy (Chinese LLM Leaderboard)

The Chinese version follows the Nejumi taxonomy, adapted for Chinese:

| Main Category | Subcategory | Chinese Benchmarks | Nejumi Equivalent |
|--------------|-------------|-------------------|-------------------|
| GLP - Knowledge | General Knowledge | C-Eval, CMMLU | Jaster (JCommonsenseQA, JMMLU) |
| GLP - Reasoning | Math Reasoning | GSM8K-ZH, GAOKAO-Math | Jaster (MAWPS, MGSM) |
| GLP - Reasoning | Logical Reasoning | LogiQA-ZH | MT-bench (reasoning) |
| GLP - Reading | QA | CMRC2018, DuReader | Jaster (JSQuAD) |
| GLP - Translation | ZH↔EN | WMT-ZH | Jaster (ALT) |
| GLP - Coding | Code Generation | HumanEval-ZH | JHumanEval |
| ALT - Safety | Toxicity | SafetyBench-ZH, CValues | LINE Yahoo Toxicity |
| ALT - Bias | Bias Detection | BBQ-ZH | JBBQ |
| ALT - Truth | Truthfulness | TruthfulQA-ZH | JTruthfulQA |

---

## 中文

本项目演示如何使用 **Weave** 和 **W&B** 进行对话词频分析、LLM 评测和可视化。

灵感来源于 [wandb/llm-leaderboard](https://github.com/wandb/llm-leaderboard) (Nejumi Leaderboard 4 - 日文 LLM 评测平台)，本项目将该概念扩展到**中文 LLM 评测**。

### 功能特性

1. 使用 Weave 追踪 LLM 对话
2. 英文文本分词 + 词频统计
3. **中文文本分词 (jieba) + 词频统计**
4. W&B 可视化 (表格 + 图表)
5. Weave Evaluation 集成
6. **中文 LLM Leaderboard 设计方案 (参考 Nejumi)**

### 为什么做中文版有意义?

[Nejumi Leaderboard](https://github.com/wandb/llm-leaderboard) 是 W&B Japan 维护的日文 LLM 评测平台, 使用 Jaster, MT-bench (日文), JBBQ 等基准进行评测。做中文版的意义在于:

- **语言特异性**: 中文有独特的 NLP 挑战 (分词、无空格分隔、字词关系等)
- **评测基准差异**: 中文需要 C-Eval、CMMLU、SuperCLUE 等专门的评测基准
- **生态需求**: 大量中文 LLM (Qwen, DeepSeek, ChatGLM, Yi, Baichuan 等) 需要统一评测
- **安全与对齐**: 需要针对中文语境的安全性和偏见评测
- **W&B 集成**: 可以复用 Nejumi 成熟的 Weave + W&B 基础设施

### 快速开始

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置 W&B API Key

```bash
export WANDB_API_KEY=your_api_key_here
```

#### 3. 运行中文词频分析

```bash
python weave_word_frequency_zh.py
```

#### 4. 运行中文 LLM 评测

```bash
python weave_evaluation_demo_zh.py
```

#### 5. 运行中文 LLM Leaderboard 设计演示

```bash
python llm_leaderboard_zh_design.py
```

### 文件说明

| 文件 | 说明 |
|------|------|
| `weave_word_frequency.py` | 英文词频分析 + Weave 追踪 |
| `weave_word_frequency_zh.py` | **中文词频分析 (jieba 分词) + Weave 追踪** |
| `weave_evaluation_demo.py` | 英文 Weave Evaluation (多评分器) |
| `weave_evaluation_demo_zh.py` | **中文 Weave Evaluation (中文评测基准)** |
| `weave_frequency_as_evaluation.py` | 对话主题分析 (作为 Evaluation) |
| `weave_with_wandb_workspace.py` | Weave + W&B Workspace 集成演示 |
| `llm_leaderboard_zh_design.py` | **中文 LLM Leaderboard 设计文档** |
| `requirements.txt` | Python 依赖 |

### 中文 LLM Leaderboard 评测分类 (对比 Nejumi)

| 大类 | 子类 | 中文评测基准 | Nejumi 对应 |
|------|------|-------------|-------------|
| 通用语言能力 - 知识 | 通用知识 | C-Eval, CMMLU | Jaster (JCommonsenseQA, JMMLU) |
| 通用语言能力 - 推理 | 数学推理 | GSM8K-ZH, 高考数学 | Jaster (MAWPS, MGSM) |
| 通用语言能力 - 推理 | 逻辑推理 | LogiQA-ZH | MT-bench (推理) |
| 通用语言能力 - 阅读 | 问答 | CMRC2018, DuReader | Jaster (JSQuAD) |
| 通用语言能力 - 翻译 | 中英互译 | WMT-ZH | Jaster (ALT) |
| 通用语言能力 - 代码 | 代码生成 | HumanEval-ZH | JHumanEval |
| 对齐性 - 安全 | 毒性 | SafetyBench-ZH, CValues | LINE Yahoo 毒性检测 |
| 对齐性 - 偏见 | 偏见检测 | BBQ-ZH | JBBQ |
| 对齐性 - 真实性 | 事实准确性 | TruthfulQA-ZH | JTruthfulQA |

### 可视化

运行脚本后, 可在 W&B 中查看:

1. **词频表** - 展示每个词的频率
2. **柱状图** - 高频词可视化
3. **对话统计** - 每条对话的 token 数
4. **评测对比** - 不同 Evaluation 的指标对比
5. **Leaderboard** - 多模型评测排行榜

### 参考文档

- [Weave Evaluation Docs](https://weave-docs.wandb.ai/guides/core-types/evaluations)
- [W&B Custom Charts](https://docs.wandb.ai/guides/app/features/custom-charts)
- [Nejumi Leaderboard](https://github.com/wandb/llm-leaderboard)
- [C-Eval Benchmark](https://cevalbenchmark.com/)
- [CMMLU](https://github.com/haonan-li/CMMLU)
