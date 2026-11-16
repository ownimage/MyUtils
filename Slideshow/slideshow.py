"""Compatibility API for the native slideshow renderer; Photoshop is not used."""
from template_render import default_template, render_file, ensure_fonts


def create_slide(filename, title, date, template=None):
    ensure_fonts()
    render_file(filename, title, date, template if template is not None else default_template())
