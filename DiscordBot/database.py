import os
from google.cloud import firestore
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# Database Structure
# Collections:
#   flagged_messages
#   user_statistics
#   moderation_actions

class DatabaseManager:
    def __init__(self):
        """Initialize Firestore client"""
        
        # Set environment variable for Google credentials
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'
        
        # Initialize Firestore client
        self.db = firestore.Client()
        print("Database connection initialized")
    
    async def log_flagged_message(self, message_data: Dict) -> Optional[str]:
        try:
            if 'flagged_at' not in message_data:
                message_data['flagged_at'] = datetime.now()
            
            # Add to collection
            doc_ref = self.db.collection('flagged_messages').add(message_data)
            print(f"Logged flagged message with ID: {doc_ref[1].id}")
            return doc_ref[1].id
            
        except Exception as e:
            print(f"Error logging flagged message: {e}")
            return None

    async def update_flagged_message_status(self, doc_id: str, status: str, moderator: str):
        """Update the status of a flagged message after moderator decision"""
        try:
            doc_ref = self.db.collection('flagged_messages').document(doc_id)
            doc_ref.update({
                'moderation_status': status,
                'moderator_decision': moderator,
                'decision_timestamp': datetime.now()
            })
            print(f"Updated flagged message {doc_id} status to {status}")
            
        except Exception as e:
            print(f"Error updating flagged message status: {e}")
    
    async def update_user_stats(self, user_id: str, guild_id: str, username: str = "",
                               flagged: bool = False, violation: bool = False, false_positive: bool = False):
        try:
            doc_id = f"{user_id}_{guild_id}"
            doc_ref = self.db.collection('user_statistics').document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                # Update existing stats
                data = doc.to_dict()
                stats = data.get('stats', {})
                
                if not violation and not false_positive:
                    stats['total_messages'] = stats.get('total_messages', 0) + 1
                    
                if flagged:
                    stats['flagged_messages'] = stats.get('flagged_messages', 0) + 1
                    
                if violation:
                    stats['violation_count'] = stats.get('violation_count', 0) + 1
                    stats['last_violation'] = datetime.now()
                if false_positive:
                    stats['false_positives'] = stats.get('false_positives', 0) + 1
                
                # Update document
                doc_ref.update({
                    'stats': stats,
                    'updated_at': datetime.now(),
                    'username': username
                })
                print(f"Updated stats for user {user_id}")
                
            else:
                # Create new user stats
                new_stats = {
                    'user_id': user_id,
                    'username': username,
                    'guild_id': guild_id,
                    'stats': {
                        'total_messages': 1 if not violation and not false_positive else 0,
                        'flagged_messages': 1 if flagged else 0,
                        'false_positives': 1 if false_positive else 0,
                        'violation_count': 1 if violation else 0,
                        'last_violation': datetime.now() if violation else None,
                        'risk_score': 0
                    },
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                doc_ref.set(new_stats)
                print(f"Created new stats for user {user_id}")
                
        except Exception as e:
            print(f"Error updating user stats: {e}")
    
    async def log_moderation_action(self, action_data: Dict):
        try:
            action_data['timestamp'] = datetime.now()
            doc_ref = self.db.collection('moderation_actions').add(action_data)
            print(f"Logged moderation action with ID: {doc_ref[1].id}")
            return doc_ref[1].id
            
        except Exception as e:
            print(f"Error logging moderation action: {e}")
            return None
    
    # Might want to use user stats in decision-making
    async def get_user_stats(self, user_id: str, guild_id: str) -> Optional[Dict]:
        try:
            doc_id = f"{user_id}_{guild_id}"
            doc = self.db.collection('user_statistics').document(doc_id).get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                print(f"No stats found for user {user_id}")
                return None
                
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return None
    
    async def get_flagged_messages(self, limit: int = 50) -> List[Dict]:
        try:
            docs = (self.db.collection('flagged_messages')
                   .order_by('flagged_at', direction=firestore.Query.DESCENDING)
                   .limit(limit)
                   .stream())
            
            messages = []
            for doc in docs:
                data = doc.to_dict()
                data['doc_id'] = doc.id
                messages.append(data)
            
            print(f"Retrieved {len(messages)} flagged messages")
            return messages
            
        except Exception as e:
            print(f"Error getting flagged messages: {e}")
            return []
    
    async def update_system_metrics(self, date: str, metrics: Dict):
        try:
            doc_ref = self.db.collection('system_metrics').document(date)
            doc = doc_ref.get()
            
            if doc.exists:
                # Update existing metrics
                existing_data = doc.to_dict()
                existing_metrics = existing_data.get('metrics', {})
                
                for key, value in metrics.items():
                    existing_metrics[key] = existing_metrics.get(key, 0) + value
                
                doc_ref.update({'metrics': existing_metrics})
            else:
                # Create new metrics document
                doc_ref.set({
                    'date': date,
                    'metrics': metrics,
                    'created_at': datetime.now()
                })
            
            print(f"Updated system metrics for {date}")
            
        except Exception as e:
            print(f"Error updating system metrics: {e}")
            
    # Dashboard-related functions
    async def get_pending_flagged_messages(self):
        """Get messages awaiting moderator review"""
        return self.db.collection('flagged_messages')\
            .where('moderation_status', '==', 'pending')\
            .limit(20).stream()

    async def save_custom_rule(self, pattern, weight, description):
        """Save a custom regex rule"""
        self.db.collection('custom_rules').add({
            'pattern': pattern,
            'weight': weight,
            'description': description,
            'created_at': datetime.now()
        })
        
    async def get_custom_rules(self):
        """Get all custom regex rules"""
        try:
            docs = self.db.collection('custom_rules').stream()
            rules = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                rules.append(data)
            return rules
        except Exception as e:
            print(f"Error getting custom rules: {e}")
            return []

    async def save_custom_rule(self, pattern, weight, description):
        """Save a custom regex rule"""
        try:
            rule_data = {
                'pattern': pattern,
                'weight': weight,
                'description': description,
                'created_at': datetime.now()
            }
            doc_ref = self.db.collection('custom_rules').add(rule_data)
            print(f"Saved custom rule: {pattern}")
            return doc_ref[1].id
        except Exception as e:
            print(f"Error saving custom rule: {e}")
            return None

    async def delete_custom_rule(self, rule_id):
        """Delete a custom regex rule"""
        try:
            self.db.collection('custom_rules').document(rule_id).delete()
            print(f"Deleted custom rule: {rule_id}")
        except Exception as e:
            print(f"Error deleting custom rule: {e}")
            
    async def get_guild_thresholds(self):
        """Get current AI thresholds"""
        try:
            doc = self.db.collection('system_config').document('ai_thresholds').get()
            if doc.exists:
                return doc.to_dict()
            else:
                return {
                    'violation_threshold': 50,
                    'high_confidence_threshold': 85
                }
        except Exception as e:
            print(f"Error getting thresholds: {e}")
            return {'violation_threshold': 50, 'high_confidence_threshold': 85}

    async def save_guild_thresholds(self, violation_threshold, high_confidence_threshold):
        """Save AI thresholds"""
        try:
            threshold_data = {
                'violation_threshold': violation_threshold,
                'high_confidence_threshold': high_confidence_threshold,
                'updated_at': datetime.now()
            }
            self.db.collection('system_config').document('ai_thresholds').set(threshold_data)
            print(f"Updated thresholds: violation={violation_threshold}, confidence={high_confidence_threshold}")
        except Exception as e:
            print(f"Error saving thresholds: {e}")

# Create sample data for testing
async def create_sample_data():
    db = DatabaseManager()
    
    sample_message = {
        'message_id': '123456789012345678',
        'guild_id': '987654321098765432',
        'channel_id': '111222333444555666',
        'user_id': '444555666777888999',
        'username': 'testuser123',
        'content': 'This is a test message that got flagged',
        'timestamp': datetime.now(),
        'source': 'ai_detection',
        'ai_scores': {
            'gemini_confidence': 75.5,
            'gemini_classification': 'sexual_extortion',
            'natural_language_toxicity': 0.8,
            'combined_score': 82.0
        },
        'moderation_status': 'pending'
    }
    
    await db.log_flagged_message(sample_message)
    
    await db.update_user_stats('444555666777888999', '987654321098765432', 
                              'testuser123', flagged=True)
    
    mod_action = {
        'message_id': '123456789012345678',
        'moderator_id': '999888777666555444',
        'moderator_username': 'mod_test',
        'action_type': 'approved',
        'action_details': 'Confirmed as violation',
        'escalated': False,
        'ai_accuracy': 'correct'
    }
    
    await db.log_moderation_action(mod_action)
    
    print("Sample data created successfully")

if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    asyncio.run(create_sample_data())