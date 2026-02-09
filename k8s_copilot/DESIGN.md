# K8s/Helm Support Copilot — Product Design Document

> **定位**：K8s/Helm Support Copilot（离线可跑），不是 coding agent。
> 把"小模型写代码能力差"变成产品优势：只输出 YAML/Helm/命令/Runbook，任何结论必须引用 evidence。

---

## 1. 产品定位与边界

### 1.1 是什么

| 维度 | 定义 |
|------|------|
| 产品名 | K8s/Helm Support Copilot |
| 部署形态 | On-Prem（离线可跑），LocalGPT 当壳 |
| 目标用户 | K8s 运维工程师、SRE、平台团队 |
| 核心价值 | 结构化诊断 + 可复制命令 + 可回滚操作 |

### 1.2 不是什么

| 明确排除 | 原因 |
|----------|------|
| 代码生成 Agent | 小模型写复杂代码不稳定 |
| 自动执行器 | 只吐脚本，不直接执行 |
| 通用聊天机器人 | 强制结构化输入输出 |

---

## 2. 小模型适合干的 K8s 任务清单

### 2.1 安装/升级指令生成
- `helm repo add/update`
- `helm upgrade --install ... -f values.yaml`
- `kubectl apply -f ...`
- namespace / serviceaccount / rolebinding 基础脚手架

### 2.2 问题定位（基于证据）
- 解析 `kubectl describe` / `kubectl get events` / pod logs
- 给出最短排查路径：P0 / P1 / P2 分级

### 2.3 配置修正（YAML/values）
- image tag、资源 requests/limits、nodeSelector、tolerations、affinity
- PVC / StorageClass 常见坑
- Ingress / Service / NetworkPolicy 常见坑

### 2.4 Runbook 产出
- 把一次 case 固化为：**症状 → 原因 → 验证 → 修复 → 回滚**

> 这些本质是"结构化文本 + 模板化操作"，小模型做得比写代码稳定得多。

---

## 3. 架构设计

```
┌─────────────────────────────────────────────┐
│              用户 / CLI / Web UI             │
└──────────────────┬──────────────────────────┘
                   │ Evidence Bundle (JSON)
                   ▼
┌─────────────────────────────────────────────┐
│          Evidence Bundle Parser              │
│  (校验必填字段、提取关键信息、裁剪上下文)     │
└──────────────────┬──────────────────────────┘
                   │ Structured Context
                   ▼
┌─────────────────────────────────────────────┐
│          System Prompt + Constraints         │
│  (禁止大型代码 / 必须引用证据 / 列出缺失)    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          Small LLM (LocalGPT / Ollama)       │
│  推荐: Qwen-2.5-7B / Llama-3-8B / Mistral   │
└──────────────────┬──────────────────────────┘
                   │ Raw Response
                   ▼
┌─────────────────────────────────────────────┐
│          Output Formatter (5 件套)           │
│  Diagnosis / Root Cause / Next Steps /       │
│  Commands & YAML / Rollback                  │
└──────────────────┬──────────────────────────┘
                   │ Structured Output
                   ▼
┌─────────────────────────────────────────────┐
│  Runbook Generator (可选：固化为 .md 文件)    │
└─────────────────────────────────────────────┘
```

---

## 4. 输入规范：Evidence Bundle

**核心原则**：把用户输入限制成一个 Evidence Bundle（否则模型开始编）。

### 4.1 必填字段

| 字段 | 来源命令 | 说明 |
|------|----------|------|
| `pods_overview` | `kubectl get pods -A -o wide` | 全局 Pod 状态 |
| `cluster_info` | `kubectl version` + `kubectl cluster-info` | 集群版本/API Server |

### 4.2 按场景必填

| 字段 | 来源命令 | 何时必填 |
|------|----------|----------|
| `pod_describe` | `kubectl describe pod <x>` | 排障时 |
| `pod_logs` | `kubectl logs <x> --tail=200` | 排障时 |
| `helm_list` | `helm list -A` | Helm 相关 |
| `helm_status` | `helm status <release>` | Helm 排障 |
| `values_yaml` | 相关段落 | 配置修正 |
| `events` | `kubectl get events --sort-by=.lastTimestamp` | 排障时 |
| `storage_info` | `kubectl get sc,pv,pvc -A` | 存储相关 |
| `network_info` | `kubectl get svc,ing,netpol -A` | 网络相关 |

