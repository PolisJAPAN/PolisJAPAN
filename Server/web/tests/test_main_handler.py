def test_handler_is_mangum_adapter():
    from mangum import Mangum

    from api.main import app, handler

    assert isinstance(handler, Mangum)
    # ラップ対象が同一のFastAPIアプリであること
    assert handler.app is app


def test_app_has_expected_routes():
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/batch/healthcheck" in paths
    assert "/theme/post_draft" in paths
    assert "/admin/info" in paths
