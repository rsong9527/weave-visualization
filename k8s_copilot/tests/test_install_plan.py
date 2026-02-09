"""Tests for the install plan generator."""

import pytest
from pathlib import Path

from k8s_copilot.generators.install_plan import (
    generate_install_plan,
    InstallPlan,
    KNOWN_COMPONENTS,
)


class TestGenerateInstallPlan:
    """Test install plan generation."""

    def test_known_component(self):
        plan = generate_install_plan("nginx-ingress", namespace="ingress-nginx")
        assert plan.component_name == "nginx-ingress"
        assert plan.namespace == "ingress-nginx"
        assert "ingress-nginx" in plan.install_sh
        assert "helm" in plan.install_sh
        assert "validate" in plan.validate_sh.lower()
        assert "rollback" in plan.rollback_sh.lower()

    def test_unknown_component(self):
        plan = generate_install_plan("my-custom-app", namespace="apps")
        assert plan.component_name == "my-custom-app"
        assert "my-custom-app" in plan.install_sh
        assert plan.values_yaml != ""

    def test_install_md_has_steps(self):
        plan = generate_install_plan("cert-manager", namespace="cert-manager")
        assert "Prerequisites" in plan.install_md
        assert "Install" in plan.install_md
        assert "Validate" in plan.install_md

    def test_install_sh_is_executable(self):
        plan = generate_install_plan("prometheus", namespace="monitoring")
        assert plan.install_sh.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in plan.install_sh

    def test_validate_sh_has_checks(self):
        plan = generate_install_plan("nginx-ingress")
        assert "PASS" in plan.validate_sh
        assert "FAIL" in plan.validate_sh
        assert "helm status" in plan.validate_sh

    def test_rollback_sh_options(self):
        plan = generate_install_plan("argocd", namespace="argocd")
        assert "--delete" in plan.rollback_sh
        assert "helm rollback" in plan.rollback_sh
        assert "helm uninstall" in plan.rollback_sh

    def test_values_yaml_has_resources(self):
        plan = generate_install_plan("cert-manager")
        assert "resources:" in plan.values_yaml
        assert "requests:" in plan.values_yaml

    def test_save_creates_files(self, tmp_path):
        plan = generate_install_plan("nginx-ingress", namespace="ingress")
        saved = plan.save(tmp_path)
        assert (saved / "install.md").exists()
        assert (saved / "install.sh").exists()
        assert (saved / "values.yaml").exists()
        assert (saved / "validate.sh").exists()
        assert (saved / "rollback.sh").exists()

    def test_to_markdown(self):
        plan = generate_install_plan("cert-manager")
        md = plan.to_markdown()
        assert "# Install Plan: cert-manager" in md
        assert "install.sh" in md
        assert "values.yaml" in md

    def test_custom_values_override(self):
        custom_values = "replicas: 3\nimage: custom:latest"
        plan = generate_install_plan(
            "nginx-ingress",
            llm_values_yaml=custom_values,
        )
        assert plan.values_yaml == custom_values


class TestKnownComponents:
    """Test the known components registry."""

    def test_has_nginx_ingress(self):
        assert "nginx-ingress" in KNOWN_COMPONENTS

    def test_has_cert_manager(self):
        assert "cert-manager" in KNOWN_COMPONENTS

    def test_has_prometheus(self):
        assert "prometheus" in KNOWN_COMPONENTS

    def test_has_argocd(self):
        assert "argocd" in KNOWN_COMPONENTS

    def test_all_have_required_fields(self):
        required = ["chart_ref", "helm_repo_add", "release_name"]
        for name, config in KNOWN_COMPONENTS.items():
            for field in required:
                assert field in config, f"{name} missing {field}"
