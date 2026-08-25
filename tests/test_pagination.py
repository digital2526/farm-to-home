from unittest.mock import Mock

import recharge


def test_get_subscriptions_follows_pagination(monkeypatch):
    responses = [
        {
            "subscriptions": [
                {"id": 1},
                {"id": 2},
            ],
            "next_cursor": "cursor-page-2",
        },
        {
            "subscriptions": [
                {"id": 3},
            ],
            "next_cursor": None,
        },
    ]

    calls = []

    def fake_request(method, url, *, retry=False, **kwargs):
        calls.append({
            "method": method,
            "url": url,
            "retry": retry,
            "params": kwargs.get("params"),
        })

        response = Mock()
        response.json.return_value = responses[len(calls) - 1]
        return response

    monkeypatch.setattr(
        recharge,
        "_request",
        fake_request,
    )

    result = recharge.get_subscriptions("customer-123")

    assert result["subscriptions"] == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]

    assert len(calls) == 2

    assert calls[0]["params"] == {
        "customer_id": "customer-123",
        "limit": 250,
    }

    assert calls[1]["params"] == {
        "customer_id": "customer-123",
        "limit": 250,
        "cursor": "cursor-page-2",
    }

    assert calls[0]["retry"] is True
    assert calls[1]["retry"] is True
