"""One strict answer contract shared by graph agents and the companion."""
import json
import re
from core.config import settings


def inline_citations(answer):
    return set(re.findall(r'\[(E\d+)\]', answer))


def validate_answer(text, evidence):
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError('Answer does not cite observed evidence')
    body, used = parsed.get('answer'), parsed.get('citation_ids')
    if (not isinstance(body, str) or not body.strip() or len(body) > settings.AI_MAX_ANSWER_CHARACTERS
            or not isinstance(used, list) or any(not isinstance(item, str) for item in used)):
        raise ValueError('Answer does not cite observed evidence')
    inline = inline_citations(body)
    valid = {item['citation_id'] for item in evidence}
    if not inline or not inline <= set(used) or not set(used) <= valid:
        raise ValueError('Answer does not cite observed evidence')
    # Extra observed IDs in the array are not presented as citations unless used inline.
    return body, inline


def display_value(value, limit=300):
    # Retained labels are data; a label containing [E999] is not an observed citation.
    text = re.sub(r'\[(E\d+)\]', r'(\1)', str(value))
    return text if len(text) <= limit else text[:max(0, limit - 1)] + '…'


def bounded_summary(answer):
    limit = settings.AI_MAX_ANSWER_CHARACTERS
    if len(answer) <= limit:
        return answer
    note = '\nSummary truncated; inspect observed evidence.'
    match = re.search(r'\[E\d+\]', answer)
    marker = match.group() if match else ''
    if not marker and limit < len(note):
        return '…'[:limit]
    if marker and limit < len(marker) + len(note):
        return (marker + ('…' if len(marker) < limit else '')) if len(marker) <= limit else '…'[:limit]
    prefix = answer[:max(0, limit - len(note))]
    prefix = re.sub(r'\[E\d*$', '', prefix)
    return (prefix + note)[:limit]
