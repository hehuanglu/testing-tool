"""Independent observation checker: consumes locked expectations; no executor imports/pass flags."""
from decimal import Decimal

def pointer(value, path):
    for part in path.strip('/').split('/') if path else []:
        key=part.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
    return value

def check_case(expected, observed):
    reasons=[]
    try:
        if expected['access']=='unknown':return {'outcome':'inconclusive','reasons':['policy-unresolved']}
        status=observed['response']['status']
        if expected['access']=='deny':
            if status not in expected['denialStatuses']:reasons.append('access-policy-violated')
            if observed.get('disclosed') is not False:reasons.append('disclosure-unresolved-or-observed')
            if 'before' not in observed or 'after' not in observed:return {'outcome':'inconclusive','reasons':reasons+['poststate-missing']}
            if observed['before']!=observed['after'] or observed.get('relatedBefore')!=observed.get('relatedAfter'):reasons.append('side-effect-after-denial')
        else:
            if status not in expected['successStatuses']:reasons.append('success-status')
            for p,v in expected.get('responseEquals',{}).items():
                if pointer(observed['response']['body'],p)!=v:reasons.append('response-projection')
            for p,v in expected.get('postEquals',{}).items():
                if pointer(observed['after'],p)!=v:reasons.append('post-transition')
            if expected.get('postUnchanged') and observed['before']!=observed['after']:reasons.append('unexpected-side-effect')
        for path,value in expected.get('relatedPostEquals',{}).items():
            if pointer(observed['relatedAfter'],path)!=value:reasons.append('related-poststate')
        if expected.get('createdResourceRead'):
            spec=expected['createdResourceRead'];created=observed['createdRead'];response=observed['response']['body']
            if (created['status']!=200 or str(pointer(created['body'],spec['idPointer']))!=str(pointer(response,spec['responseIdPointer']))
                    or str(pointer(created['body'],spec['ownerPointer']))!=str(spec['expectedOwner'])):reasons.append('created-resource-binding')
        if expected.get('checkout'):
            contract=expected['checkout'];kwargs={k:contract[k] for k in ('food_id','quantity','owner','food_name','unit_price')}
            before={'stock':pointer(observed['relatedBefore'],contract['stockPointer'])}
            after={'stock':pointer(observed['relatedAfter'],contract['stockPointer']),'cart':observed['after'],'order':observed['createdRead']['body']}
            if not check_checkout(before,after,**kwargs):reasons.append('checkout-state')
        if expected.get('pagination') and not check_pages(observed.get('pages',[]),**expected['pagination']):return {'outcome':'inconclusive','reasons':reasons+['collection-pagination-incomplete']}
        if observed.get('captureComplete') is not True:return {'outcome':'inconclusive','reasons':reasons+['unknown-projection']}
        return {'outcome':'violated' if reasons else 'matched','reasons':reasons}
    except (KeyError,IndexError,ValueError,TypeError):return {'outcome':'inconclusive','reasons':reasons+['observation-incomplete']}

def check_pages(pages, *, rows, page, size, total, identity, expected_ids, owner=None, expected_owner=None, terminal=False):
    try:
        if not pages:return False
        count=pointer(pages[0],total);width=pointer(pages[0],size)
        if type(count)!=int or type(width)!=int or count<0 or width<1:return False
        # terminal means an observed empty page. For total=0 page 0 already is
        # that page; a nonempty collection needs one after its data pages.
        data_pages=(count+width-1)//width
        if len(pages)!=max(1,data_pages+int(terminal)):return False
        if len(expected_ids)!=len(set(map(str,expected_ids))):return False
        ids=[]
        for i,p in enumerate(pages):
            values=pointer(p,rows)
            if pointer(p,page)!=i or pointer(p,size)!=width or pointer(p,total)!=count or len(values)!=min(width,max(0,count-i*width)):return False
            if owner is not None and any(str(pointer(r,owner))!=str(expected_owner) for r in values):return False
            ids.extend(str(pointer(r,identity)) for r in values)
        return len(ids)==count==len(set(ids)) and set(ids)==set(map(str,expected_ids))
    except (KeyError,IndexError,TypeError,ValueError):return False

def check_checkout(before, after, *, food_id, quantity, owner, food_name, unit_price):
    try:
        order=after['order'];item=next(v for v in order['items'] if v['foodId']==food_id)
        return (before['stock']-after['stock']==quantity and after['cart']['items']==[] and order['userId']==owner
            and order['status']=='PENDING' and item['quantity']==quantity and item['foodName']==food_name
            and Decimal(str(item['unitPrice']))==Decimal(str(unit_price))
            and Decimal(str(item['lineTotal']))==Decimal(str(unit_price))*quantity
            and Decimal(str(order['totalAmount']))==sum(Decimal(str(v['lineTotal'])) for v in order['items']))
    except (KeyError,StopIteration,TypeError,ValueError):return False

def check_cancel(before, after, quantity, repeated=None):
    try:
        return (before['order']['id']==after['order']['id'] and before['order']['status']=='PENDING'
            and after['order']['status']=='CANCELLED' and after['stock']-before['stock']==quantity
            and (repeated is None or repeated['stock']==after['stock'] and repeated['order']['status']=='CANCELLED'))
    except (KeyError,TypeError):return False
