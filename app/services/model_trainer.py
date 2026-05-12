import json
import os
import random
import threading
import csv
import io
import sys
import requests
from typing import Dict, List, Optional, Callable
from datetime import datetime
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from transformers import AutoTokenizer, AutoModel, AutoConfig
import numpy as np
from sklearn.metrics import f1_score, recall_score, accuracy_score, precision_score
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments, EarlyStoppingCallback


from .data_processor import load_data, preprocess_data, split_data
from .prediction_utils import unified_save_predictions, format_predictions_unified


TRAINING_STATUS = {}
TRAINING_STATUS_LOCK = threading.Lock()


class TeeStream:
    def __init__(self, original_stream, progress_callback):
        self.original_stream = original_stream
        self.progress_callback = progress_callback
        self.buffer = []
        self._last_tqdm = ''

    def write(self, text):
        if not text:
            return
        self.original_stream.write(text)
        if text.strip():
            self.buffer.append(text)
            combined = ''.join(self.buffer)
            if '\n' in text:
                lines = combined.split('\n')
                for line in lines[:-1]:
                    stripped = line.rstrip('\r')
                    if stripped.strip():
                        self.progress_callback('log', stripped)
                self.buffer = [lines[-1]] if lines[-1].strip() else []
            elif '\r' in text:
                full_line = combined.rstrip('\r')
                if full_line.strip() and full_line != self._last_tqdm:
                    self._last_tqdm = full_line
                    self.progress_callback('tqdm', full_line)
                self.buffer = []

    def flush(self):
        if self.buffer:
            combined = ''.join(self.buffer).rstrip('\n\r')
            if combined.strip():
                self.progress_callback('log', combined)
            self.buffer = []
        self.original_stream.flush()

    def isatty(self):
        return True


