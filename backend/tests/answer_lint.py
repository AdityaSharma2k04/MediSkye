"""
Answer Quality & Clinical Communication Linter for MediSkye QA Reports.

Inspects conversation turns (particularly follow-up turns) from markdown QA logs
(e.g., prompt_and_answers.md) for clinical prompt compliance:
1. Banned over-certain phrases.
2. Compliment openers.
3. Forbidden walkthrough artifacts in document chats (### headings, unrequested tables,
   unexpected disclaimers, Short Version, What This Report Does Not Cover).
4. Per-conversation repetition (guidepost > 1, step-by-step > 1, unsolicited retest repetition,
   excessive question closings, word count warnings > 300 words).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Regex Patterns
# ─────────────────────────────────────────────────────────────────────────────

BANNED_OVER_CERTAIN_RE = re.compile(
    r"\b(?:highly likely|absolutely|exactly why|primary driver|directly connected|"
    r"points? (?:to|toward|away from)|confirms (?:the|that)|no need to (?:panic|worry)|"
    r"fantastic shape|rather than a sign of organ damage)\b",
    re.IGNORECASE,
)

COMPLIMENT_OPENER_RE = re.compile(
    r"^\s*It is (?:so |really |completely |incredibly )?(?:natural|wonderful|smart|excellent|understandable|common)\b",
    re.IGNORECASE,
)

SHORT_VERSION_RE = re.compile(r"The Short Version", re.IGNORECASE)
DOES_NOT_COVER_RE = re.compile(r"Does Not Cover", re.IGNORECASE)
HEADING_3_RE = re.compile(r"(?m)^###\s+.*$")
TABLE_ROW_RE = re.compile(r"(?m)^\s*\|.*\|")
DISCLAIMER_RE = re.compile(r"(?im)^\s*\*{0,2}Disclaimer:\*{0,2}")

COMPARISON_QUERY_RE = re.compile(
    r"\b(?:compare|compared|comparison|versus|vs\.?|trend|trends|over\s+time|baseline|"
    r"since\s+(?:my\s+)?(?:last|previous|earlier|prior)|changed?\s+since|"
    r"changed?\s+from\s+(?:my\s+)?(?:last|previous|earlier|prior)|"
    r"difference\s+between|side\s*-?\s*by\s*-?\s*side|comparison\s+table|trend\s+table|table)\b",
    re.IGNORECASE,
)

MEDICATION_CHANGE_QUERY_RE = re.compile(
    r"\b(?:should\s+i|can\s+i|do\s+i\s+need\s+to|is\s+it\s+ok(?:ay)?\s+to)\s+(?:stop|skip|quit|discontinue|double)\b"
    r"|\b(?:stop|skip|quit|discontinue)\s+(?:taking|using|my)\b",
    re.IGNORECASE,
)

GUIDEPOST_RE = re.compile(r"\bguideposts?\b", re.IGNORECASE)
STEP_BY_STEP_RE = re.compile(r"\bstep[- ]by[- ]step\b", re.IGNORECASE)
RETEST_TIMING_RE = re.compile(r"\b(?:8\s*(?:[–-]|to)\s*12\s*weeks|repeat(?:\s+testing)?\s+in\s+\d+\s*(?:weeks|months))\b", re.IGNORECASE)
TIMELINE_QUERY_RE = re.compile(r"\b(?:when|timeline|retest|re-test|follow[- ]up\s+test|how\s+soon)\b", re.IGNORECASE)


@dataclass
class LintIssue:
    profile: str
    turn: int
    category: str
    message: str
    severity: str = "ERROR"  # "ERROR" or "WARNING"


@dataclass
class TurnData:
    turn_num: int
    turn_title: str
    is_followup: bool
    user_prompt: str
    ai_response: str


@dataclass
class ConversationData:
    profile_name: str
    is_doc_chat: bool
    turns: List[TurnData]


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_markdown_report(content: str) -> List[ConversationData]:
    """
    Parses a markdown QA log (such as prompt_and_answers.md) into structured conversations.
    """
    conversations: List[ConversationData] = []

    # Split by profile: "## Profile X: ..."
    profile_sections = re.split(r"(?m)^##\s+Profile\s+\d+:\s*(.+)$", content)
    if len(profile_sections) <= 1:
        # Fallback: single profile or raw text
        turns = _parse_turns(content)
        if turns:
            conversations.append(ConversationData(profile_name="Default", is_doc_chat=True, turns=turns))
        return conversations

    for i in range(1, len(profile_sections), 2):
        p_header = profile_sections[i].strip()
        p_body = profile_sections[i + 1] if i + 1 < len(profile_sections) else ""
        is_doc = "General Health Session" not in p_header and "self" not in p_header.lower()
        turns = _parse_turns(p_body)
        conversations.append(ConversationData(profile_name=p_header, is_doc_chat=is_doc, turns=turns))

    return conversations


def _parse_turns(body_text: str) -> List[TurnData]:
    turns: List[TurnData] = []
    # Split by "#### Question N — `Turn N ...`"
    parts = re.split(r"(?m)^####\s+Question\s+(\d+)\s+[—–-]\s*`([^`]+)`.*$", body_text)
    if len(parts) <= 1:
        return turns

    for i in range(1, len(parts), 3):
        t_num = int(parts[i])
        t_title = parts[i + 1].strip()
        t_content = parts[i + 2] if i + 2 < len(parts) else ""

        # Extract user prompt and AI response
        user_prompt = ""
        ai_response = ""

        user_match = re.search(r">\s*\*\*User Prompt:\*\*\s*(.+?)(?=\n+\*\*MediSkye|\n+###|\Z)", t_content, re.DOTALL)
        if user_match:
            user_prompt = user_match.group(1).strip()

        ai_match = re.search(r"\*\*MediSkye AI Response:\*\*\s*(.*)$", t_content, re.DOTALL)
        if ai_match:
            raw_ai = ai_match.group(1).strip()
            # Trim trailing divider or metadata
            raw_ai = re.split(r"(?m)^---+\s*$", raw_ai)[0].strip()
            ai_response = raw_ai

        is_followup = (t_num > 1) or ("follow-up" in t_title.lower()) or ("followup" in t_title.lower())
        turns.append(TurnData(
            turn_num=t_num,
            turn_title=t_title,
            is_followup=is_followup,
            user_prompt=user_prompt,
            ai_response=ai_response,
        ))

    return turns


# ─────────────────────────────────────────────────────────────────────────────
# Turn-Level Linter Checks
# ─────────────────────────────────────────────────────────────────────────────

def check_banned_phrases(text: str) -> List[str]:
    """Finds any banned over-certain phrases."""
    return [m.group(0) for m in BANNED_OVER_CERTAIN_RE.finditer(text)]


def check_compliment_opener(text: str) -> Optional[str]:
    """Finds if text begins with a stock compliment opener."""
    m = COMPLIMENT_OPENER_RE.match(text)
    return m.group(0) if m else None


def check_walkthrough_artifacts(
    ai_response: str,
    user_prompt: str,
    is_doc_chat: bool,
    is_followup: bool,
) -> List[str]:
    """
    Checks for forbidden walkthrough artifacts on follow-up turns in document chats.
    """
    if not (is_doc_chat and is_followup):
        return []

    artifacts: List[str] = []

    # 1. ### headings
    headings = HEADING_3_RE.findall(ai_response)
    if headings:
        artifacts.append(f"Forbidden ### headings in follow-up ({len(headings)} found)")

    # 2. Unrequested tables
    table_rows = TABLE_ROW_RE.findall(ai_response)
    if table_rows and not COMPARISON_QUERY_RE.search(user_prompt):
        artifacts.append(f"Unrequested Markdown table in follow-up ({len(table_rows)} rows found)")

    # 3. Disclaimer (unless user asked a medication stop/change query)
    if DISCLAIMER_RE.search(ai_response):
        if not MEDICATION_CHANGE_QUERY_RE.search(user_prompt):
            artifacts.append("Forbidden closing Disclaimer in normal follow-up turn")

    # 4. Short Version
    if SHORT_VERSION_RE.search(ai_response):
        artifacts.append("Forbidden 'The Short Version' heading in follow-up turn")

    # 5. What This Report Does Not Cover
    if DOES_NOT_COVER_RE.search(ai_response):
        artifacts.append("Forbidden 'Does Not Cover' section in follow-up turn")

    return artifacts


# ─────────────────────────────────────────────────────────────────────────────
# Conversation-Level Linter Checks
# ─────────────────────────────────────────────────────────────────────────────

def check_conversation_repetition(conversation: ConversationData) -> List[LintIssue]:
    """
    Checks per-conversation repetition:
    - guidepost count > 1
    - step-by-step count > 1
    - unsolicited repetition of follow-up tests / 8–12 weeks across follow-ups
    - > 50% of follow-ups ending with ?
    - word count warning if follow-up > 300 words
    """
    issues: List[LintIssue] = []
    p_name = conversation.profile_name

    # Concatenate all AI text for whole conversation counts
    all_ai_text = "\n".join(t.ai_response for t in conversation.turns)

    # 1. guidepost > 1
    guideposts = GUIDEPOST_RE.findall(all_ai_text)
    if len(guideposts) > 1:
        issues.append(LintIssue(
            profile=p_name,
            turn=0,
            category="Repetition",
            message=f"'guidepost(s)' used {len(guideposts)} times across conversation (max allowed: 1)",
            severity="ERROR",
        ))

    # 2. step-by-step > 1
    steps = STEP_BY_STEP_RE.findall(all_ai_text)
    if len(steps) > 1:
        issues.append(LintIssue(
            profile=p_name,
            turn=0,
            category="Repetition",
            message=f"'step-by-step' used {len(steps)} times across conversation (max allowed: 1)",
            severity="ERROR",
        ))

    # Follow-up turns specifically
    followup_turns = [t for t in conversation.turns if t.is_followup]
    if not followup_turns:
        return issues

    # 3. Unsolicited retest timing repetition across follow-ups
    unsolicited_retest_turns: List[int] = []
    for t in followup_turns:
        if RETEST_TIMING_RE.search(t.ai_response) and not TIMELINE_QUERY_RE.search(t.user_prompt):
            unsolicited_retest_turns.append(t.turn_num)

    if len(unsolicited_retest_turns) > 1:
        issues.append(LintIssue(
            profile=p_name,
            turn=0,
            category="Repetition",
            message=f"Unsolicited retest timing / 8–12 weeks repeated in multiple follow-up turns: {unsolicited_retest_turns}",
            severity="ERROR",
        ))

    # 4. > 50% of follow-ups ending with ?
    question_endings = 0
    for t in followup_turns:
        resp = t.ai_response.strip()
        # Strip trailing disclaimers or markdown formatting before checking ending punctuation
        cleaned = re.sub(r'(?im)^\s*\*{0,2}Disclaimer:\*{0,2}[\s\S]*$', '', resp).strip()
        if cleaned.endswith("?"):
            question_endings += 1

    if len(followup_turns) > 0 and (question_endings / len(followup_turns)) > 0.5:
        issues.append(LintIssue(
            profile=p_name,
            turn=0,
            category="Closing Style",
            message=f"{question_endings}/{len(followup_turns)} follow-up turns end with a question mark (>50% threshold)",
            severity="WARNING",
        ))

    # 5. Word count warning over 300 words for follow-ups
    for t in followup_turns:
        word_count = len(t.ai_response.split())
        if word_count > 300:
            issues.append(LintIssue(
                profile=p_name,
                turn=t.turn_num,
                category="Length Warning",
                message=f"Follow-up turn has {word_count} words (guideline: compact, usually under 250 words; warning over 300)",
                severity="WARNING",
            ))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Master Linter Runner
# ─────────────────────────────────────────────────────────────────────────────

def lint_conversation(conv: ConversationData) -> List[LintIssue]:
    issues: List[LintIssue] = []

    # Turn-level checks
    for t in conv.turns:
        # Banned phrases in follow-up answers
        if t.is_followup:
            banned = check_banned_phrases(t.ai_response)
            for b in banned:
                issues.append(LintIssue(
                    profile=conv.profile_name,
                    turn=t.turn_num,
                    category="Banned Phrase",
                    message=f"Banned over-certain phrase detected: '{b}'",
                    severity="ERROR",
                ))

            # Compliment openers
            comp = check_compliment_opener(t.ai_response)
            if comp:
                issues.append(LintIssue(
                    profile=conv.profile_name,
                    turn=t.turn_num,
                    category="Compliment Opener",
                    message=f"Stock compliment opener detected: '{comp}'",
                    severity="ERROR",
                ))

        # Walkthrough artifacts on follow-ups in document chats
        artifacts = check_walkthrough_artifacts(
            ai_response=t.ai_response,
            user_prompt=t.user_prompt,
            is_doc_chat=conv.is_doc_chat,
            is_followup=t.is_followup,
        )
        for art in artifacts:
            issues.append(LintIssue(
                profile=conv.profile_name,
                turn=t.turn_num,
                category="Walkthrough Artifact",
                message=art,
                severity="ERROR",
            ))

    # Conversation-level checks
    issues.extend(check_conversation_repetition(conv))
    return issues


def lint_markdown_file(file_path: str | Path) -> List[LintIssue]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = path.read_text(encoding="utf-8")
    conversations = parse_markdown_report(content)
    all_issues: List[LintIssue] = []
    for conv in conversations:
        all_issues.extend(lint_conversation(conv))
    return all_issues


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Lint MediSkye QA Markdown Log for Clinical Quality Rules.")
    parser.add_argument("file", nargs="?", default="prompt_and_answers.md", help="Path to markdown QA report")
    args = parser.parse_args()

    target = Path(args.file)
    if not target.is_file():
        print(f"File not found: {target}")
        return 1

    print(f"Linting {target.name}...")
    issues = lint_markdown_file(target)

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    print(f"\nAudit complete: {len(errors)} ERROR(s), {len(warnings)} WARNING(s)")
    if issues:
        print("\nFindings:")
        for issue in issues:
            turn_str = f"Turn {issue.turn}" if issue.turn > 0 else "Overall"
            print(f"[{issue.severity}] [{issue.profile} | {turn_str}] ({issue.category}): {issue.message}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
