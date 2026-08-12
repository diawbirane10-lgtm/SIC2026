from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

DEFAULT_MODEL = "Qwen/Qwen3-0.6B"
SYSTEM = (
    "Tu es le copilote opérateur de FLOWTRUST-AFR. Tu n'inventes jamais une mesure, un diagnostic, "
    "une consigne machine ou une procédure de sécurité. Tu expliques uniquement les preuves fournies, "
    "tu choisis parmi les outils autorisés et tu proposes des vérifications non intrusives. "
    "Aucune écriture PLC/SCADA ni commande d'actionneur n'est autorisée."
)


class JsonlSFTDataset(Dataset):
    def __init__(self, path: Path, tokenizer, max_length: int):
        self.rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        user = json.dumps(row["input"], ensure_ascii=False, sort_keys=True)
        assistant = row["output"]
        prompt_messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ]
        full_messages = prompt_messages + [{"role": "assistant", "content": assistant}]

        prompt_text = self.tokenizer.apply_chat_template(
            prompt_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        full_text = self.tokenizer.apply_chat_template(
            full_messages, tokenize=False, add_generation_prompt=False, enable_thinking=False
        )
        prompt_ids = self.tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        encoded = self.tokenizer(
            full_text,
            add_special_tokens=False,
            truncation=True,
            max_length=self.max_length,
        )
        input_ids = encoded["input_ids"]
        labels = input_ids.copy()
        cutoff = min(len(prompt_ids), len(labels))
        labels[:cutoff] = [-100] * cutoff
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}


@dataclass
class CausalCollator:
    tokenizer: object

    def __call__(self, features):
        max_len = max(len(x["input_ids"]) for x in features)
        pad_id = self.tokenizer.pad_token_id
        input_ids, attention_mask, labels = [], [], []
        for x in features:
            n = max_len - len(x["input_ids"])
            input_ids.append(x["input_ids"] + [pad_id] * n)
            attention_mask.append(x["attention_mask"] + [0] * n)
            labels.append(x["labels"] + [-100] * n)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--validation", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/operator_copilot"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("T01-E LoRA is configured for CUDA. Do not report fine-tuning as completed on CPU.")

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype, device_map="auto")
    model.config.use_cache = False

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    trainable, total = model.get_nb_trainable_parameters()
    print(f"Qwen foundation parameters: {total:,}; trainable LoRA parameters: {trainable:,}")

    train_ds = JsonlSFTDataset(args.train, tokenizer, args.max_length)
    val_ds = JsonlSFTDataset(args.validation, tokenizer, args.max_length)
    args.outdir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(args.outdir / "trainer"),
        max_steps=args.steps,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        logging_steps=20,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        gradient_checkpointing=True,
        report_to="none",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=2026,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=CausalCollator(tokenizer),
    )
    trainer.train()
    model.save_pretrained(args.outdir / "adapter")
    tokenizer.save_pretrained(args.outdir / "adapter")

    metadata = {
        "run_id": "FLOWTRUST-V2-T01-E-20260812",
        "foundation": args.model,
        "foundation_parameters": int(total),
        "trainable_adapter_parameters": int(trainable),
        "safety_policy": "read_only_evidence_grounded_operator_copilot",
        "training_rows": len(train_ds),
        "validation_rows": len(val_ds),
    }
    (args.outdir / "training_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
