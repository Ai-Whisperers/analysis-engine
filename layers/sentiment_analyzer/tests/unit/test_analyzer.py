import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if "onnxruntime" not in sys.modules:
    onnxruntime_stub = types.ModuleType("onnxruntime")

    class _SessionOptions:
        def __init__(self):
            self.intra_op_num_threads = None
            self.inter_op_num_threads = None
            self.graph_optimization_level = None

    class _InferenceSession:
        def __init__(self, *args, **kwargs):
            pass

        def get_inputs(self):
            return []

        def get_outputs(self):
            return []

    onnxruntime_stub.SessionOptions = _SessionOptions
    onnxruntime_stub.InferenceSession = _InferenceSession
    sys.modules["onnxruntime"] = onnxruntime_stub

if "transformers" not in sys.modules:
    transformers_stub = types.ModuleType("transformers")

    class _Tokenizer:
        def __call__(self, *args, **kwargs):
            raise NotImplementedError("Tokenizer stub should not be used in tests.")

        def save_pretrained(self, _path):
            raise NotImplementedError("Tokenizer stub should not be used in tests.")

    class _AutoTokenizer:
        @classmethod
        def from_pretrained(cls, _name):
            return _Tokenizer()

    transformers_stub.AutoTokenizer = _AutoTokenizer
    sys.modules["transformers"] = transformers_stub

if "opentelemetry" not in sys.modules:
    otel_module = types.ModuleType("opentelemetry")

    trace_module = types.ModuleType("opentelemetry.trace")

    class _DummyTracer:
        def start_as_current_span(self, _name):
            from contextlib import nullcontext

            return nullcontext()

    def _get_tracer(_name):
        return _DummyTracer()

    def _set_tracer_provider(_provider):
        return None

    trace_module.get_tracer = _get_tracer
    trace_module.set_tracer_provider = _set_tracer_provider
    trace_module.Tracer = _DummyTracer

    exporter_module = types.ModuleType("opentelemetry.exporter")
    jaeger_module = types.ModuleType("opentelemetry.exporter.jaeger")
    thrift_module = types.ModuleType("opentelemetry.exporter.jaeger.thrift")

    class JaegerExporter:
        def __init__(self, *args, **kwargs):
            pass

    thrift_module.JaegerExporter = JaegerExporter
    jaeger_module.thrift = thrift_module
    exporter_module.jaeger = jaeger_module

    instrumentation_module = types.ModuleType("opentelemetry.instrumentation")
    fastapi_module = types.ModuleType("opentelemetry.instrumentation.fastapi")

    class FastAPIInstrumentor:
        @staticmethod
        def instrument_app(_app):
            return None

    fastapi_module.FastAPIInstrumentor = FastAPIInstrumentor
    instrumentation_module.fastapi = fastapi_module

    sdk_module = types.ModuleType("opentelemetry.sdk")
    resources_module = types.ModuleType("opentelemetry.sdk.resources")

    class Resource:
        @classmethod
        def create(cls, _attributes):
            return cls()

    resources_module.Resource = Resource

    trace_sdk_module = types.ModuleType("opentelemetry.sdk.trace")

    class TracerProvider:
        def __init__(self, *args, **kwargs):
            pass

        def add_span_processor(self, _processor):
            pass

    trace_sdk_module.TracerProvider = TracerProvider

    export_module = types.ModuleType("opentelemetry.sdk.trace.export")

    class BatchSpanProcessor:
        def __init__(self, _exporter):
            pass

    class ConsoleSpanExporter:
        def __init__(self, *args, **kwargs):
            pass

    export_module.BatchSpanProcessor = BatchSpanProcessor
    export_module.ConsoleSpanExporter = ConsoleSpanExporter
    trace_sdk_module.export = export_module

    otel_module.trace = trace_module
    otel_module.exporter = exporter_module
    otel_module.instrumentation = instrumentation_module
    otel_module.sdk = sdk_module

    sdk_module.resources = resources_module
    sdk_module.trace = trace_sdk_module

    sys.modules["opentelemetry"] = otel_module
    sys.modules["opentelemetry.trace"] = trace_module
    sys.modules["opentelemetry.exporter"] = exporter_module
    sys.modules["opentelemetry.exporter.jaeger"] = jaeger_module
    sys.modules["opentelemetry.exporter.jaeger.thrift"] = thrift_module
    sys.modules["opentelemetry.instrumentation"] = instrumentation_module
    sys.modules["opentelemetry.instrumentation.fastapi"] = fastapi_module
    sys.modules["opentelemetry.sdk"] = sdk_module
    sys.modules["opentelemetry.sdk.resources"] = resources_module
    sys.modules["opentelemetry.sdk.trace"] = trace_sdk_module
    sys.modules["opentelemetry.sdk.trace.export"] = export_module

