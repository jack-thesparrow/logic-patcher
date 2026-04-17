# setup.py

from setuptools import setup, find_packages

setup(
    name="logic-patcher",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "console_scripts": ["logic-patcher=logic_patcher.cli:main"],
        "gui_scripts": ["logic-patcher-gui=logic_patcher.gui:launch_gui"],
    },
)
