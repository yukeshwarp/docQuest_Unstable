import io
import requests
import fitz  # PyMuPDF
import os
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# Azure Function URL for PPT to PDF conversion
azure_function_url = 'https://doc2pdf.azurewebsites.net/api/HttpTrigger1'

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

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    return ' '.join(word for word in text.split())

def process_single_page(page_number, pdf_document, previous_summary):
    """Process a single page of the PDF."""
    page = pdf_document.load_page(page_number)
    text = page.get_text("text").strip()
    preprocessed_text = remove_stopwords_and_blanks(text)

    # Summarize the page text
    summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
    
    # Detect images or vector graphics on the page
    detected_images = detect_ocr_images_and_vector_graphics(pdf_document, 0.19)
    image_analysis = []

    for img_page, base64_image in detected_images:
        if img_page == page_number + 1:
            image_explanation = get_image_explanation(base64_image)
            image_analysis.append({"page_number": img_page, "explanation": image_explanation})

    return {
        "page_number": page_number + 1,
        "text_summary": summary,
        "image_analysis": image_analysis
    }, summary

def process_pdf_pages(uploaded_file):
    """Process the PDF and extract text/image summaries."""
    if uploaded_file.type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        pdf_stream = ppt_to_pdf(uploaded_file)
    else:
        pdf_stream = io.BytesIO(uploaded_file.read())

    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    
    document_data = {"pages": [], "name": uploaded_file.name}
    previous_summary = ""

    with ThreadPoolExecutor() as executor:
        future_to_page = {
            executor.submit(process_single_page, page_number, pdf_document, previous_summary): page_number
            for page_number in range(len(pdf_document))
        }

        for future in as_completed(future_to_page):
            page_number = future_to_page[future]
            try:
                page_data, previous_summary = future.result()
                document_data["pages"].append(page_data)
            except Exception as e:
                print(f"Error processing page {page_number + 1}: {e}")

    return document_data

def summarize_page(page_text, previous_summary, page_number):
    """Summarize a single page's text using LLM."""
    prompt_message = (
        f"Summarize the following page (Page {page_number}) with context from the previous summary.\n\n"
        f"Previous summary: {previous_summary}\n\n"
        f"Text:\n{page_text}\n"
    )
    azure_endpoint, api_key, api_version, model = get_env_variables()

    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers={
            "Content-Type": "application/json",
            "api-key": api_key
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an assistant that summarizes text with context."},
                {"role": "user", "content": prompt_message}
            ],
            "temperature": 0.0
        }
    )
    
    if response.status_code == 200:
        summary = response.json()['choices'][0]['message']['content'].strip()
        return summary
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

def get_env_variables():
    """Fetch environment variables."""
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    api_key = os.getenv("API_KEY")
    api_version = os.getenv("API_VERSION")
    model = os.getenv("MODEL")
    
    if not all([azure_endpoint, api_key, api_version, model]):
        raise EnvironmentError("One or more environment variables are missing.")
    
    return azure_endpoint, api_key, api_version, model

def get_image_explanation(base64_image):
    """Get image explanation from OpenAI API."""
    azure_endpoint, api_key, api_version, model = get_env_variables()
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds in Markdown."},
            {"role": "user", "content": f"Explain the content of this image in a single, coherent paragraph. The explanation should be concise and semantically meaningful."},
            {"role": "user", "content": {"image_url": f"data:image/png;base64,{base64_image}"}}
        ],
        "temperature": 0.7
    }

    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        explanation = response.json()['choices'][0]['message']['content']
        return explanation
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

def ask_question(documents, question):
    """Answer a question based on the summarized content of multiple PDFs."""
    combined_content = ""
    
    for doc_name, doc_data in documents.items():
        combined_content += f"--- Document: {doc_name} ---\n"
        combined_content += " ".join([page['text_summary'] for page in doc_data["pages"]])
    
    azure_endpoint, api_key, api_version, model = get_env_variables()
    
    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
        headers={
            "Content-Type": "application/json",
            "api-key": api_key
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an assistant that answers questions based on provided knowledge base."},
                {"role": "user", "content": f"Use the context as knowledge base and answer the question in a proper readable format: {question}\n\nContext:\n{combined_content}"}
            ],
            "temperature": 0.0
        }
    )

    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

def detect_ocr_images_and_vector_graphics(pdf_document, ocr_text_threshold=0.1):
    """Detect pages with OCR images or vector graphics."""
    detected_pages = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
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
                detected_pages.append((page_number + 1, base64_image))

    return detected_pages