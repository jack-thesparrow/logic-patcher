# logic_patcher/gui.py

import html as _html
import json
import os
import platform
import sys
import tempfile
import threading
import urllib.request

from PySide6.QtCore import Qt, Signal, QObject, QUrl, QSettings, QProcess
from PySide6.QtGui import (
    QFont, QIcon, QTextCursor, QDesktopServices,
    QShortcut, QKeySequence, QPalette,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QListWidget, QAbstractItemView,
    QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QFrame, QSizePolicy,
)

from . import __version__, __author__, __github_owner__, __github_repo__
from .core import process_folder, process_files

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RELEASES_URL = f"https://github.com/{__github_owner__}/{__github_repo__}/releases"
_API_URL      = (
    f"https://api.github.com/repos/{__github_owner__}/{__github_repo__}/releases/latest"
)
_IS_BUNDLED   = hasattr(sys, '_MEIPASS')


# ---------------------------------------------------------------------------
# Update helpers
# ---------------------------------------------------------------------------

def _fetch_latest_release():
    req = urllib.request.Request(
        _API_URL, headers={"User-Agent": "logic-patcher-updater"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return data["tag_name"], data.get("assets", []), data.get("html_url", _RELEASES_URL)


def _version_tuple(v):
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def _find_deb_asset(assets):
    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "armhf"}
    arch = arch_map.get(platform.machine(), platform.machine())
    for a in assets:
        if a["name"].endswith(f"_{arch}.deb"):
            return a
    for a in assets:          # arch-agnostic fallback
        if a["name"].endswith(".deb"):
            return a
    return None


# ---------------------------------------------------------------------------
# Icon helper
# ---------------------------------------------------------------------------

def _app_icon():
    for name in ("icon.svg", "icon.png"):
        for candidate in (
            os.path.join(getattr(sys, "_MEIPASS", ""), "assets", name),
            os.path.join(os.path.dirname(__file__), "..", "assets", name),
        ):
            p = os.path.normpath(candidate)
            if os.path.isfile(p):
                return QIcon(p)
    return QIcon()


# ---------------------------------------------------------------------------
# Custom title bar
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Drop-aware list widget
# ---------------------------------------------------------------------------

class _DropList(QListWidget):
    paths_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.paths_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# ---------------------------------------------------------------------------
# Signal carriers
# ---------------------------------------------------------------------------

class _WorkerSignals(QObject):
    log      = Signal(str)
    progress = Signal(int, int)
    finished = Signal(int, int, str)
    error    = Signal(str)


class _UpdateSignals(QObject):
    result = Signal(str, object, str)   # tag, asset|None, release_url
    error  = Signal(str)


class _DlSignals(QObject):
    log      = Signal(str)
    progress = Signal(int, int, int)  # pct, done_bytes, total_bytes
    done     = Signal(str)            # dest path
    error    = Signal(str)


# ---------------------------------------------------------------------------
# About dialog
# ---------------------------------------------------------------------------

class _AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("About Logic Patcher")
        self.setWindowIcon(parent.windowIcon() if parent else QIcon())
        self.setFixedSize(460, 240)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        bg = QApplication.instance().palette().color(QPalette.ColorRole.Window).name()
        card = QFrame()
        card.setObjectName("aboutCard")
        card.setStyleSheet(
            f"#aboutCard {{ background: {bg}; border-radius: 12px; }}"
        )
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setSpacing(8)
        lay.setContentsMargins(32, 24, 32, 20)

        version = QLabel(f"<b style='font-size:13pt'>Version {__version__}</b>")
        version.setAlignment(Qt.AlignCenter)
        lay.addWidget(version)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        lay.addWidget(sep)

        desc = QLabel(
            "Patches .logic binary files by replacing the\n"
            "student name and roll number stored inside."
        )
        desc.setAlignment(Qt.AlignCenter)
        lay.addWidget(desc)

        author = QLabel(f"Created by  <b>{__author__}</b>")
        author.setAlignment(Qt.AlignCenter)
        lay.addWidget(author)

        gh = QLabel(
            f'<a href="https://github.com/{__github_owner__}">'
            f'github.com/{__github_owner__}</a>'
        )
        gh.setAlignment(Qt.AlignCenter)
        gh.setOpenExternalLinks(True)
        lay.addWidget(gh)

        repo = QLabel(f'<a href="{_RELEASES_URL}">Releases</a>')
        repo.setAlignment(Qt.AlignCenter)
        repo.setOpenExternalLinks(True)
        lay.addWidget(repo)

        lay.addStretch()

        close = QPushButton("Close")
        close.setFixedWidth(100)
        close.setAutoDefault(False)
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignCenter)


