"""One strict answer contract shared by graph agents and the companion."""
import json
import re
from core.config import settings


class AnswerValidationError(ValueError):
    """Application-owned diagnostics; never include rejected model text."""
    REASONS = {
        'invalid_shape': 'Return a JSON object containing answer and citation_ids.',
        'invalid_answer': 'answer must be a nonempty text string.',
        'answer_too_long': 'answer exceeds AI_MAX_ANSWER_CHARACTERS.',
        'missing_citation_ids': 'The required citation_ids array is missing.',
        'invalid_citation_ids': 'citation_ids must be an array of evidence ID strings.',
        'missing_inline_citations': 'answer contains no inline [E#] references.',
        'unlisted_inline_citations': 'An inline reference is missing from citation_ids.',
        'unknown_citations': 'A reference identifies evidence not observed in this turn.',
    }

    def __init__(self, code):
        self.code = code if code in self.REASONS else 'invalid_shape'
        self.detail = self.REASONS[self.code]
        super().__init__('Answer does not cite observed evidence')


def inline_citations(answer):
    return set(re.findall(r'\[(E\d+)\]', answer))


def validate_answer(text, evidence):
    if not isinstance(text, str):
        raise AnswerValidationError('invalid_shape')
    try:
        parsed = json.loads(text)
    except RecursionError:
        raise AnswerValidationError('invalid_shape') from None
    if not isinstance(parsed, dict):
        raise AnswerValidationError('invalid_shape')
    body, used = parsed.get('answer'), parsed.get('citation_ids')
    if not isinstance(body, str) or not body.strip():
        raise AnswerValidationError('invalid_answer')
    if len(body) > settings.AI_MAX_ANSWER_CHARACTERS:
        raise AnswerValidationError('answer_too_long')
    if 'citation_ids' not in parsed:
        raise AnswerValidationError('missing_citation_ids')
    if not isinstance(used, list) or any(not isinstance(item, str) for item in used):
        raise AnswerValidationError('invalid_citation_ids')
    inline = inline_citations(body)
    valid = {item['citation_id'] for item in evidence}
    if not inline:
        raise AnswerValidationError('missing_inline_citations')
    if not inline <= valid or not set(used) <= valid:
        raise AnswerValidationError('unknown_citations')
    if not inline <= set(used):
        raise AnswerValidationError('unlisted_inline_citations')
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
    if marker and not inline_citations(prefix):
        prefix = prefix[:max(0, limit - len(note) - len(marker) - 1)].rstrip()
        prefix = re.sub(r'\[E\d*$', '', prefix).rstrip()
        prefix = f'{prefix} {marker}' if prefix else marker
    return prefix + note
