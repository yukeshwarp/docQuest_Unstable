import io
import requests
import fitz  # PyMuPDF
import os
import base64
import ray
from dotenv import load_dotenv
ray.init()
load_dotenv()  # Load environment variables from the .env file

azure_endpoint = os.getenv("AZURE_ENDPOINT")
api_key = os.getenv("API_KEY")
api_version = os.getenv("API_VERSION")
model = os.getenv("MODEL")

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    cleaned_text = ' '.join(word for word in text.split())
    return cleaned_text

def detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold=0.1):
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

def get_image_explanation(base64_image):
    """Get image explanation from OpenAI API."""
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds in Markdown."},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": "Explain the content of this image in a single, coherent paragraph. The explanation should be concise and semantically meaningful."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                }
            ]}
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
        return f"Error: {response.status_code}, {response.text}"

def summarize_page(page_text, previous_summary, page_number):
    """Summarize a single page's text using LLM."""
    prompt_message = (
        f"Summarize the following page (Page {page_number}) with context from the previous summary.\n\n"
        f"Previous summary: {previous_summary}\n\n"
        f"Text:\n{page_text}\n"
    )

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
        return f"Error: {response.status_code}, {response.text}"

@ray.remote
def process_single_page(page_number, pdf_document, previous_summary):
    """Process a single page to extract the text summary and image analysis."""
    page = pdf_document.load_page(page_number)
    text = page.get_text("text").strip()
    preprocessed_text = remove_stopwords_and_blanks(text)

    # Summarize the page
    summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)

    # Detect images or graphics on the page
    base64_image = detect_ocr_images_and_vector_graphics_in_pdf(page)
    image_analysis = []

    if base64_image:
        image_explanation = get_image_explanation(base64_image)
        image_analysis.append({"page_number": page_number + 1, "explanation": image_explanation})

    return {
        "page_number": page_number + 1,
        "text_summary": summary,
        "image_analysis": image_analysis
    }

def process_pdf_pages(uploaded_file):
    """Process each page of the PDF using Ray for parallelization."""
    # Open the PDF document from the uploaded file stream
    pdf_stream = io.BytesIO(uploaded_file.read())
    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    
    document_data = {"pages": [], "name": uploaded_file.name}

    # Create Ray tasks for each page
    tasks = []
    previous_summary = ""
    for page_number in range(len(pdf_document)):
        task = process_single_page.remote(page_number, pdf_document, previous_summary)
        tasks.append(task)

    # Gather the results from Ray workers
    processed_pages = ray.get(tasks)

    # Close the PDF document after processing
    pdf_document.close()

    # Add all the pages to the document data
    document_data["pages"] = processed_pages

    return document_data

def ask_question(documents, question):
    """Answer a question based on the summarized content of multiple PDFs."""
    combined_content = ""
    
    for doc_name, doc_data in documents.items():
        for page in doc_data["pages"]:
            # Combine text summaries and image analysis
            page_summary = page['text_summary']
            if page["image_analysis"]:
                image_explanation = "\n".join(
                    f"Page {img['page_number']}: {img['explanation']}" for img in page["image_analysis"]
                )
            else:
                image_explanation = "No image analysis."
            
            combined_content += f"Page {page['page_number']}\nSummary: {page_summary}\nImage Analysis: {image_explanation}\n\n"

    # Use the combined content for LLM prompt
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
                {"role": "user", "content": f"Use the context as knowledge base and answer the question in a proper readable format.\n\nQuestion: {question}\n\nContext:\n{combined_content}"}
            ],
            "temperature": 0.0
        }
    )

    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")
