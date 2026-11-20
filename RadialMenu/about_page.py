"""Offline attribution and exact bundled icon license notices."""
from html import escape
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextBrowser, QDialog
from photo_tools.fluent import QPushButton
from icon_library import libraries, ASSETS

def credits_html():
    sections = ['<h1>About RadialMenu</h1>',
        '<p>Application-specific radial shortcuts. Thank you to the creators of the icon libraries below.</p>',
        '<p>All icon sets remain attributed separately. Full bundled licenses and copyright notices follow; they are available offline.</p>']
    sections.append('<h2>Included icon sets</h2><ul>')
    for slug, manifest in libraries().items():
        sections.append(f'<li><a href="#{escape(slug,quote=True)}">{escape(manifest["label"])}</a> '
            f'{escape(manifest["version"])} — {escape(manifest.get("license_label","See license"))}</li>')
    sections.append('</ul>')
    for slug, manifest in libraries().items():
        label = manifest['label']
        count = sum(not entry.get('retired') for entry in manifest['icons'])
        sections.append(f'<a name="{escape(slug,quote=True)}"></a><h2>{escape(label)} {escape(manifest["version"])}</h2>')
        sections.append(f'<p>{count:,} bundled variants · {escape(manifest.get("license_label","See full license below"))}</p>')
        sections.append('<p>'+escape(manifest.get('attribution', label+' contributors. Copyright and permission notices appear below.'))+'</p>')
        for title,url in [('Project website',manifest.get('website',manifest['source'])),('Downloaded release',manifest['source'])]:
            sections.append(f'<p><a href="{escape(url,quote=True)}">{title}</a></p>')
        text = (ASSETS/slug/'LICENSE').read_text(encoding='utf-8')
        # Preserve every upstream notice, including Lucide's Feather-derived list.
        sections.append('<pre style="white-space: pre-wrap;">'+escape(text)+'</pre>')
    return ''.join(sections)

class AboutPage(QWidget):
    def __init__(self, back, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28,24,28,24)
        heading = QLabel('About & Licenses')
        heading.setObjectName('title')
        layout.addWidget(heading)
        self.browser = QTextBrowser()
        self.browser.setAccessibleName('Icon attributions and full licenses')
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(credits_html())
        layout.addWidget(self.browser,1)
        button = QPushButton('Back')
        button.clicked.connect(back)
        layout.addWidget(button)

def show_about_dialog(parent=None):
    dialog = QDialog(parent)
    dialog.setWindowTitle('RadialMenu — About & Licenses')
    dialog.resize(820,640)
    layout = QVBoxLayout(dialog)
    layout.addWidget(AboutPage(dialog.accept,dialog))
    dialog.exec()
