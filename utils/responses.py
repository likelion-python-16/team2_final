from rest_framework.response import Response

def ok(data=None, status_code=200):
    return Response({"data": data}, status=status_code)