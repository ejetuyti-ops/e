import sys
from urllib.parse import quote_plus

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QToolBar,
    QLineEdit,
    QProgressBar,
)

from PyQt6.QtWebEngineWidgets import QWebEngineView


class MyBrowser(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("متصفحي الأول")
        self.resize(1100, 720)

        self.setStyleSheet("""
            QMainWindow {
                background: #111827;
            }

            QToolBar {
                background: #1f2937;
                border: none;
                padding: 7px;
                spacing: 5px;
            }

            QToolButton {
                color: white;
                background: #374151;
                padding: 8px;
                border-radius: 6px;
            }

            QToolButton:hover {
                background: #2563eb;
            }

            QLineEdit {
                color: white;
                background: #374151;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 9px;
                selection-background-color: #2563eb;
            }

            QTabWidget::pane {
                border: none;
            }

            QTabBar::tab {
                color: white;
                background: #1f2937;
                padding: 10px 18px;
            }

            QTabBar::tab:selected {
                background: #2563eb;
            }

            QStatusBar {
                color: white;
                background: #111827;
            }
        """)

        # التبويبات
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self.sync_address)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        # شريط الأدوات
        toolbar = QToolBar("شريط المتصفح")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # أزرار التنقل
        back = QAction("رجوع", self)
        back.triggered.connect(
            lambda: self.current_browser().back()
        )
        toolbar.addAction(back)

        forward = QAction("تقدم", self)
        forward.triggered.connect(
            lambda: self.current_browser().forward()
        )
        toolbar.addAction(forward)

        reload = QAction("تحديث", self)
        reload.triggered.connect(
            lambda: self.current_browser().reload()
        )
        toolbar.addAction(reload)

        home = QAction("الرئيسية", self)
        home.triggered.connect(
            lambda: self.current_browser().setUrl(
                QUrl("https://www.google.com")
            )
        )
        toolbar.addAction(home)

        # شريط العنوان
        self.address = QLineEdit()
        self.address.setPlaceholderText(
            "اكتب عنوان الموقع أو كلمات البحث..."
        )
        self.address.returnPressed.connect(self.navigate)
        toolbar.addWidget(self.address)

        # فتح تبويب جديد
        new_tab = QAction("تبويب +", self)
        new_tab.setShortcut(QKeySequence("Ctrl+T"))
        new_tab.triggered.connect(self.add_tab)
        self.addAction(new_tab)
        toolbar.addAction(new_tab)

        # مؤشر تحميل الصفحة
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(150)
        self.progress.setMaximumHeight(8)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

        self.add_tab("https://www.google.com")

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_tab(self, url=None):
        browser = QWebEngineView()

        index = self.tabs.addTab(browser, "تبويب جديد")
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(
            lambda qurl, b=browser: self.update_address(qurl, b)
        )

        browser.titleChanged.connect(
            lambda title, b=browser: self.update_title(title, b)
        )

        browser.loadStarted.connect(
            lambda b=browser: self.load_started(b)
        )

        browser.loadProgress.connect(
            lambda value, b=browser: self.update_progress(value, b)
        )

        browser.loadFinished.connect(
            lambda ok, b=browser: self.load_finished(ok, b)
        )

        if url:
            browser.setUrl(QUrl(url))
        else:
            browser.setUrl(QUrl("https://www.google.com"))

        return browser

    def navigate(self):
        text = self.address.text().strip()

        if not text:
            return

        # إذا كتب المستخدم كلمات، يبحث عنها في Google.
        if " " in text or (
            "." not in text
            and not text.startswith(("http://", "https://"))
            and not text.startswith("localhost")
        ):
            url = QUrl(
                "https://www.google.com/search?q="
                + quote_plus(text)
            )
        else:
            if not text.startswith(("http://", "https://")):
                text = "https://" + text

            url = QUrl(text)

        self.current_browser().setUrl(url)

    def update_address(self, url, browser):
        if browser == self.current_browser():
            self.address.setText(url.toString())

    def sync_address(self, index):
        browser = self.current_browser()

        if browser:
            self.address.setText(browser.url().toString())
            self.setWindowTitle(
                (browser.title() or "تبويب جديد") + " - متصفحي"
            )

    def update_title(self, title, browser):
        index = self.tabs.indexOf(browser)

        if index >= 0:
            self.tabs.setTabText(
                index,
                (title or "تبويب جديد")[:25]
            )

        if browser == self.current_browser():
            self.setWindowTitle(
                (title or "متصفحي الأول") + " - متصفحي"
            )

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

            if not ok:
                self.statusBar().showMessage(
                    "تعذّر تحميل الصفحة. تحقق من الإنترنت أو العنوان.",
                    5000
                )
            else:
                self.statusBar().showMessage("تم تحميل الصفحة", 2500)

    def close_tab(self, index):
        if self.tabs.count() == 1:
            self.tabs.currentWidget().setUrl(
                QUrl("https://www.google.com")
            )
            return

        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()


app = QApplication(sys.argv)
app.setApplicationName("MyBrowser")

window = MyBrowser()
window.show()

sys.exit(app.exec())