import json
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AISettings, Conversation, Message, TypeSafeDecisionLog, KnowledgeItem
from app.schemas import TypeSafeDecisionResult, ActionType, IntentType, OptionEvaluation
from app.services.ai_service import AIService
from app.services.learning_service import LearningService

logger = # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # logging.getLogger("TypeSafeAI")

class TypeSafeAIEngine:
    @staticmethod
    def _detect_human_request_or_complaint(text: str) -> Optional[str]:
        """Detects if customer explicitly demanded human support or expresses severe anger."""
        human_triggers = [
            "پشتیبان انسانی", "وصل کن به پشتیبان", "آدم واقعی", "پشتیبان واقعی", 
            "با انسان صحبت کنم", "اپراتور", "انسان می‌خوام", "انسان میخوام", 
            "connect to agent", "human agent", "talk to human", "real person"
        ]
        complaint_triggers = [
            "شکایت", "ناراضی", "کلاهبرداری", "پولم رو پس بدید", "استرداد وجه",
            "کنسل کنید", "پاسخگو نیستید", "افتضاح", "complaint", "refund", "scam"
        ]
        lower = text.lower()
        for t in human_triggers:
            if t in lower:
                return "HUMAN_REQUEST"
        for t in complaint_triggers:
            if t in lower:
                return "COMPLAINT"
        
    @classmethod
    async def evaluate_and_decide(
        cls,
        db: AsyncSession,
        conversation: Conversation,
        customer_message_text: str,
        settings: AISettings
    ) -> TypeSafeDecisionResult:
        """
        Runs the TypeSafe decision process:
        1. Context & History assembly
        2. Knowledge Base & Past Agent Solutions retrieval
        3. Multi-option evaluation with LLM or fallback heuristics
        4. Guardrails & Threshold verification
        5. Logs decision to database
        """
        # 1. Retrieve relevant knowledge from DB (including past agent-learned answers)
        relevant_docs = await LearningService.retrieve_relevant_knowledge(
            db, 
            query=customer_message_text, 
            site_id=conversation.site_id,
            limit=4
        )

        knowledge_context = ""
        cited_ids = []
        for idx, (doc, score) in enumerate(relevant_docs, 1):
            knowledge_context += f"\n[منبع {idx} - شناسه {doc.id} - ارتباط {int(score*100)}% - دسته‌بندی {doc.category}]:\nعنوان/پرسش: {doc.title}\nپاسخ/توضیح: {doc.content}\n"
            cited_ids.append(doc.id)

        # 2. Check rule-based override (e.g. customer explicit demand for human)
        rule_trigger = cls._detect_human_request_or_complaint(customer_message_text)

        # 3. Call LLM if API Key is configured and valid
        decision_result: Optional[TypeSafeDecisionResult] = None
        latency = 0
        model_name = settings.model_name
        provider_name = settings.provider_name

        if settings.api_key and settings.base_url:
            try:
                system_instruction = f"""
{settings.system_prompt}

شما مجهز به موتور تصمیم‌گیری ایمن (TypeSafe AI Decision Engine) هستید.
وظیفه شما این است که پیام کاربر را تحلیل کرده، گزینه‌های مختلف اقدام را بسنجید و یک تصمیم قطعی بر اساس چارچوب JSON زیر بگیرید:

گزینه‌های ممکن برای اقدام (Action Options):
1. "AUTO_ANSWER": زمانی که اطلاعات کافی در منابع دانش یا پیشینه وجود دارد و پاسخ با قطعیت بالا مشخص است.
2. "SUGGEST_TO_AGENT": زمانی که پاسخ تقریبی را می‌دانید یا نیاز به بررسی و تایید اپراتور انسانی است.
3. "TRANSFER_TO_HUMAN": زمانی که سوال نیازمند دسترسی به پنل مدیریت/حساب بانکی، شکایت تند، یا درخواست مستقیم کاربر برای اتصال به پشتیبان انسانی است.
4. "CLARIFY": زمانی که پیام کاربر به شدت مبهم یا ناقص است و باید ابتدا توضیح بیشتری بخواهید.

دسته‌بندی‌های نیت (Intent):
- "faq", "technical_support", "billing_sales", "complaint", "human_request", "greeting", "other"

منابع دانش و پاسخ‌های قبلی همکاران پشتیبان:
{knowledge_context if knowledge_context else "هیچ منبع مشابهی یافت نشد."}

پاسخ شما باید صرفاً یک آبجکت JSON معتبر بدون هیچ توضیح اضافه باشد با این فیلدها:
{{
  "intent": "یکی از دسته‌ها",
  "confidence": عدد اعشاری بین 0.0 تا 1.0,
  "evaluated_options": [
    {{"action": "AUTO_ANSWER", "score": 0.0 تا 1.0, "reasoning": "دلیل"}},
    {{"action": "SUGGEST_TO_AGENT", "score": 0.0 تا 1.0, "reasoning": "دلیل"}},
    {{"action": "TRANSFER_TO_HUMAN", "score": 0.0 تا 1.0, "reasoning": "دلیل"}},
    {{"action": "CLARIFY", "score": 0.0 تا 1.0, "reasoning": "دلیل"}}
  ],
  "selected_action": "یکی از 4 اکشن فوق",
  "reason": "دلیل انتخاب این اکشن به فارسی",
  "suggested_reply": "متن پاسخی که باید به کاربر داده شود (در صورت AUTO_ANSWER یا SUGGEST_TO_AGENT)"
}}
"""
                # Fetch last 4 conversation messages for context
                history_messages = [
                    {"role": "system", "content": system_instruction}
                ]
                # Add recent messages
                for m in conversation.messages[-5:]:
                    if not m.is_internal:
                        role = "user" if m.sender_type == "customer" else "assistant"
                        history_messages.append({"role": role, "content": m.content})
                
                # Ensure the latest customer message is present
                if not any(m["content"] == customer_message_text for m in history_messages if m["role"] == "user"):
                    history_messages.append({"role": "user", "content": customer_message_text})

                res = await AIService.chat_completion(
                    base_url=settings.base_url,
                    api_key=settings.api_key,
                    model_name=settings.model_name,
                    messages=history_messages,
                    temperature=settings.temperature,
                    response_format={"type": "json_object"}
                )
                latency = res["latency_ms"]
                raw_json = res["content"]
                
                # Clean JSON code blocks if present
                clean_json = re.sub(r'^```json\s*', '', raw_json.strip())
                clean_json = re.sub(r'\s*```$', '', clean_json)
                
                parsed_data = json.loads(clean_json)
                parsed_data["cited_knowledge_ids"] = cited_ids
                decision_result = TypeSafeDecisionResult(**parsed_data)

            except Exception as e:
                logger.error(f"Error in LLM TypeSafe completion: {e}")
                decision_result = None

        # 4. Fallback / Mock Engine if no API key or LLM error
        if decision_result is None:
            decision_result = cls._heuristic_fallback_decision(
                customer_message=customer_message_text,
                relevant_docs=relevant_docs,
                rule_trigger=rule_trigger,
                threshold=settings.auto_answer_threshold
            )
            model_name = "Built-in TypeSafe Heuristic Engine"
            provider_name = "Local Rules & Knowledge Retriever"
            latency = 12

        # 5. Apply safety guardrails on top of the decision
        if rule_trigger == "HUMAN_REQUEST":
            decision_result.selected_action = ActionType.TRANSFER_TO_HUMAN
            decision_result.intent = IntentType.HUMAN_REQUEST
            decision_result.confidence = 1.0
            decision_result.reason = "کاربر صراحتاً درخواست ارتباط با پشتیبان انسانی دارد."
            decision_result.suggested_reply = "درخواست شما دریافت شد. در حال انتقال مکالمه به همکاران پشتیبان انسانی هستیم. لطفاً چند لحظه شکیبا باشید."

        elif rule_trigger == "COMPLAINT" and settings.auto_handoff_on_complaint:
            decision_result.selected_action = ActionType.TRANSFER_TO_HUMAN
            decision_result.intent = IntentType.COMPLAINT
            decision_result.reason = "پیام شامل نارضایتی یا شکایت است و طبق تنظیمات ایمنی مستقیماً به پشتیبان ارجاع شد."
            decision_result.suggested_reply = "از تجربه پیش‌آمده پوزش می‌طلبیم. تیکت شما به صورت ویژه به مدیریت و همکاران پشتیبان ارجاع داده شد تا سریعاً بررسی شود."

        # If confidence is below threshold, prevent AUTO_ANSWER
        if decision_result.selected_action == ActionType.AUTO_ANSWER and decision_result.confidence < settings.auto_answer_threshold:
            decision_result.selected_action = ActionType.SUGGEST_TO_AGENT
            decision_result.reason += f" (اطمینان {int(decision_result.confidence*100)}% کمتر از آستانه مجاز {int(settings.auto_answer_threshold*100)}% بود، لذا جهت تایید به پشتیبان ارجاع شد)"

        # 6. Save decision log to DB
        options_json = json.dumps([opt.model_dump() for opt in decision_result.evaluated_options], ensure_ascii=False)
        cited_json = json.dumps(decision_result.cited_knowledge_ids, ensure_ascii=False)

        decision_log = TypeSafeDecisionLog(
            conversation_id=conversation.id,
            customer_message=customer_message_text,
            intent=decision_result.intent.value,
            confidence=decision_result.confidence,
            action=decision_result.selected_action.value,
            reason=decision_result.reason,
            options_evaluated_json=options_json,
            suggested_reply=decision_result.suggested_reply or "",
            retrieved_knowledge_json=cited_json,
            model_used=model_name,
            provider=provider_name,
            latency_ms=latency
        )
        db.add(decision_log)
        await db.commit()
        await db.refresh(decision_log)

        # Record knowledge item usage if auto answered
        if decision_result.selected_action == ActionType.AUTO_ANSWER and cited_ids:
            await LearningService.record_usage(db, cited_ids)

        return decision_result

    @classmethod
    def _heuristic_fallback_decision(
        cls,
        customer_message: str,
        relevant_docs: List[tuple],
        rule_trigger: Optional[str],
        threshold: float
    ) -> TypeSafeDecisionResult:
        """
        High-precision fallback heuristic when LLM API Key is not set or network fails.
        Enables out-of-the-box demo testing and guarantees system never crashes.
        """
        msg = customer_message.strip()
        lower = msg.lower()

        # Greetings check
        greetings = ["سلام", "درود", "صبح بخیر", "عصر بخیر", "وقت بخیر", "hello", "hi"]
        if any(g == lower for g in greetings) or any(lower.startswith(g + " ") for g in greetings):
            return TypeSafeDecisionResult(
                intent=IntentType.GREETING,
                confidence=0.98,
                selected_action=ActionType.AUTO_ANSWER,
                reason="پیام احوال‌پرسی استاندارد شناسایی شد.",
                evaluated_options=[
                    OptionEvaluation(action=ActionType.AUTO_ANSWER, score=0.98, reasoning="پاسخ گرم و محترمانه سریع به احوالپرسی"),
                    OptionEvaluation(action=ActionType.SUGGEST_TO_AGENT, score=0.1, reasoning="غیرضروری برای احوالپرسی ساده"),
                    OptionEvaluation(action=ActionType.TRANSFER_TO_HUMAN, score=0.05, reasoning="بدون نیاز به انسان"),
                    OptionEvaluation(action=ActionType.CLARIFY, score=0.0, reasoning="پیام کاملاً مشخص است")
                ],
                suggested_reply="سلام و درود! روزتون بخیر. چطور می‌تونم کمکتون کنم؟",
                cited_knowledge_ids=[]
            )

        # If relevant knowledge matched with high score
        if relevant_docs:
            best_doc, score = relevant_docs[0]
            if score >= 0.70:
                return TypeSafeDecisionResult(
                    intent=IntentType.FAQ,
                    confidence=score,
                    selected_action=ActionType.AUTO_ANSWER if score >= threshold else ActionType.SUGGEST_TO_AGENT,
                    reason=f"تطابق قوی ({int(score*100)}%) با پایگاه دانش: '{best_doc.title}'",
                    evaluated_options=[
                        OptionEvaluation(action=ActionType.AUTO_ANSWER, score=score, reasoning="تطابق مستقیم با پرسش‌های متداول و آموزش‌های قبلی"),
                        OptionEvaluation(action=ActionType.SUGGEST_TO_AGENT, score=round(1.0 - score + 0.2, 2), reasoning="بررسی انسانی در صورت حساس بودن موضوع"),
                        OptionEvaluation(action=ActionType.TRANSFER_TO_HUMAN, score=0.1, reasoning="مورد نیازی به ارجاع دستی ندارد"),
                        OptionEvaluation(action=ActionType.CLARIFY, score=0.1, reasoning="سوال به اندازه کافی شفاف است")
                    ],
                    suggested_reply=f"{best_doc.content}\n\n(آیا پاسخ سوالتان را دریافت کردید یا نیاز به راهنمایی بیشتری دارید؟)",
                    cited_knowledge_ids=[best_doc.id]
                )
            elif score >= 0.35:
                # Moderate score: suggest to agent
                return TypeSafeDecisionResult(
                    intent=IntentType.TECHNICAL_SUPPORT,
                    confidence=score,
                    selected_action=ActionType.SUGGEST_TO_AGENT,
                    reason=f"تطابق متوسط ({int(score*100)}%) با سند '{best_doc.title}'. نیاز به تایید پشتیبان دارد.",
                    evaluated_options=[
                        OptionEvaluation(action=ActionType.SUGGEST_TO_AGENT, score=0.85, reasoning="پشتیبان پیش‌نویس را بررسی و در صورت تایید ارسال کند"),
                        OptionEvaluation(action=ActionType.AUTO_ANSWER, score=score, reasoning="ریسک پاسخ غیردقیق برای اطمینان متوسط"),
                        OptionEvaluation(action=ActionType.TRANSFER_TO_HUMAN, score=0.6, reasoning="انتقال به انسان در صورت عدم تایید پیش‌نویس"),
                        OptionEvaluation(action=ActionType.CLARIFY, score=0.4, reasoning="ممکن است کاربر نیاز به توضیح بیشتر داشته باشد")
                    ],
                    suggested_reply=f"بر اساس سوابق: {best_doc.content}",
                    cited_knowledge_ids=[best_doc.id]
                )

        # No match or low match
        return TypeSafeDecisionResult(
            intent=IntentType.OTHER,
            confidence=0.40,
            selected_action=ActionType.TRANSFER_TO_HUMAN,
            reason="اطلاعات کافی در پایگاه دانش برای این سوال یافت نشد؛ ارجاع به پشتیبان انسانی جهت راهنمایی دقیق و یادگیری سیستم.",
            evaluated_options=[
                OptionEvaluation(action=ActionType.TRANSFER_TO_HUMAN, score=0.90, reasoning="سوال جدید است و نیاز به پاسخ دقیق پشتیبان انسانی دارد"),
                OptionEvaluation(action=ActionType.AUTO_ANSWER, score=0.15, reasoning="اطلاعات کافی برای پاسخ خودکار وجود ندارد"),
                OptionEvaluation(action=ActionType.SUGGEST_TO_AGENT, score=0.50, reasoning="هیچ پیش‌نویس معتبری موجود نیست"),
                OptionEvaluation(action=ActionType.CLARIFY, score=0.60, reasoning="می‌توان از کاربر جزئیات بیشتری خواست")
            ],
            suggested_reply="پیام شما دریافت شد. هم‌اکنون به یکی از همکاران پشتیبانی ارجاع گردید تا سریعاً شما را راهنمایی کنند.",
            cited_knowledge_ids=[]
        )
