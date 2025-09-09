import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# Import your Base, main app, and key modules
from src.database.core import Base, get_db
from src.main import app
from src.entities.user import User
from src.utils import password_utils

# Use an in-memory SQLite database for testing
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a new, isolated in-memory database session for each test.
    """
    engine = create_engine(
        TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_user(db_session):
    """
    Creates a pre-defined, verified, password-based user in the test database.
    """
    user_data = {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "password_hash": password_utils.get_password_hash("ValidPassword123!"),
        "is_verified": True,
        "auth_provider": "email",
    }
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_session, mocker):
    """
    Creates a TestClient for the app, overriding dependencies and mocking external services.
    """
    # Mock all external services to ensure tests are isolated and fast
    mocker.patch("src.email_service.send_verification_email", return_value=None)
    mocker.patch("src.email_service.send_password_reset_email", return_value=None)
    mocker.patch("src.denylist_service.is_token_denylisted", return_value=False)
    mocker.patch("src.denylist_service.add_token_to_denylist", return_value=None)
    
    # Mock the google auth flow
    mocker.patch("src.auth.service.oauth.google.authorize_redirect", return_value=MagicMock())
    mocker.patch("src.auth.service.oauth.google.authorize_access_token", return_value={
        "userinfo": {
            "email": "google.user@example.com", "given_name": "Google", "family_name": "User",
        }
    })

    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client, test_user):
    """
    Logs in the `test_user` and returns valid authorization headers.
    """
    login_data = {
        "username": test_user.email,
        "password": "ValidPassword123!"
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 202, "Failed to log in test user for auth_headers"
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}