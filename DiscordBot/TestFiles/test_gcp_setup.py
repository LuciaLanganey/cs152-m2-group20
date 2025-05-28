# test_gcp_setup.py
import os
import json
from google.cloud import language_v1
import google.generativeai as genai

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../google-credentials.json'

# Load tokens
with open('../tokens.json') as f:
    tokens = json.load(f)

# Test Natural Language API
def test_natural_language():
    client = language_v1.LanguageServiceClient()
    text = "Hello, this is a test message."
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    
    # Test sentiment analysis
    response = client.analyze_sentiment(request={'document': document})
    print(f"Natural Language API works. Sentiment: {response.document_sentiment.score}")

# Test Gemini API
def test_gemini():
    print("\n=== Testing Gemini API ===")
    try:
        genai.configure(api_key=tokens['gemini'])
        
        model_names = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        
        for model_name in model_names:
            try:
                print(f"Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Hello, respond with just 'Gemini API working!'")
                print(f"Gemini API works with {model_name}. Response: {response.text}")
                break
            except Exception as e:
                print(f"{model_name} failed: {e}")
                continue
    except Exception as e:
        print(f"Gemini API test failed: {e}")

# Test Toxicity Detection
def test_toxicity_detection():
    print("\n=== Testing Toxicity Detection ===")
    try:
        client = language_v1.LanguageServiceClient()
        toxic_text = "You are stupid. I hate you!"
        document = language_v1.Document(content=toxic_text, type_=language_v1.Document.Type.PLAIN_TEXT)
        
        response = client.analyze_sentiment(request={'document': document})
        print(f"Toxicity test. Sentiment score: {response.document_sentiment.score}")
        
        if response.document_sentiment.score < -0.5:
            print("Negative sentiment")
        else:
            print("Not correctly flagged as toxic")
            
    except Exception as e:
        print(f"Toxicity test failed: {e}")

if __name__ == "__main__":
    test_natural_language()
    test_gemini()
    test_toxicity_detection()