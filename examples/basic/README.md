# Basic examples

These demos need a local model server (Ollama by default).

## Prerequisites

1. Install the package: `pip install -e ".[dev]"`
2. Start Ollama and pull a model:

```shell
ollama serve
ollama pull llama3.2
```

## Chat demo

Run:

```shell
python examples/basic/chat_demo.py
```

Expected: the interpreter prints a short reply and may execute local python if the model emits a code fence. With `auto_run=True` in the demo, code runs without a prompt.
