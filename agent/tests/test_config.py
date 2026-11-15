"""The public viewer config is dynamic, offline, and never a secret dump."""
import os
import socket
import sys

import pytest
from fastapi.testclient import TestClient

from agent.app import app
from data import costar_tools, vexcel_tools
from index import search


@pytest.fixture
def config_client(monkeypatch):
    original_connect = socket.socket.connect
    def no_network(*args, **kwargs):
        fallback = getattr(socket, '_fallback_socketpair', None)
        if fallback is not None and sys._getframe(1).f_code is fallback.__code__:
            return original_connect(*args, **kwargs)
        raise AssertionError("/config must not access the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "1")
    monkeypatch.setenv("TYPECAST_ENGINE", "fixed")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("MATTERPORT_SDK_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    for adapter in (costar_tools, vexcel_tools, search):
        monkeypatch.setattr(adapter, "USE_MOCKS", True)
    return TestClient(app)


def test_config_exact_allow_list_and_absent_key(config_client):
    response = config_client.get("/config")
    assert response.status_code == 200
    assert response.json() == {"mode": "mock", "engine": "fixed", "tracing": False,
                               "matterport_sdk_key": None}


def test_config_reads_current_adapters_and_settings(config_client, monkeypatch):
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    # A changed environment alone cannot relabel already-imported mock adapters.
    assert config_client.get("/config").json()["mode"] == "mock"
    monkeypatch.setattr(vexcel_tools, "USE_MOCKS", False)
    assert config_client.get("/config").json()["mode"] == "mixed"
    for adapter in (costar_tools, search):
        monkeypatch.setattr(adapter, "USE_MOCKS", False)
    monkeypatch.setenv("TYPECAST_ENGINE", "DEEP")
    monkeypatch.setenv("LANGSMITH_API_KEY", "private-config-tracing-key")
    monkeypatch.setenv("MATTERPORT_SDK_KEY", "browser-domain-allowed-sdk-key")
    config = config_client.get("/config").json()
    assert config == {"mode": "live", "engine": "deep", "tracing": True,
                      "matterport_sdk_key": "browser-domain-allowed-sdk-key"}
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    assert config_client.get("/config").json()["tracing"] is False
    monkeypatch.setenv("TYPECAST_ENGINE", "fixed")
    monkeypatch.delenv("LANGSMITH_API_KEY")
    monkeypatch.delenv("MATTERPORT_SDK_KEY")
    config = config_client.get("/config").json()
    assert config["engine"] == "fixed" and config["tracing"] is False
    assert config["matterport_sdk_key"] is None


def test_config_credential_values_never_leak(config_client, monkeypatch):
    for name in ("MATTERPORT_API_KEY", "MATTERPORT_API_SECRET", "OPENAI_API_KEY",
                 "LANGSMITH_API_KEY", "VEXCEL_API_KEY", "PHOTON_PROJECT_SECRET",
                 "UNEXPECTED_PROVIDER_KEY", "UNEXPECTED_PROVIDER_SECRET", "AUTH_TOKEN"):
        monkeypatch.setenv(name, f"private-config-value-for-{name.lower()}")
    monkeypatch.setenv("MATTERPORT_SDK_KEY", "public-browser-config-sdk-value")
    response = config_client.get("/config")
    assert response.status_code == 200
    assert set(response.json()) == {"mode", "engine", "tracing", "matterport_sdk_key"}
    assert response.json()["matterport_sdk_key"] == "public-browser-config-sdk-value"
    # Check every current credential value, including unanticipated providers.
    # Report names only on failure; actual local environment values stay private.
    leaked_names = [name for name, value in os.environ.items()
                    if name != "MATTERPORT_SDK_KEY"
                    and name.endswith(("_KEY", "_SECRET", "_TOKEN"))
                    and value and value in response.text]
    assert not leaked_names, f"Credential leakage for environment names: {leaked_names}"


@pytest.mark.parametrize("credential_name", ["MATTERPORT_API_KEY", "MATTERPORT_API_SECRET", "AUTH_TOKEN"])
def test_config_rejects_sdk_key_aliased_to_private_credential(config_client, monkeypatch, credential_name):
    monkeypatch.setenv(credential_name, "private-credential-copied-to-sdk-key")
    monkeypatch.setenv("MATTERPORT_SDK_KEY", "private-credential-copied-to-sdk-key")
    response = config_client.get("/config")
    assert response.status_code == 200
    assert response.json()["matterport_sdk_key"] is None
    assert "private-credential-copied-to-sdk-key" not in response.text


def test_config_rejects_invalid_engine_without_echoing_value(config_client, monkeypatch):
    monkeypatch.setenv("TYPECAST_ENGINE", "private-invalid-engine-value")
    response = config_client.get("/config")
    assert response.status_code == 503
    assert "private-invalid-engine-value" not in response.text
