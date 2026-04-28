"""
Test script to verify data loading works correctly
"""
import os
import torch

# Construct path to table_cell data
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'data', 'table_cell')
data_dir = os.path.abspath(data_dir)

print(f"Looking for data in: {data_dir}")

train_path = os.path.join(data_dir, 'train.bin')
val_path = os.path.join(data_dir, 'val.bin')

print(f"\nTrain path: {train_path}")
print(f"Val path: {val_path}")

print(f"\nTrain file exists: {os.path.exists(train_path)}")
print(f"Val file exists: {os.path.exists(val_path)}")

if os.path.exists(train_path):
    file_size = os.path.getsize(train_path)
    print(f"Train file size: {file_size} bytes")
    print(f"Expected number of tokens: {file_size // 2} (uint16)")

    train_data = torch.from_file(train_path, dtype=torch.long)
    print(f"\nTrain data loaded successfully!")
    print(f"Train data shape: {train_data.shape}")
    print(f"Train data dtype: {train_data.dtype}")
    print(f"First 20 values: {train_data[:20]}")

if os.path.exists(val_path):
    file_size = os.path.getsize(val_path)
    print(f"\nVal file size: {file_size} bytes")
    print(f"Expected number of tokens: {file_size // 2} (uint16)")

    val_data = torch.from_file(val_path, dtype=torch.long)
    print(f"\nVal data loaded successfully!")
    print(f"Val data shape: {val_data.shape}")
    print(f"Val data dtype: {val_data.dtype}")
    print(f"First 20 values: {val_data[:20]}")
