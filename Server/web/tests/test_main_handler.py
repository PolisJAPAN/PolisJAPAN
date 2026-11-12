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


def test_swagger_is_disabled_in_deployed_envs():
    from api.main import create_app

    # 本番LambdaはAPP_ENV=serverless。productionと同様にSwaggerを公開しない
    for env in ("production", "serverless"):
        app = create_app(env)
        assert (app.docs_url, app.redoc_url, app.openapi_url) == (None, None, None)
        paths = {getattr(route, "path", None) for route in app.routes}
        assert not ({"/docs", "/redoc", "/openapi.json"} & paths)


def test_swagger_is_enabled_in_local_envs():
    from api.main import create_app

    for env in ("localhost", "development"):
        app = create_app(env)
        assert app.docs_url == "/docs" and app.openapi_url == "/openapi.json"
