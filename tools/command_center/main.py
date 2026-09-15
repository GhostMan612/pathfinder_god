# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import json
import random
import re
import sys
import threading
from pathlib import Path

import hub_api
import services
import sfx
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

PALETTE = {
    "bg": "#1E1B18",
    "panel": "#28241F",
    "text": "#F3E9D2",
    "gold": "#D4AF37",
    "crimson": "#7B1E1E",
    "green": "#4CAF50",
    "red": "#F44336",
    "muted": "#9E9484",
}

QSS = f"""
QWidget {{ background: {PALETTE['bg']}; color: {PALETTE['text']}; font-size: 13px; }}
QLabel#header {{ color: {PALETTE['gold']}; font-size: 18px; font-weight: bold; }}
QLabel#muted {{ color: {PALETTE['muted']}; font-size: 11px; }}
QLineEdit, QComboBox, QSpinBox {{ background: {PALETTE['panel']}; border: 1px solid {PALETTE['gold']}; border-radius: 4px; padding: 6px; }}
QPushButton {{ background: {PALETTE['crimson']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['gold']}; border-radius: 4px; padding: 7px 16px; font-weight: bold; }}
QPushButton:hover {{ background: #932828; }}
QPushButton:disabled {{ color: {PALETTE['muted']}; border-color: {PALETTE['muted']}; }}
QTabWidget::pane {{ border: 1px solid {PALETTE['gold']}; }}
QTabBar::tab {{ background: {PALETTE['panel']}; padding: 8px 18px; border: 1px solid {PALETTE['gold']}; }}
QTabBar::tab:selected {{ background: {PALETTE['crimson']}; color: {PALETTE['text']}; font-weight: bold; }}
QTextBrowser {{ background: {PALETTE['panel']}; border: 1px solid {PALETTE['gold']}; border-radius: 4px; padding: 8px; }}
QStatusBar {{ background: {PALETTE['panel']}; color: {PALETTE['muted']}; }}
"""

CHAT_HISTORY_FILE = Path(__file__).parent / "chat_history.json"


class CallSignal(QObject):
    ok = Signal(object)
    fail = Signal(str)


def run_bg(fn, on_ok=None, on_fail=None):
    sig = CallSignal()
    if on_ok:
        sig.ok.connect(on_ok)
    if on_fail:
        sig.fail.connect(on_fail)

    def runner():
        try:
            result = fn()
            sig.ok.emit(result)
        except Exception as e:
            sig.fail.emit(str(e))

    threading.Thread(target=runner, daemon=True).start()


def dot(color: str) -> str:
    return f'<span style="color:{color}; font-size:16px;">&#9679;</span>'


def header_label(text: str, name: str = "header") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    return lbl


class ServicesTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self._status_bar = status_bar
        root = QVBoxLayout(self)

        root.addWidget(header_label("Services"))
        root.addWidget(header_label("Ollama serves the local LLM; the Hub is the FastAPI God on :8000. "
                                    "Start Ollama first, then the Hub.", "muted"))

        self._ollama_dot = QLabel(dot(PALETTE["muted"]))
        self._ollama_label = QLabel(f"Ollama ({hub_api.OLLAMA_URL}) - checking...")
        ollama_row = QHBoxLayout()
        ollama_row.addWidget(self._ollama_dot)
        ollama_row.addWidget(self._ollama_label)
        ollama_row.addStretch()
        b_ollama = QPushButton("Start")
        b_ollama.clicked.connect(self._start_ollama)
        b_ollama_stop = QPushButton("Stop")
        b_ollama_stop.clicked.connect(self._stop_ollama)
        b_ollama_log = QPushButton("Log")
        b_ollama_log.clicked.connect(lambda: self._show_log("Ollama"))
        ollama_row.addWidget(b_ollama)
        ollama_row.addWidget(b_ollama_stop)
        ollama_row.addWidget(b_ollama_log)
        root.addLayout(ollama_row)

        self._hub_dot = QLabel(dot(PALETTE["muted"]))
        self._hub_label = QLabel("Hub (:8000) - checking...")
        self._hub_detail = QLabel("", objectName="muted")
        hub_row = QHBoxLayout()
        hub_row.addWidget(self._hub_dot)
        hub_row.addWidget(self._hub_label)
        hub_row.addStretch()
        b_hub = QPushButton("Start")
        b_hub.clicked.connect(self._start_hub)
        b_hub_stop = QPushButton("Stop")
        b_hub_stop.clicked.connect(self._stop_hub)
        b_hub_log = QPushButton("Log")
        b_hub_log.clicked.connect(lambda: self._show_log("Hub"))
        hub_row.addWidget(b_hub)
        hub_row.addWidget(b_hub_stop)
        hub_row.addWidget(b_hub_log)
        root.addLayout(hub_row)
        root.addWidget(self._hub_detail)

        root.addStretch()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _show_log(self, name):
        if name == "Ollama":
            text = services.ollama.get_log_tail()
        else:
            text = services.hub.get_log_tail()
        self._status_bar.showMessage(f"Showing {name} log (check console)", 3000)
        print(f"\n=== {name} LOG ===\n{text}\n")

    def _refresh(self):
        ollama_ok = hub_api.ollama_up()
        self._ollama_dot.setText(dot(PALETTE["green"] if ollama_ok else PALETTE["red"]))
        self._ollama_label.setText(f"Ollama ({hub_api.OLLAMA_URL}) - "
                                   f"{'running' if ollama_ok else 'down'}"
                                   f"{' (managed)' if services.ollama.running else ''}")

        health = hub_api.hub_health()
        hub_ok = health is not None
        self._hub_dot.setText(dot(PALETTE["green"] if hub_ok else PALETTE["red"]))
        self._hub_label.setText(f"Hub (:8000) - {'running' if hub_ok else 'down'}"
                                f"{' (managed)' if services.hub.running else ''}")
        if health:
            self._hub_detail.setText(
                f"model: {health.get('ollama_model', '?')}   |   "
                f"databases: {', '.join(health.get('databases_found', []) or ['none'])}   |   "
                f"version: {health.get('version', '?')}")
        else:
            self._hub_detail.setText("")

    def _start_ollama(self):
        ok, msg = services.start_ollama()
        self._status_bar.showMessage(msg, 5000)
        self._refresh()

    def _stop_ollama(self):
        ok, msg = services.ollama.stop()
        self._status_bar.showMessage(msg, 5000)
        self._refresh()

    def _start_hub(self):
        ok, msg = services.start_hub()
        self._status_bar.showMessage(msg, 5000)
        self._refresh()

    def _stop_hub(self):
        ok, msg = services.hub.stop()
        self._status_bar.showMessage(msg, 5000)
        self._refresh()


class ModelsTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self._status_bar = status_bar
        root = QVBoxLayout(self)
        root.addWidget(header_label("Models"))
        row = QHBoxLayout()
        self._pull_name = QLineEdit()
        self._pull_name.setPlaceholderText("model name to pull, e.g. qwen2.5:3b")
        b_refresh = QPushButton("Refresh")
        b_refresh.clicked.connect(self.refresh)
        b_pull = QPushButton("Pull")
        b_pull.clicked.connect(self._pull)
        row.addWidget(self._pull_name, stretch=1)
        row.addWidget(b_pull)
        row.addWidget(b_refresh)
        root.addLayout(row)
        self._list = QTextBrowser()
        root.addWidget(self._list, stretch=1)
        self.refresh()

    def refresh(self):
        run_bg(hub_api.installed_models, self._show, self._show_err)

    def _show(self, models):
        if not models:
            self._list.setHtml("<i>Ollama is down or no models installed.</i>")
            return
        rows = "".join(
            f"<p><b style='color:{PALETTE['gold']}'>{m.get('name', '?')}</b> "
            f"<span style='color:{PALETTE['muted']}'>"
            f"({m.get('size', 0) / 1e9:.1f} GB)</span></p>"
            for m in models)
        self._list.setHtml(rows)

    def _show_err(self, msg):
        self._list.setHtml(f"<i style='color:{PALETTE['red']}'>{msg}</i>")

    def _pull(self):
        name = self._pull_name.text().strip()
        if not name:
            return
        self._status_bar.showMessage(f"Pulling {name}... (large downloads take a while)", 8000)
        import requests

        def job():
            r = requests.post(f"{hub_api.OLLAMA_URL}/api/pull",
                              json={"name": name}, timeout=3600)
            r.raise_for_status()
            return name

        run_bg(job, lambda _: self.refresh(), self._show_err)


class RulesTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(header_label("Rules Search"))
        row = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("Search rules, spells, feats, monsters...")
        self._query.returnPressed.connect(self._search)
        self._edition = QComboBox()
        self._edition.addItems(["both", "2e", "1e"])
        self._limit = QSpinBox()
        self._limit.setRange(1, 50)
        self._limit.setValue(10)
        b = QPushButton("Search")
        b.clicked.connect(self._search)
        row.addWidget(self._query, stretch=1)
        row.addWidget(self._edition)
        row.addWidget(self._limit)
        row.addWidget(b)
        root.addLayout(row)
        self._results = QTextBrowser()
        root.addWidget(self._results, stretch=1)

    def _search(self):
        q = self._query.text().strip()
        if not q:
            return
        self._results.setHtml("<i>Searching...</i>")
        run_bg(lambda: hub_api.rules_search(q, self._edition.currentText(),
                                            self._limit.value()),
               self._show, self._show_err)

    def _show(self, results):
        if not results:
            self._results.setHtml("<i>No results.</i>")
            return
        parts = []
        for r in results:
            tags = " | ".join(filter(None, [r.get("system", "").upper(),
                                            r.get("category", ""),
                                            r.get("source_book", "")]))
            content = (r.get("content", "") or "").replace("\n", "<br>")
            parts.append(f"<p><b style='color:{PALETTE['gold']}'>{r.get('name', '?')}</b><br>"
                         f"<span style='color:{PALETTE['muted']}'>{tags}</span><br>{content}</p><hr>")
        self._results.setHtml("".join(parts))

    def _show_err(self, msg):
        self._results.setHtml(f"<i style='color:{PALETTE['red']}'>Hub unreachable: {msg}</i>")


GENERATOR_KINDS = ["character", "npc", "monster", "boss", "map", "campaign", "encounter"]


class GeneratorsTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self._status_bar = status_bar
        root = QVBoxLayout(self)
        root.addWidget(header_label("Generators"))
        row = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.addItems(GENERATOR_KINDS)
        self._edition = QComboBox()
        self._edition.addItems(["2e", "1e", "both"])
        b = QPushButton("Generate")
        b.clicked.connect(self._generate)
        row.addWidget(QLabel("kind:"))
        row.addWidget(self._kind)
        row.addWidget(QLabel("edition:"))
        row.addWidget(self._edition)
        row.addWidget(b)
        row.addStretch()
        root.addLayout(row)
        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("e.g. cunning goblin alchemist who hates fire")
        self._prompt.returnPressed.connect(self._generate)
        root.addWidget(self._prompt)
        self._out = QTextBrowser()
        root.addWidget(self._out, stretch=1)

    def _generate(self):
        prompt = self._prompt.text().strip()
        if not prompt:
            return
        kind = self._kind.currentText()
        self._out.setHtml(f"<i>The God is forging your {kind}... (LLM, may take a minute)</i>")
        self._status_bar.showMessage(f"Generating {kind}...", 4000)
        run_bg(lambda: hub_api.generate(kind, prompt, self._edition.currentText()),
               self._show, self._show_err)

    def _show(self, data):
        backend = data.get("backend", "?")
        answer = (data.get("answer", "") or "").replace("\n", "<br>")
        self._out.setHtml(f"<span style='color:{PALETTE['muted']}'>via {backend}</span><br><br>{answer}")

    def _show_err(self, msg):
        self._out.setHtml(f"<i style='color:{PALETTE['red']}'>Generation failed: {msg}</i>")


# Dice notation regex supporting: NdM, NdMkhN, NdMklN, NdMkh, NdMkl
DICE_RE = re.compile(r"(\d*)d(\d+)(?:kh(\d*))?(?:kl(\d*))?", re.IGNORECASE)

def parse_dice_notation(notation: str) -> dict:
    """Parse dice notation into components.
    Supports: NdM, NdMkhN, NdMklN, NdMkh (keep highest 1), NdMkl (keep lowest 1)
    Returns dict with: count, sides, keep_highest, keep_lowest, modifier
    """
    # Strip trailing text like " (Adv)" before parsing
    notation = notation.split(" ")[0].strip()
    
    # Handle modifiers (+N, -N)
    modifier = 0
    # Split on + or - that are not part of kh/kl
    parts = re.split(r'(?<!\w)([+-])(?!\w)', notation)
    # Simple approach: extract trailing modifier
    mod_match = re.search(r'([+-]\d+)$', notation)
    if mod_match:
        modifier = int(mod_match.group(1))
        notation = notation[:mod_match.start()]
    
    m = DICE_RE.fullmatch(notation.strip())
    if not m:
        return {}
    
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    keep_highest = int(m.group(3)) if m.group(3) else (1 if m.group(3) == '' else None)
    keep_lowest = int(m.group(4)) if m.group(4) else (1 if m.group(4) == '' else None)
    
    return {
        'count': count,
        'sides': sides,
        'keep_highest': keep_highest,
        'keep_lowest': keep_lowest,
        'modifier': modifier
    }

