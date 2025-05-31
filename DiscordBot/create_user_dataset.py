import pandas as pd
import random
from datetime import datetime, timedelta

def create_user_dataset():    
    df = pd.read_csv("M3_Dataset - Full Sorted .csv")
    
    user_profiles = create_users()
    
    enhanced_data = []
    
    for index, row in df.iterrows():
        message = row['Sample Message']
        is_sextortion = row['Label']
        
        # Pick a user for this message
        user = pick_user_for_message(user_profiles, is_sextortion)
        
        # Create record
        record = {
            'message_id': f"msg_{index:03d}",
            'user_id': user['user_id'],
            'username': user['username'],
            'message_content': message,
            'true_sextortion_label': is_sextortion,
            
            # User stats
            'total_messages': user['total_messages'],
            'flagged_messages': user['flagged_messages'],
            'violation_count': user['violation_count'],
            'false_positives': user['false_positives'],
            'days_since_last_violation': user['days_since_last_violation'],
            
            # Calculated metrics
            'flagged_rate': user['flagged_rate'],
            'violation_rate': user['violation_rate'],
            'false_positive_rate': user['false_positive_rate'],
            'user_risk_score': user['risk_score'],
            'user_risk_level': user['risk_level'],
        }
        enhanced_data.append(record)
        
    enhanced_df = pd.DataFrame(enhanced_data)
    enhanced_df.to_csv("with_user_stats.csv", index=False)
    
    return enhanced_df

def create_users():
    profiles = []
    
    # High-risk users
    for i in range(5):
        profile = {
            'user_id': f"high_risk_user_{i+1}",
            'username': f"HighRiskUser{i+1}",
            'total_messages': random.randint(50, 200),
            'flagged_messages': random.randint(15, 40),
            'violation_count': random.randint(8, 25),
            'false_positives': random.randint(2, 8),
            'days_since_last_violation': random.randint(1, 30),
            'type': 'high_risk'
        }
        calculate_metrics(profile)
        profiles.append(profile)
    
    # Medium-risk users
    for i in range(8):
        profile = {
            'user_id': f"medium_risk_user_{i+1}",
            'username': f"MediumRiskUser{i+1}",
            'total_messages': random.randint(100, 300),
            'flagged_messages': random.randint(5, 15),
            'violation_count': random.randint(2, 8),
            'false_positives': random.randint(2, 6),
            'days_since_last_violation': random.randint(30, 120),
            'type': 'medium_risk'
        }
        calculate_metrics(profile)
        profiles.append(profile)
    
    # Low-risk users
    for i in range(10):
        profile = {
            'user_id': f"low_risk_user_{i+1}",
            'username': f"LowRiskUser{i+1}",
            'total_messages': random.randint(200, 500),
            'flagged_messages': random.randint(3, 8),
            'violation_count': random.randint(0, 2),
            'false_positives': random.randint(4, 8),
            'days_since_last_violation': random.randint(180, 365) if random.random() > 0.3 else None,
            'type': 'low_risk'
        }
        calculate_metrics(profile)
        profiles.append(profile)
    
    # No Risk users
    for i in range(12):
        profile = {
            'user_id': f"clean_user_{i+1}",
            'username': f"CleanUser{i+1}",
            'total_messages': random.randint(100, 400),
            'flagged_messages': random.randint(0, 3),
            'violation_count': 0,
            'false_positives': random.randint(0, 3),
            'days_since_last_violation': None,
            'type': 'clean'
        }
        calculate_metrics(profile)
        profiles.append(profile)
    
    return profiles

def calculate_metrics(profile):
    total = profile['total_messages']
    flagged = profile['flagged_messages']
    violations = profile['violation_count']
    false_pos = profile['false_positives']
    
    profile['flagged_rate'] = flagged / max(total, 1)
    profile['violation_rate'] = violations / max(flagged, 1) if flagged > 0 else 0
    profile['false_positive_rate'] = false_pos / max(flagged, 1) if flagged > 0 else 0
    
    # Calculate risk score
    risk = 0.0
    
    # High flagged rate increases risk
    if profile['flagged_rate'] > 0.1:
        risk += 0.3
    elif profile['flagged_rate'] > 0.05:
        risk += 0.15
    
    # High violation rate increases risk
    if profile['violation_rate'] > 0.7:
        risk += 0.4
    elif profile['violation_rate'] > 0.5:
        risk += 0.2
    
    # High false positive rate decreases risk
    if profile['false_positive_rate'] > 0.5:
        risk -= 0.2
    
    # Recent violations increase risk
    if profile['days_since_last_violation'] is not None:
        if profile['days_since_last_violation'] < 7:
            risk += 0.3
        elif profile['days_since_last_violation'] < 30:
            risk += 0.1
    
    profile['risk_score'] = max(0.0, min(1.0, risk))
    
    # Set risk level
    if profile['risk_score'] > 0.6:
        profile['risk_level'] = 'high_risk'
    elif profile['risk_score'] > 0.3:
        profile['risk_level'] = 'medium_risk'
    elif profile['risk_score'] > 0.1:
        profile['risk_level'] = 'low_risk'
    else:
        profile['risk_level'] = 'minimal_risk'

def pick_user_for_message(users, is_sextortion):
    if is_sextortion == 1:
        # Sextortion more likely from risky users
        if random.random() < 0.4:
            candidates = [u for u in users if u['type'] == 'high_risk']
        elif random.random() < 0.3:
            candidates = [u for u in users if u['type'] == 'medium_risk']
        else:
            candidates = [u for u in users if u['type'] in ['low_risk', 'clean']]
    else:
        # Safe messages more from clean users
        if random.random() < 0.5:
            candidates = [u for u in users if u['type'] == 'clean']
        elif random.random() < 0.3:
            candidates = [u for u in users if u['type'] == 'low_risk']
        else:
            candidates = [u for u in users if u['type'] in ['medium_risk', 'high_risk']]
    
    return random.choice(candidates)

if __name__ == "__main__":
    print("Creating User Dataset")
    
    enhanced_df = create_user_dataset()