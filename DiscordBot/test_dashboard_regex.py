import asyncio
from regex_check import RegexCheck
from database import DatabaseManager

async def test_dashboard_rules():
    print("Testing Dashboard Regex Rules Integration")
    
    check = RegexCheck()
    database = DatabaseManager()
    
    print("Current rules in database:")
    
    rules = await database.get_custom_rules()
    if not rules:
        print("No rules found in database")
        return
    
    print(f"Found {len(rules)} rules:")
    for i, rule in enumerate(rules, 1):
        print(f"  {i}. Pattern: {rule['pattern']}")
        print(f"     Description: {rule.get('description', 'No description')}")
        print(f"     Weight: {rule['weight']}")
        print()
    
    # Tests
    test_message = "Send me $100 bitcoin or I'll share your photos"
    print(f"Testing message: '{test_message}'")
    
    check.clear_cache()
    
    result = await check.apply_regex_rules(test_message)
    
    print(f"Regex score: +{result['total_regex_score'] * 100:.1f}%")
    print(f"Rules applied: {result['rules_applied']}")
    print(f"Patterns matched: {len(result['patterns_matched'])}")
    
    if result['patterns_matched']:
        print("Matched patterns:")
        for pattern in result['patterns_matched']:
            print(f"  - {pattern['description']} (Pattern: {pattern['pattern']}, Weight: +{pattern['weight']*100:.1f}%)")
    else:
        print("No patterns matched")
    
    test_message2 = "I have your intimate photos and will post them"
    print(f"\nTesting message 2: '{test_message2}'")
    print("-" * 30)
    
    result2 = await check.apply_regex_rules(test_message2)
    print(f"Regex score: +{result2['total_regex_score'] * 100:.1f}%")
    
    if result2['patterns_matched']:
        print("Matched patterns:")
        for pattern in result2['patterns_matched']:
            print(f"  - {pattern['description']} (Weight: +{pattern['weight']*100:.1f}%)")
    
    print(f"\n Dashboard rules are {'working' if result['rules_applied'] > 0 else 'NOT working'}")

if __name__ == "__main__":
    asyncio.run(test_dashboard_rules())