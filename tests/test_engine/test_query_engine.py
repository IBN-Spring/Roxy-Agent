"""Tests for QueryEngine model/tool-call normalization."""

import json

from roxy.engine.query_engine import _normalize_tool_call, _to_plain_json


class _FunctionObject:
    def __init__(self):
        self.name = "knowledge_query"
        self.arguments = {"query": "单细胞"}


class _ToolCallObject:
    def __init__(self):
        self.id = "call_1"
        self.type = "function"
        self.function = _FunctionObject()


def test_normalize_tool_call_converts_function_object_to_plain_dict():
    normalized = _normalize_tool_call(_ToolCallObject())

    assert normalized == {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "knowledge_query",
            "arguments": '{"query": "单细胞"}',
        },
    }
    json.dumps(normalized, ensure_ascii=False)


def test_to_plain_json_handles_model_dump_objects():
    class Obj:
        def model_dump(self):
            return {"function": _FunctionObject()}

    plain = _to_plain_json(Obj())

    assert plain["function"]["name"] == "knowledge_query"
    json.dumps(plain, ensure_ascii=False)


def test_none_tool_calls_can_be_normalized_like_empty_list():
    message = {"content": "done", "tool_calls": None}
    tool_calls = [_normalize_tool_call(tc) for tc in (message.get("tool_calls") or [])]

    assert tool_calls == []
