import os
from google.cloud import firestore

# Test Firestore connection and operations
def test_firestore_connection():    
    creds_file = '../google-credentials.json'
    
    if os.path.exists(creds_file):
        print(f"Credentials file found: {creds_file}")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_file
    else:
        print(f"Credentials file not found: {creds_file}")
        return False
    
    try:
        db = firestore.Client()
        print("Firestore client created successfully")
    except Exception as e:
        print(f"Failed to create Firestore client: {e}")
        return False
    
    try:
        collections = db.collections()
        print("Successfully connected to Firestore database")
        
        collection_names = [col.id for col in collections]
        if collection_names:
            print(f"Found existing collections: {collection_names}")
        else:
            print("Database is empty")
        
        return True
        
    except Exception as e:
        print(f"Error accessing Firestore: {e}")
        return False

if __name__ == "__main__":
    success = test_firestore_connection()
    if success:
        print("Firestore connection is working")
    else:
        print("Firestore connection failed")