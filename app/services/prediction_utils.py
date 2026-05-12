import os
import csv
import torch
from typing import Dict, List


def format_predictions_unified(all_ids, all_outputs, all_labels, model_type: str) -> List[Dict]:
    probabilities = torch.softmax(all_outputs, dim=-1)
    positive_probs = probabilities[:, 1].numpy()

    predictions = []
    for i in range(len(all_ids)):
        predictions.append({
            'id': int(all_ids[i]),
            'predicted_probability': float(positive_probs[i]),
            'target_label': int(all_labels[i])
        })
    return predictions


def unified_save_predictions(predictions: List[Dict], model_name: str, data_dir: str, result_dir: str, filename: str) -> str:
    os.makedirs(result_dir, exist_ok=True)
    output_path = os.path.join(result_dir, f"{filename}_predictions.csv")

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'predicted_probability', 'target_label'])
        writer.writeheader()
        writer.writerows(predictions)

    return output_path