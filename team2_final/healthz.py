from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["GET"])
def healthz(_):
    return Response({"status": "ok"})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
import json

@csrf_exempt
@require_POST
def simple_token(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('invalid json')
    username = data.get('username','')
    password = data.get('password','')
    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse({'error': {'code':'unauthorized','message':'invalid credentials','status_code':401}}, status=401)
    refresh = RefreshToken.for_user(user)
    return JsonResponse({'access': str(refresh.access_token), 'refresh': str(refresh)})
