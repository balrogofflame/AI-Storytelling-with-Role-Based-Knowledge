"""Small, server-only OpenAI Responses client; no third-party dependencies."""

import json
import os
import socket
from urllib import error, request

API_URL = "https://api.openai.com/v1/responses"


class AppError(Exception):
    def __init__(self, code, message, status=503):
        super().__init__(message)
        self.code = code
        self.status = status


def configuration_status():
    return {
        "key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "model_configured": bool(os.getenv("OPENAI_MODEL", "").strip()),
    }


def read_configuration():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not key:
        raise AppError("missing_key", "尚未設定 API 金鑰，請使用 start.ps1 在本機輸入。")
    if not model:
        raise AppError("missing_model", "尚未設定模型名稱，請使用 start.ps1 在本機輸入。")
    if any(c.isspace() for c in key) or not key.isascii():
        raise AppError("invalid_key", "金鑰格式不正確，請重新複製 API 金鑰。")
    if len(model) > 200 or any(c.isspace() for c in model) or not model.isascii():
        raise AppError("invalid_model", "模型名稱格式不正確，請填入帳號可用的模型 ID。")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if base_url != "https://api.openai.com/v1":
        raise AppError("unsupported_endpoint", "此版本使用 OpenAI 官方服務，請移除 OPENAI_BASE_URL 設定。")
    return key, model


def provider_error(status, body):
    try:
        detail = json.loads(body).get("error", {})
        code, kind = detail.get("code"), detail.get("type")
    except (ValueError, AttributeError):
        code, kind = None, None
    if status == 401:
        return AppError("authentication", "API 金鑰無效或已失效，請在平台檢查金鑰。")
    if status in (403, 404):
        return AppError("model_access", "無法使用此模型或服務，請檢查模型名稱、專案權限及帳號狀態。")
    if status == 429:
        if kind == "insufficient_quota" or code in {
            "insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached",
            "billing_limit_reached", "monthly_budget_exceeded", "usage_limit_reached",
        }:
            return AppError("quota", "API 額度或用量上限不足，請檢查 API 平台的帳務與限制。")
        return AppError("rate_limit", "AI 請求過於頻繁，請稍後手動重試。", 429)
    if status == 400:
        return AppError("request_rejected", "模型不接受本次請求，請確認模型支援 Responses API。")
    return AppError("provider_unavailable", "AI 服務暫時無法使用，請稍後手動重試。")


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def generate(instructions, question, *, schema=None):
    key, model = read_configuration()
    payload = {
        "model": model,
        "instructions": instructions,
        "input": [{"role": "user", "content": question}],
        "store": False,
        "max_output_tokens": 2048,
    }
    if model == "gpt-6-luna":
        # This demo only needs short answers grounded in a few facts.
        payload["reasoning"] = {"effort": "none"}
        payload["max_output_tokens"] = 512
    if schema is not None:
        payload["text"] = {"format": {
            "type": "json_schema", "name": "scenario_additions", "strict": True,
            "schema": schema,
        }}
        payload["max_output_tokens"] = 1024
    req = request.Request(API_URL, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }, method="POST")
    try:
        # Do not forward credentials to redirected hosts. No automatic paid retries.
        with request.build_opener(NoRedirect()).open(req, timeout=45) as response:
            data = json.load(response)
    except error.HTTPError as exc:
        raise provider_error(exc.code, exc.read(65536)) from None
    except (TimeoutError, socket.timeout):
        raise AppError("timeout", "AI 等待逾時，請稍後手動重試；此請求仍可能產生費用。", 504) from None
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise AppError("timeout", "AI 等待逾時，請稍後手動重試。", 504) from None
        raise AppError("connection", "無法連線到 AI，請檢查網路、代理伺服器與憑證設定。") from None
    except (ValueError, OSError):
        raise AppError("invalid_response", "無法讀取 AI 回應，請稍後手動重試。", 502) from None
    if not isinstance(data, dict) or data.get("status") != "completed":
        raise AppError("incomplete", "AI 未完成回答，請稍後手動重試或檢查模型設定。", 502)
    texts = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    answer = "\n".join(texts).strip()
    actual_model = data.get("model")
    if not answer or not isinstance(actual_model, str) or not actual_model:
        raise AppError("empty_response", "AI 未回傳文字或模型名稱，請檢查模型設定。", 502)
    return {"answer": answer, "model": actual_model}


def generate_json(instructions, question, schema):
    result = generate(instructions, question, schema=schema)
    try:
        data = json.loads(result["answer"])
    except (ValueError, TypeError):
        raise AppError("invalid_plan", "AI 回傳的新增設定格式不正確，未寫入檔案。", 502) from None
    return {"data": data, "model": result["model"]}
