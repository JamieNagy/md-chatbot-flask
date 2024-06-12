import torch
from trl import SFTTrainer
from peft import LoraConfig
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    pipeline,
)
from flask import Flask, request, jsonify
from pyngrok import ngrok

# Install dependencies
import os

os.system(
    "pip install -q accelerate==0.21.0 peft==0.4.0 bitsandbytes==0.40.2 transformers==4.31.0 trl==0.4.7"
)
os.system("export LC_ALL=C.UTF-8")
os.system("export LANG=C.UTF-8")
os.system("pip install flask pyngrok")
os.system("pip install huggingface_hub")

# Load model and tokenizer
llama_model = AutoModelForCausalLM.from_pretrained(
    pretrained_model_name_or_path="aboonaji/llama2finetune-v2",
    quantization_config=BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=getattr(torch, "float16"),
        bnb_4bit_quant_type="nf4",
    ),
)
llama_model.config.use_cache = False
llama_model.config.pretraining_tp = 1

llama_tokenizer = AutoTokenizer.from_pretrained(
    pretrained_model_name_or_path="aboonaji/llama2finetune-v2", trust_remote_code=True
)
llama_tokenizer.pad_token = llama_tokenizer.eos_token
llama_tokenizer.padding_side = "right"

training_arguments = TrainingArguments(
    output_dir="./results", per_device_train_batch_size=4, max_steps=100
)

llama_sft_trainer = SFTTrainer(
    model=llama_model,
    args=training_arguments,
    train_dataset=load_dataset(
        path="aboonaji/wiki_medical_terms_llam2_format", split="train"
    ),
    tokenizer=llama_tokenizer,
    peft_config=LoraConfig(
        task_type="CAUSAL_LM", r=64, lora_alpha=16, lora_dropout=0.1
    ),
    dataset_text_field="text",
)

llama_sft_trainer.train()


def get_answer(question):
    user_prompt = question
    text_generation_pipeline = pipeline(
        task="text-generation",
        model=llama_model,
        tokenizer=llama_tokenizer,
        max_length=300,
    )
    model_answer = text_generation_pipeline(f"<s>[INST] {user_prompt} [/INST]")
    return model_answer[0]["generated_text"]


app = Flask(__name__)


@app.route("/process", methods=["POST"])
def process():
    data = request.json.get("data")
    result = get_answer(data)
    return jsonify({"result": result})


if __name__ == "__main__":
    public_url = ngrok.connect(port=5000)
    print(f"Public URL: {public_url}")
    app.run(port=5000)