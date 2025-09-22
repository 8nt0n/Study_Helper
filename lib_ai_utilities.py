import requests
import json
from openai import OpenAI


import fitz
import base64
import requests
import json
import os

import mimetypes
from google import genai
from google.genai import types

# setup
import tomllib
# Read the TOML file
with open("config.toml", "rb") as f:   # Must be opened in binary mode
    config = tomllib.load(f)

# Access variables
print(config["Api_keys"]["Gemini"])   # your Gemini API KEY
print(config["Api_keys"]["OpenAi"])   # your Open Ai API KEY

google_ai_studio_key = config["Api_keys"]["Gemini"]


os.environ['OPENAI_API_KEY'] = config["Api_keys"]["OpenAi"]

def prompt_chat_gpt(model, prompt):
    print("prompting...")
    client = OpenAI()

    response = client.responses.create(
        model=model,
        input=prompt
    )
    return response.output_text


def prompt_gemini(api_key: str, prompt: str) -> str:
    """
    Sends a prompt to the Gemini API and returns the generated text.

    Args:
        api_key (str): Your Google AI Studio API key.
        prompt (str): The text prompt to send to the model.

    Returns:
        str: The generated response from the Gemini model.
    """
    # The API endpoint for the gemini-2.5-flash-preview-05-20 model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    # The payload for the API request
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Make the POST request to the API
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response
        response_data = response.json()

        # Extract the generated text from the response
        generated_text = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text generated.")

        return generated_text

    except requests.exceptions.HTTPError as errh:
        return f"HTTP Error: {errh}"
    except requests.exceptions.ConnectionError as errc:
        return f"Error Connecting: {errc}"
    except requests.exceptions.Timeout as errt:
        return f"Timeout Error: {errt}"
    except requests.exceptions.RequestException as err:
        return f"Something went wrong: {err}"
    except (IndexError, KeyError) as e:
        return f"Error parsing response: {e}. Raw response: {response.text}"


def get_mime_type(file_path):
    """
    Determines the MIME type of a file based on its extension.
    """
    _, ext = os.path.splitext(file_path.lower())
    if ext in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    elif ext == '.pdf':
        return 'application/pdf'
    return None


def prompt_gemini_multimodal(prompt, files=None):
    """
    Sends a multimodal prompt (text and files) to the Gemini API.

    Args:
        prompt (str): The text prompt for the model.
        files (list): A list of file paths (images or PDFs) to include.
    
    Returns:
        dict: The JSON response from the API.
    """
    api_key = google_ai_studio_key 

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    parts = [{"text": prompt}]

    if files:
        for file_path in files:
            mime_type = get_mime_type(file_path)
            if not mime_type:
                print(f"Skipping unsupported file type: {file_path}")
                continue
            
            # For PDFs, you must first extract the content
            if mime_type == 'application/pdf' and fitz:
                print(f"Processing PDF: {file_path}")
                pdf_parts = []
                try:
                    doc = fitz.open(file_path)
                    for page_num in range(min(10, doc.page_count)):  # Process up to 10 pages to avoid large payloads
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        base64_img = base64.b64encode(img_data).decode('utf-8')
                        pdf_parts.append({
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64_img
                            }
                        })
                    doc.close()
                    parts.extend(pdf_parts)
                except Exception as e:
                    print(f"Error processing PDF file {file_path}: {e}")
                    continue
            
            # For images, simply encode and add
            elif mime_type in ['image/jpeg', 'image/png']:
                print(f"Processing image: {file_path}")
                try:
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                        parts.append({
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_data
                            }
                        })
                except FileNotFoundError:
                    print(f"File not found: {file_path}")
                    continue
            else:
                print(f"Unsupported MIME type: {mime_type}")
                continue

    payload = {
        "contents": [{"parts": parts}]
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
def generate_image(prompt, max_retries=5, initial_delay=1):
    """
    Generates an image using the gemini-2.5-flash-image-preview model via the Gemini API.
    Includes an exponential backoff strategy for handling 429 RESOURCE_EXHAUSTED errors.

    Args:
        prompt (str): The text prompt to guide the image generation.
        max_retries (int): The maximum number of times to retry the request.
        initial_delay (int): The initial delay in seconds before the first retry.

    Returns:
        tuple: A tuple containing the base64-encoded image data (str) and
               the MIME type (str), or (None, None) if an error occurs.
    """
    api_key = google_ai_studio_key 

    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": [
                "TEXT",
                "IMAGE"
            ]
        },
        "key": api_key
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(api_url, json=payload)
            
            # Check for a 429 error specifically
            if response.status_code == 429:
                delay = initial_delay * (2 ** retries)
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                continue
            
            response.raise_for_status()
            
            result = response.json()
            
            candidates = result.get("candidates", [])
            if candidates and len(candidates) > 0:
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        inline_data = part["inlineData"]
                        return inline_data.get("data"), inline_data.get("mimeType")
            
            return None, None

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the API call: {e}")
            return None, None
    
    return None, None

