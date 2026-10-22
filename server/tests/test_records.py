from uuid import uuid4


def mutation(text="手机上的点子", version=0, recorded_at="2026-10-22T09:00:00+08:00", attachments=None):
    return {"mutation_id":str(uuid4()), "expected_version":version,
            "payload":{"text":text, "recorded_at":recorded_at, "attachments":attachments or []}}


def test_retry_after_lost_ack_creates_one_record(setup_api):
    c, a, _, _ = setup_api
    url = f"/v1/ideas/{uuid4()}/record"
    request = mutation()
    first = c.put(url, headers=a, json=request)
    assert first.status_code == 200
    assert c.put(url, headers=a, json=request).json() == first.json()
    assert len(c.get("/v1/changes", headers=a).json()["events"]) == 1
    assert c.put(url, headers=a, json=request | {"payload":request["payload"] | {"text":"changed"}}).status_code == 409


def test_raw_and_review_have_separate_versions(setup_api):
    c, a, _, _ = setup_api
    base = f"/v1/ideas/{uuid4()}"
    assert c.put(base+"/record", headers=a, json=mutation()).status_code == 200
    review = {"mutation_id":str(uuid4()),"expected_version":0,"payload":{"reflection":"今晚的补充"}}
    assert c.put(base+"/review", headers=a, json=review).json()["accepted_version"] == 1
    assert c.put(base+"/record", headers=a, json=mutation("原文更新",1)).json()["accepted_version"] == 2


def test_conflict_preserves_server_copy(setup_api):
    c, a, _, _ = setup_api
    url = f"/v1/ideas/{uuid4()}/record"
    c.put(url, headers=a, json=mutation("原文"))
    response = c.put(url, headers=a, json=mutation("过期副本"))
    assert response.status_code == 409
    assert response.json()["detail"]["current"]["text"] == "原文"


def test_change_cursor_ignores_device_clock(setup_api):
    c, a, _, _ = setup_api
    for time in ("2050-01-01T00:00:00Z","2000-01-01T00:00:00Z"):
        c.put(f"/v1/ideas/{uuid4()}/record",headers=a,json=mutation(recorded_at=time))
    first = c.get("/v1/changes?after=0&limit=1",headers=a).json()
    assert first["has_more"] is True
    second = c.get(f"/v1/changes?after={first['next_cursor']}&limit=1",headers=a).json()
    assert len(second["events"]) == 1
    assert second["events"][0]["entity_id"] != first["events"][0]["entity_id"]


def test_empty_records_and_duplicate_image_order_rejected(setup_api):
    c,a,_,_=setup_api
    assert c.put(f"/v1/ideas/{uuid4()}/record",headers=a,json=mutation("  ")).status_code == 422
    images=[{"id":str(uuid4()),"order":0,"mime_type":"image/png","size_bytes":10,"sha256":"a"*64} for _ in range(2)]
    assert c.put(f"/v1/ideas/{uuid4()}/record",headers=a,json=mutation(attachments=images)).status_code == 422

