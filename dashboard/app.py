from flask import Flask, render_template, request, jsonify
import asyncio
import sys
import os
from functools import wraps
import re

sys.path.append('../DiscordBot/core')
from regex_check import RegexCheck
from database import DatabaseManager

regex_check = RegexCheck()
app = Flask(__name__)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper

db = DatabaseManager()

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/rules')
def rules():
    return render_template('rules.html')

@app.route('/api/flagged-messages')
@async_route
async def get_flagged_messages():
    messages = await db.get_flagged_messages(limit=10)
    return jsonify(messages)

@app.route('/api/custom-rules')
@async_route
async def get_custom_rules():
    rules = await db.get_custom_rules()
    return jsonify(rules)

@app.route('/api/custom-rules', methods=['POST'])
@async_route
async def add_custom_rule():
    data = request.json
    pattern = data.get('pattern', '').strip()
    weight = float(data.get('weight', 0))
    description = data.get('description', '').strip()
    
    if not pattern or weight < 0 or weight > 1:
        return jsonify({'error': 'Invalid pattern or weight'}), 400
    
    validation = await regex_check.validate_pattern(pattern)
    if not validation['valid']:
        return jsonify({'error': f'Invalid regex: {validation["error"]}'}), 400
    
    await db.save_custom_rule(pattern, weight, description)
    
    regex_check.clear_cache()
    
    return jsonify({'success': True})

@app.route('/api/custom-rules/<rule_id>', methods=['DELETE'])
@async_route
async def delete_custom_rule(rule_id):
    await db.delete_custom_rule(rule_id)
    return jsonify({'success': True})

@app.route('/api/thresholds')
@async_route
async def get_thresholds():
    thresholds = await db.get_guild_thresholds()
    return jsonify(thresholds)

@app.route('/api/thresholds', methods=['POST'])
@async_route
async def update_thresholds():
    data = request.json
    violation_threshold = int(data.get('violation_threshold', 50))
    high_confidence_threshold = int(data.get('high_confidence_threshold', 85))
    
    # Validation
    if not (0 <= violation_threshold <= 100) or not (0 <= high_confidence_threshold <= 100):
        return jsonify({'error': 'Thresholds must be between 0 and 100'}), 400
    
    if violation_threshold >= high_confidence_threshold:
        return jsonify({'error': 'Violation threshold must be less than high confidence threshold'}), 400
    
    await db.save_guild_thresholds(violation_threshold, high_confidence_threshold)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)