"""LLM service for generating life story chapters and compiling books."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from ..config import Settings

# Get the prompts directory path
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    """
    Load a prompt template from a markdown file.

    Args:
        filename: Name of the prompt file (e.g., "chapter_prompt.md")

    Returns:
        Prompt template string

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    prompt_path = _PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


# Load prompts from markdown files
CHAPTER_PROMPT = _load_prompt("chapter_prompt.md")
COMPILE_PROMPT = _load_prompt("compile_prompt.md")
SUMMARY_PROMPT = _load_prompt("summary_prompt.md")


class LifeStoryLLM:
    """LLM service for generating life story narratives."""

    def __init__(self, settings: Settings, use_langgraph: bool = False):
        """
        Initialize the LLM service.

        Args:
            settings: Application settings with provider configuration
            use_langgraph: If True, use LangGraph (not yet implemented)
        """
        self.settings = settings
        self.use_langgraph = use_langgraph
        self._llm = None
        self._chapter_chain = None
        self._compile_chain = None
        self._summary_chain = None
        # Store generated chapters: {person_id: {chapter_id: {narrative, title, ...}}}
        self._saved_chapters: dict[str, dict[str, dict]] = {}
        # Store compiled stories: {person_id: {book_text, style_guide, compiled_at}}
        self._saved_stories: dict[str, dict] = {}

    def _make_llm(self):
        """Factory method to create the appropriate LLM based on provider."""
        if self._llm is not None:
            return self._llm

        provider = self.settings.PROVIDER.lower()

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            api_key = self.settings.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required when PROVIDER=openai")

            model_name = self.settings.MODEL_NAME

            self._llm = ChatOpenAI(
                model=model_name,
                temperature=self.settings.TEMPERATURE,
                timeout=self.settings.TIMEOUT_SEC,
                max_tokens=self.settings.MAX_TOKENS,
                api_key=api_key,
            )

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            api_key = self.settings.ANTHROPIC_API_KEY
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY is required when PROVIDER=anthropic")

            model_name = self.settings.MODEL_NAME
            if model_name == "gpt-4o-mini":
                model_name = "claude-3-5-sonnet-latest"

            self._llm = ChatAnthropic(
                model=model_name,
                temperature=self.settings.TEMPERATURE,
                timeout=self.settings.TIMEOUT_SEC,
                max_tokens=self.settings.MAX_TOKENS,
                api_key=api_key,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        return self._llm

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        if TIKTOKEN_AVAILABLE:
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except Exception:
                pass

        # Fallback: rough estimate (4 chars per token)
        return len(text) // 4

    def _get_chapter_chain(self):
        """Get or create the chapter generation chain."""
        if self._chapter_chain is not None:
            return self._chapter_chain

        prompt = ChatPromptTemplate.from_template(CHAPTER_PROMPT)
        llm = self._make_llm()
        output_parser = StrOutputParser()

        self._chapter_chain = prompt | llm | output_parser
        return self._chapter_chain

    def _get_compile_chain(self):
        """Get or create the book compilation chain."""
        if self._compile_chain is not None:
            return self._compile_chain

        prompt = ChatPromptTemplate.from_template(COMPILE_PROMPT)
        llm = self._make_llm()
        output_parser = StrOutputParser()

        self._compile_chain = prompt | llm | output_parser
        return self._compile_chain

    def _get_summary_chain(self):
        """Get or create the chapter summary generation chain."""
        if self._summary_chain is not None:
            return self._summary_chain

        prompt = ChatPromptTemplate.from_template(SUMMARY_PROMPT)
        llm = self._make_llm()
        output_parser = StrOutputParser()

        self._summary_chain = prompt | llm | output_parser
        return self._summary_chain

    async def _map_reduce_chunks(
        self, chunks: list[str], prompt_template: ChatPromptTemplate
    ) -> str:
        """
        Map-reduce strategy for processing long fact chunks.

        Args:
            chunks: List of fact chunks
            prompt_template: Prompt template to use

        Returns:
            Combined narrative text
        """
        if not chunks:
            return ""

        if len(chunks) == 1:
            return chunks[0]

        # For simplicity, we'll process chunks sequentially
        # In production, this could be parallelized
        llm = self._make_llm()
        output_parser = StrOutputParser()
        chain = prompt_template | llm | output_parser

        summaries = []
        for chunk in chunks:
            try:
                # Use await since we're in an async context
                summary = await chain.ainvoke({"facts_bullets": chunk})
                summaries.append(summary)
            except Exception:
                # Fallback: use chunk as-is if summarization fails
                summaries.append(chunk)

        # Combine summaries
        return "\n\n".join(summaries)

    async def _retry_with_backoff(self, coro_func, max_retries: int = 3):
        """
        Retry a coroutine function with exponential backoff.

        Args:
            coro_func: Coroutine function (callable that returns a coroutine) to execute
            max_retries: Maximum number of retries

        Returns:
            Result of the coroutine

        Raises:
            The last exception encountered if all retries fail
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                # Call the coroutine function to get a fresh coroutine object
                coro = coro_func()
                return await asyncio.wait_for(
                    coro, timeout=self.settings.TIMEOUT_SEC
                )
            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        # If we've exhausted all retries, raise the last exception
        if last_exception:
            raise last_exception
        # This should never happen, but handle edge case
        raise RuntimeError("Retry loop completed without result or exception")

    async def agenerate_chapter(
        self,
        person_id: str,
        chapter_id: str,
        facts: list[dict],
        style_guide: Optional[str] = None,
        context_summary: Optional[str] = None,
    ) -> str:
        """
        Generate a chapter narrative from facts.

        Args:
            person_id: Person identifier
            chapter_id: Chapter identifier
            facts: List of fact dictionaries with fields: question_id, text, created_at
            style_guide: Optional style guide text
            context_summary: Optional summary of previous chapters

        Returns:
            Generated narrative text
        """
        # Convert facts to bullet points
        facts_bullets = "\n".join([f"- {fact.get('text', '')}" for fact in facts])

        # Get chapter title (simplified - in production, fetch from database)
        chapter_title = f"פרק {chapter_id}"

        # Check token count and chunk if necessary
        estimated_tokens = self._estimate_tokens(facts_bullets)
        chunk_size_tokens = 1200  # Target chunk size

        if estimated_tokens > 1500:
            # Split facts into chunks
            chunks = []
            current_chunk = []
            current_tokens = 0

            for fact in facts:
                fact_text = f"- {fact.get('text', '')}\n"
                fact_tokens = self._estimate_tokens(fact_text)

                if current_tokens + fact_tokens > chunk_size_tokens and current_chunk:
                    chunks.append("\n".join([f"- {f.get('text', '')}" for f in current_chunk]))
                    current_chunk = [fact]
                    current_tokens = fact_tokens
                else:
                    current_chunk.append(fact)
                    current_tokens += fact_tokens

            if current_chunk:
                chunks.append("\n".join([f"- {f.get('text', '')}" for f in current_chunk]))

            # Use map-reduce if we have chunks
            if len(chunks) > 1:
                # For now, combine chunks and process together
                # In production, implement proper map-reduce
                facts_bullets = "\n\n".join(chunks)
        else:
            chunks = [facts_bullets]

        # Prepare context
        context_text = context_summary or "אין תקציר מהפרקים הקודמים."
        style_text = style_guide or "אין מדריך סגנון ספציפי."

        # Build prompt inputs
        prompt_inputs = {
            "chapter_title": chapter_title,
            "context_summary": context_text,
            "facts_bullets": facts_bullets,
            "style_guide": style_text,
        }

        # Get chain and invoke
        chain = self._get_chapter_chain()

        async def _invoke():
            return await chain.ainvoke(prompt_inputs)

        result = await self._retry_with_backoff(_invoke)

        # Clean and return
        narrative = result.strip() if result else ""
        
        # Save the generated chapter
        if person_id not in self._saved_chapters:
            self._saved_chapters[person_id] = {}
        
        self._saved_chapters[person_id][chapter_id] = {
            "id": chapter_id,
            "title": chapter_title,
            "narrative": narrative,
            "facts": facts,
            "style_guide": style_guide,
            "context_summary": context_summary,
        }
        
        return narrative

    async def acompile_book(
        self,
        person_id: str,
        chapters: Optional[list[dict]] = None,
        style_guide: Optional[str] = None,
    ) -> str:
        """
        Compile a full book from chapter summaries.

        Args:
            person_id: Person identifier
            chapters: Optional list of chapter dictionaries with narrative text.
                     If None, uses saved chapters for this person_id.
            style_guide: Optional style guide text

        Returns:
            Compiled book text
        """
        # Use saved chapters if available, otherwise use provided chapters
        if person_id in self._saved_chapters and self._saved_chapters[person_id]:
            # Use saved chapters
            saved_chapters_dict = self._saved_chapters[person_id]
            chapters_to_use = list(saved_chapters_dict.values())
        elif chapters:
            # Use provided chapters
            chapters_to_use = chapters
        else:
            # No chapters available
            chapters_to_use = []
        
        # Extract chapter summaries
        chapter_summaries = []
        for chapter in chapters_to_use:
            chapter_id = chapter.get("id", "")
            chapter_title = chapter.get("title", f"פרק {chapter_id}")
            narrative = chapter.get("narrative", "")
            if narrative:
                chapter_summaries.append(f"## {chapter_title}\n\n{narrative}")

        chapter_text = "\n\n".join(chapter_summaries) if chapter_summaries else "אין פרקים זמינים."

        # Build timeline (simplified - in production, extract from facts)
        timeline = "טיימליין לא זמין."

        # Prepare prompt inputs
        style_text = style_guide or "אין מדריך סגנון ספציפי."

        prompt_inputs = {
            "style_guide": style_text,
            "chapter_summaries": chapter_text,
            "timeline": timeline,
        }

        # Get chain and invoke
        chain = self._get_compile_chain()

        async def _invoke():
            return await chain.ainvoke(prompt_inputs)

        result = await self._retry_with_backoff(_invoke)

        # Clean and return
        book_text = result.strip() if result else ""
        
        # Save the compiled story
        self._saved_stories[person_id] = {
            "book_text": book_text,
            "style_guide": style_guide,
            "compiled_at": datetime.now().isoformat(),
            "chapters_used": len(chapters_to_use),
        }
        
        return book_text

    def get_compiled_story(self, person_id: str) -> Optional[dict]:
        """
        Get a compiled story for a person.

        Args:
            person_id: Person identifier

        Returns:
            Dictionary with story data if found, None otherwise
        """
        return self._saved_stories.get(person_id)

    async def agenerate_summary(self, narrative: str) -> str:
        """
        Generate a 100-200 word summary of a chapter narrative.

        Args:
            narrative: The full chapter narrative text

        Returns:
            Generated summary text (100-200 words)
        """
        if not narrative or not narrative.strip():
            return ""

        prompt_inputs = {
            "narrative": narrative,
        }

        chain = self._get_summary_chain()

        async def _invoke():
            return await chain.ainvoke(prompt_inputs)

        result = await self._retry_with_backoff(_invoke)

        # Clean and return
        summary = result.strip() if result else ""
        return summary

    def to_structured(self, schema):
        """
        Example method for structured output (future enhancement).

        Args:
            schema: Pydantic schema for structured output

        Returns:
            Chain configured for structured output
        """
        # This is a placeholder for future structured output support
        # Example: chain.with_structured_output(schema)
        raise NotImplementedError("Structured output not yet implemented")

