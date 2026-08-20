from __future__ import annotations

import pytest
from flask import Flask


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    return app
