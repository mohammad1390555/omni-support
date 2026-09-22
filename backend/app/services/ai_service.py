import time
import httpx
from typing import List, Dict, Any, Optional

class AIService:
    @staticmethod
    async def test_connection(
        base_url: str,
        api_key: str,
        model_name: str,
        provider_name: str = "Custom"
    ) -> Dict[str, Any]:
        """
        Tests connection to the specified OpenAI-compatible endpoint.
        Measures roundtrip latency and returns the model response.
        """
        clean_base = base_url.rstrip("/")
        endpoint = f"{clean_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
        # If openrouter or specific provider, some require extra headers
        if "openrouter" in clean_base.lower():
            headers["HTTP-Referer"] = "https://omni-support.local"
            headers["X-Title"] = "OmniSupport AI"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a test ping bot. Respond with exactly: 'OK_READY'"},
                {"role": "user", "content": "ping"}
            ],
            "max_tokens": 10,
            "temperature": 0.0
        }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, json=payload, headers=headers)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    return {
                        "success": True,
                        "latency_ms": latency_ms,
                        "message": f"اتصال موفقیت‌آمیز به {provider_name} ({model_name}) با تاخیر {latency_ms}ms",
                        "sample_response": content
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency_ms,
                        "message": f"خطا از طرف ارائه‌دهنده (کد {res.status_code}): {res.text[:200]}",
                        "sample_response": None
                    }
        except httpx.ConnectError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "success": False,
                "latency_ms": latency_ms,
                "message": f"خطا در برقراری ارتباط با آدرس سرور: {base_url}. لطفاً Base URL را بررسی کنید.",
                "sample_response": None
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "latency_ms": 15000,
                "message": "پاسخی از سرور دریافت نشد (Timeout بعد از ۱۵ ثانیه).",
                "sample_response": None
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": 0,
                "message": f"خطای ناشناخته در اتصال: {str(e)}",
                "sample_response": None
            }

    @staticmethod
    async def chat_completion(
        base_url: str,
        api_key: str,
        model_name: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a standard OpenAI-compatible chat completion.
        Supports JSON mode if specified.
        """
        clean_base = base_url.rstrip("/")
        endpoint = f"{clean_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        if "openrouter" in clean_base.lower():
            headers["HTTP-Referer"] = "https://omni-support.local"
            headers["X-Title"] = "OmniSupport AI"

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(endpoint, json=payload, headers=headers)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if res.status_code != 200:
                raise RuntimeError(f"AI Provider error ({res.status_code}): {res.text}")
            
            data = res.json()
            message_obj = data.get("choices", [{}])[0].get("message", {})
            content = message_obj.get("content", "")
            return {
                "content": content,
                "latency_ms": latency_ms,
                "raw": data
            }
