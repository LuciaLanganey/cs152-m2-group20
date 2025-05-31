import pandas as pd
import asyncio
from ai_classifier import AIClassifier
from sklearn.metrics import accuracy_score
from datetime import datetime, timedelta

class UserContextTester:
    def __init__(self):
        self.classifier = None
        
    async def initialize(self):
        self.classifier = AIClassifier()
        
    def load_dataset(self, csv_path="with_user_stats.csv"):
        df = pd.read_csv(csv_path)
        return df
    
    async def test_with_and_without_context(self, df):
        print(f"\nTesting baseline vs user context")
        
        baseline_results = []
        context_results = []
        
        for index, row in df.iterrows():
            message = row['message_content']
            true_label = row['true_sextortion_label']
            
            print(f"Testing {index+1}/{len(df)}: {message[:40]}...")
            
            try:
                # Test without user context
                baseline_result = await self.classifier.classify_message(message)
                baseline_score = baseline_result['ai_scores']['combined_score']
                baseline_prediction = 1 if baseline_result['is_violation'] else 0
                
                # Test with user context
                user_stats = self.make_user_stats(row)
                context_result = await self.classifier.classify_message_with_user_context(message, user_stats)
                context_score = context_result['ai_scores']['combined_score']
                context_prediction = 1 if context_result['is_violation'] else 0
                
                # Calculate difference
                adjustment = context_score - baseline_score
                
                print(f"  Baseline: {baseline_score:.1f}% -> Context: {context_score:.1f}% (change: {adjustment:+.1f})")
                
                # Store results
                baseline_results.append({
                    'true_label': true_label,
                    'predicted_label': baseline_prediction,
                    'score': baseline_score,
                    'correct': true_label == baseline_prediction,
                    'user_risk': row['user_risk_level']
                })
                
                context_results.append({
                    'true_label': true_label,
                    'predicted_label': context_prediction,
                    'score': context_score,
                    'correct': true_label == context_prediction,
                    'user_risk': row['user_risk_level'],
                    'adjustment': adjustment
                })
                
            except Exception as e:
                print(f"  Error: {e}")
                # Add error records
                error_record = {
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': false,
                    'user_risk': row['user_risk_level']
                }
                baseline_results.append(error_record)
                context_results.append({**error_record, 'adjustment': 0})
        
        return baseline_results, context_results
    
    def make_user_stats(self, row):
        # Handle last violation date
        days_since = row['days_since_last_violation']
        if pd.notna(days_since):
            last_violation = datetime.now() - timedelta(days=int(days_since))
        else:
            last_violation = None
        
        return {
            'stats': {
                'total_messages': int(row['total_messages']),
                'flagged_messages': int(row['flagged_messages']),
                'violation_count': int(row['violation_count']),
                'false_positives': int(row['false_positives']),
                'last_violation': last_violation,
                'risk_score': float(row['user_risk_score'])
            }
        }
    
    def compare_results(self, baseline_results, context_results):
        print("Comparison Results")
        
        # Calculate accuracies
        baseline_acc = sum(r['correct'] for r in baseline_results) / len(baseline_results)
        context_acc = sum(r['correct'] for r in context_results) / len(context_results)
        
        print(f"Baseline accuracy: {baseline_acc:.3f} ({baseline_acc*100:.1f}%)")
        print(f"With user context: {context_acc:.3f} ({context_acc*100:.1f}%)")
        
        improvement = context_acc - baseline_acc
        print(f"Improvement: {improvement:+.3f} ({improvement*100:+.1f}%)")
        
        # Count changes
        changes = sum(1 for i in range(len(baseline_results)) 
                     if baseline_results[i]['predicted_label'] != context_results[i]['predicted_label'])
        print(f"Classification changes: {changes}")
        
        # Show by risk level
        print(f"\nBy user risk level:")
        risk_levels = ['minimal_risk', 'low_risk', 'medium_risk', 'high_risk']
        
        for risk in risk_levels:
            baseline_subset = [r for r in baseline_results if r['user_risk'] == risk]
            context_subset = [r for r in context_results if r['user_risk'] == risk]
            
            if baseline_subset:
                baseline_risk_acc = sum(r['correct'] for r in baseline_subset) / len(baseline_subset)
                context_risk_acc = sum(r['correct'] for r in context_subset) / len(context_subset)
                risk_improvement = context_risk_acc - baseline_risk_acc
                
                print(f"  {risk}: {baseline_risk_acc:.3f} -> {context_risk_acc:.3f} ({risk_improvement:+.3f})")
        
        return baseline_acc, context_acc
    
    def save_comparison(self, baseline_results, context_results):
        comparison_data = []
        
        for i in range(len(baseline_results)):
            baseline = baseline_results[i]
            context = context_results[i]
            
            comparison_data.append({
                'true_label': baseline['true_label'],
                'baseline_score': baseline['score'],
                'baseline_prediction': baseline['predicted_label'],
                'baseline_correct': baseline['correct'],
                'context_score': context['score'],
                'context_prediction': context['predicted_label'],
                'context_correct': context['correct'],
                'adjustment': context.get('adjustment', 0),
                'user_risk': baseline['user_risk'],
                'changed': baseline['predicted_label'] != context['predicted_label']
            })
        
        df = pd.DataFrame(comparison_data)
        df.to_csv("user_context_results.csv", index=False)

async def main():
    print("User Context Classifier Test")
    
    tester = UserContextTester()
    await tester.initialize()
    
    # Load data and test
    df = tester.load_dataset()
    baseline_results, context_results = await tester.test_with_and_without_context(df)
    
    # Compare and save
    baseline_acc, context_acc = tester.compare_results(baseline_results, context_results)
    tester.save_comparison(baseline_results, context_results)
    
if __name__ == "__main__":
    asyncio.run(main())