"""Owned Spring cart/order DAG and independent business assertions; never DB bootstrap."""
from ..product_checks import check_checkout,check_cancel
from .spring_orders import checkout


def exercise(client,actors,catalog,run_id,record):
    """A dedicated food receipt is required; source food IDs are never invented.

    client is the existing DirectClient, already bound to a locked common workflow.
    record durably saves each newly created exact-ID ledger revision, before next mutation.
    All HTTP allocations are unique and remain no-replay under lost ACK.
    """
    if catalog.get('runId')!=run_id or not catalog.get('creationEvidence') or not catalog.get('dedicated') or catalog['quantity']<2:raise ValueError('dedicated catalog ownership missing')
    food_id=catalog['foodId'];owner=catalog['ownerRef'];customer=actors[owner];ledger=[];checks=[]
    def call(label,actor,oid,method,path,body=None,permission='read',expected=(200,)):
        s,b,e=client.request(label,actor,{'operationRef':oid,'method':method,'path':path,'body':body},permission)
        if s not in expected:raise ValueError('Spring fixture operation did not match expected status; no replay')
        return b,e
    for kind in ('DINE_IN','DELIVERY'):
        prefix=kind.lower()
        food,_=call(prefix+'-stock-before',owner,'food.read','GET','/api/foods/'+str(food_id))
        cart,_=call(prefix+'-cart-before',owner,'cart.read','GET','/api/cart')
        if cart['items']:raise ValueError('fixture customer cart not empty; no existing data edits')
        cart,e=call(prefix+'-cart-add',owner,'cart.add','POST','/api/cart/items',{'foodId':food_id,'quantity':catalog['quantity']},'mutation')
        item=next(i for i in cart['items'] if i['food']['id']==food_id)
        ledger.append({'runId':run_id,'kind':'cart-item','wireId':str(item['id']),'actorRef':owner,'creationEvidence':e,'state':'created'});record(ledger)
        # Dedicated update/remove positives are separate from checkout fixtures.
        cart,_=call(prefix+'-cart-update',owner,'cart.update','PUT','/api/cart/items/'+str(item['id']),{'quantity':catalog['quantity']},'mutation')
        call(prefix+'-cart-remove',owner,'cart.remove','DELETE','/api/cart/items/'+str(item['id']),permission='mutation')
        empty,_=call(prefix+'-cart-removed',owner,'cart.read','GET','/api/cart')
        if empty['items']:raise ValueError('cart remove poststate mismatch')
        ledger[-1]={**ledger[-1],'state':'removed'};record(ledger)
        call(prefix+'-cart-checkout-add',owner,'cart.add','POST','/api/cart/items',{'foodId':food_id,'quantity':catalog['quantity']},'mutation')
        order,e=call(prefix+'-checkout',owner,'order.create','POST','/api/orders',checkout(kind),'mutation',expected=(201,))
        ledger.append({'runId':run_id,'kind':'order','wireId':str(order['id']),'actorRef':owner,'creationEvidence':e,'state':'PENDING'});record(ledger)
        stock,_=call(prefix+'-stock-after',owner,'food.read','GET','/api/foods/'+str(food_id))
        cart,_=call(prefix+'-cart-after',owner,'cart.read','GET','/api/cart')
        read,_=call(prefix+'-order-read',owner,'order.read','GET','/api/orders/'+str(order['id']))
        if order!=read:raise ValueError('order snapshot changed at immediate readback')
        valid=check_checkout({'stock':food['stockQuantity']},{'stock':stock['stockQuantity'],'cart':cart,'order':read},
            food_id=food_id,quantity=catalog['quantity'],owner=int(customer['subject']),food_name=food['name'],unit_price=food['price'])
        checks.append({'kind':kind,'checkoutMatched':valid})
        if not valid:raise ValueError('checkout stock/snapshot/cart assertion failed')
        cancelled,_=call(prefix+'-cancel',owner,'order.cancel','DELETE','/api/orders/'+str(order['id']),permission='mutation')
        restored,_=call(prefix+'-stock-restored',owner,'food.read','GET','/api/foods/'+str(food_id))
        call(prefix+'-cancel-repeat',owner,'order.cancel','DELETE','/api/orders/'+str(order['id']),permission='mutation',expected=(409,))
        again,_=call(prefix+'-stock-repeat',owner,'food.read','GET','/api/foods/'+str(food_id))
        final,_=call(prefix+'-cancel-retained',owner,'order.read','GET','/api/orders/'+str(order['id']))
        valid=check_cancel({'order':read,'stock':stock['stockQuantity']},{'order':cancelled,'stock':restored['stockQuantity']},catalog['quantity'],{'stock':again['stockQuantity'],'order':final})
        checks[-1]['cancelMatched']=valid
        if not valid:raise ValueError('cancel stock/retained/repeat assertion failed')
        ledger[-1]={**ledger[-1],'state':'CANCELLED'};record(ledger)
    return {'ledger':ledger,'checks':checks,'cleanupStatus':'orders CANCELLED retained; fresh actors retained; no DB cleanup'}
