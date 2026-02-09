"""Allow running as: python -m k8s_copilot"""
from .cli import main
import sys

sys.exit(main())
