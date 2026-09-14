# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
LLM Orchestrator — 2-tier fallback (Ollama → Raw FTS5 excerpts).

The GM Storyteller can call these agent tools:
- Rules Lawyer: lookup_rule, calculate_dc, validate_action
- NPC Compiler: create_npc, save_npc_to_db, level_up
- Continuity Keeper: process_session, get_campaign_context
"""

import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.rag.retriever import Retriever
from app.rag.raw_fallback import search_rules
from app.agents.rules_lawyer import RulesLawyerAgent, RULES_LAWYER_TOOLS
from app.agents.npc_compiler import NPCCompilerAgent, NPC_COMPILER_TOOLS
# ContinuityKeeper imported lazily to avoid circular import

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    answer: str
    backend: str  # "ollama" | "raw-excerpts"
    mode: str
    edition: str
    sources: list[dict]


class LLMOrchestrator:
    def __init__(self, repo: CampaignRepository):
        self.repo = repo
        self.settings = get_settings()
        self.ollama = OllamaClient(self.settings.ollama_host)
        self.retriever = Retriever(repo)

        # Sub-agents (called as tools by GM Storyteller)
        self.rules_lawyer = RulesLawyerAgent(repo)
        self.npc_compiler = NPCCompilerAgent(repo)
        # Lazy import to avoid circular dependency
        from app.agents.continuity import ContinuityKeeper
        self.continuity_keeper = ContinuityKeeper(repo, self)

    # ──────────────────────────────────────────────────────────────
    # Main Generation Entry Point
    # ──────────────────────────────────────────────────────────────

    def _supports_tools(self, model: str) -> bool:
        """qwen2.5 family natively supports ReAct tool calling; phi4-mini does not reliably."""
        m = model.lower()
        return "qwen" in m or "tool" in m or "mistral" in m

    async def _agentic_chat(
        self,
        prompt: str,
        system: str,
        original_prompt: str,
        edition: str,
        tools: list[dict],
    ) -> str:
        """3-turn ReAct loop for tool-capable models (qwen2.5:3b Q4_K_M).

        Turn 1: model decides tool_calls → Turn 2: execute tools → Turn 3: narrative.
        Falls back to single generate if no tool_calls.
        Gemini §15.3 minimal loop, adapted to async httpx + our repo tools.
        """
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        # Turn 1
        msg1 = await self.ollama.chat(
            messages=messages,
            model=self.settings.ollama_model,
            tools=tools,
            temperature=self.settings.ollama_temperature,
            num_predict=self.settings.ollama_num_predict,
        )
        # Ollama returns {role, content, tool_calls: [{function:{name, arguments}}]}
        tool_calls = msg1.get("tool_calls") or []
        if not tool_calls:
            # No tool needed — direct answer
            return msg1.get("content", "")

        messages.append(msg1)
        # Turn 2: execute each tool
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            # Ollama may return arguments as JSON string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = await self.handle_tool_call(name, args)
            # Tool result as 'tool' role (Ollama expects role=tool, content=json)
            messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False), "name": name})

        # Turn 3: final narrative
        msg3 = await self.ollama.chat(
            messages=messages,
            model=self.settings.ollama_model,
            temperature=self.settings.ollama_temperature,
            num_predict=self.settings.ollama_num_predict,
        )
        return msg3.get("content", "") or msg1.get("content", "")

    async def generate(
        self,
        prompt: str,
        edition: str,
        mode: str | None = None,
        history: list[list[str]] | None = None,
    ) -> LLMResult:
        # Build system prompt with available tools
        system = self._build_system_prompt(mode, edition)
        original_prompt = prompt  # Save original for fallback

        # Tier 1: Ollama with RAG + Agent Tools
        try:
            if self.settings.rag_enabled:
                context = await self.retriever.query(prompt, edition=edition, k=self.settings.rag_limit)
                prompt = self._build_rag_prompt(prompt, context, edition, mode)

            # Prepare tool definitions for Ollama
            tools = RULES_LAWYER_TOOLS + NPC_COMPILER_TOOLS + [
                {
                    "type": "function",
                    "function": {
                        "name": "process_session",
                        "description": "Process a session log for continuity (entity extraction, summary, facts)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "campaign_id": {"type": "integer"},
                                "session_num": {"type": "integer"},
                                "session_log": {"type": "string"}
                            },
                            "required": ["campaign_id", "session_num", "session_log"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_campaign_context",
                        "description": "Get campaign context for next session (summary + relevant entities)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "campaign_id": {"type": "integer"}
                            },
                            "required": ["campaign_id"]
                        }
                    }
                }
            ]

            # Use agentic ReAct loop for qwen2.5:3b (5-7 tok/s → 8-11 tok/s with Q4), keep single generate for phi4-mini
            if self._supports_tools(self.settings.ollama_model):
                answer = await self._agentic_chat(prompt, system, original_prompt, edition, tools)
            else:
                answer = await self.ollama.generate(
                    prompt=prompt,
                    system=system,
                    model=self.settings.ollama_model,
                    temperature=self.settings.ollama_temperature,
                    num_predict=self.settings.ollama_num_predict,
                )

            # Get sources from RAG using original prompt to avoid FTS5 syntax errors
            sources = await self.retriever.get_sources(original_prompt, edition=edition, k=5)

            return LLMResult(
                answer=answer,
                backend="ollama",
                mode=mode or "auto",
                edition=edition,
                sources=sources,
            )

        except Exception as e:
            logger.warning(f"Ollama failed: {e}, falling back to raw excerpts")

        # Tier 2: Raw rule excerpts (always works)
        # Use the original prompt, not the augmented prompt, to avoid FTS5 syntax errors
        hits = await search_rules(original_prompt, edition=edition, limit=5, repo=self.repo)
        answer = self._format_raw_excerpts(hits, original_prompt)
        sources = [
            {"name": h["name"], "content": h["content"][:200], "source_book": h.get("source_book", "")}
            for h in hits
        ]

        return LLMResult(
            answer=answer,
            backend="raw-excerpts",
            mode=mode or "auto",
            edition=edition,
            sources=sources,
        )

    # ──────────────────────────────────────────────────────────────
    # Tool Handlers (called when Ollama invokes a tool)
    # ──────────────────────────────────────────────────────────────

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call and return result."""
        try:
            if tool_name == "lookup_rule":
                return await self.rules_lawyer.lookup_rule(arguments["query"])
            elif tool_name == "calculate_dc":
                return await self.rules_lawyer.calculate_dc(
                    arguments["level"],
                    arguments.get("rarity", "common"),
                    arguments.get("proficiency", "trained")
                )
            elif tool_name == "validate_action":
                return await self.rules_lawyer.validate_action(
                    arguments["action"],
                    arguments["character_sheet"],
                    arguments.get("target")
                )
            elif tool_name == "create_npc":
                return await self.npc_compiler.create_npc(arguments["concept"])
            elif tool_name == "save_npc_to_db":
                return await self.npc_compiler.save_npc_to_db(arguments["npc_json"])
            elif tool_name == "level_up":
                return await self.npc_compiler.level_up(arguments["character_id"])
            elif tool_name == "process_session":
                return await self.continuity_keeper.process_session(
                    arguments["campaign_id"],
                    arguments["session_num"],
                    arguments["session_log"]
                )
            elif tool_name == "get_campaign_context":
                return self.continuity_keeper.get_campaign_context(arguments["campaign_id"])
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}

    async def stream(
        self,
        prompt: str,
        edition: str,
        mode: str | None = None,
        history: list[list[str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama."""
        system = self._build_system_prompt(mode, edition)

        try:
            if self.settings.rag_enabled:
                context = await self.retriever.query(prompt, edition=edition, k=self.settings.rag_limit)
                prompt = self._build_rag_prompt(prompt, context, edition, mode)

            async for chunk in self.ollama.stream(
                prompt=prompt,
                system=system,
                model=self.settings.ollama_model,
            ):
                yield chunk

        except Exception as e:
            logger.warning(f"Ollama stream failed: {e}")
            yield f"\n\n[Error: {e}]"

    # ──────────────────────────────────────────────────────────────
    # Prompt Builders
    # ──────────────────────────────────────────────────────────────

    def _build_system_prompt(self, mode: str | None, edition: str) -> str:
        mode_desc = {
            "character": "Generate a complete Player Character with full backstory.",
            "npc": "Generate a complete NPC with stat block, personality, and hooks.",
            "monster": "Generate a bestiary entry with stats, tactics, and lore.",
            "boss": "Generate a boss encounter with lair, minions, phases, and dramatic arc.",
            "map": "Generate a theater-of-mind map with zones, hazards, and secrets.",
            "campaign": "Generate a campaign premise with arcs, factions, and timeline.",
            "encounter": "Generate a balanced encounter with XP budget, terrain, and tactics.",
        }.get(mode, "Act as the Pathfinder GM.")

        return f"""You are the Pathfinder God — a master GM with perfect rules knowledge for Pathfinder {edition.upper()}e.
{mode_desc}

You have access to specialist agents as tools. Use them:
- Rules Lawyer: For ANY rules question. NEVER guess. Call lookup_rule first.
- NPC Compiler: For generating NPCs/characters. Outputs legal ABC stat blocks.
- Continuity Keeper: For campaign memory. Call process_session after each session.

Workflow for a player action:
1. Player declares action (e.g., "I Trip the ogre")
2. Call Rules Lawyer validate_action with action + character sheet
3. Rules Lawyer returns legal/illegal + rule citation
4. You narrate using the exact rule from the citation

Workflow for generation requests:
1. Call appropriate agent tool (create_npc, etc.)
2. Agent returns structured JSON
3. You format it narratively for the player

Be concise but evocative. Never hallucinate rules — if unsure, call the tool.

Citation Fidelity (MANDATORY):
- Cite your sources using the exact format: [Source Book - Rule Name].
- You must summarize mechanics in 3 sentences or less.
- Do not reproduce stat blocks verbatim or copy more than 300 chars from any source.
- Prefer summarization over quotation to respect ORC licensing."""

    def _build_rag_prompt(self, prompt: str, context: list[dict], edition: str, mode: str | None) -> str:
        context_text = "\n\n---\n\n".join(
            f"[{c.get('source_book', 'Unknown')}] {c.get('name', 'Rule')}: {c.get('content', '')[:500]}"
            for c in context
        )
        return f"""Context from rulebooks:
{context_text}

User request: {prompt}"""

    def _format_raw_excerpts(self, hits: list[dict], query: str) -> str:
        if not hits:
            return f"No rules found for '{query}'. Try a different search term."

        lines = [f"Raw rule excerpts for '{query}':\n"]
        for i, hit in enumerate(hits, 1):
            lines.append(
                f"{i}. **{hit['name']}** ({hit.get('system', '?')}) — {hit.get('source_book', 'Unknown')}\n"
                f"   {hit['content'][:300]}..."
            )
        return "\n".join(lines)