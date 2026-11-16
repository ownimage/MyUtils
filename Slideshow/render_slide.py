"""Render one image with the native renderer (legacy command entry point)."""
import sys
from slideshow import create_slide

if __name__ == '__main__':
    create_slide(sys.argv[1], sys.argv[2], sys.argv[3])
