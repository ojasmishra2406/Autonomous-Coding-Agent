import os
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class ModelResponse:
    def __init__(
        self, 
        text: Optional[str] = None,
        function_calls: Optional[List[Dict[str, Any]]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        thoughts_tokens: int = 0
    ):
        self.text = text
        self.function_calls = function_calls or []
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.thoughts_tokens = thoughts_tokens

class Provider(ABC):
    def __init__(self):
        with open(os.path.join("src", "tool_schemas.json")) as f:
            self.raw_schemas = json.load(f)

    @abstractmethod
    def call_model(self, history: List[Dict[str, Any]], system_prompt: str) -> ModelResponse:
        pass

class GeminiProvider(Provider):
    def __init__(self, model_name="gemini-3.7-flash"):
        super().__init__()
        from google import genai
        from google.genai import types
        self.model_name = model_name
        self.client = genai.Client()
        self.types = types
        self.tool = types.Tool(function_declarations=[
            types.FunctionDeclaration(**s) for s in self.raw_schemas
        ])
    
    def call_model(self, history: List[Dict[str, Any]], system_prompt: str) -> ModelResponse:
        gemini_history = []
        for msg in history:
            role = msg["role"]
            if role == "user":
                gemini_history.append(self.types.Content(role="user", parts=[self.types.Part.from_text(text=msg["content"])]))
            elif role == "assistant":
                parts = []
                if msg.get("content"):
                    parts.append(self.types.Part.from_text(text=msg["content"]))
                for tc in msg.get("tool_calls", []):
                    parts.append(self.types.Part.from_function_call(name=tc["name"], args=tc["args"]))
                if parts:
                    gemini_history.append(self.types.Content(role="model", parts=parts))
            elif role == "tool":
                func_resp = self.types.FunctionResponse(name=msg["name"], response={"result": msg["content"]}, id=msg.get("tool_call_id"))
                gemini_history.append(self.types.Content(role="user", parts=[self.types.Part(function_response=func_resp)]))

        config = self.types.GenerateContentConfig(
            system_instruction=self.types.Content(role="system", parts=[self.types.Part.from_text(text=system_prompt)]),
            tools=[self.tool],
            temperature=0.0
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=gemini_history,
            config=config
        )
        
        text = ""
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for p in response.candidates[0].content.parts:
                if p.text:
                    text += p.text
                if p.function_call:
                    args = p.function_call.args if isinstance(p.function_call.args, dict) else dict(p.function_call.args) if p.function_call.args else {}
                    function_calls.append({
                        "id": p.function_call.id or "",
                        "name": p.function_call.name,
                        "args": args
                    })
                    
        in_tok = out_tok = th_tok = 0
        if response.usage_metadata:
            in_tok = response.usage_metadata.prompt_token_count
            out_tok = response.usage_metadata.candidates_token_count
            th_tok = getattr(response.usage_metadata, 'thoughts_token_count', 0)
            
        return ModelResponse(
            text=text,
            function_calls=function_calls,
            input_tokens=in_tok,
            output_tokens=out_tok,
            thoughts_tokens=th_tok
        )

class GroqProvider(Provider):
    def __init__(self, model_name: str = None):
        super().__init__()
        from openai import OpenAI
        self.model_name = model_name or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        # Convert schema to OpenAI format (requires lowercase types)
        def _convert_schema(schema_obj):
            if isinstance(schema_obj, dict):
                new_obj = {}
                for k, v in schema_obj.items():
                    if k == "type" and isinstance(v, str):
                        new_obj[k] = v.lower()
                    else:
                        new_obj[k] = _convert_schema(v)
                return new_obj
            elif isinstance(schema_obj, list):
                return [_convert_schema(item) for item in schema_obj]
            return schema_obj

        self.tools = []
        for s in self.raw_schemas:
            self.tools.append({
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "parameters": _convert_schema(s.get("parameters", {"type": "object", "properties": {}}))
                }
            })
            
    def call_model(self, history: List[Dict[str, Any]], system_prompt: str) -> ModelResponse:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                m = {"role": "assistant", "content": msg.get("content") or ""}
                
                tcs = []
                for tc in msg.get("tool_calls", []):
                    import json
                    tcs.append({
                        "id": tc.get("id") or "call_0",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"])
                        }
                    })
                if tcs:
                    m["tool_calls"] = tcs
                messages.append(m)
            elif msg["role"] == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id") or "call_0",
                    "name": msg["name"],
                    "content": json.dumps(msg["content"]) if isinstance(msg["content"], dict) else str(msg["content"])
                })
                
        # Retry up to 4 times with exponential backoff for transient Groq errors
        last_exc = None
        for attempt in range(4):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.tools,
                    temperature=0.0
                )
                last_exc = None
                break
            except Exception as e:
                last_exc = e
                err_str = str(e).lower()
                # Retry on transient errors: rate limits, empty output, server errors
                if any(k in err_str for k in ("rate_limit", "429", "503", "model output", "overloaded", "timeout")):
                    wait = 5 * (2 ** attempt)
                    print(f"[GroqProvider] Transient error (attempt {attempt+1}/4), retrying in {wait}s: {str(e)[:120]}")
                    time.sleep(wait)
                else:
                    raise  # non-retriable error, propagate immediately
        if last_exc is not None:
            raise last_exc
        
        choice = response.choices[0].message
        
        text = choice.content or ""
        function_calls = []
        if choice.tool_calls:
            import json
            for tc in choice.tool_calls:
                function_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if tc.function.arguments else {}
                })
                
        in_tok = out_tok = th_tok = 0
        if response.usage:
            in_tok = response.usage.prompt_tokens
            out_tok = response.usage.completion_tokens
            th_tok = 0
            
        return ModelResponse(
            text=text,
            function_calls=function_calls,
            input_tokens=in_tok,
            output_tokens=out_tok,
            thoughts_tokens=th_tok
        )

