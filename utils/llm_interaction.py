import os
from dotenv import load_dotenv
import requests
from utils.config import azure_endpoint, api_key, api_version, model
import logging

# Set up logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

def get_headers():
    """Generate common headers for the API requests."""
    return {
        "Content-Type": "application/json",
        "api-key": api_key
    }

def get_image_explanation(base64_image):
    """Get image explanation from OpenAI API."""
    headers = get_headers()
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

    try:
        response = requests.post(
            f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
            headers=headers,
            json=data,
            timeout=10  # Add timeout for API request
        )
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No explanation provided.")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error requesting image explanation: {e}")
        return f"Error: Unable to fetch image explanation due to network issues or API error."

def summarize_page(page_text, previous_summary, page_number):
    """Summarize a single page's text using LLM."""
    headers = get_headers()
    prompt_message = (
        f"Summarize the following page (Page {page_number}) with context from the previous summary.\n\n"
        f"Previous summary: {previous_summary}\n\n"
        f"Text:\n{page_text}\n"
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an assistant that summarizes text with context."},
            {"role": "user", "content": prompt_message}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(
            f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
            headers=headers,
            json=data,
            timeout=10  # Add timeout for API request
        )
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No summary provided.").strip()
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error summarizing page {page_number}: {e}")
        return f"Error: Unable to summarize page {page_number} due to network issues or API error."

def ask_question(documents, question, chat_history):
    """Answer a question based on the summarized content of multiple PDFs and chat history."""
    combined_content = ""
    
    # Combine document summaries and image analyses
    for doc_name, doc_data in documents.items():
        for page in doc_data["pages"]:
            page_summary = page['text_summary']
            image_explanation = "\n".join(
                f"Page {img['page_number']}: {img['explanation']}" for img in page["image_analysis"]
            ) if page["image_analysis"] else "No image analysis."
            
            combined_content += (
                f"Page {page['page_number']}\n"
                f"Summary: {page_summary}\n"
                f"Image Analysis: {image_explanation}\n\n"
            )

    # Format the chat history into a conversation format
    conversation_history = "".join(
        f"User: {chat['question']}\nAssistant: {chat['answer']}\n" for chat in chat_history
    )

    # Prepare the prompt message
    prompt_message = (
        f"Use the context as knowledge base and answer the question in a proper redable format: {question}\n\Context:\n{combined_content}\nPrevious responses over the current chat session: {conversation_history}")

    headers = get_headers()

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an assistant that answers questions based on provided knowledge base."},
            {"role": "user", "content": prompt_message}
        ],
        "temperature": 0.0
    }

    try:
        response = requests.post(
            f"{azure_endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}",
            headers=headers,
            json=data,
            timeout=10  # Add timeout for API request
        )
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No answer provided.").strip()
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error answering question '{question}': {e}")
        raise Exception(f"Unable to answer the question due to network issues or API error.")
