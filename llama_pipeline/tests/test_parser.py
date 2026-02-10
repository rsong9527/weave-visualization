"""Tests for the log parser."""

import json
import tempfile
from pathlib import Path

import pytest

from pipeline.parser import LogParser, ParseResult


@pytest.fixture
def sample_log(tmp_path):
    """Create a sample log file."""
    log_content = """\
2026-02-10T03:12:01 [INFO] Starting on pod/api-server-7b8f9c-xk2lm
2026-02-10T03:12:30 [ERROR] Connection timeout: status=503
2026-02-10T03:12:50 [WARN] CPU spike: cpu=94%
2026-02-10T03:12:55 [ERROR] OOMKilled: container/payment-svc memory limit exceeded
  at com.example.PaymentService.processPayment(PaymentService.java:142)
2026-02-10T03:13:00 [WARN] Latency p99=2350ms
"""
    log_file = tmp_path / "test.log"
    log_file.write_text(log_content)
    return str(log_file)


@pytest.fixture
def config_file(tmp_path):
    """Create a minimal config for testing."""
    import yaml
    config = {
        "parser": {
            "max_lines": 5000,
            "output_dir": str(tmp_path / "data"),
            "patterns": [
                {"name": "error", "regex": r"(?i)(error|exception|fatal|panic|fail)\s*[:=]?\s*(.+)"},
                {"name": "timestamp", "regex": r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"},
                {"name": "status_code", "regex": r"(?:status|code|HTTP)[=:\s]+(\d{3})"},
                {"name": "k8s_pod", "regex": r"(?:pod|container)[/=:\s]+([a-z0-9][-a-z0-9]*)"},
                {"name": "metric", "regex": r"(?:cpu|memory|mem|disk|latency|p99|p95)[=:\s]+([0-9.]+[%a-zA-Z]*)"},
                {"name": "stack_trace", "regex": r"^\s+at\s+(.+)"},
            ],
        }
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    return str(config_path)


def test_parser_extracts_facts(sample_log, config_file):
    """Parser should extract structured facts from logs."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    assert isinstance(result, ParseResult)
    assert result.total_lines > 0
    assert len(result.facts) > 0
    assert "error" in result.summary
    assert "timestamp" in result.summary


def test_parser_extracts_errors(sample_log, config_file):
    """Parser should find error lines."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    error_facts = [f for f in result.facts if f.category == "error"]
    assert len(error_facts) >= 2  # "Connection timeout" and "OOMKilled"


def test_parser_extracts_metrics(sample_log, config_file):
    """Parser should extract metric values."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    metric_facts = [f for f in result.facts if f.category == "metric"]
    assert len(metric_facts) >= 1
    values = [f.value for f in metric_facts]
    assert any("94%" in v for v in values)


def test_parser_extracts_k8s_pods(sample_log, config_file):
    """Parser should extract Kubernetes pod names."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    pod_facts = [f for f in result.facts if f.category == "k8s_pod"]
    assert len(pod_facts) >= 1


def test_parser_handles_empty_input(config_file, tmp_path):
    """Parser should handle empty files gracefully."""
    empty_file = tmp_path / "empty.log"
    empty_file.write_text("")

    parser = LogParser(config_path=config_file)
    result = parser.parse(str(empty_file))

    assert result.total_lines == 0
    assert len(result.facts) == 0


def test_parser_json_output(sample_log, config_file):
    """Parser output should be valid JSON."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    json_str = result.to_json()
    data = json.loads(json_str)

    assert "source" in data
    assert "facts" in data
    assert "summary" in data
    assert isinstance(data["facts"], list)


def test_parser_facts_text(sample_log, config_file):
    """facts_text should produce readable text for prompt injection."""
    parser = LogParser(config_path=config_file)
    result = parser.parse(sample_log)

    text = result.facts_text
    assert isinstance(text, str)
    assert len(text) > 0
    assert "[error]" in text or "[timestamp]" in text


def test_parser_file_not_found(config_file):
    """Parser should raise FileNotFoundError for missing files."""
    parser = LogParser(config_path=config_file)
    with pytest.raises(FileNotFoundError):
        parser.parse("/nonexistent/path/logs.txt")


def test_parser_truncates_long_input(config_file, tmp_path):
    """Parser should truncate inputs exceeding max_lines."""
    # Create a file with 10000 lines
    big_file = tmp_path / "big.log"
    lines = [f"2026-02-10T03:12:{i:02d} [ERROR] error line {i}" for i in range(10000)]
    big_file.write_text("\n".join(lines))

    parser = LogParser(config_path=config_file)
    result = parser.parse(str(big_file))

    # Should be capped at max_lines (5000)
    assert result.total_lines == 5000
