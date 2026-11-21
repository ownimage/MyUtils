"""Rebuild Windows multi-resolution icons from the suite's original SVG sources."""
import io
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main():
    folder = Path(__file__).resolve().parents[1] / 'assets' / 'icons'
    for source in sorted(folder.glob('*.svg')):
        renderer = QSvgRenderer(str(source))
        if not renderer.isValid():
            raise ValueError(f'Invalid icon: {source}')
        image = QImage(256, 256, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        Image.open(io.BytesIO(bytes(buffer.data()))).save(
            source.with_suffix('.ico'), sizes=[(size, size) for size in (16,20,24,32,40,48,64,128,256)])
        print(source.with_suffix('.ico').name)


if __name__ == '__main__':
    main()
