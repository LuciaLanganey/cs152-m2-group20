import pandas as pd
import asyncio
from ai_classifier import AIClassifier
from sklearn.metrics import confusion_matrix, accuracy_score
import json

class ClassifierTest:
    def __init__(self):
        self.classifier = None
        
    async def initialize(self):        
        self.classifier = AIClassifier()
            
    def load_test_dataset(self, csv_path):        
        df = pd.read_csv(csv_path)
        
        # Shuffle for random order
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        print("Dataset shuffled")
        
        # Show distribution
        if 'Label' in df.columns:
            counts = df['Label'].value_counts()
            print(f"Dataset: {counts.get(0, 0)} safe messages, {counts.get(1, 0)} sextortion messages")
        
        return df
    
    async def run_test(self, df):        
        results = []
        
        for index, row in df.iterrows():
            message = row['Sample Message']
            true_label = int(row['Label'])
            
            print(f"Testing {index+1}/{len(df)}: {message[:50]}...")
            
            try:
                # Run classifier
                result = await self.classifier.classify_message(message)
                
                # Get prediction
                score = result['ai_scores']['combined_score']
                predicted_label = 1 if result['is_violation'] else 0
                is_correct = (true_label == predicted_label)
                
                # Store result
                results.append({
                    'message': message,
                    'true_label': true_label,
                    'predicted_label': predicted_label,
                    'score': score,
                    'correct': is_correct,
                    'classification': result['final_classification']
                })
                
                print(f"  Score: {score:.1f}%, Predicted: {predicted_label}, Actual: {true_label}, Correct: {is_correct}")
                
            except Exception as e:
                print(f"  Error: {e}")
                results.append({
                    'message': message,
                    'true_label': true_label,
                    'predicted_label': 0,
                    'score': 0,
                    'correct': false,
                    'classification': 'error'
                })
        
        return results
    
    def analyze_results(self, results):
        print("Test Results")
        
        # Calculate metrics
        y_true = [r['true_label'] for r in results]
        y_pred = [r['predicted_label'] for r in results]
        
        accuracy = accuracy_score(y_true, y_pred)
        cm = confusion_matrix(y_true, y_pred)
        
        print(f"Accuracy: {accuracy:.3f} ({accuracy*100:.1f}%)")
        
        print("\nConfusion Matrix:")
        print("                Predicted")
        print("               Safe    Sextortion")
        print(f"Actual Safe:     {cm[0,0]:3d}       {cm[0,1]:3d}")
        print(f"Actual Sextortion: {cm[1,0]:3d}       {cm[1,1]:3d}")
        
        # Calculate detailed metrics
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            print(f"\nMetrics:")
            print(f"Precision: {precision:.3f}")
            print(f"Recall: {recall:.3f}")
            print(f"F1-Score: {f1_score:.3f}")
            
            # Show errors
            self.show_errors(results)
        
        return accuracy
    
    

async def main():
    print("Classifier Test")
    
    # Initialize
    tester = ClassifierTest()
    await tester.initialize()
    
    # Load and test
    df = tester.load_test_dataset("M3_Dataset - Full Sorted .csv")
    results = await tester.run_test(df)
    
    # Analyze
    accuracy = tester.analyze_results(results)
    
    print(f"\nFinal accuracy: {accuracy*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())