class CerebrasProvider(GroqProvider):
    def __init__(self, model_name: str = "gpt-oss-120b"):
        Provider.__init__(self)  # skips GroqProvider init which requires GROQ_API_KEY
        from openai import OpenAI
        self.model_name = os.environ.get("CEREBRAS_MODEL", model_name)
        self.client = OpenAI(
            base_url="https://api.cerebras.ai/v1",
            api_key=os.environ.get("CEREBRAS_API_KEY")
        )
        
        def _convert_schema(schema_obj):
            if isinstance(schema_obj, dict):
                new_obj = {}
                for k, v in schema_obj.items():
                    if k == "type" and isinstance(v, str):
                        new_obj[k] = v.lower()
                    else:
                        new_obj[k] = _convert_schema(v)
                return new_obj
            elif isinstance(schema_obj, list):
                return [_convert_schema(item) for item in schema_obj]
            return schema_obj

        self.tools = []
        for s in self.raw_schemas:
            self.tools.append({
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "parameters": _convert_schema(s.get("parameters", {}))
                }
            })

class MistralProvider(GroqProvider):
    def __init__(self, model_name: str = "codestral-latest"):
        Provider.__init__(self)
        from openai import OpenAI
        self.model_name = os.environ.get("MISTRAL_MODEL", model_name)
        self.client = OpenAI(
            base_url="https://api.mistral.ai/v1",
            api_key=os.environ.get("MISTRAL_API_KEY")
        )
        
        def _convert_schema(schema_obj):
            if isinstance(schema_obj, dict):
                new_obj = {}
                for k, v in schema_obj.items():
                    if k == "type" and isinstance(v, str):
                        new_obj[k] = v.lower()
                    else:
                        new_obj[k] = _convert_schema(v)
                return new_obj
            elif isinstance(schema_obj, list):
                return [_convert_schema(item) for item in schema_obj]
            return schema_obj

        self.tools = []
        for s in self.raw_schemas:
            self.tools.append({
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "parameters": _convert_schema(s.get("parameters", {}))
                }
            })
