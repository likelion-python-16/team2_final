import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_token_issue_and_refresh(api_client, user):
    obtain = api_client.post(reverse("token_obtain_pair"), {"username":"alice","password":"pw1234!"}, format="json")
    assert obtain.status_code == 200
    tokens = obtain.json()
    assert "access" in tokens and "refresh" in tokens

    refresh = api_client.post(reverse("token_refresh"), {"refresh": tokens["refresh"]}, format="json")
    assert refresh.status_code == 200
    assert "access" in refresh.json()

@pytest.mark.django_db
def test_users_list_requires_auth(api_client):
    url = reverse("users-list")  # router basename='users'
    r = api_client.get(url)
    assert r.status_code in (401, 403)

@pytest.mark.django_db
def test_users_list_with_auth(auth_client, bakery):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    bakery.make(User, _quantity=3) # model-bakery
    url = reverse("users-list")
    r = auth_client.get(url)
    assert r.status_code == 200
    data = r.json()
    # pagination 여부에 따라 형태 체크
    if isinstance(data, dict) and "results" in data:
        assert isinstance(data["results"], list)
    else:
        assert isinstance(data, list)