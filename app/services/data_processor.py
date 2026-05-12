import json
import random
from typing import Dict, List


def load_data(file_path: str) -> List[Dict]:
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                item = json.loads(line)
                data.append(item)
    return data


def preprocess_data(data: List[Dict], seed: int = 42) -> List[Dict]:
    for item in data:
        agent = item.get('agent', 'human')
        item['label'] = 0 if agent == 'human' else 1

    random.seed(seed)
    random.shuffle(data)

    return data


def split_data(data: List[Dict], train_ratio: float = 0.7, val_ratio: float = 0.2):
    total = len(data)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    train_data = data[:train_end]
    val_data = data[train_end:val_end]
    test_data = data[val_end:]

    for item in train_data:
        item['type'] = 'train'
    for item in val_data:
        item['type'] = 'val'
    for item in test_data:
        item['type'] = 'test'

    return train_data, val_data, test_data