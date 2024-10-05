import fitz  # PyMuPDF
import base64

def detect_ocr_images_and_vector_graphics(page, ocr_text_threshold=0.1):
    """Detect images or vector graphics on a single page and check text coverage.

    Args:
        page: The page object to analyze.
        ocr_text_threshold (float): The maximum text coverage percentage to consider for OCR detection.

    Returns:
        Base64 image data if an image is detected and text coverage is below the threshold; otherwise, None.
    """
    # Check for images on the page
    images = page.get_images(full=True)
    
    # Check for vector graphics
    vector_graphics_detected = any(page.get_drawings())

    # Get the text and its blocks
    text = page.get_text("text")
    text_blocks = page.get_text("blocks")

    # Proceed only if images or vector graphics are detected and there is some text
    if (images or vector_graphics_detected) and text.strip():
        page_area = page.rect.width * page.rect.height  # Total area of the page
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)  # Total text area
        text_coverage = text_area / page_area  # Calculate text coverage percentage

        # Check if text coverage is below the threshold for OCR detection
        if text_coverage < ocr_text_threshold:
            # Create a pixmap (image) of the page
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")  # Convert pixmap to bytes
            base64_image = base64.b64encode(img_data).decode("utf-8")  # Convert bytes to base64
            return base64_image  # Return base64 image data

    return None  # No images detected or coverage too high
