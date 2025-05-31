import re
import asyncio
from typing import Dict, List
from database import DatabaseManager

class RegexCheck:
    def __init__(self):
        self.database = DatabaseManager()
        self._cached_rules = None
        self._cache_timestamp = None
    
    async def apply_regex_rules(self, message: str) -> Dict:
        try:
            rules = await self._get_rules()
            
            total_score = 0.0
            patterns_matched = []
            
            message_lower = message.lower()
            
            for rule in rules:
                pattern = rule['pattern']
                weight = rule['weight']
                description = rule.get('description', '')
                
                try:
                    if re.search(pattern, message_lower, re.IGNORECASE):
                        total_score += weight
                        patterns_matched.append({
                            'pattern': pattern,
                            'description': description,
                            'weight': weight
                        })
                        print(f"  Regex match: {description or pattern} (+{weight*100:.1f}%)")
                except re.error:
                    print(f"Invalid regex pattern: {pattern}")
                    continue
            
            return {
                'total_regex_score': min(total_score, 0.1),
                'patterns_matched': patterns_matched,
                'rules_applied': len(rules)
            }
            
        except Exception as e:
            print(f"Error applying regex rules: {e}")
            return {
                'total_regex_score': 0.0, 
                'patterns_matched': [],
                'rules_applied': 0
            }
    
    async def _get_rules(self) -> List[Dict]:
        try:
            import time
            current_time = time.time()
            
            if (self._cached_rules is None or 
                self._cache_timestamp is None or 
                current_time - self._cache_timestamp > 60):
                
                self._cached_rules = await self.database.get_custom_rules()
                self._cache_timestamp = current_time
                print(f"Loaded {len(self._cached_rules)} regex rules from database")
            
            return self._cached_rules
            
        except Exception as e:
            print(f"Error loading regex rules: {e}")
            return []
    
    def clear_cache(self):
        self._cached_rules = None
        self._cache_timestamp = None
    
    async def test_pattern(self, pattern: str, test_message: str) -> bool:
        try:
            return bool(re.search(pattern, test_message, re.IGNORECASE))
        except re.error:
            return False
    
    async def validate_pattern(self, pattern: str) -> Dict:
        try:
            re.compile(pattern)
            return {'valid': True, 'error': None}
        except re.error as e:
            return {'valid': False, 'error': str(e)}
    
    async def setup_test_rules(self):
        test_rules = [
            {"pattern": r"\$\d+", "weight": 0.05, "description": "Money amounts"},
            {"pattern": r"pay.*bitcoin", "weight": 0.08, "description": "Bitcoin payment demands"},
            {"pattern": r"send.*money.*urgent", "weight": 0.06, "description": "Urgent payment requests"},
            {"pattern": r"i have.*photo", "weight": 0.08, "description": "Photo possession claims"},
            {"pattern": r"share.*pics.*online", "weight": 0.07, "description": "Online sharing threats"},
        ]
        
        print(f"Setting up {len(test_rules)} test regex rules...")
        
        for rule in test_rules:
            await self.database.save_custom_rule(rule["pattern"], rule["weight"], rule["description"])
        
        self.clear_cache()
        print("Test rules added to database")
    
    async def run_test(self):
        print("Testing Regex Rules")
        
        await self.setup_test_rules()
        
        test_messages = [
            "Send me $500 or I'll share your photos online",
            "Pay bitcoin now or else",
            "I have your photos",
            "Give me money urgent please",
            "Hello how are you today?",
            "Can you help with homework?",
            "Share some pics online later",
            "I need $20 for lunch",
        ]
        
        print("\nTesting messages:")
        
        results = []
        
        for i, message in enumerate(test_messages, 1):
            print(f"\nTest {i}: '{message}'")
            
            try:
                regex_result = await self.apply_regex_rules(message)
                regex_score = regex_result['total_regex_score'] * 100
                patterns_matched = regex_result.get('patterns_matched', [])
                
                print(f"  Regex Score: +{regex_score:.1f}%")
                print(f"  Rules Applied: {regex_result['rules_applied']}")
                
                if patterns_matched:
                    print(f"  Patterns matched:")
                    for pattern in patterns_matched:
                        print(f"    - {pattern['description']} (+{pattern['weight']*100:.1f}%)")
                else:
                    print(f"  No regex patterns matched")
                
                results.append({
                    'message': message,
                    'regex_score': regex_score,
                    'patterns_count': len(patterns_matched),
                    'patterns': patterns_matched
                })
                
            except Exception as e:
                print(f"  Error: {e}")
                results.append({
                    'message': message,
                    'error': str(e)
                })
        
        return results

async def test_regex():
    regex = RegexCheck()
    await regex.run_test()

if __name__ == "__main__":
    print("Running Regex Test")
    asyncio.run(test_regex())