import asyncio
from ai_classifier import AIClassifier

async def regex_test_simple():
    classifier = AIClassifier()
    
    test_message = "Send me $500 or I'll share your photos"
    
    base_result = await classifier.classify_message(test_message)
    print(f"Base score: {base_result['ai_scores']['combined_score']}%")
    
    regex_result = await classifier.classify_message_with_regex(test_message)
    print(f"With regex: {regex_result['ai_scores']['combined_score']}%")
    print(f"Regex bonus: +{regex_result['ai_scores'].get('regex_bonus', 0)}%")

asyncio.run(regex_test_simple())