import os
import time

import requests

HF_TOKEN = os.getenv("HF_TOKEN")
HF_TEXT_MODEL = os.getenv("HF_TEXT_MODEL")
HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "nateraw/food")

# 새 Router 기반 도메인
# 예: https://router.huggingface.co/hf-inference/models/nateraw/food
ROUTER_BASE = "https://router.huggingface.co/hf-inference"


class HFError(Exception):
    pass


def _build_model_url(model_env: str) -> str:
    """
    환경 변수에 전체 URL이 들어있으면 그대로 사용하고,
    모델 아이디만 들어있으면 Router 기반 URL로 변환.
    """
    if not model_env:
        raise HFError("HF model name not set in environment")

    model_env = model_env.strip()
    if model_env.startswith("http://") or model_env.startswith("https://"):
        return model_env

    # 기본 패턴: https://router.huggingface.co/hf-inference/models/{MODEL_ID}
    return f"{ROUTER_BASE}/models/{model_env}"


def hf_text2text(prompt: str, max_new_tokens: int = 180, retries: int = 2) -> str:
    """
    허깅페이스 Hosted Inference API로 텍스트 생성.
    - api-inference.huggingface.co → router.huggingface.co/hf-inference 로 마이그레이션 반영
    - 콜드스타트(503)면 짧게 재시도.
    """
    if not HF_TOKEN:
        raise HFError("HF_TOKEN not set")
    if not HF_TEXT_MODEL:
        raise HFError("HF_TEXT_MODEL not set in .env/.env.prod")

    url = _build_model_url(HF_TEXT_MODEL)
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_new_tokens},
        "options": {"wait_for_model": True},
    }

    last_status = None
    last_body = None

    for i in range(retries + 1):
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        last_status, last_body = r.status_code, r.text

        if r.status_code == 503:
            # 모델 로딩 중 → 잠깐 기다렸다가 재시도
            time.sleep(2 + i)
            continue

        if not r.ok:
            raise HFError(f"HF API error {r.status_code}: {r.text}")

        data = r.json()
        # 다양한 응답 포맷 처리
        if isinstance(data, list) and data and isinstance(data[0], dict):
            if "generated_text" in data[0]:
                return data[0]["generated_text"]
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]

        raise HFError(f"Unexpected HF text API response format: {data}")

    # 여기까지 왔다는 건 503만 반복됐다는 뜻
    raise HFError(f"HF API not ready after retries (last={last_status}: {last_body})")


def hf_image_classify(image_bytes: bytes, top_k: int = 3, retries: int = 2):
    """
    허깅페이스 이미지 분류 API 호출.
    - api-inference.huggingface.co → router.huggingface.co/hf-inference 로 마이그레이션 반영
    """
    if not HF_TOKEN:
        raise HFError("HF_TOKEN not set")
    if not HF_IMAGE_MODEL:
        raise HFError("HF_IMAGE_MODEL not set in .env/.env.prod")

    url = _build_model_url(HF_IMAGE_MODEL)
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/octet-stream",
    }

    last_status = None
    last_body = None

    for i in range(retries + 1):
        r = requests.post(
            url,
            headers=headers,
            params={"wait_for_model": "true"},
            data=image_bytes,
            timeout=60,
        )
        last_status, last_body = r.status_code, r.text

        if r.status_code == 503:
            # 모델 로딩 중
            time.sleep(2 + i)
            continue

        if not r.ok:
            # 410 같은 것도 여기서 바로 에러로 래핑
            raise HFError(f"HF API error {r.status_code}: {r.text}")

        data = r.json()

        # 일반적인 이미지 분류 응답: [{"label": "...", "score": 0.99}, ...]
        if isinstance(data, list):
            predictions = []
            for item in data[:top_k]:
                if not isinstance(item, dict):
                    continue
                label = item.get("label") or item.get("class")
                score = item.get("score") or item.get("confidence", 0)
                if label is None:
                    continue
                predictions.append({"label": label, "score": float(score or 0)})
            if predictions:
                return predictions

        # {"error": "..."} 형태면 재시도 (예: Model is loading)
        if isinstance(data, dict) and "error" in data:
            time.sleep(1)
            continue

        # 여기도 예외적인 포맷
        raise HFError(f"Unexpected HF image API response format: {data}")

    raise HFError(f"HF API not ready after retries (last={last_status}: {last_body})")
