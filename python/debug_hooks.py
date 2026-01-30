
import sys
import os
sys.path.append(os.getcwd())
from PyInstaller.utils.hooks import collect_submodules

try:
    modules = collect_submodules('src')
    print("Found modules:", modules)
except Exception as e:
    print("Error collecting modules:", e)
