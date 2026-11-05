"""Schema/auth compatibility before dispatch. Does not grant scope or execute tools.

Callers still apply the selected executor's admission, auth validation, target
binding, fixture/state checks and journal. Descriptors must come from the runtime
that will receive the request, never inferred from a source version or tool name.
"""
import copy
from jsonschema import Draft202012Validator


def listing(value):
    if isinstance(value,dict) and isinstance(value.get('result'),dict):value=value['result']
    if not isinstance(value,dict) or not isinstance(value.get('tools'),list) or value.get('nextCursor'):
        raise ValueError('full tools/list required')
    result={}
    for tool in value['tools']:
        if not isinstance(tool,dict) or not isinstance(tool.get('name'),str) or tool['name'] in result:
            raise ValueError('invalid/duplicate runtime tool')
        result[tool['name']]=tool
    return result


def contract(schema):
    """Keep JSON Schema semantics, excluding prose; no external resolution."""
    if isinstance(schema,dict):
        if any(k in schema and not schema[k].startswith('#/') for k in ('$ref','$dynamicRef','$recursiveRef')):
            raise ValueError('external schema reference not comparable offline')
        # Property names such as 'description' are data; remove prose only at schema nodes.
        result={}
        for k,v in schema.items():
            if k in ('description','title','examples','$comment'):continue
            if k in ('properties','$defs','definitions','patternProperties'):
                result[k]={name:contract(s) for name,s in v.items()}
            elif k in ('required','enum','type') and isinstance(v,list):result[k]=sorted(v,key=str)
            elif k in ('const','default'):result[k]=copy.deepcopy(v)
            else:result[k]=contract(v)
        return result
    if isinstance(schema,list):return [contract(v) for v in schema]
    return schema


def compare_contracts(left,right):
    """Compare actual runtime schemas; source requiredness/types aren't inferred."""
    a=listing(left);b=listing(right);rows=[]
    for name in sorted(a.keys() & b.keys()):
        sa=a[name].get('inputSchema');sb=b[name].get('inputSchema')
        if not isinstance(sa,dict) or not isinstance(sb,dict):
            rows.append({'name':name,'comparison':'not-comparable'});continue
        try:ca,cb=contract(sa),contract(sb)
        except ValueError:
            rows.append({'name':name,'comparison':'not-comparable','reason':'external schema reference'});continue
        pa=sa.get('properties',{});pb=sb.get('properties',{})
        rows.append({'name':name,'sameSchemaContract':ca==cb,
            'leftRequired':sa.get('required',[]),'rightRequired':sb.get('required',[]),
            'leftAdditionalProperties':sa.get('additionalProperties','unspecified'),
            'rightAdditionalProperties':sb.get('additionalProperties','unspecified'),
            'fieldsOnlyLeft':sorted(pa.keys()-pb.keys()),'fieldsOnlyRight':sorted(pb.keys()-pa.keys()),
            'changedFieldContracts':[{ 'field':p,'left':contract(pa[p]),'right':contract(pb[p])}
                                     for p in sorted(pa.keys() & pb.keys()) if contract(pa[p])!=contract(pb[p])],
            'leftContract':ca,'rightContract':cb})
    return {'onlyLeft':sorted(a.keys()-b.keys()),'onlyRight':sorted(b.keys()-a.keys()),'tools':rows,
            'meaning':'Actual schemas only. Description/auth semantics and execution must be checked separately.'}


def assess_executor(candidate, tool_name, arguments, *, auth_kind='none'):
    """Precise non-dispatch rejection. Unknown fields aren't assumed meaningful."""
    result={'executor':candidate['id'],'tool':tool_name,'compatible':False,'execution':'not-operated'}
    def reject(status,reason,**detail):return {**result,'status':status,'reason':reason,**detail}
    try:tools=listing(candidate['tools'])
    except ValueError:return reject('configuration-error','runtime-list-incomplete')
    if tool_name not in tools:return reject('not-exposed','tool-not-registered')
    schema=tools[tool_name].get('inputSchema')
    if not isinstance(schema,dict) or not isinstance(schema.get('properties'),dict):
        return reject('configuration-error','schema-not-comparable')
    missing=sorted(set(arguments)-schema['properties'].keys())
    if missing:return reject('not-operated','schema-field-missing',fields=missing,
        explanation='Tool exists; requested fields are not explicit capabilities, even if additionalProperties permits them.')
    try:
        contract(schema)
        Draft202012Validator.check_schema(schema)
        errors=list(Draft202012Validator(schema).iter_errors(arguments))
    except Exception:return reject('configuration-error','schema-not-comparable')
    if errors:
        return reject('input-error','schema-input-invalid',errors=[{'path':list(e.absolute_path),'keyword':e.validator} for e in errors])
    semantics=candidate.get('semantics',{}).get(tool_name,{})
    if tool_name=='zap_attack_start':
        if auth_kind=='none' and arguments.get('authSessionId'):
            return reject('configuration-error','auth-kind-not-declared')
        exact=any(k in arguments for k in ('method','postData'))
        if exact and semantics.get('exactBodyRequiresPreparedAuth') is not True:
            return reject('configuration-error','exact-request-semantics-unverified')
        if exact and (semantics.get('executionMode')!='direct' or auth_kind=='none' or not arguments.get('authSessionId')):
            return reject('configuration-error','exact-request-needs-direct-prepared-auth')
        if auth_kind!='none':
            if auth_kind=='json-bearer' and semantics.get('executionMode')!='direct':
                return reject('configuration-error','json-bearer-needs-direct')
            if auth_kind not in semantics.get('activeAuthKinds',[]):return reject('configuration-error','auth-kind-incompatible',authKind=auth_kind)
            if auth_kind not in candidate.get('configuredAuthKinds',[]):return reject('configuration-error','auth-kind-not-configured',authKind=auth_kind)
            if not arguments.get('authSessionId'):return reject('configuration-error','prepared-auth-session-missing',nextAction='bind the prepared session ID to this attack request')
            if candidate.get('sessionValidated') is not True:return reject('configuration-error','session-not-validated',nextAction='prepare/validate legitimate session before attack')
    return {**result,'compatible':True,'status':'compatible','reason':'actual-schema-and-auth-match',
            'acceptance':'compatibility only; baseline, delivery/response/readback and terminal execution remain required'}


