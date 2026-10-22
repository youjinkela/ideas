import importlib
import json
import httpx
import pytest


def module():
    try:return importlib.import_module("idea_echo_desktop.ai")
    except ImportError:pytest.fail("Opt-in AI assistance is not implemented")


def test_only_current_text_is_sent_without_images_or_vault():
    ai=module();received=[]
    def transport(request):
        received.append(json.loads(request.content))
        return httpx.Response(200,json={"choices":[{"message":{"content":"你最想解决的具体问题是什么？"}}]})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        reply=ai.ask_ai({"mode":"ask","text":"当前点子","reflection":"我的想法","prompt":"","attachments":[{"url":"private.jpg"}],"vault":"C:/private"},ai.AiSettings("https://model.example/v1","model","not-a-real-key"),client)
    assert reply["text"]=="你最想解决的具体问题是什么？"
    outgoing=json.dumps(received,ensure_ascii=False)
    assert "当前点子" in outgoing and "我的想法" in outgoing
    assert "private.jpg" not in outgoing and "C:/private" not in outgoing
    assert "tools" not in received[0]


def test_missing_config_returns_setup_required():
    ai=module()
    with pytest.raises(ai.SetupRequired):ai.ask_ai({"text":"点子"},ai.AiSettings())


def test_timeout_is_recoverable_without_fabricated_response():
    ai=module()
    def timeout(request):raise httpx.ReadTimeout("timeout",request=request)
    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ValueError):ai.ask_ai({"text":"原文","mode":"expand"},ai.AiSettings("https://model.example/v1","model","key"),client)

