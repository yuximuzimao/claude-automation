import pytest

from order_review import cdp


def test_eval_js_uses_runtime_evaluate_and_parses_json(monkeypatch):
    calls = []

    def fake_cdp_call(target_id, method, params, chrome_port, timeout):
        calls.append(
            {
                "target_id": target_id,
                "method": method,
                "params": params,
                "chrome_port": chrome_port,
                "timeout": timeout,
            }
        )
        return {"result": {"value": '{"ok": true, "count": 2}'}}

    monkeypatch.setattr(cdp, "cdp_call", fake_cdp_call)

    result = cdp.eval_js("target-1", "1 + 1", chrome_port=9333, timeout=9)

    assert result == {"ok": True, "count": 2}
    assert calls == [
        {
            "target_id": "target-1",
            "method": "Runtime.evaluate",
            "params": {
                "expression": "1 + 1",
                "awaitPromise": True,
                "returnByValue": True,
            },
            "chrome_port": 9333,
            "timeout": 9,
        }
    ]


def test_extract_eval_value_raises_on_page_exception():
    with pytest.raises(cdp.CdpError):
        cdp._extract_eval_value({"exceptionDetails": {"text": "boom"}})
