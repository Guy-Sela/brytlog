import json
import urllib.request
import urllib.error

class LLMClient:
    def __init__(self, timeout=30):
        self.timeout = timeout

    def post(self, url: str, data: dict, headers: dict) -> dict:
        """
        Generic POST method with basic error handling.
        """
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                return {"error": {"message": f"HTTP {e.code}: {err_body}"}}
            except:
                return {"error": {"message": f"HTTP Error {e.code}"}}
        except urllib.error.URLError as e:
            return {"error": {"message": f"Network Error: {e.reason}"}}
        except TimeoutError:
            return {"error": {"message": "Request timed out"}}
        except Exception as e:
            return {"error": {"message": str(e)}}

def get_client():
    return LLMClient()
