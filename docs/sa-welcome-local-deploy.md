# SA 见面礼：On-Prem K8s Support Copilot（本地部署版）

## 一句话定位
**离线可跑的 K8s/Helm Support Copilot**，不是 coding agent。
小模型更稳定地做“结构化文本 + 模板化操作”。

## 适合小模型、能稳定交付的 K8s 任务
1. 安装/升级指令生成  
   - `helm repo add` / `helm repo update`  
   - `helm upgrade --install ... -f values.yaml`  
   - `kubectl apply -f ...`  
   - namespace / serviceaccount / rolebinding 脚手架
2. 问题定位（基于证据）  
   - 解析 `kubectl describe` / `kubectl get events` / pod logs  
   - 给出最短排查路径：P0 / P1 / P2
3. 配置修正（YAML/values）  
   - image tag、requests/limits、nodeSelector、tolerations、affinity  
   - PVC / StorageClass 常见坑  
   - Ingress / Service / NetworkPolicy 常见坑
4. runbook 产出  
   - 症状 → 原因 → 验证 → 修复 → 回滚

## 本地部署卖点（给客户讲清楚）
- **数据不出域**：日志/配置只在本地集群内处理  
- **可审计**：输入证据 + 输出步骤可回溯  
- **可控**：规则约束模型，避免“编答案”  
- **低门槛**：输出可复制命令和 YAML

## 强约束输入：Evidence Bundle
必须强制要求以下证据（缺一补一）：
- `kubectl get pods -A -o wide`
- `kubectl describe pod <x>`
- `kubectl logs <x> --tail=200`
- `helm list -A` 或 `helm status <rel>`
- `values.yaml`（相关片段）
- 集群版本 / CRI / CNI / StorageClass 信息

## 固定输出五件套（稳定交付）
1. Diagnosis（引用证据行）
2. Root cause（假设 + 证据链）
3. Next steps（P0 / P1 / P2 + 预期结果）
4. Commands / YAML patch（可复制）
5. Rollback（怎么撤）+ Customer message

## “安装一个 K8s”的正确输出方式
只输出“可执行脚本包”，不自动执行：
- `install.md`（步骤）
- `install.sh`（命令）
- `values.yaml`（配置）
- `validate.sh`（验收：kubectl/helm 检查）
- `rollback.sh`（回滚）

## 把“写代码能力差”变成产品优势
- 禁止输出大型代码改动
- 允许输出：YAML / Helm / 命令 / runbook
- 任何结论必须引用 evidence
- 不确定就列出“还缺什么信息”

## SA 演示流程（简短版）
1. **收证据包** → 让客户拷贝 5 条命令输出  
2. **生成五件套** → 快速定位 + 操作指令  
3. **复制执行** → 客户侧执行，模型不越权  
4. **沉淀 runbook** → 形成可复用 SOP