def roll_dice(notation: str) -> tuple[int, list[int], dict]:
    """Roll dice according to notation. Returns (total, rolls_list, details_dict)."""
    parsed = parse_dice_notation(notation)
    if not parsed:
        return 0, [], {}
    
    count = parsed['count']
    sides = parsed['sides']
    keep_highest = parsed['keep_highest']
    keep_lowest = parsed['keep_lowest']
    modifier = parsed['modifier']
    
    rolls = [random.randint(1, sides) for _ in range(count)]
    kept = list(rolls)
    
    if keep_highest is not None:
        kept.sort(reverse=True)
        kept = kept[:keep_highest]
    elif keep_lowest is not None:
        kept.sort()
        kept = kept[:keep_lowest]
    
    total = sum(kept) + modifier
    return total, rolls, {
        'notation': notation,
        'rolls': rolls,
        'kept': kept,
        'modifier': modifier,
        'keep_highest': parsed['keep_highest'],
        'keep_lowest': parsed['keep_lowest']
    }


class DiceTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(header_label("Dice"))
        
        # Notation input row
        row = QHBoxLayout()
        self._notation = QLineEdit("2d6+3")
        self._notation.setPlaceholderText("e.g. 2d20kh1 (adv), 2d20kl1 (dis), 4d6kh3, 1d20+5")
        self._notation.returnPressed.connect(self._roll)
        b = QPushButton("Roll")
        b.clicked.connect(self._roll)
        row.addWidget(self._notation, stretch=1)
        row.addWidget(b)
        root.addLayout(row)
        
        # Quick buttons for common rolls
        quick_row = QHBoxLayout()
        quick_rolls = ["d20", "2d20kh1 (Adv)", "2d20kl1 (Dis)", "4d6kh3", "1d20+5", "2d6+3"]
        for qr in quick_rolls:
            btn = QPushButton(qr)
            btn.clicked.connect(lambda _, q=qr: self._set_notation(q))
            quick_row.addWidget(btn)
        root.addLayout(quick_row)
        
        self._result = QLabel("-")
        self._result.setStyleSheet(f"font-size: 42px; font-weight: bold; color: {PALETTE['gold']};")
        self._result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._result)
        self._history = QTextBrowser()
        root.addWidget(self._history, stretch=1)
        self._rolls: list[str] = []

    def _set_notation(self, notation: str):
        self._notation.setText(notation)
        self._roll()

    def _roll(self):
        notation = self._notation.text().strip()
        if not notation:
            return
        total, rolls, details = roll_dice(notation)
        if not details:
            self._result.setText("bad notation")
            return
        
        # Build detail string
        rolls_str = ', '.join(str(r) for r in details['rolls'])
        kept_str = ', '.join(str(r) for r in details['kept']) if 'kept' in details else ''
        kh = details.get('keep_highest')
        kl = details.get('keep_lowest')
        if kh:
            kept_str = f"kh{kh}({kept_str})"
        elif kl:
            kept_str = f"kl{kl}({kept_str})"
        else:
            kept_str = f"[{rolls_str}]"
        
        mod = details.get('modifier', 0)
        mod_str = f" {mod:+d}" if mod != 0 else ""
        line = f"{details['notation']} rolls=[{rolls_str}] kept={kept_str}{mod_str} = {total}"
        
        self._result.setText(str(total))
        self._rolls.insert(0, line)
        self._rolls = self._rolls[:20]
        self._history.setHtml("<br>".join(self._rolls))
        # Royalty-free roll audio (winsound, never blocks/fails the UI)
        if len(rolls) == 1 and rolls[0] == 20 and details.get('modifier', 0) == 0:
            sfx.crit()
        else:
            sfx.roll()


class GuideTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self._status_bar = status_bar
        self._streaming = False
        self._chat_history = []
        root = QVBoxLayout(self)
        root.addWidget(header_label("Guide"))
        self._chat = QTextBrowser()
        root.addWidget(self._chat, stretch=1)
        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask the God... (streams via the Hub WebSocket)")
        self._input.returnPressed.connect(self._send)
        self._edition = QComboBox()
        self._edition.addItems(["both", "2e", "1e"])
        b = QPushButton("Send")
        b.clicked.connect(self._send)
        row.addWidget(self._input, stretch=1)
        row.addWidget(self._edition)
        row.addWidget(b)
        root.addLayout(row)
        self._chat.setHtml("<i>The God awaits your question. Start the Hub in Services first.</i>")
        self._load_chat_history()

    class _ChunkSignal(QObject):
        chunk = Signal(str)
        done = Signal(str)
        fail = Signal(str)

    def _send(self):
        if self._streaming:
            return
        query = self._input.text().strip()
        if not query:
            return
        self._input.clear()
        self._streaming = True
        edition = self._edition.currentText()
        self._chat.append(f"<p align='right'><b style='color:{PALETTE['gold']}'>You:</b> {query}</p>")
        self._chat_history.append({"role": "user", "content": query})
        self._save_chat_history()
        self._status_bar.showMessage("Streaming from the God...", 4000)
        sig = self._ChunkSignal()
        sig.chunk.connect(self._on_chunk)
        sig.done.connect(self._on_done)
        sig.fail.connect(self._on_fail)

        def job():
            try:
                for event in hub_api.stream_events(query, edition):
                    etype = event.get("type", "")
                    if etype == "chunk":
                        sig.chunk.emit(event.get("text", "") or "")
                    elif etype == "error":
                        sig.fail.emit(event.get("message", "hub error"))
                        return
                    elif etype == "end":
                        break
                sig.done.emit("")
            except Exception as e:
                sig.fail.emit(str(e))

        threading.Thread(target=job, daemon=True).start()

    def _on_chunk(self, text):
        cursor = self._chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._chat.setTextCursor(cursor)

    def _on_done(self, _):
        self._streaming = False
        self._chat.append("")
        sfx.tap()
        # Save the assistant's response
        # The full response is in the chat widget; we need to extract it
        # For simplicity, we'll just mark that a response was completed
        pass

    def _on_fail(self, msg):
        self._streaming = False
        self._chat.append(f"<p><i style='color:{PALETTE['red']}'>stream failed: {msg}</i></p>")
        self._chat_history.append({"role": "assistant", "content": f"<i>stream failed: {msg}</i>"})
        self._save_chat_history()

    def _load_chat_history(self):
        try:
            if CHAT_HISTORY_FILE.exists():
                data = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
                self._chat_history = data.get("messages", [])
                if self._chat_history:
                    html_parts = []
                    for msg in self._chat_history:
                        if msg["role"] == "user":
                            html_parts.append(f"<p align='right'><b style='color:{PALETTE['gold']}'>You:</b> {msg['content']}</p>")
                        else:
                            html_parts.append(f"<p>{msg['content']}</p>")
                    self._chat.setHtml("".join(html_parts))
                else:
                    self._chat.setHtml("<i>The God awaits your question. Start the Hub in Services first.</i>")
        except Exception:
            self._chat.setHtml("<i>The God awaits your question. Start the Hub in Services first.</i>")

    def _save_chat_history(self):
        try:
            data = {"messages": self._chat_history}
            CHAT_HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pathfinder God - Command Center")
        self.resize(1080, 760)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("Ready. Start Ollama + Hub in Services, then explore.")
        self.tabs.addTab(ServicesTab(self.statusBar()), "Services")
        self.tabs.addTab(ModelsTab(self.statusBar()), "Models")
        self.tabs.addTab(RulesTab(), "Rules")
        self.tabs.addTab(GeneratorsTab(self.statusBar()), "Generators")
        self.tabs.addTab(DiceTab(), "Dice")
        self.tabs.addTab(GuideTab(self.statusBar()), "Guide")

        # System tray
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(QIcon("app_icon.ico"))
        self._tray_icon.setToolTip("Pathfinder God - Command Center")
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray_icon.showMessage(
            "Pathfinder God",
            "Command Center minimized to tray. Right-click tray icon to quit.",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setApplicationName("Pathfinder God Command Center")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
