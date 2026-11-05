"""Synthetic reviewed facts, independent of any product or scanner runtime."""
import copy


def context(**changes):
    value = dict(product='synthetic', environment='offline', origin='https://fixture.invalid', build='b1',
        method='PATCH', route='/objects/{id}', inputLocation='body:setting', actorRef='owner', role='member',
        relation='owner', objectRef='object-one', state='active', objective='personal-setting')
    value.update(changes)
    return value


def case(cid='pin', units=None, **changes):
    row = dict(caseId=cid, question='Is this setting scoped to its owner?', evidenceRefs=['reviewed-ui'],
        featureIds=[cid], objectiveDepth='persistence', requiredEvidence=units or ['own-read', 'sibling-read'],
        coverageContext=context(), expectedBehavior='Only owner setting changes', expectationBasis='Assigned synthetic policy', prerequisites=[], actions=[])
    row.update(changes)
    return row


def inventory(cases=None, **changes):
    cases = copy.deepcopy(cases if cases is not None else [case()])
    value = dict(workflowVersion=1, productLocation='/synthetic', track='fe-authenticated', complete=True, cases=cases,
        engagement=dict(objective='Assess assigned settings', scopeBasis='Synthetic user assignment', methodBoundary='ZAP observations', authorityNotes=[], limits=[]),
        discoveryReview=dict(sources=[dict(id='ui', kind='ui-source', location='synthetic-ui', reviewedScope='assigned settings')],
            features=[dict(id=c['caseId'], name=c['caseId'], sourceIds=['ui'], disposition='mapped', caseIds=[c['caseId']]) for c in cases],
            reviewedCaseIds=[c['caseId'] for c in cases], unresolved=[], basis='Reviewed assigned action and its API consumer'))
    value.update(changes)
    return value


def operation(oid='attempt-a', **changes):
    value = dict(id=oid, status='partial', coverageContext=context(), readback=dict(pin=dict(ownerChanged=True, siblingUnchanged=True)))
    value.update(changes)
    return value


def link(oid='attempt-a', units=None, **changes):
    value = dict(operationId=oid, observationUnits=units or ['own-read', 'sibling-read'], resultPath='/readback/pin',
        resultRead=True, basis='Owner and sibling read independently compared', context=context(), role='support')
    value.update(changes)
    return value


def observed(links=None, **changes):
    value = dict(outcome='matched', resultRead=True, basis='Compared observed settings', evidenceLinks=links if links is not None else [link()])
    value.update(changes)
    return value


def action(aid, kind='execute', effect='read', **changes):
    return dict(id=aid, kind=kind, effect=effect, **changes)


class FakeTime:
    def __init__(self):self.now=0;self.sleeps=[]
    def clock(self):return self.now
    async def sleep(self, seconds):self.sleeps.append(seconds);self.now+=seconds
