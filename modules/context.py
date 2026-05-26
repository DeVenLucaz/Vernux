# =============================================================================
# modules/context.py — Session Memory & Live Environment State
# Version: 0.3.0 | Phase 2 — Knowledge Base
# =============================================================================

import os

class SessionContext:
    """
    Tracks everything that happened during the current VERNUX session.
    In-memory only — not persisted across restarts.
    """
    def __init__(self):
        self.cwd                  = os.path.expanduser("~")
        self.vernux_created_files = set()
        self.installed_packages   = set()
        self.recipe_state         = {}   # {recipe_id: {step: int, done: bool}}
        self.command_history      = []   # [(input, command, exit_code)]

    def update_cwd(self, new_path: str):
        if new_path and os.path.isdir(new_path):
            self.cwd = new_path

    def get_cwd(self) -> str:
        return self.cwd

    def track_installed(self, package_name: str):
        self.installed_packages.add(package_name)

    def track_created_file(self, filepath: str):
        self.vernux_created_files.add(filepath)

    def is_vernux_created(self, filepath: str) -> bool:
        return filepath in self.vernux_created_files

    def log_command(self, user_input: str, command: str, exit_code: int):
        self.command_history.append((user_input, command, exit_code))

    def to_safety_context(self) -> dict:
        """Convert to the dict format safety.classify() expects."""
        return {
            "vernux_created_files": self.vernux_created_files,
            "cwd": self.cwd,
        }

    def get_session_summary(self) -> dict:
        return {
            "cwd":              self.cwd,
            "commands_run":     len(self.command_history),
            "packages_installed": list(self.installed_packages),
            "files_created":    list(self.vernux_created_files),
        }

# Global singleton
_session = None

def get_session() -> SessionContext:
    global _session
    if _session is None:
        _session = SessionContext()
    return _session