class ModelTrainerService:
    def __init__(self, output_dir: str = "results/model_training"):
        self.output_dir = os.path.abspath(os.path.normpath(output_dir))
        os.makedirs(self.output_dir, exist_ok=True)

    def preprocess_uploaded_data(self, file_content: str, seed: int = 42) -> Dict:
        data = []
        for line in file_content.strip().split('\n'):
            line = line.strip()
            if line:
                item = json.loads(line)
                data.append(item)

        if not data:
            return {'success': False, 'message': 'Empty data'}

        data = preprocess_data(data, seed)
        train_data, val_data, test_data = split_data(data, 0.7, 0.2)

        stats = {
            'total': len(data),
            'train': len(train_data),
            'val': len(val_data),
            'test': len(test_data),
            'human_count': sum(1 for item in data if item.get('label') == 0),
            'agent_count': sum(1 for item in data if item.get('label') == 1)
        }

        return {
            'success': True,
            'train_data': train_data,
            'val_data': val_data,
            'test_data': test_data,
            'stats': stats
        }

    def run_training(self, task_id: str, train_data: List[Dict], val_data: List[Dict],
                     test_data: List[Dict], model_type: str, progress_callback: Callable,
                     params: Optional[Dict] = None):
        if params is None:
            params = {}

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = TeeStream(old_stdout, progress_callback)
        sys.stderr = TeeStream(old_stderr, progress_callback)

        try:
            if model_type == 'modernbert':
                self._run_modernbert(task_id, train_data, val_data, test_data, progress_callback, params)
            elif model_type == 'gptsniffer':
                self._run_gptsniffer(task_id, train_data, val_data, test_data, progress_callback, params)
            else:
                raise ValueError(f"Unknown model type: {model_type}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _run_modernbert(self, task_id: str, train_data: List[Dict], val_data: List[Dict],
                        test_data: List[Dict], progress_callback: Callable, params: Dict):

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        progress_callback('status', f'Using device: {device}')

        seed = params.get('seed', 42)
        torch.manual_seed(seed)
        np.random.seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        model_name = params.get('model_name', 'answerdotai/ModernBERT-base')
        max_length = params.get('max_length', 512)
        batch_size = params.get('batch_size', 64)
        learning_rate = params.get('learning_rate', 5e-5)
        epochs = params.get('epochs', 3)

        progress_callback('status', 'Loading tokenizer and model...')
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        class CodeDataset(Dataset):
            def __init__(self, data, tokenizer, max_length=512, split_type='train'):
                self.tokenizer = tokenizer
                self.max_length = max_length
                self.samples = []
                self.ids = []
                for item in data:
                    code = item['code']
                    label = item.get('label')
                    item_id = item.get('id')
                    if label is not None:
                        label = int(label)
                    self.samples.append((code, label))
                    self.ids.append(item_id)

            def __len__(self):
                return len(self.samples)

            def __getitem__(self, idx):
                code, label = self.samples[idx]
                item_id = self.ids[idx]
                encoding = self.tokenizer(
                    code, max_length=self.max_length, padding='max_length',
                    truncation=True, return_tensors='pt'
                )
                item = {
                    'input_ids': encoding['input_ids'].squeeze(0),
                    'attention_mask': encoding['attention_mask'].squeeze(0),
                    'id': item_id
                }
                if label is not None:
                    item['labels'] = torch.tensor(label, dtype=torch.long)
                return item

        train_dataset = CodeDataset(train_data, tokenizer, max_length, 'train')
        val_dataset = CodeDataset(val_data, tokenizer, max_length, 'val')
        test_dataset = CodeDataset(test_data, tokenizer, max_length, 'test')

        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_dataloader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

        try:
            config = AutoConfig.from_pretrained(model_name)
            bert = AutoModel.from_pretrained(model_name, use_safetensors=True)
        except (OSError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise RuntimeError(
                f'Failed to download model {model_name}: Cannot connect to Hugging Face Hub. '
                f'Please check your network connection or configure a proxy and try again. '
                f'Original error: {e}'
            )
        dropout = nn.Dropout(params.get('dropout_rate', 0.1))
        classifier = nn.Linear(config.hidden_size, 2)

        class ModernBERTClassifier(nn.Module):
            def __init__(self):
                super().__init__()
                self.bert = bert
                self.dropout = dropout
                self.classifier = classifier

            def forward(self, input_ids, attention_mask, labels=None):
                outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
                pooled = outputs.last_hidden_state[:, 0, :]
                pooled = self.dropout(pooled)
                logits = self.classifier(pooled)
                loss = None
                if labels is not None:
                    loss_fct = nn.CrossEntropyLoss()
                    loss = loss_fct(logits, labels)
                return {'loss': loss, 'logits': logits}

        model = ModernBERTClassifier().to(device)
        optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=params.get('weight_decay', 0.01))

        total_steps = len(train_dataloader) * epochs
        warmup_steps = int(total_steps * params.get('warmup_ratio', 0.1))

        def lr_lambda(current_step):
            if current_step < warmup_steps:
                return float(current_step) / float(max(1, warmup_steps))
            progress = (current_step - warmup_steps) / (total_steps - warmup_steps)
            return max(0.0, 0.5 * (1.0 + np.cos(np.pi * progress)))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

        progress_callback('status', f'Starting ModernBERT training for {epochs} epochs...')
        progress_callback('max_epochs', epochs)
        progress_callback('current_epoch', 0)

        best_f1 = 0.0
        global_step = 0

        for epoch in range(epochs):
            if self._is_cancelled(task_id):
                progress_callback('status', 'Training cancelled by user')
                return

            progress_callback('current_epoch', epoch + 1)
            progress_callback('status', f'Epoch {epoch + 1}/{epochs} - Training...')

            model.train()
            total_loss = 0
            total_batches = len(train_dataloader)
            progress_callback('total_batches', total_batches)
            for batch_idx, batch in enumerate(train_dataloader):
                if self._is_cancelled(task_id):
                    return
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)
                optimizer.zero_grad()
                outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
                loss = outputs['loss']
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                total_loss += loss.item()
                global_step += 1
                progress_callback('current_batch', batch_idx + 1)
                progress_callback('batch_loss', round(loss.item(), 4))

            avg_train_loss = total_loss / len(train_dataloader)

            model.eval()
            val_loss = 0
            all_preds = []
            all_labels = []
            val_total_batches = len(val_dataloader)
            progress_callback('status', f'Epoch {epoch + 1}/{epochs} - Validating...')
            progress_callback('total_batches', val_total_batches)
            progress_callback('current_batch', 0)
            with torch.no_grad():
                for val_batch_idx, batch in enumerate(val_dataloader):
                    input_ids = batch['input_ids'].to(device)
                    attention_mask = batch['attention_mask'].to(device)
                    labels = batch['labels'].to(device)
                    outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
                    val_loss += outputs['loss'].item()
                    preds = torch.argmax(outputs['logits'], dim=-1)
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(labels.cpu().numpy())
                    progress_callback('current_batch', val_batch_idx + 1)

            avg_val_loss = val_loss / len(val_dataloader)
            val_f1 = f1_score(all_labels, all_preds, average='weighted')
            val_recall = recall_score(all_labels, all_preds, average='weighted')
            val_acc = accuracy_score(all_labels, all_preds)

            if val_f1 > best_f1:
                best_f1 = val_f1

            progress_callback('epoch_metrics', {
                'epoch': epoch + 1,
                'train_loss': round(avg_train_loss, 4),
                'val_loss': round(avg_val_loss, 4),
                'val_f1': round(val_f1, 4),
                'val_recall': round(val_recall, 4),
                'val_accuracy': round(val_acc, 4)
            })

        progress_callback('status', 'Evaluating on test set...')
        model.eval()
        test_loss = 0
        all_test_preds = []
        all_test_labels = []
        all_test_ids = []
        all_test_logits = []
        test_total_batches = len(test_dataloader)
        progress_callback('total_batches', test_total_batches)
        progress_callback('current_batch', 0)

        with torch.no_grad():
            for test_batch_idx, batch in enumerate(test_dataloader):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)
                ids = batch['id']
                outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
                test_loss += outputs['loss'].item()
                all_test_preds.extend(torch.argmax(outputs['logits'], dim=-1).cpu().numpy())
                all_test_labels.extend(labels.cpu().numpy())
                all_test_ids.extend(ids.tolist())
                all_test_logits.append(outputs['logits'].cpu())
                progress_callback('current_batch', test_batch_idx + 1)

        avg_test_loss = test_loss / len(test_dataloader)
        test_f1 = f1_score(all_test_labels, all_test_preds, average='weighted')
        test_recall = recall_score(all_test_labels, all_test_preds, average='weighted')
        test_acc = accuracy_score(all_test_labels, all_test_preds)

        progress_callback('test_metrics', {
            'test_loss': round(avg_test_loss, 4),
            'test_f1': round(test_f1, 4),
            'test_recall': round(test_recall, 4),
            'test_accuracy': round(test_acc, 4)
        })

        all_test_logits = torch.cat(all_test_logits, dim=0)
        all_test_labels_tensor = torch.tensor(all_test_labels)
        all_test_ids_tensor = torch.tensor(all_test_ids)

        predictions = format_predictions_unified(
            all_test_ids_tensor, all_test_logits, all_test_labels_tensor, 'modernbert'
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(self.output_dir, f"modernbert_{timestamp}")
        os.makedirs(result_dir, exist_ok=True)

        csv_path = os.path.join(result_dir, 'predictions.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'predicted_probability', 'target_label'])
            writer.writeheader()
            writer.writerows(predictions)

        progress_callback('predictions', predictions)
        progress_callback('result_dir', result_dir)
        progress_callback('status', 'ModernBERT training completed!')

    def _run_gptsniffer(self, task_id: str, train_data: List[Dict], val_data: List[Dict],
                        test_data: List[Dict], progress_callback: Callable, params: Dict):

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        progress_callback('status', f'Using device: {device}')

        seed = params.get('seed', 42)
        torch.manual_seed(seed)
        np.random.seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        model_name = params.get('model_name', 'microsoft/codebert-base')
        max_length = params.get('max_length', 512)
        batch_size = params.get('batch_size', 32)
        learning_rate = params.get('learning_rate', 5e-5)
        epochs = params.get('epochs', 12)

        progress_callback('status', 'Loading tokenizer and model...')
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name, use_safetensors=True).to(device)
        except (OSError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise RuntimeError(
                f'Failed to download model {model_name}: Cannot connect to Hugging Face Hub. '
                f'Please check your network connection or configure a proxy and try again. '
                f'Original error: {e}'
            )

        class UnifiedCodeDataset(Dataset):
            def __init__(self, data, tokenizer, max_length=512, split_type='train'):
                self.tokenizer = tokenizer
                self.max_length = max_length
                self.samples = []
                self.ids = []
                for item in data:
                    code = item['code']
                    label = item.get('label')
                    item_id = item.get('id')
                    if label is not None:
                        label = int(label)
                    self.samples.append((code, label))
                    self.ids.append(item_id)

            def __len__(self):
                return len(self.samples)

            def __getitem__(self, idx):
                code, label = self.samples[idx]
                item_id = self.ids[idx]
                inputs = self.tokenizer(
                    code, padding='max_length', max_length=self.max_length,
                    truncation=True, return_tensors='pt'
                )
                item = {
                    'input_ids': inputs['input_ids'].squeeze(0),
                    'attention_mask': inputs['attention_mask'].squeeze(0),
                    'id': item_id
                }
                if label is not None:
                    item['labels'] = torch.tensor(label, dtype=torch.long)
                return item

        train_dataset = UnifiedCodeDataset(train_data, tokenizer, max_length, 'train')
        val_dataset = UnifiedCodeDataset(val_data, tokenizer, max_length, 'val')
        test_dataset = UnifiedCodeDataset(test_data, tokenizer, max_length, 'test')

        def compute_metrics(eval_pred):
            predictions, labels = eval_pred
            predictions = np.argmax(predictions, axis=1)
            return {
                'weighted_f1': f1_score(labels, predictions, average='weighted'),
                'macro_f1': f1_score(labels, predictions, average='macro'),
                'precision': precision_score(labels, predictions, average='weighted'),
                'recall': recall_score(labels, predictions, average='weighted'),
                'accuracy': accuracy_score(labels, predictions)
            }

        training_args = TrainingArguments(
            output_dir=os.path.join(self.output_dir, f"gptsniffer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            logging_steps=10,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model='weighted_f1',
            greater_is_better=True,
            disable_tqdm=False,
            dataloader_pin_memory=torch.cuda.is_available()
        )

        progress_callback('status', f'Starting GPTSniffer (CodeBERT) training for {epochs} epochs...')
        progress_callback('max_epochs', epochs)
        progress_callback('current_epoch', 0)
        progress_callback('log', f'Using device: {device}')
        progress_callback('log', f'Model: {model_name}')
        progress_callback('log', f'Max sequence length: {max_length}')
        progress_callback('log', f'Batch size: {batch_size}')
        progress_callback('log', f'Learning rate: {learning_rate}')
        progress_callback('log', f'Epochs: {epochs}')

        class CallbackTrainer(Trainer):
            def __init__(self, task_id, service, progress_callback, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._task_id = task_id
                self._service = service
                self._progress_callback = progress_callback
                self._current_epoch = 0

            def train(self, *args, **kwargs):
                return super().train(*args, **kwargs)

        trainer = CallbackTrainer(
            task_id=task_id,
            service=self,
            progress_callback=progress_callback,
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3, early_stopping_threshold=0.001)]
        )

        original_log = trainer.log
        def patched_log(*args):
            logs = args[0] if args else {}
            if self._is_cancelled(task_id):
                raise RuntimeError("Training cancelled")
            if 'loss' in logs:
                progress_callback('log', str(logs))
            if 'eval_weighted_f1' in logs:
                progress_callback('epoch_metrics', {
                    'epoch': int(logs.get('epoch', 0)),
                    'val_f1': round(logs.get('eval_weighted_f1', 0), 4),
                    'val_recall': round(logs.get('eval_recall', 0), 4),
                    'val_accuracy': round(logs.get('eval_accuracy', 0), 4),
                    'val_loss': round(logs.get('eval_loss', 0), 4)
                })
                progress_callback('current_epoch', int(logs.get('epoch', 0)))
            original_log(*args)
        trainer.log = patched_log

        try:
            trainer.train()
        except RuntimeError as e:
            if "cancelled" in str(e):
                progress_callback('status', 'Training cancelled by user')
                return
            raise

        progress_callback('status', 'Evaluating on test set...')

        test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        model.eval()
        all_outputs = []
        all_labels = []
        all_ids = []
        test_total_batches = len(test_dataloader)
        progress_callback('total_batches', test_total_batches)
        progress_callback('current_batch', 0)

        with torch.no_grad():
            for test_batch_idx, batch in enumerate(test_dataloader):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)
                ids = batch['id']
                outputs = model(input_ids, attention_mask=attention_mask)
                all_outputs.append(outputs.logits.cpu())
                all_labels.extend(labels.cpu().numpy())
                all_ids.extend(ids.tolist())
                progress_callback('current_batch', test_batch_idx + 1)

        all_outputs = torch.cat(all_outputs, dim=0)
        all_labels_tensor = torch.tensor(all_labels)
        all_ids_tensor = torch.tensor(all_ids)

        predictions = format_predictions_unified(all_ids_tensor, all_outputs, all_labels_tensor, 'gptsniffer')

        test_preds = np.argmax(all_outputs.numpy(), axis=1)
        test_f1 = f1_score(all_labels, test_preds, average='weighted')
        test_recall = recall_score(all_labels, test_preds, average='weighted')
        test_acc = accuracy_score(all_labels, test_preds)
        test_loss = nn.CrossEntropyLoss()(all_outputs, all_labels_tensor).item()

        progress_callback('test_metrics', {
            'test_loss': round(test_loss, 4),
            'test_f1': round(test_f1, 4),
            'test_recall': round(test_recall, 4),
            'test_accuracy': round(test_acc, 4)
        })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(self.output_dir, f"gptsniffer_{timestamp}")
        os.makedirs(result_dir, exist_ok=True)

        csv_path = os.path.join(result_dir, 'predictions.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'predicted_probability', 'target_label'])
            writer.writeheader()
            writer.writerows(predictions)

        progress_callback('predictions', predictions)
        progress_callback('result_dir', result_dir)
        progress_callback('status', 'GPTSniffer training completed!')

    def _is_cancelled(self, task_id: str) -> bool:
        with TRAINING_STATUS_LOCK:
            status = TRAINING_STATUS.get(task_id, {})
            return status.get('cancelled', False)

    @staticmethod
    def cancel_training(task_id: str):
        with TRAINING_STATUS_LOCK:
            if task_id in TRAINING_STATUS:
                TRAINING_STATUS[task_id]['cancelled'] = True

    @staticmethod
    def init_task(task_id: str):
        with TRAINING_STATUS_LOCK:
            TRAINING_STATUS[task_id] = {'cancelled': False}

    @staticmethod
    def cleanup_task(task_id: str):
        with TRAINING_STATUS_LOCK:
            if task_id in TRAINING_STATUS:
                del TRAINING_STATUS[task_id]