from sovereigninterpreter import (
    FilesystemMutator,
    LocalMessageRouter,
    Message,
    SafetyRules,
    SafetyViolation,
    SovereignConfig,
    SovereignInterpreter,
    SovereignMemory,
    MemoryPack,
)
from sovereigninterpreter.embeddings import LocalEmbeddings
from sovereigninterpreter.filesystem import FilesystemError
from sovereigninterpreter.util import paint, use_color


def test_local_embeddings_deterministic():
    emb = LocalEmbeddings(dimensions=32)
    a = emb.embed("sovereign local memory")
    b = emb.embed("sovereign local memory")
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_memory_pack_roundtrip():
    mem = SovereignMemory()
    mem.remember("short note", kind="short")
    mem.remember("long fact about local execution", kind="long")
    pack = mem.export_pack()
    assert isinstance(pack, MemoryPack)
    mem2 = SovereignMemory()
    mem2.import_pack(pack)
    hits = mem2.recall("execution", k=3)
    assert any("execution" in h.content for h in hits)


def test_safety_blocks_cloud_exfil():
    rules = SafetyRules()
    try:
        rules.check("please call api.openai.com now")
        assert False, "expected SafetyViolation"
    except SafetyViolation:
        pass


def test_safety_allows_local():
    rules = SafetyRules()
    rules.check("Use http://127.0.0.1:11434 for inference")


def test_router():
    router = LocalMessageRouter()
    router.send("worker", Message(role="user", content="go", sender="si"))
    msgs = router.receive("worker")
    assert len(msgs) == 1
    assert msgs[0].content == "go"
    assert router.receive("worker") == []


def test_filesystem_sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    fs = FilesystemMutator(config=cfg, base=tmp_path)
    fs.write("workspace/hello.txt", "hi")
    assert fs.read("workspace/hello.txt") == "hi"
    try:
        fs.write("/etc/passwd", "nope")
        assert False, "expected FilesystemError"
    except FilesystemError:
        pass


def test_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert use_color() is False
    assert paint("x", "31") == "x"
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert use_color() is True


def test_public_exports():
    cfg = SovereignConfig(kill_switch=False)
    from sovereigninterpreter.llm import MockLocalLLM

    mock = MockLocalLLM()
    mock.set_text("ready")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    assert si.config.allow_cloud is False
