import pytest
from django.urls import reverse
from datetime import date

@pytest.mark.django_db
def test_intakes_crud(auth_client):
    url = reverse("intakes-list")

    # CREATE (필수: date만)
    payload = {"date": date.today().isoformat()}
    r1 = auth_client.post(url, payload, format="json")
    assert r1.status_code in (200, 201), r1.content
    nid = r1.json()["id"]

    # RETRIEVE
    r2 = auth_client.get(reverse("intakes-detail", args=[nid]))
    assert r2.status_code == 200

    # PATCH (옵션 필드 아무거나)
    r3 = auth_client.patch(reverse("intakes-detail", args=[nid]),
                           {"kcal_total": 500}, format="json")
    assert r3.status_code in (200, 202)

    # LIST
    r4 = auth_client.get(url)
    assert r4.status_code == 200

    # DELETE
    r5 = auth_client.delete(reverse("intakes-detail", args=[nid]))
    assert r5.status_code in (200, 204)
