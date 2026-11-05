"""Bounded read-only async observation polling; no mutation or policy verdicts."""
import asyncio
import inspect
import math
import time

STAGES = {'ack', 'domain', 'processing', 'persistence', 'consumer'}
PRIVATE_KEYS = {'token', 'authorization', 'cookie', 'setcookie', 'password', 'passwordvalue',
                'secret', 'clientsecret', 'privatekey', 'apikey', 'accesstoken',
                'refreshtoken', 'setuptoken', 'sessiontoken'}
RAW_KEYS = {'request', 'response', 'requestheader', 'responseheader', 'requestbody', 'responsebody', 'exception', 'headers'}


def safe_facts(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('fact keys must be strings')
            normalized = key.lower().replace('-', '').replace('_', '')
            if normalized in RAW_KEYS:
                continue
            result[key] = '[private]' if normalized in PRIVATE_KEYS else safe_facts(item)
        return result
    if isinstance(value, (tuple, list)):
        return [safe_facts(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError('facts must be finite JSON')


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('positive finite ' + label + ' required')
    return value


async def wait_for_observation(sample, evaluate, *, context, timeout_seconds, interval_seconds,
                               remaining_seconds, clock=time.monotonic, sleep=asyncio.sleep,
                               cancelled=lambda: False):
    """sample(*, context, timeout_seconds) MUST be async and read-only.

    asyncio.wait_for bounds each sample as well as the adapter transport timeout.
    The adapter must propagate timeout_seconds to its transport, honor cancellation
    and never perform blocking I/O on the event loop. Evaluate returns a dictionary
    with status, stage, facts and missingConditions. Reader exceptions end this wait;
    an adapter may classify transient reads as pending within the same budget.
    """
    if not isinstance(context, dict) or context.get('stage') not in STAGES:
        raise ValueError('explicit observation stage/context required')
    if not inspect.iscoroutinefunction(sample):
        raise ValueError('async read-only sample required')
    positive(timeout_seconds, 'timeout');positive(interval_seconds, 'interval')
    initial_remaining = remaining_seconds() if callable(remaining_seconds) else remaining_seconds
    positive(initial_remaining, 'remaining time')
    started = clock();deadline = started + min(timeout_seconds, initial_remaining)
    facts = {};missing = [];stage = context['stage']
    def result(status, **extra):
        return dict(status=status, stage=stage, elapsed=max(0, clock() - started),
            missingConditions=list(missing), facts=facts, outcomeUnknown=context.get('outcomeUnknown', False), **extra)
    while True:
        if cancelled():
            return result('cancelled')
        budget = deadline - clock()
        if callable(remaining_seconds):
            current = remaining_seconds()
            if isinstance(current, bool) or not isinstance(current, (int, float)) or not math.isfinite(current):
                raise ValueError('finite remaining time required')
            budget = min(budget, current)
        if budget <= 0:
            return result('timeout')
        try:
            value = await asyncio.wait_for(sample(context=dict(context), timeout_seconds=budget), timeout=budget)
        except asyncio.TimeoutError:
            return result('timeout')
        except asyncio.CancelledError:
            return result('cancelled')
        except Exception as error:
            return result('reader-error', errorType=type(error).__name__)
        if cancelled():
            return result('cancelled')
        if clock() >= deadline or callable(remaining_seconds) and remaining_seconds() <= 0:
            return result('timeout')
        try:
            if not isinstance(value, dict) or not isinstance(value.get('context'), dict):
                raise ValueError('sample identity context required')
            identity = {k: v for k, v in context.items() if k not in ('stage', 'outcomeUnknown')}
            if any(value['context'].get(k) != v for k, v in identity.items()):
                return result('context-mismatch')
            decision = evaluate(value)
            status = decision['status']
            if status not in ('ready', 'pending', 'terminal-failure', 'context-mismatch'):
                raise ValueError('invalid observation decision')
            facts = safe_facts(decision.get('facts', {}))
            missing = decision.get('missingConditions', [])
            if not isinstance(missing, list) or any(not isinstance(m, str) for m in missing):
                raise ValueError('invalid missing conditions')
            if status == 'ready' and (decision.get('stage') != stage or value.get('stage') != stage):
                status = 'pending';missing = ['required-stage:' + stage]
            if status != 'pending':
                return result(status)
        except Exception as error:
            return result('reader-error', errorType=type(error).__name__)
        budget = deadline - clock()
        if callable(remaining_seconds):
            budget = min(budget, remaining_seconds())
        if budget <= 0:
            return result('timeout')
        try:
            waited = sleep(min(interval_seconds, budget))
            if inspect.isawaitable(waited):
                await waited
        except asyncio.CancelledError:
            return result('cancelled')
