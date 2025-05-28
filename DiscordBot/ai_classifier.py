import json
import os
from typing import Dict, List
import google.generativeai as genai
from google.cloud import language_v1
import asyncio
from datetime import datetime

class AIClassifier:
    def __init__(self):
        with open('tokens.json') as f:
            tokens = json.load(f)
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'
        
        genai.configure(api_key=tokens['gemini'])
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')

        self.language_client = language_v1.LanguageServiceClient()
        
        print("AI Classifier initialized with Gemini and Natural Language APIs")
    
    async def classify_message(self, message_content: str) -> Dict:
        print(f"Analyzing message: '{message_content[:50]}...'")
        
        # Run both analyses
        gemini_result = await self._classify_with_gemini(message_content)
        nl_result = await self._enhanced_natural_language_analysis(message_content)
        
        # Combine results
        combined_result = self._combine_classifications(gemini_result, nl_result, message_content)
        
        print(f"Analysis complete. Combined score: {combined_result['ai_scores']['combined_score']}%")
        return combined_result
    
    async def _classify_with_gemini(self, message: str) -> Dict:
        """Use Gemini to classify sexual extortion content"""
        try:
            prompt = f"""
You are an expert content moderator specializing ONLY in sexual extortion and sextortion detection.

CRITICAL: This message should get a HIGH score (70-100) ONLY if it contains ALL of these:
1. Clear possession or threat involving INTIMATE/SEXUAL photos, videos, or content
2. Explicit demand for money/payment to prevent sharing
3. Direct threat to distribute the intimate content

Examples of HIGH scores (70-100):
- "Send me $500 or I'll post your nude photos online"
- "Pay me or I'll share your intimate videos with everyone"
- "I have your private pictures and will release them unless you give me money"

Examples that should get LOW scores (0-30):
- "Hey, how are you doing today?" → 5-10 (friendly greeting)
- "I'm really upset about what happened" → 10-15 (emotional expression)
- "You better apologize or else!" → 20-30 (vague threat, no intimate content)
- "Pay me $100 and I won't tell your secret" → 30-40 (blackmail but no intimate content mentioned)

Analyze this message: "{message}"

Give a confidence_score of 0-30 unless the message clearly involves intimate/sexual content threats with payment demands.

Respond with ONLY a JSON object:
{{
    "is_sexual_extortion": true/false,
    "confidence_score": 0-100,
    "classification": "sexual_extortion" or "general_threat" or "safe",
    "reasoning": "brief explanation focusing on presence/absence of intimate content threats and payment demands",
    "risk_indicators": ["specific", "elements", "found"]
}}
"""
            
            response = self.gemini_model.generate_content(prompt)
            
            # Parse JSON response
            try:
                response_text = response.text.strip()
                
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                
                result = json.loads(response_text)
                return {
                    'gemini_confidence': result.get('confidence_score', 0),
                    'gemini_classification': result.get('classification', 'unknown'),
                    'gemini_reasoning': result.get('reasoning', 'No reasoning provided'),
                    'gemini_risk_indicators': result.get('risk_indicators', []),
                    'gemini_is_violation': result.get('is_sexual_extortion', False)
                }
            except json.JSONDecodeError:
                print(f"Gemini response parsing failed. Raw response: {response.text}")
                return {
                    'gemini_confidence': 0,
                    'gemini_classification': 'json_parse_error',
                    'gemini_reasoning': 'Failed to parse Gemini response as JSON',
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
            'is_violation': combined_score > 75,
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
        if combined_score > 85:
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
    
    async def compare_ai_systems(self, test_messages: List[str]) -> Dict:
        print("Running AI system comparison\n")
        
        results = {
            'comparison_timestamp': datetime.now(),
            'total_messages': len(test_messages),
            'individual_results': [],
            'performance_summary': {}
        }
        
        gemini_scores = []
        nl_scores = []
        agreements = []
        
        for i, message in enumerate(test_messages, 1):
            print(f"--- Comparing Message {i} ---")
            result = await self.classify_message(message)
            
            gemini_score = result['research_data']['individual_scores']['gemini_only']
            nl_score = result['research_data']['individual_scores']['nl_only']
            
            gemini_scores.append(gemini_score)
            nl_scores.append(nl_score)
            
            agreement = abs(gemini_score - nl_score) < 20
            agreements.append(agreement)
            
            individual_result = {
                'message': message,
                'gemini_score': gemini_score,
                'nl_score': nl_score,
                'combined_score': result['ai_scores']['combined_score'],
                'agreement': agreement,
                'final_classification': result['final_classification']
            }
            
            results['individual_results'].append(individual_result)
            if agreement:
                print(f"Message {i} - Agreement: Yes")
            else:
                print(f"Message {i} - Agreement: No")
            print(f"Gemini: {gemini_score} | NL: {nl_score} | Combined: {result['ai_scores']['combined_score']}")
        
        agreement_rate = sum(agreements) / len(agreements) * 100
        correlation = self._calculate_correlation(gemini_scores, nl_scores)
        
        results['performance_summary'] = {
            'agreement_rate': round(agreement_rate, 1),
            'gemini_avg_score': round(sum(gemini_scores) / len(gemini_scores), 2),
            'nl_avg_score': round(sum(nl_scores) / len(nl_scores), 2),
            'combined_avg_score': round(sum(r['combined_score'] for r in results['individual_results']) / len(results['individual_results']), 2),
            'correlation': correlation,
            'flagged_by_gemini': sum(1 for score in gemini_scores if score > 70),
            'flagged_by_nl': sum(1 for score in nl_scores if score > 70),
            'flagged_by_combined': sum(1 for r in results['individual_results'] if r['combined_score'] > 75)
        }
        
        return results
    
    def _calculate_correlation(self, scores1: List[float], scores2: List[float]) -> float:
        # Correlation calculation using Pearson's method
        if len(scores1) != len(scores2) or len(scores1) == 0:
            return 0.0
        
        mean1 = sum(scores1) / len(scores1)
        mean2 = sum(scores2) / len(scores2)
        
        numerator = sum((scores1[i] - mean1) * (scores2[i] - mean2) for i in range(len(scores1)))
        
        sum_sq1 = sum((score - mean1) ** 2 for score in scores1)
        sum_sq2 = sum((score - mean2) ** 2 for score in scores2)
        
        if sum_sq1 == 0 or sum_sq2 == 0:
            return 0.0
        
        denominator = (sum_sq1 * sum_sq2) ** 0.5
        return round(numerator / denominator, 3) if denominator != 0 else 0.0

# Testing
async def test_classifier():
    print("Testing Enhanced AI Classifier \n")
    
    classifier = AIClassifier()
    
    test_messages = [
        "Hey, how are you doing today?",
        "I'm really upset about what happened.",
        "You better apologize or else!",
        "Pay me $100 and I won't tell anyone your secret.",
        "Send me money or I'll share those photos I have of you.",
        "I have your intimate pictures and will post them online unless you pay me $500.",
        "Give me $200 by tomorrow or everyone will see what you did.",
        "I know where you live and I have recordings of our conversation."
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"--- Test {i} ---")
        result = await classifier.classify_message(message)
        
        print(f"Message: '{message}'")
        print(f"Final Classification: {result['final_classification']}")
        print(f"Combined Score: {result['ai_scores']['combined_score']}%")
        print(f"Is Violation: {result['is_violation']}")
        print(f"Confidence Level: {result['confidence_level']}")
        
        details = result['analysis_details']
        if details['gemini_risk_indicators']:
            print(f"Gemini Risk Indicators: {details['gemini_risk_indicators']}")
        if details['nl_threat_patterns']:
            print(f"NL Threat Patterns: {details['nl_threat_patterns']}")
        
        print(f"NL Sentiment: {details['nl_sentiment']} | NL Threat Level: {details['nl_threat_level']}")
        print()

async def test_system_comparison():
    print("Testing System Comparison\n")
    
    classifier = AIClassifier()
    
    test_messages = [
        "Hello there, how are you?",
        "I'm really angry about this situation!",
        "You better fix this or there will be consequences.",
        "I have some compromising information about you.",
        "Pay me $200 or I'll share your private photos.",
        "Send me money now or I'll post your pictures online.",
        "I'll release those videos unless you give me what I want.",
        "Your family will see everything if you don't cooperate by tomorrow."
    ]
    
    results = await classifier.compare_ai_systems(test_messages)
    
    print("\n Comparison Results:")
    summary = results['performance_summary']
    print(f"Agreement Rate: {summary['agreement_rate']}%")
    print(f"Gemini Average Score: {summary['gemini_avg_score']}")
    print(f"Natural Language Average Score: {summary['nl_avg_score']}")
    print(f"Combined Average Score: {summary['combined_avg_score']}")
    print(f"Score Correlation: {summary['correlation']}")
    print(f"Messages Flagged - Gemini: {summary['flagged_by_gemini']} | NL: {summary['flagged_by_nl']} | Combined: {summary['flagged_by_combined']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "compare": # Note: Use the 'compare' argument to run system comparison
        asyncio.run(test_system_comparison())
    else:
        asyncio.run(test_classifier())