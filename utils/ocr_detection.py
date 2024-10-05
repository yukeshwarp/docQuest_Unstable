import fitz  # PyMuPDF
import base64

def detect_ocr_images_and_vector_graphics(page, ocr_text_threshold=0.19):
    """Detect images or vector graphics on a single page.

    Args:
        page: The page object to analyze.
        ocr_text_threshold: The threshold for text coverage to determine if an image is detected.

    Returns:
        Tuple containing the page number and base64 image data if an image is detected; otherwise, None.
    """
    # Check for images on the page
    images = page.get_images(full=True)
    text = page.get_text("text")
    text_blocks = page.get_text("blocks")
    vector_graphics_detected = any(page.get_drawings())

    if (images or vector_graphics_detected) and text.strip():
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area

        if text_coverage < ocr_text_threshold:
            pix = page.get_pixmap() 
            img_data = pix.tobytes("png")
            base64_image = base64.b64encode(img_data).decode("utf-8")
            return base64_image  # Return base64 image data

    # If no valid image is detected, return None
    return None
