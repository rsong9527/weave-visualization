"""Tests for the output formatter."""

import pytest

from k8s_copilot.formatters.output_formatter import (
    DiagnosisOutput,
    NextStep,
    parse_llm_response,
    validate_output_constraints,
    format_diagnosis_output,
)


# ─── Sample LLM responses ───────────────────────────────────────────────────

GOOD_RESPONSE = """\
## 1. Diagnosis

The pod `nginx-deploy-5d4b7c8f9-x2k8p` is in CrashLoopBackOff with 5 restarts.
[Evidence: pod_describe] shows Exit Code 1.
[Evidence: pod_logs] shows nginx config error: invalid number of arguments in "worker_processes" directive.

## 2. Root Cause

The nginx configuration file has a syntax error in the `worker_processes` directive.
[Evidence: pod_logs line 1] The error message explicitly states the config issue.

### Missing Information Needed
- The actual nginx.conf content (mounted via ConfigMap?)

## 3. Next Steps

- **P0** (immediate): Fix the nginx.conf ConfigMap → Expected result: Pod starts successfully
- **P1** (important): Add config validation to CI/CD pipeline → Expected result: Catch config errors before deploy
- **P2** (improvement): Set up readiness probe → Expected result: Traffic only routes to healthy pods

## 4. Commands / YAML Patch

```bash
# Check the ConfigMap
kubectl get configmap -n default -l app=nginx

# Edit the ConfigMap
kubectl edit configmap nginx-config -n default
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
  namespace: default
data:
  nginx.conf: |
    worker_processes auto;
    events {
      worker_connections 1024;
    }
    http {
      server {
        listen 80;
        location / {
          root /usr/share/nginx/html;
        }
      }
    }
```

## 5. Rollback + Customer Message

### Rollback Procedure
```bash
kubectl rollout undo deployment/nginx-deploy -n default
```

### Customer Message
The nginx pod was crashing due to a syntax error in the nginx configuration.
We have corrected the worker_processes directive. The pod should now start normally.
Please verify by accessing the service endpoint.
"""

BAD_RESPONSE_NO_SECTIONS = "The pod is crashing because of a config error. Fix the config."

BAD_RESPONSE_NO_EVIDENCE = """\
## 1. Diagnosis
The pod is crashing.

## 2. Root Cause
Config error probably.

## 3. Next Steps
- **P0**: Fix it → Expected result: It works

## 4. Commands / YAML Patch
```bash
kubectl delete pod bad-pod
```

## 5. Rollback + Customer Message
Just undo it.
"""


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestParseLLMResponse:
    """Test parsing LLM responses into structured output."""

    def test_good_response_parsed(self):
        output = parse_llm_response(GOOD_RESPONSE)
        assert output.diagnosis != ""
        assert output.root_cause != ""
        assert len(output.next_steps) >= 1
        assert output.commands_yaml != ""
        assert output.rollback != ""

    def test_good_response_has_citations(self):
        output = parse_llm_response(GOOD_RESPONSE)
        assert len(output.evidence_citations) > 0

    def test_good_response_next_steps_priorities(self):
        output = parse_llm_response(GOOD_RESPONSE)
        priorities = {s.priority for s in output.next_steps}
        assert "P0" in priorities

    def test_bad_response_no_sections(self):
        output = parse_llm_response(BAD_RESPONSE_NO_SECTIONS)
        assert output.diagnosis != ""
        assert len(output.warnings) > 0

    def test_customer_message_extracted(self):
        output = parse_llm_response(GOOD_RESPONSE)
        assert output.customer_message != ""


class TestValidateConstraints:
    """Test output constraint validation."""

    def test_good_response_passes(self):
        output = parse_llm_response(GOOD_RESPONSE)
        violations = validate_output_constraints(output)
        # Good response should have minimal violations
        assert not any("R3" in v for v in violations)  # Has citations

    def test_no_evidence_citation(self):
        output = parse_llm_response(BAD_RESPONSE_NO_EVIDENCE)
        violations = validate_output_constraints(output)
        assert any("R3" in v for v in violations)

    def test_no_rollback(self):
        output = DiagnosisOutput()
        violations = validate_output_constraints(output)
        assert any("R5" in v for v in violations)


class TestDiagnosisOutputMarkdown:
    """Test Markdown rendering."""

    def test_renders_all_sections(self):
        output = parse_llm_response(GOOD_RESPONSE)
        md = output.to_markdown()
        assert "## 1. Diagnosis" in md
        assert "## 2. Root Cause" in md
        assert "## 3. Next Steps" in md
        assert "## 4. Commands / YAML Patch" in md
        assert "## 5. Rollback + Customer Message" in md

    def test_empty_output_renders(self):
        output = DiagnosisOutput()
        md = output.to_markdown()
        assert "Diagnosis Report" in md

    def test_warnings_shown(self):
        output = DiagnosisOutput(warnings=["Test warning"])
        md = output.to_markdown()
        assert "Test warning" in md


class TestFormatDiagnosisOutput:
    """Test the end-to-end formatting function."""

    def test_end_to_end(self):
        result = format_diagnosis_output(GOOD_RESPONSE)
        assert isinstance(result, str)
        assert "Diagnosis Report" in result
        assert "## 1. Diagnosis" in result
