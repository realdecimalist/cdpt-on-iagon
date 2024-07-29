import requests
import json
import time
import logging
import chardet
import os
from base64 import b64encode
import openai

# Configure logging
log_file_path = 'scraper.log'
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_RAW_URL = "https://raw.githubusercontent.com/realdecimalist/cdpt-on-iagon/main/cdpt_repo.json"
OPENAI_API_URL = "https://api.openai.com/v1/vector_stores/vs_tiNayixAsoF0CJZjnkgCvXse/files"

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

def validate_json(json_data_str):
    """Validate JSON data and log specific invalid characters."""
    try:
        json.loads(json_data_str)
        return True
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: {e.msg} at line {e.lineno} column {e.colno} (char {e.pos})")
        # Log the specific character causing the error
        error_position = e.pos
        invalid_char = json_data_str[error_position:error_position+10]  # Log 10 characters around the error
        logging.error(f"Invalid JSON character(s) near: {invalid_char}")
        return False

def commit_to_github(file_path, repo, branch, commit_message):
    """Commit a file to a GitHub repository."""
    with open(file_path, 'rb') as file:
        content = file.read()
    encoded_content = b64encode(content).decode('utf-8')

    url = f"https://api.github.com/repos/{repo}/contents/{os.path.basename(file_path)}"
    
    # Fetch the file's metadata to get the sha
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        sha = response.json()['sha']
    else:
        sha = None

    data = {
        "message": commit_message,
        "content": encoded_content,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    response = requests.put(url, headers=HEADERS, data=json.dumps(data))
    if response.status_code == 201:
        logging.info(f"Successfully committed {file_path} to {repo} on branch {branch}")
    else:
        logging.error(f"Failed to commit {file_path} to {repo}: {response.text}")

def delete_previous_file(file_path, repo, branch):
    """Delete the previous file from the GitHub repository."""
    url = f"https://api.github.com/repos/{repo}/contents/{os.path.basename(file_path)}"
    
    # Fetch the file's metadata to get the sha
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        sha = response.json()['sha']
        data = {
            "message": "Delete previous cdpt_repo.json",
            "sha": sha,
            "branch": branch
        }
        response = requests.delete(url, headers=HEADERS, data=json.dumps(data))
        if response.status_code == 200:
            logging.info(f"Successfully deleted {file_path} from {repo} on branch {branch}")
        else:
            logging.error(f"Failed to delete {file_path} from {repo}: {response.text}")
    else:
        logging.info(f"No previous {file_path} found in {repo} on branch {branch}")

def upload_to_vector_store(file_path):
    """Upload the JSON file to the OpenAI vector store."""
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        logging.error("OPENAI_API_KEY is not set.")
        return

    vector_store_id = 'vs_tiNayixAsoF0CJZjnkgCvXse'
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json',
        'OpenAI-Beta': 'assistants=v2'
    }
    url = f'https://api.openai.com/v1/vector_stores/{vector_store_id}/files'
    logging.info(f"Uploading {file_path} to {url}")

    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        json_data_str = json.dumps(json_data)

    if not validate_json(json_data_str):
        logging.error("JSON validation failed. Aborting upload.")
        return

    # Include the file_id parameter
    payload = {
        "file_id": os.path.basename(file_path)
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        logging.info("Successfully updated the vector store.")
    else:
        logging.error(f"Failed to update the vector store: {response.text}")
        logging.debug(f"Response status code: {response.status_code}")
        logging.debug(f"Response headers: {response.headers}")
        logging.debug(f"Response content: {response.content}")

def fetch_and_upload_cdpt_repo_json():
    logging.info("Fetching cdpt_repo.json from GitHub raw URL")
    try:
        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()  # Raise HTTPError for bad responses
        file_content = response.content
        logging.info("Successfully fetched cdpt_repo.json")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch cdpt_repo.json: {e}")
        return

    openai_headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2"
    }

    try:
        logging.info("Uploading cdpt_repo.json to OpenAI Vector Store")
        json_data_str = file_content.decode('utf-8')

        if not validate_json(json_data_str):
            logging.error("JSON validation failed. Aborting upload.")
            return

        upload_response = requests.post(OPENAI_API_URL, headers=openai_headers, data=json_data_str)

        logging.info(f"Upload response status: {upload_response.status_code}")
        logging.info(f"Upload response content: {upload_response.content.decode('utf-8')}")

        if upload_response.status_code == 404:
            logging.error("Failed to update the vector store: File not found.")
        elif upload_response.status_code == 400:
            logging.error("Failed to update the vector store: Invalid request.")
        elif upload_response.status_code != 200:
            logging.error(f"Failed to update the vector store: {upload_response.text}")
        else:
            logging.info("File uploaded successfully")
    except Exception as e:
        logging.error(f"Exception during upload to OpenAI Vector Store: {e}")

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

    # Delete the previous file from GitHub
    repo = "realdecimalist/cdpt-on-iagon"
    branch = "main"
    delete_previous_file(output_file_path, repo, branch)

    # Commit the new file to GitHub
    commit_message = "Add cdpt_repo.json"
    commit_to_github(output_file_path, repo, branch, commit_message)

    logging.info(f"{output_file_path} exists. Proceeding to upload to OpenAI Vector Store")

    # Upload to OpenAI Vector Store
    upload_to_vector_store(output_file_path)

    # Fetch and upload cdpt_repo.json directly from the GitHub raw URL
    fetch_and_upload_cdpt_repo_json()

    # Log the entire content of the scraper.log file
    with open(log_file_path, 'r') as log_file:
        log_content = log_file.read()
        logging.info(f"Scraper log content:\n{log_content}")

if __name__ == "__main__":
    logging.info("Script execution started")
    main()
    logging.info("Script execution completed")
