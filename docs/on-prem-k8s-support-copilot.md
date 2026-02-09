# On-Prem K8s Support Copilot (offline-capable)

## Positioning
- Define the product as a "K8s/Helm Support Copilot" instead of a
  "coding agent".
- Small models are more reliable at structured text and templated
  operations than at complex repo patching.

## Stable K8s task set for small models
1. Install/upgrade command generation
   - `helm repo add` / `helm repo update`
   - `helm upgrade --install ... -f values.yaml`
   - `kubectl apply -f ...`
   - namespace / serviceaccount / rolebinding scaffolding
2. Troubleshooting (evidence-based)
   - parse `kubectl describe`, `kubectl get events`, pod logs
   - shortest path with P0 / P1 / P2 steps
3. Config fixes (YAML/values)
   - image tag, requests/limits, nodeSelector, tolerations, affinity
   - PVC / StorageClass pitfalls
   - Ingress / Service / NetworkPolicy pitfalls
4. Runbook output
   - symptom -> cause -> verify -> fix -> rollback

## On-prem architecture (LocalGPT as shell)
### Input contract (must be enforced)
Require an "Evidence Bundle" for every request:
- `kubectl get pods -A -o wide`
- `kubectl describe pod <x>`
- `kubectl logs <x> --tail=200`
- `helm list -A` or `helm status <rel>`
- `values.yaml` (relevant sections)
- cluster version / CRI / CNI / StorageClass info

Rules:
- If evidence is missing, request the exact items needed.
- Do not speculate. Every conclusion must cite evidence lines.

### Output contract (fixed five-pack)
1. Diagnosis (cite evidence lines)
2. Root cause (hypothesis + evidence chain)
3. Next steps (P0 / P1 / P2 + expected outcome)
4. Commands / YAML patch (copy/paste ready)
5. Rollback + customer message

## "Install a K8s" meaning
The model outputs an executable script package and does not run it:
- `install.md` (steps)
- `install.sh` (commands)
- `values.yaml` (config)
- `validate.sh` (kubectl/helm checks)
- `rollback.sh` (rollback)

## Guardrails that turn "can't code" into an advantage
- Prohibit large code changes
- Allow YAML / Helm / commands / runbooks only
- Require evidence citations for conclusions
- List missing info when uncertain
