# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
LLM Orchestrator â€” 2-tier fallback (Ollama â†’ Raw FTS5 excerpts).

The GM Storyteller can call these agent tools:
- Rules Lawyer: lookup_rule, calculate_dc, validate_action
- NPC Compiler: create_npc, save_npc_to_db, level_up
- Continuity Keeper: process_session, get_campaign_context
"""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from app.agents.npc_compiler import NPC_COMPILER_TOOLS, NPCCompilerAgent
from app.agents.rules_lawyer import RULES_LAWYER_TOOLS, RulesLawyerAgent
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.rag.raw_fallback import search_rules
from app.rag.retriever import Retriever

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

    async def close(self) -> None:
        """Release the httpx clients this orchestrator owns.

        An orchestrator is built per request (/ask, /generate/{kind}, the
        continuity background task) and each one lazily created its own
        httpx.AsyncClient, whose socket pool was never closed. That
        accumulated connections and file handles for the life of the process.
        """
        for holder in (
            getattr(self, "ollama", None),
            getattr(self, "rules_lawyer", None),
            getattr(self, "npc_compiler", None),
        ):
            client = getattr(holder, "ollama", None)
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    logger.debug("failed to close an Ollama client", exc_info=True)

    async def __aenter__(self) -> "LLMOrchestrator":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Main Generation Entry Point
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        Turn 1: model decides tool_calls â†’ Turn 2: execute tools â†’ Turn 3: narrative.
        Falls back to single generate if no tool_calls.
        Gemini Â§15.3 minimal loop, adapted to async httpx + our repo tools.
        """
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        # Turn 1
        msg1 = await self.ollama.chat(
            messages=messages,
            model=self.settings.model_for("chat"),
            tools=tools,
            temperature=self.settings.ollama_temperature,
            num_predict=self.settings.ollama_num_predict,
        )
        # Ollama returns {role, content, tool_calls: [{function:{name, arguments}}]}
        tool_calls = msg1.get("tool_calls") or []
        if not tool_calls:
            # No tool needed â€” direct answer
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
            model=self.settings.model_for("chat"),
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
                prompt = self._build_rag_prompt(prompt, context, edition, mode, history)

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

            # Use agentic ReAct loop for qwen2.5:3b (5-7 tok/s â†’ 8-11 tok/s with Q4), keep single generate for phi4-mini
            if self._supports_tools(self.settings.model_for("chat")):
                answer = await self._agentic_chat(prompt, system, original_prompt, edition, tools)
            else:
                answer = await self.ollama.generate(
                    prompt=prompt,
                    system=system,
                    model=self.settings.model_for("chat"),
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

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Tool Handlers (called when Ollama invokes a tool)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Stream tokens, yielding (backend, chunk).

        Previously this yielded bare strings and, on failure, yielded the text
        "[Error: ...]". Two bugs came out of that: ask.py hard-coded
        backend="ollama" on every frame, so an error or a fallback was labelled
        as an LLM answer; and the documented offline FTS5 fallback never ran at
        all here, unlike on /ask, so /stream answered nothing useful with Ollama
        down. Now it yields the same raw-excerpts fallback generate() uses.
        """
        system = self._build_system_prompt(mode, edition)

        try:
            if self.settings.rag_enabled:
                context = await self.retriever.query(prompt, edition=edition, k=self.settings.rag_limit)
                prompt = self._build_rag_prompt(prompt, context, edition, mode, history)

            async for chunk in self.ollama.stream(
                prompt=prompt,
                system=system,
                model=self.settings.model_for("chat"),
            ):
                yield ("ollama", chunk)

        except Exception as e:
            logger.warning(f"Ollama stream failed: {e}")
            try:
                from app.rag.raw_fallback import search_rules
                hits = await search_rules(prompt, edition=edition, limit=5, repo=self.repo)
                yield ("raw-excerpts", self._format_raw_excerpts(hits, prompt))
            except Exception as inner:
                logger.warning(f"raw fallback also failed: {inner}")
                yield ("error", f"[Error: {e}]")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Prompt Builders
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        return f"""You are the Pathfinder God â€” a master GM with perfect rules knowledge for Pathfinder {edition.upper()}e.
{mode_desc}

You are a PLAYER'S GM, not a rule server. Your job is to run the table, so:
- Speak like a GM narrating a session. Set the scene, then hand the next decision to the players.
- Never do a player's thinking for them. End every player-turn reply by asking "What do you do?" or offering 2-3 concrete options.
- In combat: track initiative order, current HP, active conditions, and the next whose turn it is. If a roll is needed, call for it before ruling.
- Keep it tight at the table: 2-4 sentences of narration per reply; expand into descriptive pros only when the players ask or when a scene change makes it necessary.
- Let house-ruled stakes drive the rules. When a ruling matters, ground it with a Lookup_Rule citation; when it does not, just narrate.
- Offer rolls where the fiction is ambiguous (concealment, darkness, surprising an NPC) instead of pre-deciding outcomes.
- When the players ask a question about their own characters or the clock, answer from the actual campaign ledger, not from generic knowledge.

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

Be concise but evocative. Never hallucinate rules â€” if unsure, call the tool.

Citation Fidelity (MANDATORY):
- Cite your sources using the exact format: [Source Book - Rule Name].
- You must summarize mechanics in 3 sentences or less.
- Do not reproduce stat blocks verbatim or copy more than 300 chars from any source.
- Prefer summarization over quotation to respect ORC licensing."""

    def _history_block(self, history: list[list[str]] | None) -> str:
        """Render prior turns, mirroring the CLI path in agent/gm.py.

        /ask and /stream both accepted and validated `history`, and then never
        referenced it again - the identifier appeared nowhere in either body. The
        Spoke sends it expecting follow-up questions to work, so every "and what
        about him?" was answered with no idea what "him" referred to.
        """
        if not history:
            return ""
        lines = []
        for turn in history[-6:]:
            if not isinstance(turn, (list, tuple)) or len(turn) < 2:
                continue
            question, answer = turn[0], turn[1]
            if question:
                lines.append(f"User: {question}")
            if answer:
                lines.append(f"GM: {answer}")
        if not lines:
            return ""
        return "Earlier in this conversation:\n" + "\n".join(lines) + "\n\n"

    def _build_rag_prompt(
        self,
        prompt: str,
        context: list[dict],
        edition: str,
        mode: str | None,
        history: list[list[str]] | None = None,
    ) -> str:
        context_text = "\n\n---\n\n".join(
            f"[{c.get('source_book', 'Unknown')}] {c.get('name', 'Rule')}: {c.get('content', '')[:500]}"
            for c in context
        )
        return f"""Context from rulebooks:
{context_text}

{self._history_block(history)}User request: {prompt}"""

    def _format_raw_excerpts(self, hits: list[dict], query: str) -> str:
        if not hits:
            return f"No rules found for '{query}'. Try a different search term."

        lines = [f"Raw rule excerpts for '{query}':\n"]
        for i, hit in enumerate(hits, 1):
            lines.append(
                f"{i}. **{hit['name']}** ({hit.get('system', '?')}) â€” {hit.get('source_book', 'Unknown')}\n"
                f"   {hit['content'][:300]}..."
            )
        return "\n".join(lines)
