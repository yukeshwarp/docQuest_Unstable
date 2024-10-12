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
                    "text": "Explain the content of this image. The explanation should be concise and semantically meaningful. Do not make assumptions about the specification of the image and be acuurate in your explaination."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                }
            ]}
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
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "No explanation provided.")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Error requesting image explanation: {e}")
        return f"Error: Unable to fetch image explanation due to network issues or API error."

def summarize_page(page_text, previous_summary, page_number):
    """Summarize a single page's text using LLM."""
    headers = get_headers()
    prompt_message = (
        f"Please rewrite the following page content from (Page {page_number}) along with context from the previous page summary to make them concise and well-structured."
        f"Maintain proper listing and referencing of the contents if present."
        f"Do not add any new information or make assumptions. Keep the meaning accurate and the language clear."
        f"Previous page summary: {previous_summary}\n\n"
        f"Current page content:\n{page_text}\n"
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an Archivist who reads the given knowledge and maintains documents, records, or information in a systematic and accurate way."},
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
        logging.error(f"Error Analysing page {page_number}: {e}")
        return f"Error: Unable to summarize page {page_number} due to network issues or API error."

def ask_question(documents, question, chat_history):
    """Answer a question based on the full text, summarized content of multiple PDFs, and chat history."""
    combined_content = ""

    # Combine document full texts, summaries, and image analyses
    for doc_name, doc_data in documents.items():
        for page in doc_data["pages"]:
            page_summary = page['text_summary']
            page_full_text = page.get('full_text', 'No text available')  # Include full text
            
            image_explanation = "\n".join(
                f"Page {img['page_number']}: {img['explanation']}" for img in page["image_analysis"]
            ) if page["image_analysis"] else "No image analysis."

            combined_content += (
                f"Page {page['page_number']}\n"
                f"Full Text: {page_full_text}\n"
                f"Summary: {page_summary}\n"
                f"Image Analysis: {image_explanation}\n\n"
            )

    # Format the chat history into a conversation format
    conversation_history = "".join(
        f"User: {chat['question']}\nAssistant: {chat['answer']}\n" for chat in chat_history
    )

    # Prepare the prompt message
    prompt_message = (
        f"""
        You are given the following content:

        ---
        {combined_content}
        ---
        Previous responses over the current chat session: {conversation_history}

        Answer the following question based only on the information provided in the content above with all the factual data. 
        Answer the question in a proper readable format."

        Question: {question}
        """
    )

    headers = get_headers()

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an assistant that answers questions based only on provided knowledge base."},
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
