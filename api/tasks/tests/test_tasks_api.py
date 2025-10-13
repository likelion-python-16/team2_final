import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_tasks_basic_crud(auth_client, user, bakery):
    url = reverse("tasks-list")

    # WorkoutPlan은 user FK가 있다고 가정 → user 넣기
    workout_plan = bakery.make("tasks.WorkoutPlan", user=user)

    # Exercise에는 user 필드가 없음 → user 제거
    exercise = bakery.make("tasks.Exercise")

    payload = {
        "workout_plan": workout_plan.id,
        "exercise": exercise.id,
        # 선택 필드
        # "duration_min": 30,
        # "order": 1,
    }
    r1 = auth_client.post(url, payload, format="json")
    assert r1.status_code in (200, 201), r1.content
    tid = r1.json()["id"]

    r2 = auth_client.get(reverse("tasks-detail", args=[tid]))
    assert r2.status_code == 200

    r3 = auth_client.patch(reverse("tasks-detail", args=[tid]), {"duration_min": 45}, format="json")
    assert r3.status_code in (200, 202)

    r4 = auth_client.get(url)
    assert r4.status_code == 200

    r5 = auth_client.delete(reverse("tasks-detail", args=[tid]))
    assert r5.status_code in (200, 204)
