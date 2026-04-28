"""
Prepare the table_cell dataset for character-level language modeling.
Process EIA (Environmental Impact Assessment) table data with special tokens.
"""
import os
import pickle
import numpy as np

# Read the input file
input_file_path = os.path.join(os.path.dirname(__file__), 'raw', 'table_cell_input.txt')

with open(input_file_path, 'r', encoding='utf-8') as f:
    data = f.read()

print(f"Length of dataset in characters: {len(data):,}")

# Get all the unique characters that occur in this text
chars = sorted(list(set(data)))
vocab_size = len(chars)
print("All the unique characters:", ''.join(chars))
print(f"Vocab size: {vocab_size:,}")

# Create a mapping from characters to integers
stoi = {ch: i for i, ch in enumerate(chars)}
itos = {i: ch for i, ch in enumerate(chars)}

def encode(s):
    return [stoi[c] for c in s]  # encoder: take a string, output a list of integers

def decode(l):
    return ''.join([itos[i] for i in l])  # decoder: take a list of integers, output a string

# Create the train and validation splits
n = len(data)
train_data = data[:int(n * 0.9)]
val_data = data[int(n * 0.9):]

# Encode both to integers
train_ids = encode(train_data)
val_ids = encode(val_data)
print(f"Train has {len(train_ids):,} tokens")
print(f"Val has {len(val_ids):,} tokens")

# Export to bin files
train_ids = np.array(train_ids, dtype=np.uint16)
val_ids = np.array(val_ids, dtype=np.uint16)

# Save to table_cell directory
output_dir = os.path.join(os.path.dirname(__file__), 'table_cell')
os.makedirs(output_dir, exist_ok=True)

train_bin_path = os.path.join(output_dir, 'train.bin')
val_bin_path = os.path.join(output_dir, 'val.bin')
train_ids.tofile(train_bin_path)
val_ids.tofile(val_bin_path)

# Save the meta information as well, to help us encode/decode later
meta = {
    'vocab_size': vocab_size,
    'itos': itos,
    'stoi': stoi,
}
meta_path = os.path.join(output_dir, 'meta.pkl')
with open(meta_path, 'wb') as f:
    pickle.dump(meta, f)

print(f"\nData preparation complete!")
print(f"Train data saved to: {train_bin_path}")
print(f"Val data saved to: {val_bin_path}")
print(f"Meta data saved to: {meta_path}")
print(f"Vocab size: {vocab_size}")
print(f"Special tokens found: <project_name>, <location>, <pollutant>, <standard>, <monitoring_point>, <sensitive_target>")
