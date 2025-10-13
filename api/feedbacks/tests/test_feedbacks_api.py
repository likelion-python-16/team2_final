import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_feedbacks_crud(auth_client):
    url = reverse("feedbacks-list")

    # CREATE (user 자동주입, message만 필수)
    r1 = auth_client.post(url, {"message": "테스트 피드백"}, format="json")
    assert r1.status_code in (200, 201), r1.content
    fid = r1.json()["id"]

    # RETRIEVE
    r2 = auth_client.get(reverse("feedbacks-detail", args=[fid]))
    assert r2.status_code == 200

    # PATCH
    r3 = auth_client.patch(reverse("feedbacks-detail", args=[fid]),
                           {"message": "수정됨"}, format="json")
    assert r3.status_code in (200, 202)

    # LIST
    r4 = auth_client.get(url)
    assert r4.status_code == 200

    # DELETE
    r5 = auth_client.delete(reverse("feedbacks-detail", args=[fid]))
    assert r5.status_code in (200, 204)
