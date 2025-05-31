import pandas as pd
import asyncio
from ai_classifier import AIClassifier
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

class ClassifierTest:
    def __init__(self):
        self.classifier = None
        
    async def initialize(self):        
        self.classifier = AIClassifier()
            
    def load_test_dataset(self, csv_path):        
        df = pd.read_csv(csv_path)
        
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        
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
                result = await self.classifier.classify_message(message)
                
                score = result['ai_scores']['combined_score']
                predicted_label = 1 if result['is_violation'] else 0
                is_correct = (true_label == predicted_label)
                
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
                    'correct': False,
                    'classification': 'error'
                })
        
        return results
    
    def analyze_results(self, results):
        print("Test Results")
        
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
        
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1_score_val = f1_score(y_true, y_pred, zero_division=0)
            
            print(f"\nMetrics:")
            print(f"True Positives (TP): {tp}")
            print(f"True Negatives (TN): {tn}")
            print(f"False Positives (FP): {fp}")
            print(f"False Negatives (FN): {fn}")
            print(f"Precision: {precision:.3f}")
            print(f"Recall: {recall:.3f}")
            print(f"F1-Score: {f1_score_val:.3f}")
        
        return accuracy

async def main():
    print("Classifier Test")
    
    tester = ClassifierTest()
    await tester.initialize()
    
    df = tester.load_test_dataset("M3_Dataset - Full Sorted .csv")
    results = await tester.run_test(df)
    
    accuracy = tester.analyze_results(results)
    
    print(f"\nFinal accuracy: {accuracy*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())