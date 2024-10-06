import streamlit as st
from utils.pdf_processing import process_pdf_pages
from utils.llm_interaction import ask_question

# Initialize session state variables to avoid reloading and reprocessing
if 'documents' not in st.session_state:
    st.session_state.documents = {}  # Dictionary to hold document name and data
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'question_input' not in st.session_state:
    st.session_state.question_input = ""

# Function to handle user question and get the answer
def handle_question(prompt):
    if prompt:
        # Use the cached document data for the query
        answer = ask_question(st.session_state.documents, prompt)
        # Add the question-answer pair to the chat history
        st.session_state.chat_history.append({"question": prompt, "answer": answer})

# Function to display document data
def display_documents_data():
    for doc_name, doc_data in st.session_state.documents.items():
        st.subheader(f"Document: {doc_name}")
        for page in doc_data["pages"]:
            st.write(f"**Page {page['page_number']} Summary:**")
            st.write(page['text_summary'])
            if page['image_analysis']:
                st.write("**Image Analysis:**")
                for img in page['image_analysis']:
                    st.write(f"- Page {img['page_number']}: {img['explanation']}")
            st.markdown("---")  # Separator for pages

# Streamlit application title
st.title("docQuest")

# Sidebar for file upload and document information
with st.sidebar:
    st.subheader("docQuest")
    
    # File uploader
    uploaded_files = st.file_uploader("Upload and manage files here", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Check if the uploaded file is new or different from the previously uploaded files
            if uploaded_file.name not in st.session_state.documents:
                st.session_state.documents[uploaded_file.name] = None  # Initialize with None

                # Process the PDF if not already processed
                with st.spinner(f'Processing {uploaded_file.name}...'):
                    st.session_state.documents[uploaded_file.name] = process_pdf_pages(uploaded_file)
                st.success(f"{uploaded_file.name} processed successfully! Let's explore your documents.")

# Main page for chat interaction
if st.session_state.documents:
    st.subheader("Let us know more about your documents..")
    
    # Display document data
    display_documents_data()

    # Create a placeholder container for chat history
    chat_placeholder = st.empty()

    # Function to display chat history dynamically
    def display_chat():
        with chat_placeholder.container():
            if st.session_state.chat_history:
                st.subheader("Chats", divider="orange")
                for chat in st.session_state.chat_history:
                    # ChatGPT-like alignment: user input on the right, assistant response on the left                
                    user_chat = f"<div style='float: right; display: inline-block; margin: 5px; border-radius: 8px; padding: 10px; margin-left: 3vw;'> {chat['question']}</div>"
                    assistant_chat = f"<div style='float: left; display: inline-block; margin: 5px; border-radius: 8px; padding: 10px; margin-right: 3vw;'> {chat['answer']}</div>"                    
                    st.markdown(f"\n")
                    st.markdown(user_chat, unsafe_allow_html=True)
                    st.markdown(assistant_chat, unsafe_allow_html=True)
                    st.markdown("---")

    # Display the chat history
    display_chat()

    # Input for user questions using chat input
    prompt = st.chat_input("Let me know what you want to know about your documents..", key="chat_input")
    
    # Check if the prompt has been updated
    if prompt:
        handle_question(prompt)  # Call the function to handle the question
        st.session_state.question_input = ""  # Clear the input field after sending
        display_chat()  # Re-display the chat after adding the new entry
