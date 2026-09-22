import re
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import KnowledgeItem, Conversation, Message

class LearningService:
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        Tokenizes Persian & English text into clean lowercase words,
        removing stop words and punctuation.
        """
        if not text:
            return set()
        stop_words = {
            "و", "یا", "از", "به", "در", "با", "که", "این", "آن", "برای", 
            "تا", "شد", "است", "یک", "رو", "را", "هم", "نه", "اگر", "چون",
            "می", "های", "ها", "ای", "چیست", "کجا", "سلام", "درود", "لطفا"
        }
        # keep persian & alphanumeric characters
        tokens = re.findall(r'[\w\u0600-\u06FF]+', text.lower())
        return {t for t in tokens if len(t) > 1 and t not in stop_words}

    @classmethod
    async def retrieve_relevant_knowledge(
        cls,
        db: AsyncSession,
        query: str,
        site_id: Optional[str] = None,
        limit: int = 4
    ) -> List[Tuple[KnowledgeItem, float]]:
        """
        Finds the most relevant knowledge base items & past agent-learned answers.
        Returns a list of tuples: (KnowledgeItem, score between 0.0 and 1.0).
        """
        query_tokens = cls._tokenize(query)
        if not query_tokens:
            return []

        # Query all approved knowledge items for this site or global
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.is_approved == True,
            or_(KnowledgeItem.site_id == site_id, KnowledgeItem.site_id == None)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        scored_items: List[Tuple[KnowledgeItem, float]] = []

        for item in items:
            title_tokens = cls._tokenize(item.title)
            content_tokens = cls._tokenize(item.content)
            tag_tokens = cls._tokenize(item.tags or "")

            if not (title_tokens or content_tokens):
                continue

            # Weighting: title and tag matches carry higher importance
            title_intersection = query_tokens.intersection(title_tokens)
            content_intersection = query_tokens.intersection(content_tokens)
            tag_intersection = query_tokens.intersection(tag_tokens)

            title_score = len(title_intersection) / max(len(query_tokens), 1)
            content_score = len(content_intersection) / max(len(query_tokens), 1)
            tag_score = len(tag_intersection) / max(len(query_tokens), 1)

            # Boost agent_learned items if they closely match
            learned_boost = 1.1 if item.category == "agent_learned" else 1.0

            total_score = (title_score * 0.55 + content_score * 0.30 + tag_score * 0.15) * learned_boost
            
            # Exact substring bonus
            if query.strip().lower() in item.title.lower() or item.title.lower() in query.strip().lower():
                total_score = max(total_score, 0.85)

            if total_score > 0.12:
                scored_items.append((item, min(round(total_score, 3), 1.0)))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items[:limit]

    @classmethod
    async def learn_from_agent_response(
        cls,
        db: AsyncSession,
        conversation_id: str,
        customer_question: str,
        agent_answer: str,
        title: Optional[str] = None,
        category: str = "agent_learned",
        tags: str = "agent_response",
        site_id: Optional[str] = None
    ) -> KnowledgeItem:
        """
        Saves an agent's answer into the KnowledgeItem database so the AI
        learns and can use it in future user queries.
        """
        item_title = title.strip() if title and title.strip() else customer_question.strip()[:150]
        
        # Check if an identical or almost identical item exists
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.title == item_title,
            KnowledgeItem.source_conversation_id == conversation_id
        )
        existing = (await db.execute(stmt)).scalars().first()
        if existing:
            existing.content = agent_answer.strip()
            existing.tags = tags
            await db.commit()
            await db.refresh(existing)
            return existing

        item = KnowledgeItem(
            site_id=site_id,
            title=item_title,
            content=agent_answer.strip(),
            category=category,
            source="agent_learned",
            source_conversation_id=conversation_id,
            is_approved=True,
            usage_count=0,
            tags=tags
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @classmethod
    async def record_usage(cls, db: AsyncSession, item_ids: List[str]):
        """Increments usage counter for cited knowledge items."""
        if not item_ids:
            return
        stmt = select(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids))
        items = (await db.execute(stmt)).scalars().all()
        for item in items:
            item.usage_count += 1
        await db.commit()
