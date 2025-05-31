import pandas as pd
import asyncio
import sys
sys.path.append('../core')
from ai_classifier import AIClassifier
from database import DatabaseManager
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
import random
from datetime import datetime, timedelta

class ClassifierTest:
    def __init__(self):
        self.classifier = None
        self.database = None
        self.current_thresholds = None
        
    async def initialize(self):        
        self.classifier = AIClassifier()
        self.database = DatabaseManager()
        
        # Get current thresholds from database
        self.current_thresholds = await self.database.get_guild_thresholds()
        print(f"Using dynamic thresholds from database:")
        print(f"  Violation threshold: {self.current_thresholds['violation_threshold']}%")
        print(f"  High confidence threshold: {self.current_thresholds['high_confidence_threshold']}%")
            
    def load_test_dataset(self, csv_path, sample_size=50):        
        df = pd.read_csv(csv_path)
        
        # Take random sample
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        
        print(f"Using {len(df)} messages for testing")
        
        if 'Label' in df.columns:
            counts = df['Label'].value_counts()
            print(f"Dataset: {counts.get(0, 0)} safe messages, {counts.get(1, 0)} sextortion messages")
        
        return df
    
    def _apply_dynamic_threshold(self, score):
        return 1 if score > self.current_thresholds['violation_threshold'] else 0
    
    def _get_final_classification(self, score):
        if score > self.current_thresholds['high_confidence_threshold']:
            return 'high_confidence_violation'
        elif score > 75:
            return 'likely_violation'
        elif score > self.current_thresholds['violation_threshold']:
            return 'possible_violation'
        elif score > 30:
            return 'low_risk'
        else:
            return 'safe'
    
    async def test_base_classifier(self, df):
        print("\nTest 1: Base Classifier (with dynamic thresholds)")
        results = []
        
        for index, row in df.iterrows():
            message = row['Sample Message']
            true_label = int(row['Label'])
            
            try:
                result = await self.classifier.classify_message(message)
                score = result['ai_scores']['combined_score']
                
                predicted_label = self._apply_dynamic_threshold(score)
                
                result['is_violation'] = predicted_label == 1
                result['final_classification'] = self._get_final_classification(score)
                result['threshold_used'] = self.current_thresholds['violation_threshold']
                
                results.append({
                    'true_label': true_label,
                    'predicted_label': predicted_label,
                    'score': score,
                    'correct': (true_label == predicted_label),
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
                
            except Exception as e:
                print(f"Error on row {index}: {e}")
                results.append({
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': False,
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
        
        return results
    
    async def test_classifier_with_regex(self, df):
        print("\nTest 2: Classifier + Regex (with dynamic thresholds)")
        results = []
        
        for index, row in df.iterrows():
            message = row['Sample Message']
            true_label = int(row['Label'])
            
            try:
                result = await self.classifier.classify_message_with_regex(message)
                score = result['ai_scores']['combined_score']
                
                predicted_label = self._apply_dynamic_threshold(score)
                
                result['is_violation'] = predicted_label == 1
                result['final_classification'] = self._get_final_classification(score)
                result['threshold_used'] = self.current_thresholds['violation_threshold']
                
                results.append({
                    'true_label': true_label,
                    'predicted_label': predicted_label,
                    'score': score,
                    'correct': (true_label == predicted_label),
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
 
            except Exception as e:
                print(f"Error on row {index}: {e}")
                results.append({
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': False,
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
        
        return results
    
    async def test_classifier_with_user_stats(self, df):
        print("\nTest 3: Classifier + User Stats (with dynamic thresholds)")
        results = []
        
        for index, row in df.iterrows():
            message = row['Sample Message']
            true_label = int(row['Label'])
            
            try:
                user_stats = self._generate_test_user_stats()
                result = await self.classifier.classify_message_with_user_context(message, user_stats)
                score = result['ai_scores']['combined_score']
                
                predicted_label = self._apply_dynamic_threshold(score)
                
                result['is_violation'] = predicted_label == 1
                result['final_classification'] = self._get_final_classification(score)
                result['threshold_used'] = self.current_thresholds['violation_threshold']
                
                results.append({
                    'true_label': true_label,
                    'predicted_label': predicted_label,
                    'score': score,
                    'correct': (true_label == predicted_label),
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
                
            except Exception as e:
                print(f"Error on row {index}: {e}")
                results.append({
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': False,
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
        
        return results
    
    async def test_classifier_combined(self, df):
        print("\nTest 4: Classifier + Regex + User Stats (with dynamic thresholds)")
        results = []
        
        for index, row in df.iterrows():
            message = row['Sample Message']
            true_label = int(row['Label'])
            
            try:
                # Regex result
                regex_result = await self.classifier.classify_message_with_regex(message)
                
                user_stats = self._generate_test_user_stats()
                base_result = await self.classifier.classify_message(message)
                
                base_score = base_result['ai_scores']['combined_score']
                regex_bonus = regex_result['ai_scores'].get('regex_bonus', 0)
                
                # Apply user context to the combined score
                combined_result = await self.classifier.classify_message_with_user_context(message, user_stats)
                user_adjustment = combined_result['ai_scores'].get('user_risk_adjustment', 0)
                
                final_score = min(100, base_score + regex_bonus + user_adjustment)
                
                # Use dynamic threshold instead of hardcoded
                predicted_label = self._apply_dynamic_threshold(final_score)
                
                results.append({
                    'true_label': true_label,
                    'predicted_label': predicted_label,
                    'score': final_score,
                    'correct': (true_label == predicted_label),
                    'threshold_used': self.current_thresholds['violation_threshold']
                })

            except Exception as e:
                print(f"Error on row {index}: {e}")
                results.append({
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': False,
                    'threshold_used': self.current_thresholds['violation_threshold']
                })
        
        return results
    
    def _generate_test_user_stats(self):
        total_messages = random.randint(10, 1000)
        flagged_rate = random.uniform(0.01, 0.15)
        flagged_messages = int(total_messages * flagged_rate)
        violation_rate = random.uniform(0.3, 0.8)
        violation_count = int(flagged_messages * violation_rate)
        false_positives = flagged_messages - violation_count
        
        return {
            'stats': {
                'total_messages': total_messages,
                'flagged_messages': flagged_messages,
                'violation_count': violation_count,
                'false_positives': false_positives,
                'last_violation': datetime.now() - timedelta(days=random.randint(1, 30)),
                'risk_score': random.uniform(0.1, 0.7)
            }
        }
    
    def analyze_results(self, results, test_name):
        print(f"\n{test_name} Results:")
        
        # Show threshold used
        if results and 'threshold_used' in results[0]:
            print(f"Threshold used: {results[0]['threshold_used']}%")
        
        y_true = [r['true_label'] for r in results]
        y_pred = [r['predicted_label'] for r in results]
        
        accuracy = accuracy_score(y_true, y_pred)
        cm = confusion_matrix(y_true, y_pred)
        
        print(f"Accuracy: {accuracy:.3f} ({accuracy*100:.1f}%)")
        
        print(f"\nConfusion Matrix:")
        print(f"                Predicted")
        print(f"               Safe    Sextortion")
        print(f"Actual Safe:     {cm[0,0]:3d}       {cm[0,1]:3d}")
        print(f"Actual Sextortion: {cm[1,0]:3d}       {cm[1,1]:3d}")
        
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            
            print(f"\nMetrics:")
            print(f"True Positives (TP): {tp}")
            print(f"True Negatives (TN): {tn}")
            print(f"False Positives (FP): {fp}")
            print(f"False Negatives (FN): {fn}")
            print(f"Precision: {precision:.3f}")
            print(f"Recall: {recall:.3f}")
            print(f"F1-Score: {f1:.3f}")
        
        return accuracy, precision, recall, f1
    
    def compare_all_results(self, results_dict):
        print("Comparison Summary")
        
        if results_dict:
            first_results = list(results_dict.values())[0]
            if first_results and 'threshold_used' in first_results[0]:
                print(f"All tests used violation threshold: {first_results[0]['threshold_used']}%")
                print(f"High confidence threshold: {self.current_thresholds['high_confidence_threshold']}%")
        
        metrics = {}
        for test_name, results in results_dict.items():
            y_true = [r['true_label'] for r in results]
            y_pred = [r['predicted_label'] for r in results]
            
            accuracy = accuracy_score(y_true, y_pred)
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            
            metrics[test_name] = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1
            }
        
        print(f"{'Test':<25} {'Accuracy':<10} {'Precision':<10} {'Recall':<10} {'F1-Score':<10}")
        
        for test_name, metric in metrics.items():
            print(f"{test_name:<25} {metric['accuracy']:.3f}     {metric['precision']:.3f}      {metric['recall']:.3f}    {metric['f1']:.3f}")
        
        best_accuracy = max(metrics.values(), key=lambda x: x['accuracy'])
        best_test = [name for name, metric in metrics.items() if metric['accuracy'] == best_accuracy['accuracy']][0]
        print(f"\nBest performing test: {best_test} (Accuracy: {best_accuracy['accuracy']:.3f})")

async def main():
    print("Classifier Test")
    
    tester = ClassifierTest()
    await tester.initialize()
    df = tester.load_test_dataset("../data/M3_Dataset - Full Sorted .csv", sample_size=50)
    
    # Run all 4 tests
    base_results = await tester.test_base_classifier(df)
    regex_results = await tester.test_classifier_with_regex(df)
    user_results = await tester.test_classifier_with_user_stats(df)
    combined_results = await tester.test_classifier_combined(df)
    
    # Analyze each test
    tester.analyze_results(base_results, "Base Classifier")
    tester.analyze_results(regex_results, "Classifier + Regex")
    tester.analyze_results(user_results, "Classifier + User Stats")
    tester.analyze_results(combined_results, "Combined Classifier")
    
    # Compare all results
    all_results = {
        "Base Classifier": base_results,
        "Classifier + Regex": regex_results,
        "Classifier + User Stats": user_results,
        "Combined Classifier": combined_results
    }
    
    tester.compare_all_results(all_results)

if __name__ == "__main__":
    asyncio.run(main())