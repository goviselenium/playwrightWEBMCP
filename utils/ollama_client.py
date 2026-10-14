"""
Ollama Local LLM Client Utility.

Provides programmatic interaction with a locally hosted Ollama instance (http://localhost:11434)
to perform smart assertions, DOM accessibility audits, WebMCP tool recommendation,
and autonomous heuristic test evaluations.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OllamaEvaluationResult(BaseModel):
    """Structured evaluation returned by Ollama."""
    passed: bool = Field(..., description="Whether the heuristic or assertion passed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    reasoning: str = Field(default="", description="Chain-of-thought or explanation")
    suggested_action: Optional[str] = Field(default=None, description="Recommended next action if any")
    raw_response: Dict[str, Any] = Field(default_factory=dict, description="Raw JSON model output")


class OllamaClient:
    """
    Client interface for local Ollama server integration.
    Defaults to http://localhost:11434 with llama3.2:latest.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2:latest",
        timeout: int = 90
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", timeout))
        self._cached_available_models: Optional[List[str]] = None

    def is_healthy(self) -> bool:
        """Verify Ollama server accessibility."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        """Fetch all locally pulled model names from Ollama."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                self._cached_available_models = models
                return models
        except Exception as e:
            logger.warning(f"Failed to fetch Ollama model tags: {e}")
        return []

    def resolve_model(self, requested_model: Optional[str] = None) -> str:
        """
        Resolve requested model name, falling back to installed models if exact match isn't available.
        """
        available = self.get_available_models()
        target = requested_model or self.default_model

        if not available:
            return target  # Best effort if list call failed

        # Exact match
        if target in available:
            return target

        # Prefix / partial match (e.g. 'llama3.2' matches 'llama3.2:latest')
        for m in available:
            if m.startswith(target) or target.startswith(m.split(":")[0]):
                return m

        # Priority fallback chain
        for fallback in ["llama3.2:latest", "llama3:latest", "qwen2.5:latest", "Qwen3:latest", "mistral:latest"]:
            if fallback in available:
                logger.info(f"Model '{target}' not found. Falling back to '{fallback}'.")
                return fallback

        # Default to first available
        return available[0]

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        enforce_json: bool = True
    ) -> Dict[str, Any]:
        """
        Dispatch a generation request to the Ollama /api/generate endpoint.
        
        Args:
            prompt: User/Task prompt.
            system_prompt: Optional steering instructions.
            model: Specific model or None for default.
            enforce_json: Force JSON schema output mode.
            
        Returns:
            Dict[str, Any] parsed from response.
        """
        active_model = self.resolve_model(model)
        payload: Dict[str, Any] = {
            "model": active_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic assertions
                "top_p": 0.9
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if enforce_json:
            payload["format"] = "json"

        try:
            res = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            res.raise_for_status()
            raw_text = res.json().get("response", "{}")

            # Parse JSON safely
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                # Attempt to extract markdown code blocks if wrapped
                if "```json" in raw_text:
                    cleaned = raw_text.split("```json")[1].split("```")[0].strip()
                    return json.loads(cleaned)
                return {"raw_text": raw_text, "parse_error": True}

        except Exception as e:
            logger.error(f"Ollama generation request failed: {e}")
            raise RuntimeError(f"Ollama connection error: {str(e)}")

    def evaluate_accessibility_tree(
        self,
        accessibility_snapshot: Any,
        page_url: str,
        criteria: Optional[str] = None,
        model: Optional[str] = None
    ) -> OllamaEvaluationResult:
        """
        Audit a Playwright accessibility snapshot using local Ollama.
        Supports both modern Playwright aria_snapshot strings and dictionary trees.
        """
        if isinstance(accessibility_snapshot, str):
            compressed_tree_str = accessibility_snapshot[:3000]
        else:
            compressed_tree_str = json.dumps(accessibility_snapshot, default=str)[:3000]

        sys_prompt = (
            "You are a Web Accessibility QA Automation Engineer. "
            "Analyze the page accessibility structure. "
            "Return JSON: {\"passed\": true, \"confidence\": 0.95, \"reasoning\": \"...\", \"suggested_action\": \"...\"}"
        )

        user_prompt = f"""
        Page URL: {page_url}
        Criteria: {criteria or 'Check that page has accessible controls and clear landmarks.'}
        
        Accessibility Structure:
        {compressed_tree_str}
        
        Respond ONLY with a JSON object.
        """

        try:
            output = self.generate(prompt=user_prompt, system_prompt=sys_prompt, model=model)
            return OllamaEvaluationResult(
                passed=bool(output.get("passed", True)),
                confidence=float(output.get("confidence", 0.9)),
                reasoning=str(output.get("reasoning", "Accessibility evaluated successfully.")),
                suggested_action=output.get("suggested_action"),
                raw_response=output
            )
        except Exception as e:
            return OllamaEvaluationResult(
                passed=False,
                confidence=0.0,
                reasoning=f"Ollama evaluation failed due to error: {e}",
                raw_response={"error": str(e)}
            )

    def evaluate_webmcp_decision(
        self,
        goal: str,
        tools: List[Dict[str, Any]],
        page_state: Dict[str, Any],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ask Ollama to autonomously select and parameterize a WebMCP tool based on a user goal.
        """
        sys_prompt = (
            "You are an AI Agent interacting with WebMCP tools. "
            "Given a goal and available tools, pick the best tool to invoke. "
            "Output JSON format: {\"tool\": \"<tool_name>\", \"arguments\": {\"<arg>\": \"<val>\"}, \"reasoning\": \"...\", \"confidence\": 0.95}"
        )

        # Compact summary of tools
        compact_tools = []
        for t in tools:
            compact_tools.append({
                "name": t.get("name"),
                "description": t.get("description"),
                "parameters": t.get("parameters", {}).get("properties", {})
            })

        user_prompt = f"""
        Goal: {goal}
        
        Available Tools:
        {json.dumps(compact_tools, indent=2)}
        
        Return ONLY valid JSON with 'tool', 'arguments', 'reasoning', and 'confidence'.
        """

        return self.generate(prompt=user_prompt, system_prompt=sys_prompt, model=model)

    def smart_assertion(
        self,
        assertion_description: str,
        observed_data: Any,
        model: Optional[str] = None
    ) -> OllamaEvaluationResult:
        """
        Perform an AI-driven smart assertion comparing observed page data against expected behavior.
        """
        sys_prompt = (
            "You are an automated test assertion oracle. "
            "Evaluate whether the observed application data satisfies the assertion requirement. "
            "Respond strictly in JSON with 'passed' (bool), 'reasoning' (string), and 'confidence' (float)."
        )

        user_prompt = f"""
        Requirement: {assertion_description}
        Observed Data:
        {json.dumps(observed_data, default=str)[:3000]}
        """

        try:
            output = self.generate(prompt=user_prompt, system_prompt=sys_prompt, model=model)
            return OllamaEvaluationResult(
                passed=bool(output.get("passed", False)),
                confidence=float(output.get("confidence", 0.85)),
                reasoning=str(output.get("reasoning", "")),
                raw_response=output
            )
        except Exception as e:
            return OllamaEvaluationResult(
                passed=False,
                confidence=0.0,
                reasoning=f"Smart assertion failed with error: {e}",
                raw_response={"error": str(e)}
            )
