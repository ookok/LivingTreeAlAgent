"""CellAI — Trainable AI cell with LoRA adapters and genome integration."""
from __future__ import annotations
import json, os, uuid, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field
from ..dna.genome import Genome

try:
    import torch
except ImportError:
    torch = None

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model, PeftModel  # noqa: F401
except ImportError:
    AutoModelForCausalLM = AutoTokenizer = Trainer = TrainingArguments = None
    LoraConfig = get_peft_model = PeftModel = None

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
        if torch is None or AutoModelForCausalLM is None:
            return {"status": "skipped", "reason": "torch/peft not installed"}
        logger.info(f"Training cell {self.name} with {len(data)} samples, {epochs} epochs")

        texts = [d.get("text", json.dumps(d)) for d in data]
        if not texts:
            return {"status": "skipped", "reason": "no training data"}

        os.makedirs(str(self.checkpoint_dir), exist_ok=True)

        # Tokenize
        encoded = self._tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
        input_ids = encoded.input_ids

        # Optimizer + scheduler
        optimizer = torch.optim.AdamW(self._model.parameters(), lr=kwargs.get("lr", 5e-5))
        batch_size = min(kwargs.get("batch_size", 4), len(input_ids))
        total_loss = 0.0
        steps = 0

        self._model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for i in range(0, len(input_ids), batch_size):
                batch = input_ids[i:i + batch_size]
                optimizer.zero_grad()
                outputs = self._model(batch, labels=batch)
                loss = outputs.loss
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                steps += 1
            total_loss += epoch_loss
            avg_loss = epoch_loss / max((len(input_ids) // batch_size), 1)
            logger.debug(f"  Epoch {epoch+1}/{epochs}: loss={avg_loss:.4f}")

        avg_total_loss = total_loss / max(steps, 1)
        self.genome.add_mutation(
            f"Trained on {len(data)} samples, {epochs} epochs, loss={avg_total_loss:.4f}",
            source="cell_trainer",
        )

        # Save checkpoint
        try:
            ckpt_path = self.checkpoint_dir / f"{self.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self._model.save_pretrained(str(ckpt_path))
            self._tokenizer.save_pretrained(str(ckpt_path))
        except Exception:
            ckpt_path = None

        return {
            "status": "completed", "epochs": epochs, "samples": len(data),
            "loss": round(avg_total_loss, 4), "steps": steps,
            "checkpoint": str(ckpt_path) if ckpt_path else "",
        }

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
