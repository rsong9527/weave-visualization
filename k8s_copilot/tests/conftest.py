"""Configure test paths."""
import sys
from pathlib import Path

# Add the k8s-copilot directory to sys.path so we can import the sub-packages
sys.path.insert(0, str(Path(__file__).parent.parent))
