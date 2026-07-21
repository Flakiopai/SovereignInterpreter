from sovereigninterpreter.config import CloudForbiddenError, SovereignConfig
from sovereigninterpreter.llm import LocalLLM, MockLocalLLM, create_completion


def test_mock_complete():
    mock = MockLocalLLM()
    mock.set_text("hello local")
    assert mock.complete([{"role": "user", "content": "hi"}]) == "hello local"
    mock.assert_create_called()


def test_create_completion_factory():
    cc = create_completion({"role": "assistant", "content": "ok"})
    assert cc.choices[0].message.content == "ok"


def test_local_llm_blocks_cloud():
    cfg = SovereignConfig(allow_cloud=False)
    try:
        LocalLLM(base_url="https://api.example.com/v1", config=cfg, enforce_config=True)
        assert False, "expected CloudForbiddenError"
    except CloudForbiddenError:
        pass


def test_local_llm_allows_localhost():
    cfg = SovereignConfig(allow_cloud=False)
    client = LocalLLM(
        base_url="http://127.0.0.1:11434/v1",
        model="llama3.2",
        config=cfg,
        enforce_config=True,
    )
    assert client.base_url.endswith("/v1")
