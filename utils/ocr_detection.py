import fitz  # PyMuPDF
import base64

def detect_ocr_images_and_vector_graphics(pdf_document, ocr_text_threshold=0.1):
    """Detect pages with OCR images or vector graphics."""
    detected_pages = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)

        # Detect all images, including embedded or hidden
        images = page.get_images(full=True)
        image_count = len(images)

        # Get all vector graphics on the page
        vector_graphics_detected = bool(page.get_drawings())

        # Get all text and text blocks
        text = page.get_text("text")
        text_blocks = page.get_text("blocks")

        # Calculate page area for text coverage analysis
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area if page_area else 0  # Avoid division by zero

        # Detect if the page contains images or vector graphics and has less text coverage
        if (image_count > 0 or vector_graphics_detected) and (not text or text_coverage < ocr_text_threshold):
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            base64_image = base64.b64encode(img_data).decode("utf-8")
            detected_pages.append((page_number + 1, base64_image, image_count, vector_graphics_detected))

    return detected_pages
