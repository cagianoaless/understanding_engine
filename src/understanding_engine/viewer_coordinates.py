"""Explicit native-image/CSS/PDF mapping for the local viewer, not a viewport guess."""

import math

from .contracts import ExtractionError
from .hybrid import _docling_geometry


def require(condition, message):
    if not condition:
        raise ExtractionError("invalid_viewer_request", message)


def _numbers(values, length):
    require(isinstance(values, (list, tuple)) and len(values) == length and
            all(type(v) in (int, float) and math.isfinite(v) for v in values), "Invalid finite coordinate vector")


def browser_to_pdf(geometry, image_pixels, display_rect, pointer):
    """display_rect=[left,top,width,height]; pointer=[clientX,clientY], CSS px.

    No border/padding/object-fit/rotation is permitted on the image. CSS scaling,
    scrolling and browser zoom are represented by its actual DOMRect. X and Y
    scales are independent; do not multiply client coordinates by device DPR.
    """
    _docling_geometry(geometry, {k: geometry[k] for k in ["width", "height"]})
    _numbers(image_pixels, 2); _numbers(display_rect, 4); _numbers(pointer, 2)
    require(all(type(v) is int and 0 < v <= 8192 for v in image_pixels), "Invalid raster dimensions")
    left, top, width, height = display_rect
    require(width > 0 and height > 0, "Image has no displayed area")
    x, y = pointer[0]-left, pointer[1]-top
    require(0 <= x <= width and 0 <= y <= height, "Pointer outside displayed image")
    raster_x, raster_y = x*image_pixels[0]/width, y*image_pixels[1]/height
    return [raster_x*geometry["width"]/image_pixels[0], raster_y*geometry["height"]/image_pixels[1]]
