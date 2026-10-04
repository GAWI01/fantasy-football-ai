from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.team_service import normalize_team_response
import backend.fixture_service as fixture_service


def _manifest(event=6, season='2026-27', provenance=None):
    return SimpleNamespace(
        prediction_event=event, season=season,
        prediction_file='gw6.csv', generated_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
        player_count=1, schema_version=1, model_provenance=provenance,
    )


def _bootstrap():
    return {
        'events': [
            {'id': 1, 'deadline_time': '2026-08-15T10:00:00Z'},
            {'id': 5, 'is_current': True},
            {'id': 6, 'is_next': True},
        ],
        'elements': [{'id': 10, 'web_name': 'Saka', 'first_name': 'Bukayo',
                      'second_name': 'Saka', 'status': 'a', 'team': 1}],
        'teams': [{'id': 1}],
    }


def test_manager_display_excludes_first_name():
    result = normalize_team_response(123, {
        'id': 123, 'name': 'Test XI', 'player_first_name': 'Private',
        'player_last_name': 'Surname', 'picks': [],
    })
    assert result['manager_name'] == 'Surname'


def test_official_player_name_never_falls_back_to_first_name(monkeypatch):
    bootstrap = _bootstrap()
    bootstrap['elements'][0]['web_name'] = ''
    monkeypatch.setattr(main, 'get_bootstrap_data', lambda: bootstrap)
    monkeypatch.setattr(main, 'fetch_public_team', lambda _: {
        'team_id': 123, 'name': 'XI', 'picks': [{'player_id': 10}],
    })
    assert main.get_official_team(123)['picks'][0]['name'] == 'Saka'


def test_player_enrichment_preserves_official_minutes_and_form(monkeypatch):
    monkeypatch.setattr(main, 'get_live_player_rankings', lambda **_: {
        'current_event': 5, 'players': [{'player_id': 10, 'minutes': 90, 'form': 7.2}],
    })
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame([{
        'player_id': 10, 'predicted_points': 5.0, 'minutes': 450, 'form': 2.1,
    }]))
    data = main.get_enriched_player_rankings()
    assert data['players'][0]['minutes'] == 90
    assert data['players'][0]['form'] == 7.2
    assert data['prediction_event'] == 6
    assert data['players'][0]['predicted_points'] == 5.0


def test_forecast_for_a_player_missing_from_official_data_is_dropped(monkeypatch):
    monkeypatch.setattr(main, 'get_live_player_rankings', lambda **_: {
        'current_event': 5, 'players': [{'player_id': 10, 'minutes': 90}],
    })
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame([
        {'player_id': 10, 'predicted_points': 5.0},
        {'player_id': 99, 'predicted_points': 7.0},
    ]))
    data = main.get_enriched_player_rankings()
    assert 'model_error' not in data
    assert data['players'][0]['predicted_points'] == 5.0


def test_stale_player_forecast_is_unavailable_while_live_facts_survive(monkeypatch):
    monkeypatch.setattr(main, 'get_live_player_rankings', lambda **_: {
        'current_event': 5, 'players': [{'player_id': 10, 'minutes': 90}],
    })
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest(event=3))
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame([{
        'player_id': 10, 'predicted_points': 5.0,
    }]))
    data = main.get_enriched_player_rankings()
    assert data['players'][0]['minutes'] == 90
    assert 'predicted_points' not in data['players'][0]
    assert data['model_version'] is None
    assert 'GW3' in data['model_error']


@pytest.mark.parametrize('manifest', [_manifest(event=3), _manifest(season='2025-26')])
def test_decision_rejects_stale_gameweek_or_season_before_solver(monkeypatch, manifest):
    monkeypatch.setattr(main, 'get_team_data', lambda _: {'picks': []})
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame())
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: manifest)
    monkeypatch.setattr(main, 'build_decision', lambda *a, **k: pytest.fail('stale solver input'))
    response = TestClient(main.app).get('/api/decision/123')
    assert response.status_code == 503
    assert 'Prediction' in response.json()['detail']


def test_live_dgw_retains_live_classification_and_metadata(monkeypatch):
    monkeypatch.setattr(main, 'get_team_data', lambda _: {
        'name': 'XI', 'picks': [{'player_id': 10, 'multiplier': 3}],
    })
    monkeypatch.setattr(main, 'get_live_players', lambda **_: {
        'current_event': 5, 'gameweek_name': 'Gameweek 5', 'status': 'LIVE',
        'finished': False, 'next_event': 6, 'next_deadline_time': '2026-10-10T10:00:00Z',
        'players': [{'player_id': 10, 'team_id': 1, 'event_points': 5}],
    })
    monkeypatch.setattr(main, 'get_event_fixtures', lambda _: {'fixtures': [
        {'fixture_id': 1, 'home_team_id': 1, 'away_team_id': 2, 'started': True, 'finished': False},
        {'fixture_id': 2, 'home_team_id': 1, 'away_team_id': 3, 'started': False, 'finished': False},
    ]})
    body = TestClient(main.app).get('/team/123/live').json()
    assert body['summary']['players_live'] == 1
    assert body['summary']['players_remaining'] == 0
    assert body['summary']['live_points'] == 15
    assert body['finished'] is False
    assert body['next_event'] == 6


