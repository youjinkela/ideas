from uuid import uuid4
from test_records import mutation


def test_auth_cross_owner_denied(setup_api):
    c,a,b,_=setup_api
    url=f"/v1/ideas/{uuid4()}/record"
    assert c.put(url,headers=a,json=mutation()).status_code==200
    assert c.put(url,headers=b,json=mutation("越权",1)).status_code in (403,404)
    assert c.get("/v1/changes",headers=b).json()["events"]==[]
    assert c.get("/v1/changes").status_code==401
    assert c.post("/v1/auth/logout",headers=a).status_code==200
    assert c.get("/v1/changes",headers=a).status_code==401


def test_login_rate_limited(setup_api):
    c,_,_,_=setup_api
    statuses=[c.post("/v1/auth/login",json={"username":"alice","password":"wrong"}).status_code for _ in range(8)]
    assert 429 in statuses
