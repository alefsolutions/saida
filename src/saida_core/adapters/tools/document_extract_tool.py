from __future__ import annotations

from saida_core.core.contracts.tool import Tool


class DocumentExtractTool(Tool):
    name = "document_extract"

    def run(self, payload: dict) -> dict:
        text = payload.get("text", "")
        return {"tool": self.name, "length": len(text), "preview": text[:160]}