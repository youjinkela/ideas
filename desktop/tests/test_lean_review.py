import pytest
from fastapi.testclient import TestClient
from test_app import desktop, session, ORIGIN
from test_cache import raw_event


@pytest.mark.parametrize('method,path', [
    ('get', '/local/ai/history?id=11111111-1111-4111-8111-111111111111'),
    ('post', '/local/ai/ask'),
])
def test_model_routes_are_not_part_of_the_review_tool(tmp_path, method, path):
    app = desktop(tmp_path)
    app.state.cache.apply_events([raw_event()])
    with TestClient(app, base_url=ORIGIN) as client:
        headers = session(client)
        if method == 'post':
            response = client.post(path, headers=headers, json={'id': raw_event()['entity_id'], 'mode': 'ask'})
        else:
            response = client.get(path)
        assert response.status_code == 404


@pytest.mark.parametrize('key', ['ai_url', 'ai_model', 'ai_key'])
def test_settings_reject_retired_model_fields_without_changing_legacy_data(tmp_path, key):
    app = desktop(tmp_path)
    legacy = {'ai_url': 'https://model.example/v1', 'ai_model': 'legacy-model', 'ai_key': 'opaque-legacy-encrypted-value'}
    app.state.settings.values.update(legacy)
    app.state.settings.update()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = session(client)
        response = client.post('/local/settings', headers=headers, json={key: 'https://new.example/v1'})
        assert response.status_code == 400
        assert not any(name.startswith('ai_') for name in client.get('/local/settings').json())
        assert all(app.state.settings.get(name) == value for name, value in legacy.items())


def test_upgrade_preserves_manual_notes_and_existing_conversation_rows(tmp_path):
    app = desktop(tmp_path)
    app.state.cache.apply_events([raw_event()])
    with app.state.cache.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY,idea_id TEXT,role TEXT,text TEXT)')
        con.execute('INSERT INTO ai_messages(idea_id,role,text) VALUES(?,?,?)', (raw_event()['entity_id'], 'assistant', 'legacy fixture'))
    reopened = desktop(tmp_path)
    with TestClient(reopened, base_url=ORIGIN) as client:
        headers = session(client)
        response = client.post('/local/reflection', headers=headers, json={'id': raw_event()['entity_id'], 'reflection': '由我整理的想法'})
        assert response.status_code == 200
        assert reopened.state.cache.get(raw_event()['entity_id'])['reflection'] == '由我整理的想法'
    with reopened.state.cache.db() as con:
        assert [row[0] for row in con.execute('SELECT text FROM ai_messages')] == ['legacy fixture']
