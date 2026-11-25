"""Compatibility launcher for the current optional browser suite.

Install Python Playwright and Chromium, then run python test_browser.py.
ARCHFLOW_BROWSER_CHANNEL=msedge can select an installed Edge for local checks.
"""
import runpy

if __name__ == '__main__':
    runpy.run_path('tests/browser_ui.py', run_name='__main__')
