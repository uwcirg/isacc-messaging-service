import torch
from transformers import AutoTokenizer
import pandas as pd
from torch.utils.data import TensorDataset
from torch.utils.data import SequentialSampler, DataLoader
from scipy.special import expit as sigmoid
import numpy as np


def predict_score(message, model_path):
    if torch.cuda.is_available():
        model = torch.load(model_path)
    else:
        model = torch.load(model_path, map_location=torch.device('cpu'))

    dl = get_dataloader([message])

    result = predict(model, dl)
    return np.argmax(result[0])

def encode_sentences(sentences, labels, tokenizer):
    input_ids = []
    input_labels = []
    attention_masks = []

    for i, sentence in enumerate(sentences):
        encoded_dict = tokenizer.encode_plus(
            sentence,
            add_special_tokens=True,
            max_length=512,
            padding='max_length',
            return_tensors='pt',
            return_attention_mask=True,
            truncation=True
        )

        input_ids.append(encoded_dict['input_ids'])
        attention_masks.append(encoded_dict['attention_mask'])
        input_labels.append(labels[i])

    input_ids = torch.cat(input_ids, dim=0)
    attention_masks = torch.cat(attention_masks, dim=0)
    labels = torch.tensor(labels)

    # Combine the training inputs into a TensorDataset.
    return TensorDataset(input_ids, attention_masks, labels.float())

def encode_labels(labels: pd.Series):
    return pd.get_dummies(labels).values

def get_dataloader(test_sentences):
    tokenizer = AutoTokenizer.from_pretrained("publichealthsurveillance/PHS-BERT", do_lower_case=True)
    test_labels = [0] * len(test_sentences)
    labels = encode_labels(test_labels)
    test_dataset = encode_sentences(test_sentences, labels, tokenizer)
    sampler = SequentialSampler(test_dataset)
    test_dataloader = DataLoader(test_dataset, sampler=sampler, batch_size=8)
    return test_dataloader

def predict(model, dataloader):
    device = get_device()
    print(f'Predicting labels for {len(dataloader.dataset)} documents...')
    model.eval()
    predictions = []
    for batch in dataloader:
        batch = tuple(t.to(device) for t in batch)
        batch_input_ids, batch_input_mask, batch_labels = batch
        with torch.no_grad():
            outputs = model(batch_input_ids, token_type_ids=None,
                            attention_mask=batch_input_mask)
            logits = outputs[0]
            logits = logits.detach().cpu().numpy()
            predictions = predictions + list(logits)
    print('DONE.')
    return sigmoid(predictions)

def get_device(index=0):
    if torch.cuda.is_available() and ('USE_CPU' not in os.environ or not os.environ['USE_CPU']):
        # Tell PyTorch to use the GPU.
        print('There are %d GPU(s) available.' % torch.cuda.device_count())
        print('We will use the GPU:', torch.cuda.get_device_name(index), "at index:", index)
        return torch.device(index)
    else:
        print('No GPU available, using the CPU instead.')
        return torch.device("cpu")