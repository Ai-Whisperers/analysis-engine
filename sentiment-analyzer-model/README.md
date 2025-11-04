# Sentiment Analyzer Model

This directory should contain the ONNX INT8 quantized sentiment model.

## Setup

Run the setup script to download and prepare the model:

```bash
python -m layers.sentiment_analyzer.setup_model
```

This will:
1. Download the HuggingFace model (distilbert-sst-2)
2. Convert to ONNX format
3. Quantize to INT8 (4x faster, 75% smaller)
4. Save to `models/onnx_int8/`

## Model Details

- **Base Model**: distilbert-base-uncased-finetuned-sst-2-english
- **Format**: ONNX INT8 quantized
- **Size**: ~30MB (vs 120MB float32)
- **Performance**: 60ms inference (vs 250ms HuggingFace)

## Note

Model files are not committed to git due to size (516MB for safetensors).
They are downloaded/generated during setup.

