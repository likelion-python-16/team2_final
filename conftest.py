# APIClient, 토큰, 유저 등 픽스처
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.urls import reverse
from model_bakery import baker

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(username="alice", email="a@a.com", password="pw1234!")

@pytest.fixture
def staff_user(db):
    return User.objects.create_user(username="admin", email="admin@a.com", password="pw1234!", is_staff=True)

@pytest.fixture
def token_pair(api_client, user):
    """SimpleJWT: POST /api/token/ -> {'access','refresh'}"""
    url = reverse("token_obtain_pair")
    resp = api_client.post(url, {"username": "alice", "password": "pw1234!"}, format="json")
    assert resp.status_code == 200, resp.content
    return resp.json()

@pytest.fixture
def access_token(token_pair):
    return token_pair["access"]

@pytest.fixture
def auth_client(api_client, access_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return api_client

@pytest.fixture
def bakery():
    return baker
