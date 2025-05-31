import json
import os
from typing import Dict, List
import google.generativeai as genai
from google.cloud import language_v1
import asyncio
from datetime import datetime
from language_utils import LanguageHandler
from regex_check import RegexCheck

class AIClassifier:
    def __init__(self, violation_threshold=50, high_confidence_threshold=85):
        with open('../config/tokens.json') as f:
            tokens = json.load(f)
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../config/google-credentials.json'
        
        genai.configure(api_key=tokens['gemini'])
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.violation_threshold = violation_threshold
        self.high_confidence_threshold = high_confidence_threshold

        self.language_client = language_v1.LanguageServiceClient()
        
        self.language_handler = LanguageHandler()
        
        self.regex_check = RegexCheck()
        
        print("AI Classifier initialized with Gemini and Natural Language APIs")
    
    async def classify_message(self, message_content: str) -> Dict:
        print(f"Analyzing message: '{message_content[:50]}...'")
        
        lang_result = self.language_handler.process_message(message_content)
        analysis_text = lang_result['analysis_text']
        
        if lang_result['language_info']['language_code'] != 'en':
            print(f"Detected {lang_result['language_info']['language_name']}, using translation")
        
        # Run both analyses
        gemini_result = await self._classify_with_gemini(analysis_text)
        nl_result = await self._enhanced_natural_language_analysis(analysis_text)
        
        # Combine results
        combined_result = self._combine_classifications(gemini_result, nl_result, message_content)
        
        combined_result['language_info'] = lang_result['language_info']
        combined_result['translation_info'] = lang_result['translation_info']
        combined_result['analysis_text'] = analysis_text
        
        print(f"Analysis complete. Combined score: {combined_result['ai_scores']['combined_score']}%")
        return combined_result
    
    async def _classify_with_gemini(self, message: str) -> Dict:
        """Use Gemini to classify sexual extortion content"""
        try:
            prompt = f"""
            You are an expert content moderator specializing in sexual extortion and sextortion detection.

            CRITICAL: Give HIGH scores (70-100) for messages that contain ANY of these sextortion patterns:

            Explicity Sextorion (90-100):
            - Clear possession of intimate content + payment demand + distribution threat
            - "Send me $500 or I'll post your nude photos online"
            - "Pay me or I'll share your intimate videos with everyone"

            Strong Sextortion Indicators (70-89):
            - Possession of intimate content + implied consequences
            - "I have your private pictures and will release them unless you comply"
            - "Your device has been compromised. I found explicit content and will distribute it"
            - "I created a deepfake video featuring you. Want to prevent its release?"

            Moderate Sextortion Patterns (50-69):
            - Intimate content threats without explicit payment demands
            - "Imagine what your friends and family will think when they see these photos"
            - "I'll delete but I want something in return. I want more pics of you"
            - "How many guys have you sent dirty pics to because I have some of you"

            General Threats (30-49):
            - Vague threats or blackmail without intimate content
            - "Pay me $100 and I won't tell your secret"
            - "You better apologize or else!"

            Safe Content (0-29):
            - Normal conversation, complaints, or non-threatening messages
            - "Hey, how are you doing today?"
            - "I'm really upset about what happened"

            Key Indicators to look for:
            - Words like: pics, photos, videos, nudes, intimate, explicit, screenshots, deepfake
            - Possession language: "I have", "I found", "I recorded", "I created"
            - Distribution threats: "share", "post", "release", "distribute", "show everyone"
            - Leverage language: "unless", "or else", "prevent", "comply"
            - Victim targeting: "friends and family", "reputation", "ruin you"

            Analyze this message: "{message}"

            Be more sensitive to implicit threats and coercion involving intimate content.
            NOTE: This text may have been translated from another language, so look for the meaning and intent rather than exact wording.

            Respond with ONLY a JSON object:
            {{
                "is_sexual_extortion": true/false,
                "confidence_score": 0-100,
                "classification": "explicit_sextortion" or "strong_sextortion" or "moderate_sextortion" or "general_threat" or "safe",
                "reasoning": "brief explanation of why this score was assigned",
                "risk_indicators": ["specific", "elements", "found"]
            }}
            
            IMPORTANT: Respond with ONLY the JSON object, no additional text or code blocks.
            """
            
            response = self.gemini_model.generate_content(prompt)
            
            try:
                response_text = response.text.strip()
                
                # Handle multiple code block formats
                if '```json' in response_text:
                    # Extract content between ```json and ```
                    start = response_text.find('```json') + 7
                    end = response_text.find('```', start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                    else:
                        response_text = response_text[start:].strip()
                elif '```' in response_text:
                    # Handle generic code blocks
                    start = response_text.find('```') + 3
                    end = response_text.find('```', start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                    else:
                        response_text = response_text[start:].strip()
                
                # Clean up any remaining artifacts
                response_text = response_text.strip('`').strip()
                
                # Try to parse JSON
                result = json.loads(response_text)
                
                return {
                    'gemini_confidence': result.get('confidence_score', 0),
                    'gemini_classification': result.get('classification', 'unknown'),
                    'gemini_reasoning': result.get('reasoning', 'No reasoning provided'),
                    'gemini_risk_indicators': result.get('risk_indicators', []),
                    'gemini_is_violation': result.get('is_sexual_extortion', False)
                }
                
            except json.JSONDecodeError as e:
                print(f"Gemini JSON parsing failed. Error: {e}")
                print(f"Cleaned text: {response_text}")
                print(f"Original response: {response.text}")
                
                # Fallback: try to extract key values manually
                try:
                    import re
                    confidence_match = re.search(r'"confidence_score":\s*(\d+)', response.text)
                    classification_match = re.search(r'"classification":\s*"([^"]+)"', response.text)
                    is_violation_match = re.search(r'"is_sexual_extortion":\s*(true|false)', response.text)
                    
                    confidence = int(confidence_match.group(1)) if confidence_match else 0
                    classification = classification_match.group(1) if classification_match else 'unknown'
                    is_violation = is_violation_match.group(1) == 'true' if is_violation_match else False
                    
                    print(f"Fallback parsing successful: confidence={confidence}, classification={classification}")
                    
                    return {
                        'gemini_confidence': confidence,
                        'gemini_classification': classification,
                        'gemini_reasoning': 'Parsed via fallback method',
                        'gemini_risk_indicators': [],
                        'gemini_is_violation': is_violation
                    }
                except Exception as fallback_error:
                    print(f"Fallback parsing also failed: {fallback_error}")
                    return {
                        'gemini_confidence': 0,
                        'gemini_classification': 'json_parse_error',
                        'gemini_reasoning': 'Failed to parse Gemini response as JSON',
                        'gemini_risk_indicators': [],
                        'gemini_is_violation': False
                    }

            except Exception as e:
                print(f"Unexpected error in Gemini classification: {e}")
                return {
                    'gemini_confidence': 0,
                    'gemini_classification': 'error',
                    'gemini_reasoning': f'API Error: {str(e)}',
                    'gemini_risk_indicators': [],
                    'gemini_is_violation': False
                }
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            return {
                'gemini_confidence': 0,
                'gemini_classification': 'error',
                'gemini_reasoning': f'API Error: {str(e)}',
                'gemini_risk_indicators': [],
                'gemini_is_violation': False
            }
    
    async def _enhanced_natural_language_analysis(self, message: str) -> Dict:
        document = language_v1.Document(content=message, type_=language_v1.Document.Type.PLAIN_TEXT)
        
        analysis_results = {}
        
        # Sentiment Analysis
        try:
            sentiment_response = self.language_client.analyze_sentiment(request={'document': document})
            sentiment_score = sentiment_response.document_sentiment.score
            sentiment_magnitude = sentiment_response.document_sentiment.magnitude
            
            analysis_results['sentiment'] = {
                'score': sentiment_score,
                'magnitude': sentiment_magnitude,
                'interpretation': self._interpret_sentiment(sentiment_score, sentiment_magnitude)
            }
        except Exception as e:
            print(f"Sentiment analysis failed: {e}")
            analysis_results['sentiment'] = {'score': 0, 'magnitude': 0, 'interpretation': 'neutral'}
        
        # Entity Analysis
        try:
            entities_response = self.language_client.analyze_entities(request={'document': document})
            entities = []
            
            for entity in entities_response.entities:
                entities.append({
                    'name': entity.name,
                    'type': entity.type_.name,
                    'salience': entity.salience
                })
            
            analysis_results['entities'] = {
                'count': len(entities),
                'entities': entities,
                'has_person_entities': any(e['type'] == 'PERSON' for e in entities),
                'has_money_entities': any('money' in e['name'].lower() or '$' in e['name'] or 
                                        any(word in e['name'].lower() for word in ['dollar', 'payment', 'cash']) 
                                        for e in entities),
                'money_amounts': [e['name'] for e in entities if '$' in e['name'] or 
                                any(word in e['name'].lower() for word in ['dollar', 'hundred', 'thousand'])]
            }
        except Exception as e:
            print(f"Entity analysis failed: {e}")
            analysis_results['entities'] = {'count': 0, 'entities': [], 'has_person_entities': False, 'has_money_entities': False}
        
        try:
            syntax_response = self.language_client.analyze_syntax(request={'document': document})
            threat_patterns = self._analyze_threat_patterns(message)
            
            analysis_results['syntax'] = {
                'token_count': len(syntax_response.tokens),
                'threat_patterns': threat_patterns,
                'pattern_count': len(threat_patterns)
            }
        except Exception as e:
            print(f"Syntax analysis failed: {e}")
            analysis_results['syntax'] = {'token_count': 0, 'threat_patterns': [], 'pattern_count': 0}
        
        threat_score = self._calculate_enhanced_threat_score(analysis_results)
        
        analysis_results['enhanced_threat_assessment'] = {
            'threat_score': threat_score,
            'threat_level': self._get_threat_level(threat_score),
            'is_concerning': threat_score > 0.6,
            'confidence': min(threat_score * 100, 100)
        }
        
        return analysis_results
    
    def _interpret_sentiment(self, score: float, magnitude: float) -> str:
        if score > 0.3:
            return "positive"
        elif score < -0.5:
            if magnitude > 1.0:
                return "very_negative"
            elif magnitude > 0.7:
                return "negative"
            else:
                return "mildly_negative"
        elif score < -0.2:
            return "mildly_negative"
        else:
            return "neutral"
    
    def _analyze_threat_patterns(self, message: str) -> List[str]:
        patterns = []
        full_text = message.lower()
        
        sexual_extortion_indicators = [
            ('photos', 'money'), ('pictures', 'pay'), ('pics', '$'), 
            ('images', 'send'), ('video', 'money'), ('recording', 'pay')
        ]
        
        for content_word, payment_word in sexual_extortion_indicators:
            if content_word in full_text and payment_word in full_text:
                patterns.append('sexual_content_payment_combo')
                break
        
        possessive_intimate = ['i have your photos', 'i have your pictures', 'i have your pics', 
                              'i got your images', 'i have your videos', 'i recorded you']
        
        if any(phrase in full_text for phrase in possessive_intimate):
            patterns.append('possessive_intimate_content')
        
        distribution_intimate_phrases = [
            'post your photos', 'share your pictures', 'upload your pics',
            'show everyone your', 'send your photos to', 'post them online'
        ]
        
        if any(phrase in full_text for phrase in distribution_intimate_phrases):
            patterns.append('intimate_distribution_threat')
        
        extortion_conditionals = ['pay me or', 'send money or', 'give me $ or', 'unless you pay']
        
        if any(phrase in full_text for phrase in extortion_conditionals):
            patterns.append('payment_conditional')
        
        if ('$' in full_text or 'money' in full_text or 'pay' in full_text):
            urgency_phrases = ['by tomorrow', '24 hours', 'right now', 'immediately', 'today']
            if any(phrase in full_text for phrase in urgency_phrases):
                patterns.append('urgent_payment_demand')
        
        platforms = ['facebook', 'instagram', 'twitter', 'reddit', 'online', 'internet']
        intimate_words = ['photos', 'pictures', 'pics', 'images', 'videos']
        
        if (any(platform in full_text for platform in platforms) and 
            any(intimate in full_text for intimate in intimate_words)):
            patterns.append('platform_intimate_threat')
        
        return patterns
    
    def _calculate_enhanced_threat_score(self, analysis: Dict) -> float:
        score = 0.0
        
        # Sentiment Analysis
        sentiment = analysis.get('sentiment', {})
        if sentiment.get('interpretation') == 'very_negative':
            score += 0.15
        elif sentiment.get('interpretation') == 'negative':
            score += 0.08
        
        # Entity Analysis
        entities = analysis.get('entities', {})
        threat_patterns = analysis.get('syntax', {}).get('threat_patterns', [])
        
        if entities.get('has_money_entities', False) and len(threat_patterns) > 0:
            score += 0.15
        
        # Pattern Analysis
        high_value_patterns = {
            'sexual_content_payment_combo': 0.25,
            'possessive_intimate_content': 0.20,
            'intimate_distribution_threat': 0.18,
            'platform_intimate_threat': 0.15
        }
        
        medium_value_patterns = {
            'payment_conditional': 0.10,
            'urgent_payment_demand': 0.08
        }
        
        for pattern in threat_patterns:
            if pattern in high_value_patterns:
                score += high_value_patterns[pattern]
            elif pattern in medium_value_patterns:
                score += medium_value_patterns[pattern]
        
        high_value_count = sum(1 for p in threat_patterns if p in high_value_patterns)
        if high_value_count >= 2:
            score += 0.15
        elif high_value_count >= 1 and len(threat_patterns) >= 3:
            score += 0.08
        
        return min(score, 1.0)
    
    def _get_threat_level(self, score: float) -> str:
        if score > 0.8:
            return "very_high"
        elif score > 0.6:
            return "high"
        elif score > 0.4:
            return "medium"
        elif score > 0.2:
            return "low"
        else:
            return "minimal"

    async def classify_message_with_user_context(self, message_content: str, user_stats: Dict = None) -> Dict:
        base_result = await self.classify_message(message_content)

        if not user_stats:
            return base_result
        
        user_risk_score = self._calculate_user_risk_score(user_stats)
        adjusted_result = self._adjust_classification_with_user_context(base_result, user_risk_score, user_stats)
        return adjusted_result
    
    def _calculate_user_risk_score(self, user_stats: Dict) -> float:
        stats = user_stats.get('stats', {})
        
        total_messages = stats.get('total_messages', 1)
        flagged_messages = stats.get('flagged_messages', 0)
        violation_count = stats.get('violation_count', 0)
        false_positives = stats.get('false_positives', 0)
        
        # Calculate risk factors
        flagged_rate = flagged_messages / max(total_messages, 1)
        violation_rate = violation_count / max(flagged_messages, 1) if flagged_messages > 0 else 0
        false_positive_rate = false_positives / max(flagged_messages, 1) if flagged_messages > 0 else 0
        
        # Risk score calculation
        risk_score = 0.0
        
        # High flagged rate, increases risk
        if flagged_rate > 0.1:
            risk_score += 0.3
        elif flagged_rate > 0.05:
            risk_score += 0.15
        
        # High violation confirmation rate, increases risk
        if violation_rate > 0.7:
            risk_score += 0.4
        elif violation_rate > 0.5:
            risk_score += 0.2
        
        # High false positive rate, decreases risk
        if false_positive_rate > 0.5:
            risk_score -= 0.2
                
        return max(0.0, min(1.0, risk_score))  # Limit between 0 and 1
    
    def _adjust_classification_with_user_context(self, base_result: Dict, user_risk_score: float, user_stats: Dict) -> Dict:
        enhanced_result = base_result.copy()
        
        original_score = base_result['ai_scores']['combined_score']
        
        risk_adjustment = 0
        
        # High-risk users, increase sensitivity, lower threshold for flagging
        if user_risk_score > 0.6:
            risk_adjustment = 3
        elif user_risk_score > 0.3:
            risk_adjustment = 1
        
        # Low-risk users with high false positive rate, decrease sensitivity
        false_positive_rate = user_stats.get('stats', {}).get('false_positives', 0) / max(user_stats.get('stats', {}).get('flagged_messages', 1), 1)
        if false_positive_rate > 0.6 and user_risk_score < 0.2:
            risk_adjustment = -5
        
        adjusted_score = min(100, max(0, original_score + risk_adjustment))
        
        # Update scores
        enhanced_result['ai_scores']['combined_score'] = adjusted_score
        enhanced_result['ai_scores']['user_risk_adjustment'] = risk_adjustment
        enhanced_result['ai_scores']['original_combined_score'] = original_score
        
        enhanced_result['is_violation'] = adjusted_score > self.violation_threshold
        
        # Add user context to analysis details
        enhanced_result['analysis_details']['user_context'] = {
            'user_risk_score': round(user_risk_score, 3),
            'risk_adjustment_applied': risk_adjustment,
            'total_messages': user_stats.get('stats', {}).get('total_messages', 0),
            'violation_rate': user_stats.get('stats', {}).get('violation_count', 0) / max(user_stats.get('stats', {}).get('flagged_messages', 1), 1),
            'false_positive_rate': false_positive_rate,
            'risk_level': self._get_user_risk_level(user_risk_score)
        }
        
        if adjusted_score > self.high_confidence_threshold:
            enhanced_result['final_classification'] = 'high_confidence_violation_with_user_context'
        elif adjusted_score > 75:
            enhanced_result['final_classification'] = 'likely_violation_with_user_context'
        
        return enhanced_result
    
    def _get_user_risk_level(self, risk_score: float) -> str:
        if risk_score > 0.7:
            return "high_risk_user"
        elif risk_score > 0.4:
            return "medium_risk_user"
        elif risk_score > 0.1:
            return "low_risk_user"
        else:
            return "minimal_risk_user"
    
    def _combine_classifications(self, gemini_result: Dict, nl_result: Dict, message: str) -> Dict:        
        # Extract scores
        gemini_confidence = gemini_result.get('gemini_confidence', 0)
        nl_threat_score = nl_result.get('enhanced_threat_assessment', {}).get('threat_score', 0)
        nl_confidence = nl_threat_score * 100
        
        # Weighted combination
        gemini_weight = 0.80
        nl_weight = 0.20
        
        # Calculate combined score
        combined_score = (gemini_confidence * gemini_weight) + (nl_confidence * nl_weight)
        combined_score = round(combined_score, 2)
        
        # Determine final classification
        final_classification = self._determine_final_classification(combined_score)
        
        # Enhanced result structure
        return {
            'message_content': message,
            'timestamp': datetime.now(),
            
            # AI Scores
            'ai_scores': {
                'gemini_confidence': gemini_confidence,
                'gemini_classification': gemini_result.get('gemini_classification', 'unknown'),
                'natural_language_threat_score': nl_threat_score,
                'natural_language_confidence': nl_confidence,
                'combined_score': combined_score
            },
            
            # Final Decision
            'final_classification': final_classification,
            'is_violation': combined_score > self.violation_threshold,
            'confidence_level': self._get_confidence_level(combined_score),
            
            # Detailed Analysis
            'analysis_details': {
                'gemini_reasoning': gemini_result.get('gemini_reasoning', ''),
                'gemini_risk_indicators': gemini_result.get('gemini_risk_indicators', []),
                'nl_threat_patterns': nl_result.get('syntax', {}).get('threat_patterns', []),
                'nl_sentiment': nl_result.get('sentiment', {}).get('interpretation', 'neutral'),
                'nl_entities': nl_result.get('entities', {}).get('entities', []),
                'nl_threat_level': nl_result.get('enhanced_threat_assessment', {}).get('threat_level', 'minimal')
            },
            
            # Enhanced Metadata
            'processing_timestamp': datetime.now(),
            'model_versions': {
                'gemini_model': 'gemini-1.5-flash',
                'natural_language_api': 'v1_enhanced'
            },
            
            # Research Data
            'research_data': {
                'individual_scores': {
                    'gemini_only': gemini_confidence,
                    'nl_only': nl_confidence
                },
                'pattern_analysis': nl_result.get('syntax', {}),
                'entity_analysis': nl_result.get('entities', {}),
                'sentiment_analysis': nl_result.get('sentiment', {})
            }
        }
    
    def _determine_final_classification(self, combined_score: float) -> str:
        if combined_score > self.high_confidence_threshold:
            return 'high_confidence_violation'
        elif combined_score > 75:
            return 'likely_violation'
        elif combined_score > 50:
            return 'possible_violation'
        elif combined_score > 30:
            return 'low_risk'
        else:
            return 'safe'
    
    def _get_confidence_level(self, score: float) -> str:
        if score > 90:
            return 'very_high'
        elif score > 75:
            return 'high'
        elif score > 60:
            return 'medium'
        elif score > 40:
            return 'low'
        else:
            return 'very_low'
    
    async def classify_message_with_regex(self, message_content: str) -> Dict:
        print(f"Analyzing message with regex: '{message_content[:50]}...'")
        
        base_result = await self.classify_message(message_content)
        
        regex_result = await self.regex_check.apply_regex_rules(message_content)
        
        base_score = base_result['ai_scores']['combined_score']
        regex_bonus = regex_result['total_regex_score'] * 100
        
        regex_bonus = min(regex_bonus, 10)
        
        enhanced_result = base_result.copy()
        enhanced_result['ai_scores']['combined_score'] = min(100, base_score + regex_bonus)
        enhanced_result['ai_scores']['base_ai_score'] = base_score
        enhanced_result['ai_scores']['regex_bonus'] = regex_bonus
        enhanced_result['regex_patterns_matched'] = regex_result['patterns_matched']
        enhanced_result['regex_rules_applied'] = regex_result['rules_applied']
        
        enhanced_result['is_violation'] = enhanced_result['ai_scores']['combined_score'] > 50
        
        enhanced_result['final_classification'] = self._determine_final_classification(
            enhanced_result['ai_scores']['combined_score']
        )
        
        print(f"Analysis complete. Base: {base_score}%, Regex: +{regex_bonus}%, Total: {enhanced_result['ai_scores']['combined_score']}%")
        return enhanced_result