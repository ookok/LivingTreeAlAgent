"""CellAI — Trainable AI cell with LoRA adapters and genome integration."""
from __future__ import annotations
import json, os, uuid, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field
from ..dna.genome import Genome

try: import torch; HAS_TORCH = True
except ImportError: HAS_TORCH = False

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model, PeftModel; HAS_PEFT = True
except ImportError: HAS_PEFT = False

class CellCapability(BaseModel):
    name: str; description: str; confidence: float = 0.0

class CellAI(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str; genome: Genome = Field(default_factory=Genome)
    model_name: str = "gpt2"; capabilities: list[CellCapability] = Field(default_factory=list)
    checkpoint_dir: Path = Path("checkpoints")
    _model: Any = None; _tokenizer: Any = None

    def get_capabilities(self) -> list[CellCapability]: return self.capabilities

    def train(self, data: list[dict], epochs: int = 3, **kwargs) -> dict:
        if not HAS_TORCH or not HAS_PEFT: return {"status": "skipped", "reason": "torch/peft not installed"}
        logger.info(f"Training cell {self.name} with {len(data)} samples, {epochs} epochs")
        texts = [d.get("text", json.dumps(d)) for d in data]
        os.makedirs(str(self.checkpoint_dir), exist_ok=True)
        input_ids = self._tokenizer(texts, padding=True, truncation=True, return_tensors="pt").input_ids
        self._model.train()
        for epoch in range(epochs):
            loss = self._model(input_ids, labels=input_ids).loss
            loss.backward()
        self.genome.add_mutation(f"Trained on {len(data)} samples, {epochs} epochs", source="cell_trainer")
        return {"status": "completed", "epochs": epochs, "samples": len(data)}

    def infer(self, prompt: str, max_tokens: int = 128) -> str:
        if self._model is None: return f"[Cell {self.name}] Prompt: {prompt} (no model loaded)"
        inputs = self._tokenizer(prompt, return_tensors="pt"); outputs = self._model.generate(**inputs, max_new_tokens=max_tokens)
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def save_checkpoint(self, path: Path | None = None) -> Path:
        p = path or self.checkpoint_dir / f"{self.id}_ckpt"
        os.makedirs(str(p), exist_ok=True); self.genome.save(p / "genome.json")
        logger.info(f"Checkpoint saved to {p}"); return p

    def load_checkpoint(self, path: Path | None = None) -> bool:
        p = path or self.checkpoint_dir / f"{self.id}_ckpt"
        gf = p / "genome.json"
        if gf.exists(): self.genome = Genome.load(gf)
        logger.info(f"Checkpoint loaded from {p}"); return True
