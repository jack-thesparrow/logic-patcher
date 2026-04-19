# setup.py

from setuptools import setup, find_packages

setup(
    name="logic-patcher",
    use_scm_version={"fallback_version": "1.0.0"},
    setup_requires=["setuptools-scm"],
    packages=find_packages(),
    install_requires=[],
    extras_require={"gui": ["PySide6>=6.4"]},
    entry_points={
        "console_scripts": ["logic-patcher=logic_patcher.cli:main"],
        "gui_scripts": ["logic-patcher-gui=logic_patcher.gui:launch_gui"],
    },
)
