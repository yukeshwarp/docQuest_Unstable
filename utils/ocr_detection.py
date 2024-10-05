import fitz  # PyMuPDF
import base64

def detect_ocr_images_and_vector_graphics(pdf_document, ocr_text_threshold=0.25):
    """Detect pages with OCR images or vector graphics."""  
    detected_pages = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        images = page.get_images(full=True)
        text = page.get_text("text")
        text_blocks = page.get_text("blocks")
        vector_graphics_detected = any(page.get_drawings())
        
        # Check if there are images or vector graphics, even if text is minimal
        if images or vector_graphics_detected:
            # You can keep the text coverage logic here if needed for other checks
            if text.strip():
                page_area = page.rect.width * page.rect.height
                text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
                text_coverage = text_area / page_area

                # Only check for text coverage if there's text on the page
                if text_coverage < ocr_text_threshold:
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    base64_image = base64.b64encode(img_data).decode("utf-8")
                    detected_pages.append((page_number + 1, base64_image))
            else:  # No text detected but images/vector graphics found
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                base64_image = base64.b64encode(img_data).decode("utf-8")
                detected_pages.append((page_number + 1, base64_image))

    return detected_pages
