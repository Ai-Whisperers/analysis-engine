"""
Setup script to prepare ONNX INT8 sentiment model.

Run this once during initial setup:
    python -m layers.sentiment-analyzer.setup_model
"""

from .analyzer import SentimentAnalyzer

if __name__ == "__main__":
    print("Preparing ONNX INT8 sentiment model...")
    print("This will:")
    print("  1. Download HuggingFace model (distilbert-sst-2)")
    print("  2. Convert to ONNX format")
    print("  3. Quantize to INT8 (4x faster, 75% smaller)")
    print()

    try:
        model_path, tokenizer_name = SentimentAnalyzer.prepare_model()

        print()
        print("✓ Model preparation completed!")
        print(f"  Model path: {model_path}")
        print(f"  Tokenizer: {tokenizer_name}")
        print()
        print("You can now use the analyzer:")
        print(f'  analyzer = SentimentAnalyzer("{model_path}", "{tokenizer_name}")')

    except Exception as e:
        print(f"\n✗ Model preparation failed: {e}")
        raise
