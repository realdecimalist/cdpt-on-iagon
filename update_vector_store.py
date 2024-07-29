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
    logging.info(f"Fetching repository contents from URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # Raise HTTPError for bad responses
        logging.info(f"Successfully fetched repository contents from URL: {url}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for URL {url}: {e}")
        return None

def get_all_files(url, file_list):
    logging.info(f"Getting all files from URL: {url}")
    contents = get_repo_contents(url)
    if not contents:
        logging.error(f"No contents found at URL: {url}")
        return
    for item in contents:
        if item['type'] == 'file':
            file_list.append(item['download_url'])
            logging.info(f"Added file URL: {item['download_url']}")
        elif item['type'] == 'dir':
            get_all_files(item['url'], file_list)

def get_url_content(url):
    logging.info(f"Fetching content from URL: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        logging.info(f"Successfully fetched content from URL: {url}")
        return response.content
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for URL {url}: {e}")
        return None

def update_content(url_list):
    logging.info("Updating content from URL list")
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
    logging.info("Starting main function")
    file_list = []
    get_all_files(GITHUB_API_URL, file_list)

    if not file_list:
        logging.error("Failed to retrieve file list from the GitHub repository.")
        return

    updated_data = update_content(file_list)

    output_file_path = 'cdpt_repo.json'
    logging.info(f"Writing updated data to {output_file_path}")
    with open(output_file_path, 'w', encoding='utf-8') as file:
        json.dump(updated_data, file, ensure_ascii=False, indent=4)

    logging.info(f"Checking if {output_file_path} exists")
    if not os.path.exists(output_file_path):
        logging.error(f"{output_file_path} does not exist.")
        return

    logging.info(f"{output_file_path} exists. Proceeding to upload to OpenAI Vector Store")

    # Upload to OpenAI Vector Store
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        logging.error("OPENAI_API_KEY is not set.")
        return

    vector_store_id = 'vs_tiNayixAsoF0CJZjnkgCvXse'
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json'
    }
    url = f'https://api.openai.com/v1/vector_stores/{vector_store_id}/files'
    logging.info(f"Uploading {output_file_path} to {url}")
    with open(output_file_path, 'rb') as f:
        response = requests.post(url, headers=headers, files={'file': f})
        if response.status_code == 200:
            logging.info("Successfully updated the vector store.")
        else:
            logging.error(f"Failed to update the vector store: {response.text}")
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response headers: {response.headers}")
            logging.debug(f"Response content: {response.content}")

    # Log the entire content of the scraper.log file
    with open('scraper.log', 'r') as log_file:
        log_content = log_file.read()
        logging.info(f"Scraper log content:\n{log_content}")

if __name__ == "__main__":
    logging.info("Script execution started")
    main()
    logging.info("Script execution completed")