analyzer_module = importlib.import_module("layers.sentiment_analyzer.analyzer")
SentimentAnalyzer = analyzer_module.SentimentAnalyzer
SentimentResult = analyzer_module.SentimentResult


def test_analyze_returns_expected_results_and_updates_metrics():
    fake_model = MagicMock()
    fake_model.predict.return_value = [
        {"POSITIVE": 0.9, "NEGATIVE": 0.1},
        {"POSITIVE": 0.35, "NEGATIVE": 0.65},
    ]

    breaker_instances = []

    def breaker_factory(*args, **kwargs):
        breaker = MagicMock()

        def pass_through(func, *call_args, **call_kwargs):
            return func(*call_args, **call_kwargs)

        breaker.call.side_effect = pass_through
        breaker_instances.append(breaker)
        return breaker

    texts = ["Great service!", "Very bad experience."]

    with patch.object(analyzer_module, "CircuitBreaker", side_effect=breaker_factory):
        with patch.object(analyzer_module, "ONNXModelLoader", return_value=fake_model):
            analyzer = SentimentAnalyzer(model_path="dummy.onnx", batch_size=2)

            mock_record_processing = MagicMock()
            positive_metric = MagicMock()
            negative_metric = MagicMock()
            mock_sentiment_gauge = MagicMock()
            mock_sentiment_gauge.labels.side_effect = lambda sentiment: {
                "POSITIVE": positive_metric,
                "NEGATIVE": negative_metric,
            }[sentiment]

            with patch.object(
                analyzer_module.MetricsCollector,
                "record_processing",
                mock_record_processing,
            ), patch.object(
                analyzer_module.MetricsCollector,
                "sentiment_distribution",
                mock_sentiment_gauge,
            ):
                results = analyzer.analyze(texts)

    assert len(breaker_instances) == 2
    load_breaker, inference_breaker = breaker_instances
    load_breaker.call.assert_called_once()
    inference_breaker.call.assert_called_once()

    call_args, call_kwargs = inference_breaker.call.call_args
    assert call_args[0] is fake_model.predict
    assert call_kwargs["texts"] == texts
    assert call_kwargs["batch_size"] == 2

    fake_model.predict.assert_called_once_with(texts=texts, batch_size=2)

    assert len(results) == 2
    assert all(isinstance(r, SentimentResult) for r in results)
    assert results[0].sentiment == "POSITIVE"
    assert results[0].confidence == pytest.approx(0.9)
    assert results[0].positive_score == pytest.approx(0.9)
    assert results[0].negative_score == pytest.approx(0.1)
    assert results[1].sentiment == "NEGATIVE"
    assert results[1].confidence == pytest.approx(0.65)
    assert results[1].positive_score == pytest.approx(0.35)
    assert results[1].negative_score == pytest.approx(0.65)

    mock_record_processing.assert_called_once()
    metric_kwargs = mock_record_processing.call_args.kwargs
    assert metric_kwargs["layer"] == "sentiment_analyzer"
    assert metric_kwargs["operation"] == "analyze"
    assert metric_kwargs["records"] == len(texts)

    positive_metric.set.assert_called_once_with(1)
    negative_metric.set.assert_called_once_with(1)
