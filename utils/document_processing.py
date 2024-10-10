import io
import requests
import fitz  # PyMuPDF
import os
import base64
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
load_dotenv()  # Load environment variables from the .env file

azure_endpoint = os.getenv("AZURE_ENDPOINT")
api_key = os.getenv("API_KEY")
api_version = os.getenv("API_VERSION")
model = os.getenv("MODEL")
azure_function_url = 'https://doc2pdf.azurewebsites.net/api/HttpTrigger1'

def remove_stopwords_and_blanks(text):
    """Clean the text by removing extra spaces."""
    cleaned_text = ' '.join(word for word in text.split())
    return cleaned_text

def detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold=0.4):
    """Detect pages with OCR images or vector graphics."""
    detected_pages = []

    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        images = page.get_images(full=True)
        text = page.get_text("text")

        text_blocks = page.get_text("blocks")
        vector_graphics_detected = any(page.get_drawings())
        page_area = page.rect.width * page.rect.height
        text_area = sum((block[2] - block[0]) * (block[3] - block[1]) for block in text_blocks)
        text_coverage = text_area / page_area
        pix = page.get_pixmap() 
        img_data = pix.tobytes("png")
        base64_image = base64.b64encode(img_data).decode("utf-8")
        if text_area == 0:
            detected_pages.append((page_number + 1, base64_image))
            
        elif (images or vector_graphics_detected) and text.strip():
            if text_coverage < ocr_text_threshold:
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


def process_page_batch(pdf_document, batch, ocr_text_threshold=0.4):
    """Process a batch of PDF pages and extract summaries and image analysis."""
    previous_summary = ""
    batch_data = []

    for page_number in batch:
        page = pdf_document.load_page(page_number)
        text = page.get_text("text").strip()
        preprocessed_text = remove_stopwords_and_blanks(text)

        # Summarize the page
        summary = summarize_page(preprocessed_text, previous_summary, page_number + 1)
        previous_summary = summary

        # Detect images or graphics on the page
        detected_images = detect_ocr_images_and_vector_graphics_in_pdf(pdf_document, ocr_text_threshold)
        image_analysis = []

        for img_page, base64_image in detected_images:
            if img_page == page_number + 1:
                image_explanation = get_image_explanation(base64_image)
                image_analysis.append({"page_number": img_page, "explanation": image_explanation})

        # Store the extracted data
        batch_data.append({
            "page_number": page_number + 1,
            "text_summary": summary,
            "image_analysis": image_analysis
        })

    return batch_data

MIME_TYPES = {
    "doc": "application/msword",
    "dot": "application/msword",
    "csv": "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "docm": "application/vnd.ms-word.document.macroEnabled.12",
    "dotm": "application/vnd.ms-word.template.macroEnabled.12",
    "xls": "application/vnd.ms-excel",
    "xlt": "application/vnd.ms-excel",
    "xla": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xltx": "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "xltm": "application/vnd.ms-excel.template.macroEnabled.12",
    "xlam": "application/vnd.ms-excel.addin.macroEnabled.12",
    "xlsb": "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
    "ppt": "application/vnd.ms-powerpoint",
    "pot": "application/vnd.ms-powerpoint",
    "pps": "application/vnd.ms-powerpoint",
    "ppa": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "potx": "application/vnd.openxmlformats-officedocument.presentationml.template",
    "ppsx": "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
    "ppam": "application/vnd.ms-powerpoint.addin.macroEnabled.12",
    "pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
    "potm": "application/vnd.ms-powerpoint.template.macroEnabled.12",
    "ppsm": "application/vnd.ms-powerpoint.slideshow.macroEnabled.12",
    "mdb": "application/vnd.ms-access"
}

def get_mime_type(file_name):
    """Get the MIME type based on the file extension."""
    extension = file_name.split('.')[-1].lower()
    return MIME_TYPES.get(extension, None)

def convert_office_to_pdf(office_file):
    """Convert Office files to PDF using Azure Function and return the PDF as a BytesIO object."""
    mime_type = get_mime_type(office_file.name)
    if mime_type is None:
        raise ValueError(f"Unsupported file type: {office_file.name}")

    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Type-Actual": mime_type
    }

    response = requests.post(azure_function_url, data=office_file.read(), headers=headers)
    
    if response.status_code == 200:
        return io.BytesIO(response.content)  # Return the PDF content as a BytesIO object
    else:
        raise Exception(f"File conversion failed with status code: {response.status_code}, {response.text}")

def process_pdf_pages(uploaded_file):
    """Process the PDF pages in batches and extract summaries and image analysis."""
    file_name = uploaded_file.name
    
    # Check if the uploaded file is a PDF
    if file_name.lower().endswith('.pdf'):
        # If it's a PDF, read it directly into a BytesIO object
        pdf_stream = io.BytesIO(uploaded_file.read())
    else:
        # Convert the uploaded Office file to PDF if necessary
        pdf_stream = convert_office_to_pdf(uploaded_file)
    
    # Process the PDF document
    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    document_data = {"pages": [], "name": file_name}
    total_pages = len(pdf_document)
    
    # Batch size of 5 pages
    batch_size = 5
    page_batches = [range(i, min(i + batch_size, total_pages)) for i in range(0, total_pages, batch_size)]
    
    # Use ThreadPoolExecutor to process batches concurrently
    with ThreadPoolExecutor() as executor:
        future_to_batch = {executor.submit(process_page_batch, pdf_document, batch): batch for batch in page_batches}
        for future in as_completed(future_to_batch):
            batch_data = future.result()  # Get the result of processed batch
            document_data["pages"].extend(batch_data)
    
    # Close the PDF document after processing
    pdf_document.close()
    
    # Sort pages by page_number to ensure correct order
    document_data["pages"].sort(key=lambda x: x["page_number"])
    
    return document_data


def ask_question(documents, question, chat_history):
    """Answer a question based on the summarized content of multiple PDFs and chat history."""
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

    # Format the chat history into a conversation format
    conversation_history = ""
    for chat in chat_history:
        user_message = f"User: {chat['question']}\n"
        assistant_response = f"Assistant: {chat['answer']}\n"
        conversation_history += user_message + assistant_response

    # Use the combined content for LLM prompt
    prompt_message = (
        f"Now, using the following document analysis as context, answer the question.\n\n"
        f"Context:\n{combined_content}\n"
        f"Question: {question}"
        f"Previous responses over the current chat session:{conversation_history}\n"
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
                {"role": "system", "content": "You are an assistant that answers questions based on provided knowledge base."},
                {"role": "user", "content": prompt_message}
            ],
            "temperature": 0.0
        }
    )

    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

