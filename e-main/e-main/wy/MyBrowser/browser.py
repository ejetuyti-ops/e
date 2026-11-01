import sys
from urllib.parse import quote_plus

from PyQt6.QtCore import QUrl, QSettings
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QLineEdit,
    QProgressBar, QMenu
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


HOME_URL = "https://www.google.com"
SEARCH_URL = "https://www.google.com/search?q={}"


class MyBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("EJET", "EJETBrowser")
        self.setWindowTitle("EJET Browser")
        self.resize(1180, 760)
        self.setStyleSheet("""
            QMainWindow { background: #080d18; color: #e8eefc; }
            QToolBar {
                background: #101a2b; border: 1px solid #263751;
                padding: 8px; spacing: 6px;
            }
            QToolButton {
                color: #dbeafe; background: #1b2a42;
                border: 1px solid #304663; border-radius: 8px;
                padding: 8px 12px; font-weight: 600;
            }
            QToolButton:hover { background: #2457a6; color: white; }
            QLineEdit {
                color: #f1f5ff; background: #0b1424;
                border: 1px solid #385273; border-radius: 10px;
                padding: 10px 14px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #60a5fa; }
            QTabWidget::pane { border: 1px solid #1c2b40; }
            QTabBar::tab {
                color: #a9bad2; background: #111d2e;
                padding: 10px 17px; margin-right: 3px;
            }
            QTabBar::tab:selected { color: white; background: #1b3557; }
            QMenu {
                background: #111d2e; color: #e8eefc;
                border: 1px solid #385273; padding: 5px;
            }
            QMenu::item { padding: 7px 22px; }
            QMenu::item:selected { background: #2457a6; }
            QStatusBar { color: #9fb2cc; background: #0c1524; }
            QProgressBar { background: #1b2a42; border: none; height: 6px; }
            QProgressBar::chunk { background: #60a5fa; }
        """)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self.sync_address)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        toolbar = QToolBar("EJET navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.add_action(toolbar, "←", "رجوع", lambda: self.current_browser().back())
        self.add_action(toolbar, "→", "تقدم", lambda: self.current_browser().forward())
        self.add_action(toolbar, "⟳", "تحديث", lambda: self.current_browser().reload())
        self.add_action(toolbar, "⌂", "الرئيسية", lambda: self.current_browser().setUrl(QUrl(HOME_URL)))

        self.address = QLineEdit()
        self.address.setPlaceholderText("ابحث في Google أو اكتب عنوان موقع...")
        self.address.returnPressed.connect(self.navigate)
        toolbar.addWidget(self.address)

        self.add_action(toolbar, "اذهب", "بحث أو فتح الرابط", self.navigate)
        self.add_action(toolbar, "☆", "إضافة للمفضلة", self.add_bookmark)

        new_tab = QAction("＋ تبويب", self)
        new_tab.setShortcut(QKeySequence("Ctrl+T"))
        new_tab.triggered.connect(lambda: self.add_tab())
        self.addAction(new_tab)
        toolbar.addAction(new_tab)

        self.bookmarks_menu = QMenu("المفضلة", self)
        self.menuBar().addMenu(self.bookmarks_menu)
        self.bookmarks_menu.aboutToShow.connect(self.refresh_bookmarks_menu)

        self.history_menu = QMenu("السجل", self)
        self.menuBar().addMenu(self.history_menu)
        self.history_menu.aboutToShow.connect(self.refresh_history_menu)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(150)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

        self.add_tab(HOME_URL)

    def add_action(self, toolbar, label, tooltip, callback):
        action = QAction(label, self)
        action.setToolTip(tooltip)
        action.triggered.connect(callback)
        toolbar.addAction(action)
        return action

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_tab(self, url=None):
        browser = QWebEngineView()
        index = self.tabs.addTab(browser, "تبويب جديد")
        self.tabs.setCurrentIndex(index)
        browser.urlChanged.connect(lambda qurl, b=browser: self.update_address(qurl, b))
        browser.titleChanged.connect(lambda title, b=browser: self.update_title(title, b))
        browser.loadStarted.connect(lambda b=browser: self.load_started(b))
        browser.loadProgress.connect(lambda value, b=browser: self.update_progress(value, b))
        browser.loadFinished.connect(lambda ok, b=browser: self.load_finished(ok, b))
        browser.setUrl(QUrl(url or HOME_URL))
        return browser

    def navigate(self):
        text = self.address.text().strip()
        if not text:
            return
        if " " in text or ("." not in text and not text.startswith(("http://", "https://"))):
            target = SEARCH_URL.format(quote_plus(text))
        else:
            target = text if text.startswith(("http://", "https://")) else "https://" + text
        self.current_browser().setUrl(QUrl.fromUserInput(target))

    def update_address(self, url, browser):
        if browser == self.current_browser():
            self.address.setText(url.toString())

    def sync_address(self, index):
        browser = self.current_browser()
        if browser:
            self.address.setText(browser.url().toString())
            self.setWindowTitle((browser.title() or "EJET Browser") + " — EJET")

    def update_title(self, title, browser):
        index = self.tabs.indexOf(browser)
        if index >= 0:
            self.tabs.setTabText(index, (title or "تبويب جديد")[:25])
        if browser == self.current_browser():
            self.setWindowTitle((title or "EJET Browser") + " — EJET")

    def load_started(self, browser):
        if browser == self.current_browser():
            self.progress.setValue(0)
            self.progress.show()

    def update_progress(self, value, browser):
        if browser == self.current_browser():
            self.progress.setValue(value)
            if value >= 100:
                self.progress.hide()

    def load_finished(self, ok, browser):
        if browser == self.current_browser():
            self.progress.hide()
            if ok:
                self.statusBar().showMessage("تم تحميل الصفحة", 2500)
                self.save_history(browser.url().toString(), browser.title())
            else:
                self.statusBar().showMessage("تعذّر تحميل الصفحة. تحقق من الإنترنت أو العنوان.", 5000)

    def save_history(self, url, title):
        if not url or url == "about:blank":
            return
        items = self.settings.value("history", [])
        if not isinstance(items, list):
            items = []
        items = [item for item in items if item.get("url") != url]
        items.insert(0, {"title": title or url, "url": url})
        self.settings.setValue("history", items[:100])

    def add_bookmark(self):
        browser = self.current_browser()
        if not browser:
            return
        url = browser.url().toString()
        if not url or url == "about:blank":
            return
        items = self.settings.value("bookmarks", [])
        if not isinstance(items, list):
            items = []
        if any(item.get("url") == url for item in items):
            self.statusBar().showMessage("الموقع موجود في المفضلة", 2500)
            return
        items.append({"title": browser.title() or url, "url": url})
        self.settings.setValue("bookmarks", items)
        self.statusBar().showMessage("تمت إضافة الموقع للمفضلة", 2500)

    def refresh_bookmarks_menu(self):
        self.bookmarks_menu.clear()
        items = self.settings.value("bookmarks", [])
        if not isinstance(items, list) or not items:
            self.bookmarks_menu.addAction("لا توجد مواقع محفوظة")
            return
        for item in items:
            action = self.bookmarks_menu.addAction(item.get("title") or item["url"])
            action.triggered.connect(lambda checked=False, url=item["url"]: self.open_saved_url(url))

    def refresh_history_menu(self):
        self.history_menu.clear()
        items = self.settings.value("history", [])
        if not isinstance(items, list) or not items:
            self.history_menu.addAction("السجل فارغ")
            return
        for item in items[:30]:
            action = self.history_menu.addAction(item.get("title") or item["url"])
            action.triggered.connect(lambda checked=False, url=item["url"]: self.open_saved_url(url))
        self.history_menu.addSeparator()
        clear_action = self.history_menu.addAction("مسح السجل")
        clear_action.triggered.connect(self.clear_history)

    def open_saved_url(self, url):
        if self.current_browser():
            self.current_browser().setUrl(QUrl(url))

    def clear_history(self):
        self.settings.setValue("history", [])
        self.statusBar().showMessage("تم مسح السجل", 2500)

    def close_tab(self, index):
        if self.tabs.count() == 1:
            self.current_browser().setUrl(QUrl(HOME_URL))
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()


app = QApplication(sys.argv)
app.setApplicationName("EJET Browser")
window = MyBrowser()
window.show()
sys.exit(app.exec())
