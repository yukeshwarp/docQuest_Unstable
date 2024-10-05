import fitz  # PyMuPDF
import base64
def detect_ocr_images_and_vector_graphics(page):
    """Detect images or vector graphics on a single page.

    Args:
        page: The page object to analyze.

    Returns:
        Tuple containing page number and base64 image data if an image is detected; otherwise, None.
    """
    # Check for images on the page
    images = page.get_images(full=True)
    
    # Check for vector graphics
    vector_graphics_detected = any(page.get_drawings())

    # If images or vector graphics are detected, generate a base64 image of the page
    if images or vector_graphics_detected:
        pix = page.get_pixmap()  # Create a pixmap of the page
        img_data = pix.tobytes("png")  # Convert pixmap to bytes
        base64_image = base64.b64encode(img_data).decode("utf-8")  # Convert bytes to base64
        return base64_image  # Return base64 image data

    return None  # No images detected
