"""AI service — email classification and draft generation.

Uses DDW's LLM Provider layer. Falls back to a deterministic
mock classifier when no provider is available (unit tests, offline).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Classification prompt (from PRD §3.5)
# ------------------------------------------------------------------
CLASSIFY_PROMPT = """你是一个邮件分类助手。请根据以下邮件信息进行分类。

邮件信息：
- 主题：{subject}
- 发件人：{sender}
- 收件人：{recipients}
- 抄送：{cc}
- 内容摘要：{body_summary}

请将邮件分类为以下之一：
1. need_reply - 需要回复（直接发给我的、有明确问题、等待回复）
2. simple_confirm - 简单确认类（确认收到/同意/已阅，可以用模板回复）
3. info_only - 知会/通知（CC、系统通知、公告，只需知晓）
4. newsletter - 订阅/营销（Newsletter、推广邮件）
5. spam - 垃圾邮件（广告、钓鱼、可疑）

请返回 JSON 格式：
{{
  "classification": "分类结果",
  "confidence": 0.95,
  "reason": "分类理由",
  "suggested_action": "建议操作"
}}"""

# ------------------------------------------------------------------
# Draft generation prompt (from PRD §3.6)
# ------------------------------------------------------------------
DRAFT_PROMPT = """你是一个邮件回复助手。请根据以下邮件内容生成一封专业、简洁的回复草稿。

邮件信息：
- 主题：{subject}
- 发件人：{sender}
- 内容：{body}

要求：
1. 语气专业、友好
2. 回复简洁，不超过原文长度的 1/3
3. 如果是简单确认类，使用标准确认模板
4. 如果是需要回复的，针对问题给出具体回应
5. 使用中文回复（如果原文是中文）

请直接输出回复内容，不需要额外说明。"""


class AIService:
    """AI classification and draft generation service."""

    def __init__(self, llm_provider: Any = None) -> None:
        """
        Args:
            llm_provider: Optional DDW LLM provider instance. When None,
                          uses a deterministic mock for testing.
        """
        self.llm_provider = llm_provider

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, subject: str, sender: str, recipients: str, cc: str, body: str) -> Dict[str, Any]:
        """Classify an email message.

        Returns dict with keys: classification, confidence, reason, suggested_action
        """
        body_summary = body[:500] if body else ""
        prompt = CLASSIFY_PROMPT.format(
            subject=subject,
            sender=sender,
            recipients=recipients,
            cc=cc,
            body_summary=body_summary,
        )

        if self.llm_provider is not None:
            return self._call_llm_classify(prompt)

        # Deterministic mock classifier (for tests / offline)
        return self._mock_classify(subject, sender, body)

    def _call_llm_classify(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM provider for classification."""
        try:
            response = self.llm_provider.generate(prompt)
            return json.loads(response)
        except Exception as exc:
            logger.warning("LLM classify failed, falling back to mock: %s", exc)
            return self._mock_classify("", "", "")

    def _mock_classify(self, subject: str, sender: str, body: str) -> Dict[str, Any]:
        """Rule-based fallback classifier for offline/test use."""
        text = f"{subject} {body}".lower()
        sender_lower = sender.lower()

        # Spam detection
        spam_keywords = ["viagra", "casino", "lottery", "congratulations you won", "免费", "中奖"]
        if any(kw in text for kw in spam_keywords):
            return {
                "classification": "spam",
                "confidence": 0.92,
                "reason": "包含垃圾邮件关键词",
                "suggested_action": "移入垃圾箱",
            }

        # Newsletter detection
        newsletter_keywords = ["unsubscribe", "newsletter", "退订", "weekly digest", "weekly update"]
        if any(kw in text for kw in newsletter_keywords):
            return {
                "classification": "newsletter",
                "confidence": 0.88,
                "reason": "包含订阅/退订相关内容",
                "suggested_action": "建议退订并归档",
            }

        # Info only (CC'd or system notification)
        if "noreply" in sender_lower or "no-reply" in sender_lower or "notification" in sender_lower:
            return {
                "classification": "info_only",
                "confidence": 0.85,
                "reason": "系统通知邮件",
                "suggested_action": "标记已读并归档",
            }

        # Simple confirm
        confirm_keywords = ["确认", "收到", "同意", "已阅", "ok", "received", "acknowledged"]
        if any(kw in text for kw in confirm_keywords):
            return {
                "classification": "simple_confirm",
                "confidence": 0.80,
                "reason": "包含确认类关键词",
                "suggested_action": "生成标准确认回复",
            }

        # Default: need reply
        return {
            "classification": "need_reply",
            "confidence": 0.70,
            "reason": "需要人工回复的邮件",
            "suggested_action": "生成回复草稿",
        }

    # ------------------------------------------------------------------
    # Draft generation
    # ------------------------------------------------------------------

    def generate_draft(
        self,
        subject: str,
        sender: str,
        body: str,
        classification: str = "need_reply",
    ) -> str:
        """Generate a reply draft for the given email."""
        prompt = DRAFT_PROMPT.format(subject=subject, sender=sender, body=body)

        if self.llm_provider is not None:
            return self._call_llm_draft(prompt)

        return self._mock_draft(subject, classification)

    def _call_llm_draft(self, prompt: str) -> str:
        """Call the LLM provider for draft generation."""
        try:
            return self.llm_provider.generate(prompt)
        except Exception as exc:
            logger.warning("LLM draft failed, using mock: %s", exc)
            return self._mock_draft("", "need_reply")

    def _mock_draft(self, subject: str, classification: str) -> str:
        """Rule-based mock draft generator."""
        if classification == "simple_confirm":
            return "收到，谢谢！\n\nBest regards"
        return (
            f"您好，\n\n"
            f"感谢您的邮件「{subject}」。\n"
            f"我已收到您的来信，会尽快处理。\n\n"
            f"如有疑问请随时联系。\n\n"
            f"此致\n敬礼"
        )
