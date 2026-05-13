"""
CYPHEX — Fine-Tuning Script for qwen2.5-coder:7b

Uses QLoRA (4-bit) to fine-tune on cybersecurity patching data.
Requires: RTX 3050 6GB (fits comfortably in 4-bit)

Usage: python finetune/train.py
"""

import os
import json
import sys

def check_dependencies():
    """Check if fine-tuning dependencies are installed."""
    missing = []
    try:
        import torch
        if not torch.cuda.is_available():
            print("WARNING: CUDA not available. Training will use CPU (very slow).")
            print("Make sure you have CUDA-enabled PyTorch installed:")
            print("  pip install torch --index-url https://download.pytorch.org/whl/cu121")
    except ImportError:
        missing.append("torch")

    try:
        import transformers
    except ImportError:
        missing.append("transformers")

    try:
        import peft
    except ImportError:
        missing.append("peft")

    try:
        import trl
    except ImportError:
        missing.append("trl")

    try:
        import datasets
    except ImportError:
        missing.append("datasets")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        print("\nFor full setup, run:")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu121")
        print("  pip install transformers peft trl datasets bitsandbytes accelerate")
        sys.exit(1)


def load_training_data(filepath: str):
    """Load JSONL training data."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    print(f"Loaded {len(data)} training examples")
    return data


def train():
    """Run QLoRA fine-tuning."""
    check_dependencies()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset

    # Paths
    base_model = "Qwen/Qwen2.5-Coder-7B-Instruct"
    training_file = os.path.join(os.path.dirname(__file__), "..", "cyphex_training_data.jsonl")
    output_dir = os.path.join(os.path.dirname(__file__), "cyphex-adapter")
    merged_dir = os.path.join(os.path.dirname(__file__), "cyphex-merged")

    print(f"\n{'='*60}")
    print(f"  CYPHEX Fine-Tuning: {base_model}")
    print(f"  Training data: {training_file}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    # Check GPU
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_mem / 1024**3
        print(f"GPU: {gpu_name} ({vram:.1f} GB VRAM)")
    else:
        print("WARNING: No GPU detected. Training will be extremely slow.")

    # Load training data
    raw_data = load_training_data(training_file)

    # Convert to conversation format
    def format_example(example):
        messages = example["messages"]
        text = ""
        for msg in messages:
            if msg["role"] == "system":
                text += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "user":
                text += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "assistant":
                text += f"<|im_start|>assistant\n{msg['content']}<|im_end|>\n"
        return {"text": text}

    formatted = [format_example(d) for d in raw_data]
    dataset = Dataset.from_list(formatted)
    print(f"Dataset prepared: {len(dataset)} examples")

    # Load model in 4-bit (QLoRA)
    print("\nLoading base model (4-bit quantized)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Prepare for training
    model = prepare_model_for_kbit_training(model)

    # LoRA configuration
    lora_config = LoraConfig(
        r=16,                    # Rank (higher = more capacity, more VRAM)
        lora_alpha=32,           # Scaling factor
        target_modules=[         # Which layers to adapt
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)

    # Print trainable parameters
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Trainable parameters: {trainable_params:,} / {total_params:,} ({100 * trainable_params / total_params:.2f}%)")

    # Training configuration
    training_config = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=1,   # Small batch for 6GB VRAM
        gradient_accumulation_steps=4,    # Effective batch = 4
        learning_rate=2e-4,
        weight_decay=0.01,
        warmup_steps=5,
        logging_steps=5,
        save_steps=50,
        fp16=True,
        max_seq_length=2048,
        dataset_text_field="text",
        gradient_checkpointing=True,      # Save VRAM
    )

    # Train
    print("\nTraining with QLoRA...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_config,
        tokenizer=tokenizer,
    )

    trainer.train()

    # Save LoRA adapter
    print(f"\nSaving LoRA adapter to {output_dir}/")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Merge adapter into base model
    print(f"Merging adapter into base model...")
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)
    print(f"Merged model saved to {merged_dir}/")

    print(f"\n{'='*60}")
    print(f"  ✅ FINE-TUNING COMPLETE!")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Convert to GGUF: python -m llama_cpp.convert {merged_dir}")
    print(f"  2. Import to Ollama: ollama create cyphex-patch -f finetune/Modelfile")
    print(f"  3. Update config.py: OLLAMA_MODEL = 'cyphex-patch'")
    print(f"  4. Run CYPHEX with your custom model!")


if __name__ == "__main__":
    train()
