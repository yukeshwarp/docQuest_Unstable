import requests
import os

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
