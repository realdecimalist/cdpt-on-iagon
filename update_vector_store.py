import requests
import json
import time
import logging
import chardet
import os

# Configure logging
logging.basicConfig(filename='scraper.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_API_URL = "https://api.github.com/repos/realdecimalist/cdpt-on-iagon/contents/"
TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {TOKEN}"
}

def get_repo_contents(url):
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for URL {url}: {e}")
        return None

def get_all_files(url, file_list):
    contents = get_repo_contents(url)
    if not contents:
        return
    for item in contents:
        if item['type'] == 'file':
            file_list.append(item['download_url'])
        elif item['type'] == 'dir':
            get_all_files(item['url'], file_list)

def get_url_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.content
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for URL {url}: {e}")
        return None

def update_content(url_list):
    data = {}

    for url in url_list:
        logging.info(f"Requesting URL: {url}")
        content = get_url_content(url)

        if content:
            # Detect the encoding of the content
            result = chardet.detect(content)
            encoding = result['encoding']
            confidence = result['confidence']

            if encoding is None or confidence < 0.5:
                logging.warning(f"Low confidence in detected encoding for URL {url}. Falling back to utf-8.")
                encoding = 'utf-8'  # Fallback encoding

            logging.info(f"Detected encoding for URL {url}: {encoding} with confidence {confidence}")

            try:
                decoded_content = content.decode(encoding)
            except UnicodeDecodeError as e:
                logging.error(f"Unicode decode error for URL {url} with detected encoding {encoding}: {e}")
                continue  # Skip this URL

            # Log the response content for debugging
            logging.debug(f"Content for URL {url}: {decoded_content[:500]}...")  # Log only first 500 characters

            data[url] = decoded_content
        else:
            logging.error(f"Failed to retrieve content for URL: {url}")

        time.sleep(1)  # Respectful delay to avoid hitting server too hard

    return data

def main():
    file_list = []
    get_all_files(GITHUB_API_URL, file_list)

    if not file_list:
        logging.error("Failed to retrieve file list from the GitHub repository.")
        return

    updated_data = update_content(file_list)

    with open('cdpt_repo.json', 'w', encoding='utf-8') as file:
        json.dump(updated_data, file, ensure_ascii=False, indent=4)

    # Upload to OpenAI Vector Store
    openai_api_key = os.getenv('OPENAI_API_KEY')
    vector_store_id = os.getenv('VECTOR_STORE_ID')
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json'
    }
    url = f'https://api.openai.com/v1/vector_stores/{vector_store_id}/files'
    with open('cdpt_repo.json', 'rb') as f:
        response = requests.post(url, headers=headers, files={'file': f})
        if response.status_code == 200:
            logging.info("Successfully updated the vector store.")
        else:
            logging.error(f"Failed to update the vector store: {response.text}")
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response headers: {response.headers}")
            logging.debug(f"Response content: {response.content}")

if __name__ == "__main__":
    main()