def test_unvalidated_model_cannot_claim_full_readiness(monkeypatch):
    monkeypatch.setattr(main, 'default_gateway', SimpleNamespace(get_json=lambda *a, **k:
        SimpleNamespace(data=_bootstrap(), fetched_at=datetime.now(timezone.utc), stale=False)))
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'validate_runtime_artifacts', lambda _: {'loaded': True, 'files': []})
    body = TestClient(main.app).get('/api/v1/status').json()
    assert body['data']['model']['validation_state'] == 'unverified'
    assert body['data']['service_state'] == 'degraded'
    assert TestClient(main.app).get('/health').json() == {'status': 'ok'}


def test_known_unavailable_is_zero_but_injury_chance_is_not_zero():
    predictions = pd.DataFrame([
        {'player_id': 10, 'name': 'Player', 'predicted_points': 5.0},
        {'player_id': 11, 'name': 'Player', 'predicted_points': 4.0},
    ])
    bootstrap = {'elements': [
        {'id': 10, 'web_name': 'Saka', 'status': 's', 'chance_of_playing_next_round': 0},
        {'id': 11, 'web_name': 'Palmer', 'status': 'i', 'chance_of_playing_next_round': 75},
    ]}
    result = main._apply_official_player_state(predictions, bootstrap).set_index('player_id')
    assert result.loc[10, 'predicted_points'] == 0.0
    assert result.loc[11, 'predicted_points'] == 4.0
    assert result.loc[11, 'availability'] == 'RISK'


def test_player_enrichment_uses_current_availability_over_artifact(monkeypatch):
    bootstrap = _bootstrap()
    bootstrap['elements'][0].update(status='s', chance_of_playing_next_round=0)
    monkeypatch.setattr(main, 'get_bootstrap_data', lambda: bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame([{
        'player_id': 10, 'predicted_points': 8.0, 'xmins': 90,
    }]))
    monkeypatch.setattr(main, 'get_live_player_rankings', lambda **_: {
        'current_event': 5, 'players': [{'player_id': 10, 'minutes': 90}],
    })
    player = main.get_enriched_player_rankings()['players'][0]
    assert player['predicted_points'] == 0.0
    assert player['availability'] == 'UNAVAILABLE'
    assert player['minutes'] == 90


def test_dashboard_labels_unverified_model_without_losing_official_team(monkeypatch):
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'build_dashboard', lambda *a, **k: {
        'data': {'team': {'team_id': 123, 'name': 'XI', 'picks': []},
                 'live': None, 'history': None, 'fixtures': None, 'players': None, 'decision': None},
        'meta': {'degraded': False}, 'errors': [],
    })
    body = TestClient(main.app).get('/api/v1/dashboard/123').json()
    assert body['data']['team']['name'] == 'XI'
    assert body['meta']['model_validation_state'] == 'unverified'
    assert body['meta']['degraded'] is True
    assert any(error['area'] == 'model' for error in body['errors'])


def test_dashboard_locks_actions_when_model_target_is_not_official(monkeypatch):
    bootstrap = _bootstrap()
    bootstrap['events'].append({'id': 3, 'deadline_time': '2099-10-10T10:00:00Z'})
    monkeypatch.setattr(main, 'get_bootstrap_data', lambda: bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest(event=3))
    monkeypatch.setattr(main, 'build_dashboard', lambda *a, **k: {
        'data': {'team': {'team_id': 123, 'name': 'XI', 'picks': []},
                 'live': None, 'history': None, 'fixtures': None, 'players': None, 'decision': None},
        'meta': {'degraded': False}, 'errors': [],
    })
    body = TestClient(main.app).get('/api/v1/dashboard/123').json()
    assert body['meta']['actions_locked'] is True
    assert body['meta']['prediction_event'] is None


