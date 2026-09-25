from app.cloud.s3_storage import S3Storage
from app.core.config import Settings


class DummyS3Client:
    pass


def test_s3_sin_credenciales_estaticas_usa_default_chain(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    settings = Settings()

    captured = {}

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return DummyS3Client()

    monkeypatch.setattr("app.cloud.s3_storage.boto3.client", fake_client)

    storage = S3Storage(settings)

    assert storage._client is not None
    assert captured["service_name"] == "s3"
    assert "aws_access_key_id" not in captured["kwargs"]
    assert "aws_secret_access_key" not in captured["kwargs"]


def test_s3_con_credenciales_estaticas_las_pasa_a_boto3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "session")
    settings = Settings()

    captured = {}

    def fake_client(service_name, **kwargs):
        captured["kwargs"] = kwargs
        return DummyS3Client()

    monkeypatch.setattr("app.cloud.s3_storage.boto3.client", fake_client)

    S3Storage(settings)

    assert captured["kwargs"]["aws_access_key_id"] == "access"
    assert captured["kwargs"]["aws_secret_access_key"] == "secret"
    assert captured["kwargs"]["aws_session_token"] == "session"
