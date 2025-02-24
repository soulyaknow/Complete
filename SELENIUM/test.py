import os
import json
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests

# Webhook URL
webhook_url = "https://integration.korunaassist.com/webhook-test/67944059-2667-4476-87e0-1b6ec63ea6ef"

# Folder containing the files
folder_path = r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\docs\Alessandro Stagno"

# User information
user_info = {
    "applicant_id": "280",
    "first_name": "Alessandro",
    "last_name": "Stagno"
}

# Function to extract file metadata
def get_file_metadata(file_path):
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]  # Get file extension
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"  # Guess MIME type
    return {"file_name": file_name, "file_extension": file_extension, "mime_type": mime_type}

# Prepare metadata in the correct JSON format
file_metadata = {}

# Prepare files for multipart upload
fields = user_info.copy()  # Include user details in the request
if os.path.exists(folder_path) and os.path.isdir(folder_path):
    for index, file_name in enumerate(os.listdir(folder_path), start=1):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            metadata = get_file_metadata(file_path)
            file_metadata[f"doc{index}"] = metadata  # Store metadata using file1, file2, etc.

            # Add file to multipart form
            fields[f"doc{index}"] = (file_name, open(file_path, "rb"), metadata["mime_type"])

# Convert metadata to JSON **string** (not a file)
fields["file_metadata"] = json.dumps(file_metadata)  # Ensure it's a JSON string

# Create multipart encoder for file upload
multipart_data = MultipartEncoder(fields=fields)

# Send the request (files + metadata)
response = requests.post(
    webhook_url,
    data=multipart_data,
    headers={"Content-Type": multipart_data.content_type}
)

# Print response
print(f"Status Code: {response.status_code}")
print("Response Text:", response.text)
