import fitz  # PyMuPDF
import io
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.ocr_detection import detect_ocr_images_and_vector_graphics
from utils.llm_interaction import summarize_page

# URL of your Azure function endpoint
azure_function_url = 'https://doc2pdf.azurewebsites.net/api/HttpTrigger1'

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    cleaned_text = ' '.join(word for word in text.split())
    return cleaned_text

def process_single_page(page_number, pdf_document, previous_summary):
    """Process a single page of the PDF."""
    page = pdf_document.load_page(page_number)
    text = page.get_text("text").strip()
    preprocessed_text = remove_stopwords_and_blanks(text)

    # Summarize the page text
    summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
    
    # Detect images or vector graphics on the page
    detected_images = detect_ocr_images_and_vector_graphics(pdf_document, 0.18)
    image_analysis = []

    for img_page, base64_image in detected_images:
        if img_page == page_number + 1:
            image_analysis.append({"page_number": img_page, "image_data": base64_image})

    return {
        "page_number": page_number + 1,
        "text_summary": summary,
        "image_analysis": image_analysis
    }, summary

def ppt_to_pdf(ppt_file):
    """Convert PPT to PDF using Azure Function."""
    mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Type-Actual": mime_type
    }
    response = requests.post(azure_function_url, data=ppt_file.read(), headers=headers)
    if response.status_code == 200:
        return io.BytesIO(response.content)  # Return PDF as a BytesIO stream
    else:
        raise Exception(f"File conversion failed with status code: {response.status_code}, Response: {response.text}")

def process_pdf_pages(uploaded_file):
    """Process the PDF and extract text/image summaries."""
    # Check the file type and process accordingly
    if uploaded_file.type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        # Convert PPT to PDF
        pdf_stream = ppt_to_pdf(uploaded_file)
    else:
        # Open the PDF directly
        pdf_stream = io.BytesIO(uploaded_file.read())

    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    
    # Ensure we start with the right structure
    document_data = {"pages": [], "name": uploaded_file.name}  # Include document name
    previous_summary = ""

    # Use ThreadPoolExecutor for parallel processing of pages
    with ThreadPoolExecutor() as executor:
        future_to_page = {
            executor.submit(process_single_page, page_number, pdf_document, previous_summary): page_number
            for page_number in range(len(pdf_document))
        }

        for future in as_completed(future_to_page):
            page_number = future_to_page[future]
            try:
                page_data, previous_summary = future.result()
                document_data["pages"].append(page_data)  # Ensure we append page data correctly
            except Exception as e:
                print(f"Error processing page {page_number + 1}: {e}")

    # Debugging output to verify structure
    print(f"Processed document data for {uploaded_file.name}: {document_data}")

    return document_data