def test_live_captain_contribution_tracks_actual_vice_captain_fallback(monkeypatch):
    monkeypatch.setattr(main, 'get_team_data', lambda _: {
        'name': 'XI', 'picks': [
            {'player_id': 10, 'multiplier': 0, 'is_captain': True},
            {'player_id': 11, 'multiplier': 3, 'is_captain': False, 'is_vice_captain': True},
        ],
    })
    monkeypatch.setattr(main, 'get_live_players', lambda **_: {
        'current_event': 5, 'gameweek_name': 'Gameweek 5', 'status': 'FINISHED',
        'players': [{'player_id': 10, 'team_id': 1, 'event_points': 0},
                    {'player_id': 11, 'team_id': 1, 'event_points': 5}],
    })
    monkeypatch.setattr(main, 'get_event_fixtures', lambda _: {'fixtures': []})
    body = TestClient(main.app).get('/team/123/live').json()
    assert body['summary']['captain_contribution'] == 15


def test_fixture_player_label_does_not_fall_back_to_first_name(monkeypatch):
    monkeypatch.setattr(fixture_service, '_get_json', lambda _: {
        'picks': [{'element': 10, 'position': 1}],
    })
    bootstrap = _bootstrap()
    del bootstrap['elements'][0]['web_name']
    bootstrap['elements'][0]['element_type'] = 3
    result = fixture_service._get_current_picks(123, bootstrap, 5)
    assert result[0]['name'] == 'Saka'


def test_runtime_forecast_cannot_score_with_explicit_zero_expected_minutes():
    predictions = pd.DataFrame([{'player_id': 10, 'name': 'Saka',
                                 'predicted_points': 1.2, 'xmins': 0, 'start_probability': 0}])
    result = main._apply_official_player_state(predictions, _bootstrap())
    assert result.loc[0, 'predicted_points'] == 0.0


def test_decision_prices_and_value_use_current_official_cost():
    bootstrap = _bootstrap()
    bootstrap['elements'][0]['now_cost'] = 75
    predictions = pd.DataFrame([{'player_id': 10, 'name': 'Saka', 'price': 6.0,
                                 'predicted_points': 5.0, 'value': 0.833}])
    result = main._apply_official_player_state(predictions, bootstrap)
    assert result.loc[0, 'price'] == 7.5
    assert result.loc[0, 'value'] == pytest.approx(5.0 / 7.5)


@pytest.mark.parametrize('path', ['/team/123', '/players/top'])
def test_legacy_forecast_routes_apply_official_availability(monkeypatch, path):
    bootstrap = _bootstrap()
    bootstrap['elements'][0].update(status='s', chance_of_playing_next_round=0)
    bootstrap['teams'][0].update(name='Arsenal', short_name='ARS')
    monkeypatch.setattr(main, 'get_bootstrap_data', lambda: bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest())
    monkeypatch.setattr(main, 'get_team_fixtures', lambda *a, **k: {'current_event': 5, 'next_event': 6})
    monkeypatch.setattr(main, 'get_official_team', lambda _: {
        'name': 'XI', 'team_id': 123, 'picks': [{'player_id': 10}],
    })
    monkeypatch.setattr(main, 'load_players', lambda: pd.DataFrame([{'player_id': 10}]))
    monkeypatch.setattr(main, '_load_predictions', lambda _: (pd.DataFrame([{
        'player_id': 10, 'name': 'Full Player Name', 'team': 'Arsenal', 'position': 'MID',
        'price': 6.0, 'predicted_points': 5.0, 'xmins': 90.0,
    }]), 'gw6.csv'))
    body = TestClient(main.app).get(path).json()
    prediction = body['picks'][0]['prediction'] if 'picks' in body else body['players'][0]
    assert prediction['predicted_points'] == 0.0


def test_live_picks_carry_the_live_gameweeks_own_forecast(monkeypatch):
    monkeypatch.setattr(main, 'get_team_data', lambda _: {'name': 'XI', 'picks': [{'player_id': 10, 'multiplier': 2}]})
    monkeypatch.setattr(main, 'get_live_players', lambda **_: {
        'current_event': 6, 'gameweek_name': 'Gameweek 6', 'status': 'LIVE', 'finished': False,
        'players': [{'player_id': 10, 'team_id': 1, 'event_points': 5}],
    })
    monkeypatch.setattr(main, 'get_event_fixtures', lambda _: {'fixtures': []})
    monkeypatch.setattr(main, 'get_bootstrap_data', _bootstrap)
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest(event=6))
    monkeypatch.setattr(main, 'load_predictions', lambda: pd.DataFrame([{'player_id': 10, 'predicted_points': 4.5}]))
    body = TestClient(main.app).get('/team/123/live').json()
    assert body['picks'][0]['expected_points'] == 4.5
    monkeypatch.setattr(main, 'load_current_manifest', lambda _: _manifest(event=7))
    body = TestClient(main.app).get('/team/123/live').json()
    assert 'expected_points' not in body['picks'][0]