### 4.3 环境元数据

| 字段 | 示例 |
|------|------|
| `k8s_version` | `v1.28.4` |
| `cri` | `containerd 1.7.x` |
| `cni` | `calico 3.26` |
| `storage_class` | `local-path`, `longhorn`, `rook-ceph` |
| `os` | `Ubuntu 22.04` |

---

## 5. 输出规范：固定 5 件套

每次诊断输出必须包含以下 5 个部分：

### 5.1 Diagnosis（诊断）
- 引用 evidence 中的具体行
- 用 `[证据]` 标注来源
- 给出现象总结

### 5.2 Root Cause（根因）
- 假设 + 证据链
- 如有多个可能原因，按概率排序
- 明确列出"还缺什么信息"

### 5.3 Next Steps（下一步）
- P0（立即执行）/ P1（重要）/ P2（改善）
- 每步附带预期结果

### 5.4 Commands / YAML Patch（可复制）
- 直接可复制的命令或 YAML
- 带注释说明每一步的作用
- 禁止输出大型代码改动

### 5.5 Rollback + Customer Message
- 怎么撤销操作
- 给客户的简明消息模板

---

## 6. 安装计划生成器

当用户请求"安装一个 K8s 组件"时，模型只吐"可执行脚本包"，不直接执行：

| 文件 | 内容 |
|------|------|
| `install.md` | 步骤说明（人读） |
| `install.sh` | 可执行命令（机器跑） |
| `values.yaml` | 配置文件 |
| `validate.sh` | 验收脚本（kubectl/helm 检查） |
| `rollback.sh` | 回滚脚本 |

---

## 7. 硬约束规则（系统级）

这些规则写死在 system prompt 中，是产品可靠性的基石：

| 编号 | 规则 | 原因 |
|------|------|------|
| R1 | 禁止输出大型代码改动（>50行） | 小模型代码质量不可控 |
| R2 | 只允许输出：YAML / Helm / 命令 / Runbook | 聚焦能力圈 |
| R3 | 任何结论必须引用 evidence | 防止幻觉 |
| R4 | 不确定点必须列出"还缺什么信息" | 诚实 > 猜测 |
| R5 | 输出必须包含回滚方案 | 生产安全 |
| R6 | 命令必须可复制（含完整参数） | 用户体验 |
| R7 | YAML 必须包含 apiVersion/kind/metadata | 防止残缺输出 |

---

## 8. 推荐模型

| 模型 | 参数量 | 优势 | 适合场景 |
|------|--------|------|----------|
| Qwen-2.5-7B-Instruct | 7B | 中文好、指令遵循强 | 中文客户 |
| Llama-3.1-8B-Instruct | 8B | 英文强、社区大 | 英文客户 |
| Mistral-7B-Instruct-v0.3 | 7B | 推理快、性价比高 | 低配机器 |
| Phi-3-mini-4k | 3.8B | 超小、推理快 | 极低配 / 边缘 |

### 部署方式
- **Ollama**：最简单，`ollama run qwen2.5:7b`
- **vLLM**：高吞吐，适合多用户
- **llama.cpp**：最轻量，CPU 可跑

---

## 9. 技术栈

| 层 | 技术 |
|----|------|
| LLM Runtime | Ollama / vLLM / llama.cpp |
| 应用框架 | Python + Jinja2 模板 |
| 输入校验 | Pydantic v2 |
| CLI | Click / Typer |
| Web UI（可选） | Gradio / Streamlit |
| 打包 | Docker / Helm Chart |

---

## 10. 路线图

| 阶段 | 目标 | 交付物 |
|------|------|--------|
| P0 (MVP) | CLI 诊断 + 5件套输出 | 本仓库代码 |
| P1 | 安装计划生成器 | install pack 模板 |
| P2 | Runbook 自动归档 | Markdown 知识库 |
| P3 | Web UI + 多用户 | Gradio/Streamlit 界面 |
| P4 | Helm Chart 打包 | 一键部署到 K8s |