def choose_executor(candidates,tool_name,arguments,*,auth_kind='none'):
    decisions=[assess_executor(c,tool_name,arguments,auth_kind=auth_kind) for c in candidates]
    selected=next((d['executor'] for d in decisions if d['compatible']),None)
    return {'selected':selected,'decisions':decisions,'execution':'not-operated',
            'nextAction':'apply selected executor admission, binding and journal before dispatch' if selected else 'resolve the classified gap; do not send known-invalid fields or enable expert/shared experimental flags'}


def classify_workload(request,*,auth_kind,role=None):
    """Shape/auth facts retained for executor selection, never a product exclusion."""
    body=request.get('body');nested=isinstance(body,dict) and any(isinstance(v,(dict,list)) for v in body.values())
    content=request.get('contentType','application/json' if body is not None else None)
    limitations=[]
    if auth_kind!='json-bearer':limitations.append('fe-auth-research-auth-kind')
    if nested:limitations.append('finite-native-flat-json-shape')
    if content and content!='application/json':limitations.append('finite-native-content-type')
    return {'authKind':auth_kind,'role':role,'nestedJson':nested,'contentType':content,
        'finiteLaneGaps':limitations,'responsibilityRetained':True,'runtimeQualified':False,
        'nextAction':'compare actual tools/list and configured auth semantics with choose_executor; use its compatible deployment under admission, or implement the classified mapping/primitive before a fresh allocation'}


def map_question_capability(question, candidates):
    """Review facts plus existing schema/auth routing; compatibility is not runtime proof.

    question supplies toolName/arguments/authKind/request and requiredSupport (a
    list from transport/auth/request/fixture/readback). Each candidate may declare
    support={primitive: {verified: bool, basis: str}} and verificationLevel with
    verificationBasis. No declaration bypasses choose_executor or admission.
    """
    required = question.get('requiredSupport', ['transport', 'auth', 'request', 'fixture', 'readback'])
    if not isinstance(required, list) or set(required) - {'transport', 'auth', 'request', 'fixture', 'readback'}:
        raise ValueError('invalid required capability support')
    qid = question.get('id', question.get('caseId'))
    auth = question.get('authKind', 'none')
    classification = classify_workload(question.get('request', {}), auth_kind=auth, role=question.get('role'))
    if not question.get('toolName'):
        return dict(questionId=qid, selectedExecutor=None, support={}, missingPrimitive=['request-mapping'],
            nextPreparation=['map-question-to-reviewed-tool-and-arguments'], verificationLevel='source-reviewed',
            classification=classification, decisions=[])
    routing = choose_executor(candidates, question['toolName'], question.get('arguments', {}), auth_kind=auth)
    rows = []
    for candidate, decision in zip(candidates, routing['decisions']):
        support = {}
        for key in required:
            fact = candidate.get('support', {}).get(key, {})
            support[key] = bool(isinstance(fact, dict) and fact.get('verified') is True and fact.get('basis'))
        # Request/auth schema checks remain mandatory even when operator facts claim support.
        if not decision['compatible']:
            for key in ('request', 'auth'):
                if key in support:support[key] = False
        missing = [k for k, verified in support.items() if not verified]
        level = candidate.get('verificationLevel', 'source-reviewed')
        if level not in ('source-reviewed', 'offline-checked', 'runtime-observed'):
            raise ValueError('invalid verificationLevel')
        if not candidate.get('verificationBasis') or level == 'runtime-observed' and not candidate.get('deploymentContext'):
            level = 'source-reviewed'
        rows.append(dict(executor=candidate['id'], compatible=decision['compatible'], support=support,
            missingPrimitive=missing, verificationLevel=level, deploymentContext=copy.deepcopy(candidate.get('deploymentContext'))))
    selected = next((r for r in rows if r['compatible'] and not r['missingPrimitive']), None)
    best = selected or next((r for r in rows if r['compatible']), rows[0] if rows else None)
    missing = best['missingPrimitive'] if best else list(required)
    return dict(questionId=qid, selectedExecutor=selected['executor'] if selected else None,
        support=best['support'] if best else {}, missingPrimitive=missing,
        nextPreparation=['prepare-' + k for k in missing] or (['resolve-schema-auth-routing'] if not selected else []),
        verificationLevel=best['verificationLevel'] if best else 'source-reviewed',
        deploymentContext=best.get('deploymentContext') if best else None, classification=classification,
        decisions=routing['decisions'], candidates=rows, execution='not-operated')
