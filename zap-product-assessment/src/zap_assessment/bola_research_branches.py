"""Branch applicability and proof rollup; 1.0 historical inventories stay readable."""
DISPOSITIONS={'candidate','blocked','unsupported','not-applicable','not-run'}

def validate(inv, refs):
    if inv.get('schemaVersion') in (None,'bola-inventory/1.0'):return
    if inv.get('schemaVersion')!='bola-inventory/1.1':raise ValueError('inventory version')
    seen=set()
    for op in inv['operations']:
        branches=op.get('branches',[])
        if not branches:raise ValueError('missing branch inventory')
        for b in branches:
            if b['branchRef'] in seen or b['operationRef']!=op['operationRef']:raise ValueError('branch identity')
            seen.add(b['branchRef'])
            if b['disposition'] not in DISPOSITIONS or not b['predicate'] or not b['reason']:raise ValueError('branch disposition')
            if not b['evidenceRefs'] or not set(b['evidenceRefs'])<=refs:raise ValueError('branch provenance')
            if b['relevant'] and (not b['policyRefs'] or b['disposition']=='not-applicable'):raise ValueError('relevant branch cannot be not-applicable')
            for field in ('objectReferences','fixtureDependencies'): 
                if not isinstance(b[field],list):raise ValueError('branch dependency contract')
        if op['disposition']=='not-applicable' and any(b['relevant'] for b in branches):raise ValueError('operation rollup hides branch')

def coverage(inv, proofs):
    """Candidate is applicability only. Every tested claim needs explicit proof refs."""
    known={b['branchRef']:b for op in inv['operations'] for b in op['branches']}
    if set(proofs)-set(known):raise ValueError('unknown branch')
    rows=[];ops=[]
    for op in inv['operations']:
        bs=[]
        for b in op['branches']:
            p=proofs.get(b['branchRef'])
            if p is not None and (not p.get('caseRefs') or not p.get('evidenceRefs')):raise ValueError('branch proof absent')
            status=('tested' if p else b['disposition'] if b['disposition']!='candidate' else 'not-run') if b['relevant'] else 'not-applicable'
            row={**b,'executionStatus':status,'proof':p};rows.append(row);bs.append(row)
        relevant=[b for b in bs if b['relevant']]
        n=sum(b['executionStatus']=='tested' for b in relevant)
        state='not-applicable' if not relevant else 'tested' if n==len(relevant) else 'partial' if n else 'blocked' if any(b['executionStatus']=='blocked' for b in relevant) else 'not-run'
        ops.append({'operationRef':op['operationRef'],'coverage':state,'testedBranches':n,'relevantBranches':len(relevant)})
    return {'inventoryOperations':len(ops),'operations':ops,'branches':rows,'testedBranches':sum(b['executionStatus']=='tested' for b in rows),'relevantBranches':sum(b['relevant'] for b in rows)}
