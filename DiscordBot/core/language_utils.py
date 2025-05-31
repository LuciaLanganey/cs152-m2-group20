from googletrans import Translator, LANGUAGES
from typing import Dict

class LanguageHandler:
    def __init__(self):
        self.translator = Translator()
    
    def detect_language(self, text: str) -> Dict:
        try:
            detection = self.translator.detect(text)
            language_name = LANGUAGES.get(detection.lang, 'Unknown')
            
            return {
                'language_code': detection.lang,
                'language_name': language_name,
                'confidence': detection.confidence,
                'is_english': detection.lang == 'en'
            }
        except Exception as e:
            return {
                'language_code': 'en',
                'language_name': 'English',
                'confidence': 0.0,
                'is_english': True
            }
    
    def translate_to_english(self, text: str, source_lang: str = None) -> Dict:
        try:
            if source_lang:
                translation = self.translator.translate(text, src=source_lang, dest='en')
            else:
                translation = self.translator.translate(text, dest='en')
            
            return {
                'original_text': text,
                'translated_text': translation.text,
                'source_language': translation.src,
                'success': True
            }
        except Exception as e:
            return {
                'original_text': text,
                'translated_text': text,
                'source_language': 'unknown',
                'success': False
            }
    
    def process_message(self, message: str) -> Dict:
        language_info = self.detect_language(message)
        
        if not language_info['is_english']:
            translation_info = self.translate_to_english(message, language_info['language_code'])
            if translation_info['success']:
                analysis_text = translation_info['translated_text']
            else:
                analysis_text = message
                translation_info = None
        else:
            analysis_text = message
            translation_info = None
        
        return {
            'language_info': language_info,
            'translation_info': translation_info,
            'analysis_text': analysis_text
        }