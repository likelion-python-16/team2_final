import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_goals_crud_flow(auth_client):
    create_url = reverse("goals-list")
    payload = {
        "title": "헬스 30분",
        "target_kcal": 200,
        "goal_type": "운동",  # 자유입력 필드
    }
    r1 = auth_client.post(create_url, payload, format="json")
    assert r1.status_code in (200, 201), r1.content
    goal_id = r1.json()["id"]

    # 조회(내 것만 보이도록 get_queryset 제한했으니 OK)
    r2 = auth_client.get(reverse("goals-detail", args=[goal_id]))
    assert r2.status_code == 200

    # 부분 수정
    r3 = auth_client.patch(reverse("goals-detail", args=[goal_id]),
                           {"title": "헬스 45분"}, format="json")
    assert r3.status_code in (200, 202)

    # 목록
    r4 = auth_client.get(create_url)
    assert r4.status_code == 200

    # 삭제
    r5 = auth_client.delete(reverse("goals-detail", args=[goal_id]))
    assert r5.status_code in (200, 204)
