import pytest
from django.contrib.auth import get_user_model
User = get_user_model()

@pytest.mark.django_db
def test_user_str():
    u = User.objects.create_user(username="alice", email="a@a.com", password="pw1234!")
    # 모델 구현에 따라 "alice" 또는 "alice ()" 모두 허용
    assert str(u) in {"alice", f"{u.username}", f"{u.username} ()"}
