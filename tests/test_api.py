from fastapi.testclient import TestClient

from amin.api import app

c = TestClient(app)


def test_health():
    r = c.get("/api/health").json()
    assert r["ok"] and r["terms"] > 20 and r["attributes"] >= 6


def test_check_and_explain():
    r = c.post("/api/check", json={"arabic": "﴿يَدُ اللَّهِ فَوْقَ أَيْدِيهِمْ﴾.",
                                  "translation": "God's power is over their hands.", "use_llm": False}).json()
    f = next(x for x in r["findings"] if x["type"] == 4)
    e = c.get(f"/api/explain/{f['ref_id']}?lang=en").json()
    assert e["ayat"] and e["quotes"]
    assert all(q["link"].startswith("https://app.turath.io/") for q in e["quotes"])


def test_empty_rejected():
    assert c.post("/api/check", json={"arabic": " ", "translation": "x"}).status_code == 400


def test_index_served():
    assert c.get("/").status_code == 200
