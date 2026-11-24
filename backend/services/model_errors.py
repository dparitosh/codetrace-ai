"""Safe provider and answer diagnostics shared by agents and the companion."""
import json

import httpx
from services.answer_contract import AnswerValidationError


def model_failure_warning(error):
    """Classify failures without returning provider bodies, URLs or credentials."""
    if isinstance(error, AnswerValidationError):
        return f'Model output failed answer or citation validation ({error.code}). {error.detail}'
    if isinstance(error, httpx.TimeoutException):
        return 'Model request timed out. Check service responsiveness and AI_TIMEOUT_SECONDS / AI_AGENT_DEADLINE_SECONDS.'
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        guidance = {
            400: 'The service rejected the request. Check that the selected model supports native tool calling and that the endpoint accepts Ollama chat requests.',
            401: 'Model authentication failed. Check the configured API key and key header.',
            403: 'Model access was denied. Check service permissions and the configured key header.',
            404: 'Model or chat route was not found. Check the exact installed model name and the native /api/chat route.',
            429: 'The model service is rate limited or busy. Retry after capacity becomes available.',
        }.get(status, 'The model service returned an error. Check its availability and chat API contract.')
        return f'Model service returned HTTP {status}. {guidance}'
    if isinstance(error, httpx.RequestError):
        return 'Could not communicate with the model service. Check its address, network access and TLS configuration.'
    if isinstance(error, json.JSONDecodeError):
        return 'Model response was not valid JSON. The agent requires an answer object with citation_ids; use a model that follows the configured output contract.'
    # Only known, application-owned messages may select advice. Never echo arbitrary
    # exception text: transports and validation errors can contain sensitive input.
    advice = {
        'Invalid provider JSON response': 'Model service returned malformed JSON; no model answer was accepted.',
        'Chat readiness response was invalid': 'Model did not return the required readiness JSON object with ready=true.',
        'Select a chat model': 'No chat model is selected. Set an exact installed model in Administration.',
        'AI operation reached its total deadline': 'Agent analysis exceeded AI_AGENT_DEADLINE_SECONDS. Narrow the question or adjust the deadline after checking service latency.',
        'AI request exceeded the configured context byte budget': 'The request exceeded AI_CONTEXT_MAX_BYTES. Narrow the selected context or conversation before retrying.',
        'AI response exceeded the configured byte budget': 'The model response exceeded AI_MAX_RESPONSE_BYTES. Reduce response size or review the configured limit.',
        'Answer does not cite observed evidence': 'Model output failed answer or citation validation. It must return a bounded answer with valid observed [E#] references and citation_ids.',
        'Invalid tool-call batch': 'Model returned an invalid tool-call batch. Check native tool-calling compatibility.',
        'Tool is not permitted for this agent': 'Model requested a tool that this agent is not allowed to execute. Review the agent tool selection and model compatibility.',
        'Tool budget exhausted': 'Agent tool execution reached its step budget. Narrow the question before retrying.',
        'Select a resource from this snapshot': 'Model requested a resource outside the retained snapshot. Refine the selected context before retrying.',
        'Model output reached AI_MAX_OUTPUT_TOKENS': 'Model output reached AI_MAX_OUTPUT_TOKENS before a complete answer was accepted. Reduce requested detail or review the output-token limit.',
        'Final answer requested more tools': 'Model did not finish within AI_AGENT_MAX_STEPS and the bounded final-answer phase. Showing observed evidence.',
        'Invalid chat response': 'Model service returned an incompatible chat response. Check that the endpoint implements the native Ollama chat contract.',
    }
    return advice.get(str(error), 'Model response or tool arguments were invalid. Check native tool-calling and JSON output compatibility; showing observed graph evidence.')
