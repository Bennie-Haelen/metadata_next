from google.cloud import storage
from datetime import datetime, timezone
import json
import os

def read_from_gcs(gcs_uri):
    """
    Reads data from a given GCS URI and returns it as a string.
    """
    storage_client = storage.Client()
    bucket_name, blob_name = extract_bucket_and_blob(gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if blob.exists():
        return blob.download_as_text()
    else:
        return None

def write_to_gcs(gcs_uri, data, content_type="JSON", mode="w"):
    """
    Writes data to a given GCS URI.
    """
    storage_client = storage.Client()
    bucket_name, blob_name = extract_bucket_and_blob(gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if content_type == "JSON":
        content_type = 'application/json'
    else:
        content_type = 'text/plain'
    if mode == "a":
        # Check if the file exists and read its content
        if blob.exists():
            existing_data = blob.download_as_text()
            data = existing_data + "\n" + data  # Append new data

    # Upload the final data
    blob.upload_from_string(data, content_type=content_type)
    

def extract_bucket_and_blob(gcs_uri):
    """
    Extracts the bucket name and blob name from a GCS URI.
    """
    if gcs_uri.startswith("gs://"):
        gcs_uri = gcs_uri[5:]
    parts = gcs_uri.split("/", 1)
    return parts[0], parts[1]

def check_tracker_file(tracker_gcs_uri, table_id):
    """
    Reads the tracker file and checks if a table has already been processed.
    """
    processed_tables = set()
    read_tracker_file = read_from_gcs(tracker_gcs_uri)
    if read_tracker_file is None:
        return False
    else:
        tracker_data = read_tracker_file.splitlines()
        for line in tracker_data:
            try:
                record = json.loads(line)
                processed_tables.add(record["table_name"])
            except json.JSONDecodeError:
                pass  # Skip corrupted lines
    
    return table_id in processed_tables
    
def update_tracker_file(tracker_gcs_uri, table_id):
    """
    Updates the tracker file by adding a processed table ID.
    """
    if check_tracker_file(tracker_gcs_uri, table_id):
        #print(f"Skipping {table_id}, already processed.")
        return False  # No update needed
    
    new_entry = {"table_name": table_id, "processed_at": datetime.now(timezone.utc).isoformat() + "Z"}
    write_to_gcs(tracker_gcs_uri, json.dumps(new_entry), mode="a")
    return True

def delete_tracker_file(tracker_gcs_uri):
    """
    Deletes the tracker file after all tables have been processed.
    """
    storage_client = storage.Client()
    bucket_name, blob_name = extract_bucket_and_blob(tracker_gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()