# ---------------------------------------------------------------------------
# Log styling
# ---------------------------------------------------------------------------

_MONO = QFont("Monospace", 9)
_MONO.setStyleHint(QFont.StyleHint.Monospace)

_LOG_RULES = [
    ("[OK]",        "#2ecc71", False, False),
    ("[--]",        "#7f8c8d", False, True),
    ("[!!]",        "#e67e22", False, False),
    ("ERROR",       "#e74c3c", True,  False),
    ("   replaced", "#7f8c8d", False, True),
    ("──",          "#5dade2", True,  False),
    ("===",         "#ecf0f1", True,  False),
]


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class _MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logic Patcher")
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(700, 580)
        self._mode         = "folder"
        self._last_out     = None
        self._install_proc = None
        self._build_ui()
        self._restore_geometry()
        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(10)
        main.setContentsMargins(14, 14, 14, 14)

        # ── Menu bar ──────────────────────────────────────────────────
        menu = self.menuBar().addMenu("☰")
        menu.addAction("About Logic Patcher", self._show_about)
        menu.addAction("Check for Updates",   self._check_for_updates)

        # ── Student info ──────────────────────────────────────────────
        info_box = QFrame()
        info_box.setFrameShape(QFrame.StyledPanel)
        form = QFormLayout(info_box)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Rahul Tudu")
        self.roll_edit = QLineEdit()
        self.roll_edit.setPlaceholderText("e.g. BT24CS001")
        form.addRow("Full Name",   self.name_edit)
        form.addRow("Roll Number", self.roll_edit)
        main.addWidget(info_box)

        self.name_edit.editingFinished.connect(
            lambda: self.name_edit.setText(self.name_edit.text().strip().title())
        )
        self.roll_edit.editingFinished.connect(
            lambda: self.roll_edit.setText(self.roll_edit.text().strip().upper())
        )
        self.name_edit.textChanged.connect(lambda: self.name_edit.setStyleSheet(""))
        self.roll_edit.textChanged.connect(lambda: self.roll_edit.setStyleSheet(""))

        # ── Mode toggle ───────────────────────────────────────────────
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(10)
        toggle_row.addWidget(QLabel("Select Mode:"))

        self._mode_group = QButtonGroup(self)
        self.folder_btn  = QRadioButton("Folders")
        self.file_btn    = QRadioButton("Files")
        self.folder_btn.setChecked(True)
        self._mode_group.addButton(self.folder_btn)
        self._mode_group.addButton(self.file_btn)

        _rss = "QRadioButton:checked { color: #2ecc71; font-weight: bold; }"
        self.folder_btn.setStyleSheet(_rss)
        self.file_btn.setStyleSheet(_rss)
        self.folder_btn.toggled.connect(lambda on: on and self._set_mode("folder"))
        self.file_btn.toggled.connect(lambda on: on and self._set_mode("file"))

        toggle_row.addWidget(self.folder_btn)
        toggle_row.addWidget(self.file_btn)
        toggle_row.addStretch()
        main.addLayout(toggle_row)

        # ── Path list ─────────────────────────────────────────────────
        self.path_list = _DropList()
        self.path_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.path_list.setAlternatingRowColors(True)
        self.path_list.setMinimumHeight(110)
        self.path_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.path_list.paths_dropped.connect(self._on_paths_dropped)
        main.addWidget(self.path_list, stretch=2)

        self._drop_hint = QLabel("Drop folders here")
        self._drop_hint.setAlignment(Qt.AlignCenter)
        self._drop_hint.setStyleSheet("color: gray; font-style: italic;")
        self._drop_hint.setParent(self.path_list)
        self._drop_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.path_list.model().rowsInserted.connect(self._sync_hint)
        self.path_list.model().rowsRemoved.connect(self._sync_hint)
        self._sync_hint()

        list_btn_row = QHBoxLayout()
        self.add_btn    = QPushButton("+ Add")
        self.remove_btn = QPushButton("Remove Selected")
        self.clear_btn  = QPushButton("Clear All")
        for btn in (self.add_btn, self.remove_btn, self.clear_btn):
            list_btn_row.addWidget(btn)
        list_btn_row.addStretch()
        self.add_btn.clicked.connect(self._add_paths)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self.path_list.clear)
        main.addLayout(list_btn_row)

        # ── Progress ──────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m  files")
        self.progress.setValue(0)
        self.progress.setFixedHeight(18)
        main.addWidget(self.progress)

        # ── Log header ────────────────────────────────────────────────
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(QLabel("Output Log"))
        log_hdr.addStretch()
        clr_btn  = QPushButton("Clear")
        copy_btn = QPushButton("Copy")
        for b in (clr_btn, copy_btn):
            b.setFixedHeight(22)
            log_hdr.addWidget(b)
        clr_btn.clicked.connect(self._clear_log)
        copy_btn.clicked.connect(self._copy_log)
        main.addLayout(log_hdr)

        # ── Log view ──────────────────────────────────────────────────
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(_MONO)
        self.log_view.document().setDefaultFont(_MONO)
        self.log_view.setMinimumHeight(140)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main.addWidget(self.log_view, stretch=3)

        # ── Run row ───────────────────────────────────────────────────
        run_row = QHBoxLayout()
        self.open_out_btn = QPushButton("Open Output Folder")
        self.open_out_btn.setVisible(False)
        self.open_out_btn.clicked.connect(self._open_output)
        run_row.addWidget(self.open_out_btn)
        run_row.addStretch()
        self.run_btn = QPushButton("Run")
        self.run_btn.setFixedSize(120, 34)
        self.run_btn.setAutoDefault(False)
        self.run_btn.clicked.connect(self._run)
        run_row.addWidget(self.run_btn)
        main.addLayout(run_row)

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._run)

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _settings(self):
        return QSettings("LogicPatcher", "LogicPatcher")

    def _save_geometry(self):
        self._settings().setValue("geometry", self.saveGeometry())

    def _restore_geometry(self):
        geom = self._settings().value("geometry")
        if geom:
            self.restoreGeometry(geom)

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Drop hint overlay
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_hint()

    def _reposition_hint(self):
        if hasattr(self, "_drop_hint"):
            self._drop_hint.setGeometry(self.path_list.rect())

    def _sync_hint(self):
        self._drop_hint.setVisible(self.path_list.count() == 0)
        self._reposition_hint()

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def _set_mode(self, mode):
        self._mode = mode
        self.path_list.clear()
        self._drop_hint.setText(
            "Drop folders here" if mode == "folder"
            else "Drop .logic files or folders here"
        )

    # ------------------------------------------------------------------
    # Path list management
    # ------------------------------------------------------------------

    def _existing_paths(self):
        return {self.path_list.item(i).text() for i in range(self.path_list.count())}

    def _add_if_new(self, path):
        if path not in self._existing_paths():
            self.path_list.addItem(path)

    def _add_paths(self):
        if self._mode == "folder":
            folder = QFileDialog.getExistingDirectory(
                self, "Select Folder", "", QFileDialog.Option.ShowDirsOnly,
            )
            if folder:
                self._add_if_new(folder)
        else:
            dlg = QFileDialog(self, "Select .logic Files")
            dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
            dlg.setNameFilters(["Logic Files (*.logic)", "All Files (*)"])
            dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
            if dlg.exec():
                for f in dlg.selectedFiles():
                    self._add_if_new(f)

    def _on_paths_dropped(self, paths):
        for path in paths:
            if self._mode == "folder":
                if os.path.isdir(path):
                    self._add_if_new(path)
            else:
                if os.path.isfile(path) and path.endswith(".logic"):
                    self._add_if_new(path)
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for fname in sorted(files):
                            if fname.endswith(".logic"):
                                self._add_if_new(os.path.join(root, fname))

    def _remove_selected(self):
        for item in self.path_list.selectedItems():
            self.path_list.takeItem(self.path_list.row(item))

    # ------------------------------------------------------------------
    # Controls state
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled):
        for w in (self.name_edit, self.roll_edit,
                  self.folder_btn, self.file_btn,
                  self.add_btn, self.remove_btn, self.clear_btn,
                  self.path_list):
            w.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _append_log(self, msg):
        color, bold, italic = None, False, False
        for prefix, c, b, i in _LOG_RULES:
            if msg.startswith(prefix):
                color, bold, italic = c, b, i
                break

        escaped = _html.escape(msg).replace(" ", "&nbsp;")
        style   = "font-family:monospace;font-size:9pt;"
        if color:  style += f"color:{color};"
        if bold:   style += "font-weight:bold;"
        if italic: style += "font-style:italic;"

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.insertHtml(f'<span style="{style}">{escaped}</span><br>')
        self.log_view.ensureCursorVisible()

    def _clear_log(self):
        self.log_view.clear()

    def _copy_log(self):
        QApplication.clipboard().setText(self.log_view.toPlainText())

    # ------------------------------------------------------------------
    # Progress + output
    # ------------------------------------------------------------------

    def _update_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def _open_output(self):
        if self._last_out and os.path.isdir(self._last_out):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_out))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_fields(self):
        err_ss = "QLineEdit { border: 1.5px solid #e74c3c; }"
        ok = True
        for edit in (self.name_edit, self.roll_edit):
            if not edit.text().strip():
                edit.setStyleSheet(err_ss)
                ok = False
        return ok

    # ------------------------------------------------------------------
    # Finish / error
    # ------------------------------------------------------------------

    def _finish(self, changed, total, out):
        self._append_log(f"\n{'='*42}")
        self._append_log(f"Files changed : {changed}")
        self._append_log(f"Replacements  : {total}")
        self._append_log(f"Output        : {out}")
        self._last_out = out
        self.run_btn.setText("Run")
        self.run_btn.setEnabled(True)
        self._set_controls_enabled(True)
        self.open_out_btn.setVisible(True)
        self.statusBar().showMessage(
            f"Done — {changed} file(s) patched  ·  Output: {out}"
        )

    def _on_error(self, msg):
        self._append_log(f"ERROR: {msg}")
        self.run_btn.setText("Run")
        self.run_btn.setEnabled(True)
        self._set_controls_enabled(True)
        self.statusBar().showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Error", msg)

    # ------------------------------------------------------------------
    # Run worker
    # ------------------------------------------------------------------

    def _run(self):
        if not self.run_btn.isEnabled():
            return
        if not self._validate_fields():
            return

        name  = self.name_edit.text().strip()
        roll  = self.roll_edit.text().strip()
        paths = [self.path_list.item(i).text() for i in range(self.path_list.count())]

        if not paths:
            label = "folder" if self._mode == "folder" else "file"
            QMessageBox.warning(self, "Nothing Selected", f"Add at least one {label}.")
            return

        self.log_view.clear()
        self.progress.setValue(0)
        self.open_out_btn.setVisible(False)
        self.run_btn.setText("Running…")
        self.run_btn.setEnabled(False)
        self._set_controls_enabled(False)
        self.statusBar().showMessage("Processing…")

        sig  = _WorkerSignals()
        mode = self._mode
        sig.log.connect(self._append_log)
        sig.progress.connect(self._update_progress)
        sig.finished.connect(self._finish)
        sig.error.connect(self._on_error)
        self._sig = sig

        def worker():
            try:
                total_changed = total_reps = 0
                last_out = ""
                if mode == "folder":
                    for folder in paths:
                        sig.log.emit(f"── {folder}")
                        changed, reps, out = process_folder(
                            name, roll, folder,
                            log_callback=sig.log.emit,
                            progress_callback=sig.progress.emit,
                        )
                        total_changed += changed
                        total_reps    += reps
                        last_out       = out
                else:
                    out_folder = os.path.join(os.path.dirname(paths[0]), "replaced_output")
                    changed, reps, out = process_files(
                        name, roll, paths, out_folder,
                        log_callback=sig.log.emit,
                        progress_callback=sig.progress.emit,
                    )
                    total_changed = changed
                    total_reps    = reps
                    last_out      = out
                sig.finished.emit(total_changed, total_reps, last_out)
            except Exception as exc:
                sig.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    # ==================================================================
    # Hamburger menu actions
    # ==================================================================

    def _show_about(self):
        _AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Update checker
    # ------------------------------------------------------------------

    def _check_for_updates(self):
        self.statusBar().showMessage("Checking for updates…")
        sig = _UpdateSignals()
        sig.result.connect(self._on_update_result)
        sig.error.connect(self._on_update_error)
        self._upd_sig = sig

        def worker():
            try:
                tag, assets, url = _fetch_latest_release()
                if sys.platform == "linux":
                    asset = _find_deb_asset(assets)
                elif sys.platform == "win32":
                    asset = next(
                        (a for a in assets if a["name"] == "logic-patcher-gui.exe"), None
                    )
                else:
                    asset = None
                sig.result.emit(tag, asset, url)
            except Exception as exc:
                sig.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_error(self, msg):
        self.statusBar().showMessage("Update check failed.")
        QMessageBox.warning(
            self, "Update Check Failed",
            f"Could not reach GitHub:\n{msg}"
        )

    def _on_update_result(self, tag, asset, release_url):
        current = _version_tuple(__version__)
        latest  = _version_tuple(tag)

        if latest <= current:
            self.statusBar().showMessage("You're up to date.")
            QMessageBox.information(
                self, "No Updates",
                f"Logic Patcher {__version__} is the latest version."
            )
            return

        if not asset:
            self.statusBar().showMessage(f"Update available: {tag}")
            QMessageBox.information(
                self, "Update Available",
                f"Logic Patcher {tag} is available.\n\n"
                f"No automatic installer was found for this platform.\n"
                f"Download it manually from:\n{release_url}"
            )
            return

        self.statusBar().showMessage(f"Update available: {tag}")

        dlg = QDialog(self)
        dlg.setWindowTitle("Update Available")
        dlg.setWindowIcon(self.windowIcon())
        dlg.setFixedWidth(440)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        hdr = QLabel(
            f"<b>Logic Patcher {tag} is available</b><br>"
            f"<small style='color:gray'>You have {__version__}</small>"
        )
        hdr.setWordWrap(True)
        lay.addWidget(hdr)

        info = QLabel(f"The update will be downloaded and installed automatically.")
        info.setWordWrap(True)
        lay.addWidget(info)

        btn_row = QHBoxLayout()
        later_btn  = QPushButton("Later")
        later_btn.setAutoDefault(False)
        update_btn = QPushButton("Update Now")
        update_btn.setAutoDefault(False)
        btn_row.addWidget(later_btn)
        btn_row.addStretch()
        btn_row.addWidget(update_btn)
        lay.addLayout(btn_row)

        later_btn.clicked.connect(dlg.reject)
        update_btn.clicked.connect(dlg.accept)

        if dlg.exec() == QDialog.Accepted:
            self._download_and_install(asset)

    # ------------------------------------------------------------------
    # Download + install
    # ------------------------------------------------------------------

    def _restore_progress_bar(self):
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m  files")

    def _download_and_install(self, asset):
        url  = asset["browser_download_url"]
        name = asset["name"]
        dest = os.path.join(tempfile.gettempdir(), name)

        self.run_btn.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Downloading… %p%")
        self._append_log(f"── Downloading update: {name}")
        self.statusBar().showMessage(f"Downloading {name}…")

        dl_sig = _DlSignals()
        dl_sig.log.connect(self._append_log)
        dl_sig.progress.connect(self._on_dl_progress)
        dl_sig.done.connect(self._on_dl_done)
        dl_sig.error.connect(self._on_dl_error)
        self._dl_sig = dl_sig

        def worker():
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "logic-patcher-updater"}
                )
                with urllib.request.urlopen(req) as r:
                    total = int(r.headers.get("Content-Length", 0))
                    done  = 0
                    last_milestone = -1
                    with open(dest, "wb") as f:
                        while True:
                            chunk = r.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            if total:
                                pct = int(done * 100 / total)
                                dl_sig.progress.emit(pct, done, total)
                                milestone = (pct // 25) * 25
                                if milestone > last_milestone:
                                    last_milestone = milestone
                                    mb_done  = done / 1_048_576
                                    mb_total = total / 1_048_576
                                    dl_sig.log.emit(
                                        f"   {pct}%  {mb_done:.1f} / {mb_total:.1f} MB"
                                    )
                dl_sig.progress.emit(100, done, total or done)
                dl_sig.done.emit(dest)
            except Exception as exc:
                dl_sig.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_dl_progress(self, pct, done, total):
        self.progress.setValue(pct)
        mb = done / 1_048_576
        self.statusBar().showMessage(f"Downloading… {mb:.1f} MB")

    def _on_dl_done(self, path):
        self._append_log("[OK] Download complete.")
        self.progress.setValue(100)

        if sys.platform == "win32":
            import subprocess
            subprocess.Popen([path])
            self._restore_progress_bar()
            self.run_btn.setEnabled(True)
            QMessageBox.information(
                self, "Update Ready",
                "The new version has been launched. You can close this one."
            )
            return

        # Linux — install via pkexec dpkg
        self.progress.setRange(0, 0)   # indeterminate spinner
        self.progress.setFormat("Installing…")
        self._append_log("── Installing update (requires admin password)…")
        self.statusBar().showMessage("Installing update…")

        self._install_proc = QProcess(self)
        self._install_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._install_proc.readyReadStandardOutput.connect(self._on_install_output)
        self._install_proc.finished.connect(
            lambda code, _: self._on_install_finished(code, path)
        )
        self._install_proc.start("pkexec", ["dpkg", "-i", path])

    def _on_install_output(self):
        raw  = bytes(self._install_proc.readAllStandardOutput())
        text = raw.decode("utf-8", errors="replace").rstrip()
        for line in text.splitlines():
            if line.strip():
                self._append_log(f"   {line}")

    def _on_install_finished(self, exit_code, deb_path):
        self._restore_progress_bar()
        self.run_btn.setEnabled(True)
        if exit_code == 0:
            self.statusBar().showMessage("Update installed.")
            self._append_log("[OK] Update installed — please restart the application.")
            QMessageBox.information(
                self, "Update Installed",
                "Logic Patcher was updated successfully.\n"
                "Please restart the application."
            )
        else:
            self.statusBar().showMessage("Installation failed.")
            self._append_log(f"[!!] Installation failed (exit code {exit_code})")
            QMessageBox.warning(
                self, "Installation Failed",
                f"dpkg returned exit code {exit_code}.\n\n"
                f"You can install manually:\n"
                f"  sudo dpkg -i {deb_path}"
            )

    def _on_dl_error(self, msg):
        self._restore_progress_bar()
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage("Download failed.")
        self._append_log(f"ERROR: Download failed — {msg}")
        QMessageBox.critical(self, "Download Failed", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _charcoal_palette():
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          "#232323")
    p.setColor(QPalette.ColorRole.WindowText,      "#e8e8e8")
    p.setColor(QPalette.ColorRole.Base,            "#181818")
    p.setColor(QPalette.ColorRole.AlternateBase,   "#2a2a2a")
    p.setColor(QPalette.ColorRole.Text,            "#e8e8e8")
    p.setColor(QPalette.ColorRole.BrightText,      "#ffffff")
    p.setColor(QPalette.ColorRole.Button,          "#2e2e2e")
    p.setColor(QPalette.ColorRole.ButtonText,      "#e8e8e8")
    p.setColor(QPalette.ColorRole.Highlight,       "#4a90d9")
    p.setColor(QPalette.ColorRole.HighlightedText, "#ffffff")
    p.setColor(QPalette.ColorRole.Link,            "#4a90d9")
    p.setColor(QPalette.ColorRole.Mid,             "#505050")
    p.setColor(QPalette.ColorRole.Midlight,        "#3a3a3a")
    p.setColor(QPalette.ColorRole.Dark,            "#141414")
    p.setColor(QPalette.ColorRole.Shadow,          "#0a0a0a")
    p.setColor(QPalette.ColorRole.ToolTipBase,     "#2e2e2e")
    p.setColor(QPalette.ColorRole.ToolTipText,     "#e8e8e8")
    p.setColor(QPalette.ColorRole.PlaceholderText, "#777777")
    return p


def _apply_theme(app):
    app.setStyle("Fusion")
    try:
        is_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        is_dark = True  # default to dark on older Qt
    app.setPalette(_charcoal_palette() if is_dark else QPalette())


def launch_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setDesktopFileName("logic-patcher")
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
        app.styleHints().colorSchemeChanged.connect(lambda _: _apply_theme(app))
    except AttributeError:
        pass  # Qt < 6.5
    _apply_theme(app)
    app.setWindowIcon(_app_icon())
    win = _MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    launch_gui()
