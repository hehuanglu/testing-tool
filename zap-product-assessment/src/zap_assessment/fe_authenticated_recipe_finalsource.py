"""Explicit product adapter. Product routes/selectors/DTOs live here, never in the engine."""
from pathlib import Path
import re
from .fe_authenticated_contract import digest,validate_journeys

def discover(product):
    root=Path(product).resolve()
    files=sorted(set([*root.joinpath('fe/src').rglob('*.tsx'),*root.joinpath('fe/src/api').glob('*.ts'),*root.joinpath('be/src/modules').rglob('*controller.ts'),*root.joinpath('be/src/modules').rglob('*service.ts'),*root.joinpath('be/src/modules').rglob('*dto.ts'),*root.joinpath('be/src/modules').rglob('*entity.ts'),root/'fe/nginx.conf',root/'compose.yaml']))
    sources=[{'id':'s'+str(i),'path':str(f),'sha256':digest(f)} for i,f in enumerate(files)];source_ids={str(f.relative_to(root)):s['id'] for f,s in zip(files,sources)}
    router=(root/'fe/src/router/AppRouter.tsx').read_text();paths=re.findall(r"path: '([^']+)'",router)
    expected={'/login','/register','/transactions','/transactions/new','/accounts','/accounts/:id','/accounts/new','/expenses','/bills','new','/goals','/goals/new','/goals/:goalId/edit','/','*'}
    if set(paths)!=expected:raise ValueError('router inventory changed; reconcile source before execution')
    context=(root/'fe/src/context/AuthContext.tsx').read_text();key=re.search(r"const tokenKey = '([^']+)'",context)
    if not key:raise ValueError('storage mapping unresolved')
    prov=[source_ids['fe/src/router/AppRouter.tsx'],source_ids['fe/src/context/AuthContext.tsx']];js=[];rs=[];groups=[{'id':'main-a','actorRef':'actor-a','actorRefs':['actor-a','actor-b'],'remember':True,'terminal':'logout'},{'id':'session-a','actorRef':'actor-a','remember':False,'terminal':'dispose'},{'id':'isolation-b','actorRef':'actor-b','remember':True,'terminal':'logout'}]
    def p(kind,selector=None,value=None,**kw):return {k:v for k,v in dict(kind=kind,selector=selector,value=value,**kw).items() if v is not None}
    def nav(path,selector):return {'action':'navigate','path':path,'predicate':p('exists',selector)}
    def fill(selector,value=None,fixture=None):return {'action':'fill','selector':selector,**({'fixtureField':fixture} if fixture else {'value':value})}
    def click(selector,predicate=None):return {'action':'click','selector':selector,**({'predicate':predicate} if predicate else {})}
    def net(method,path,statuses=None,absent=False):return {'method':method,'path':path,**({'absent':True} if absent else {'statuses':statuses or [200]})}
    def add(id,path,steps,ui,network=(),effect='read',post=(),group='main-a',phase='authenticated',state='owned',source=None,prerequisites=(),setup=(),actor_override=None):
        pr=prov+([source_ids[source]] if source else []);actor=actor_override or next(g['actorRef'] for g in groups if g['id']==group)
        js.append({'id':id,'responsibilityIds':[id],'provenance':pr,'sessionGroup':group,'actorRef':actor,'phase':phase,'prerequisites':list(prerequisites),'steps':steps,'expectedUi':ui,'expectedNetwork':list(network),'postState':list(post),'effect':effect,'evidenceDepth':'W3C UI + protected actor + broker/native network + post-state','setupRefs':list(setup),'setupPermissions':['db-prerequisite'] if set(setup)&{'category','bill','paged-transactions','expense-transaction'} else []})
        rs.append({'id':id,'provenance':pr,'route':path,'action':id,'role':'user','state':state,'input':effect,'journeyIds':[id],'branchIds':[effect],'disposition':'planned'})
    def post(path,pointer,value=None,fixture=None):return {'action':'post-state','path':path,'pointer':pointer,**({'expectedFixture':fixture} if fixture else {'expectedValue':value})}
    def bind(path,pointer,value,field,match=None,fixture=None):return {'action':'readback','path':path,'pointer':pointer,'valuePointer':value,'fixtureField':field,**({'matchPointer':match,'matchFixture':fixture} if match else {})}
    for group in groups:
        steps=[nav('/login','#login-email'),fill('#login-email',fixture='username'),fill('#login-password',fixture='password')]
        if not group['remember']:steps.append(click('label:has(input[type="checkbox"])'))
        steps +=[{'action':'submit','selector':'button[type="submit"]','predicate':p('urlPath',value='/')},{'action':'identity-probe'}]
        add('login-'+group['id'],'/login',steps,[p('text','section[aria-labelledby="starter-heading"] p','Welcome'),p('storagePresent',key=key[1],area='local' if group['remember'] else 'session')],[net('POST','/api/auth/login'),net('GET','/api/v1/accounts')],group=group['id'],phase='login-pending',source='fe/src/components/auth/LoginForm.tsx')
        if group['id']!='main-a':
            add('reopen-'+group['id'],'/accounts',[{'action':'reopen','path':'/accounts','predicate':p('exists','a[href="/accounts/new"]' if group['remember'] else '#login-email')}],[p('urlPath',value='/accounts' if group['remember'] else '/login'),p('storagePresent' if group['remember'] else 'storageAbsent',key=key[1],area='local' if group['remember'] else 'session')],group=group['id'])
            if not group['remember']:
                before=js.pop();rs.pop()
                add('session-a-new-tab','/accounts',[{'action':'new-tab','path':'/accounts','predicate':p('exists','#login-email')}],[p('storageAbsent',key=key[1],area='session'),p('urlPath',value='/login')],[net('GET','/api/v1/accounts',absent=True)],effect='lifecycle',group=group['id'])
                js.append(before);rs.append({'id':before['id'],'provenance':before['provenance'],'route':'/accounts','action':before['id'],'role':'user','state':'owned','input':'lifecycle','journeyIds':[before['id']],'branchIds':['lifecycle'],'disposition':'planned'})
                add('session-a-relogin','/login',[nav('/login','#login-email'),fill('#login-email',fixture='username'),fill('#login-password',fixture='password'),click('label:has(input[type="checkbox"])'),click('button[type="submit"]',p('urlPath',value='/')),{'action':'identity-probe'},nav('/accounts','#accounts-heading'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','#accounts-heading')}],[p('storagePresent',key=key[1],area='session'),p('storageAbsent',key=key[1]),p('exists','#accounts-heading')],[net('POST','/api/auth/login'),net('GET','/api/v1/accounts')],group=group['id'],phase='login-pending',effect='lifecycle')
                continue
            add('reload-'+group['id'],'/accounts',[nav('/accounts','#accounts-heading'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','#accounts-heading')},{'action':'identity-probe'}],[p('exists','a[href="/accounts/new"]'),p('storagePresent',key=key[1],area='local' if group['remember'] else 'session')],[net('GET','/api/v1/accounts')],group=group['id']);continue
        add('home-shell','/',[nav('/','#starter-heading'),{'action':'identity-probe'},click('a[href="/accounts"]',p('exists','#accounts-heading'))],[p('exists','a[href="/accounts/new"]')],[net('GET','/api/v1/accounts')],source='fe/src/components/layout/AppShell.tsx')
        add('authenticated-not-found','/owned-fe-missing',[nav('/owned-fe-missing','#not-found-heading'),{'action':'identity-probe'},nav('/accounts','#accounts-heading')],[p('exists','a[href="/accounts/new"]')],[net('GET','/api/v1/accounts')],source='fe/src/pages/NotFoundPage.tsx')
        for name,path,text,network in [('accounts','/accounts',"You haven't linked any accounts.",[net('GET','/api/v1/accounts')]),('transactions','/transactions','You have no transactions recorded.',[net('GET','/api/v1/transactions')]),('bills','/bills',"You don't have any bills due soon.",[net('GET','/api/v1/bills')]),('expenses','/expenses','No spending data has been recorded for analysis.',[net('GET','/api/v1/expenses/summary'),net('GET','/api/v1/expenses/breakdown',[404])])]:
            add(name+'-empty',path,[nav(path,'body'),{'action':'identity-probe'},{'action':'wait','predicate':p('text','body',text)}],[p('text','body',text)],network,state='empty')
        add('accounts-populated','/accounts',[nav('/accounts','#accounts-heading'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','button[aria-label^="View details"]')}],[p('exists','button[aria-label^="View details"]')],[net('GET','/api/v1/accounts')],state='populated',source='fe/src/pages/AccountListPage.tsx',setup=('owned-account',))
        add('account-create-validation','/accounts/new',[nav('/accounts/new','#bank_name'),click('button[type="submit"]')],[p('text','#bank_name-error','Bank is required.'),p('text','#account_number_full-error','4 to 34 digits')],[net('POST','/api/v1/accounts',absent=True)],'validation',source='fe/src/pages/AddAccountPage.tsx')
        add('account-create-cancel','/accounts/new',[nav('/accounts/new','#bank_name'),fill('#bank_name',fixture='accountMarker'),click('a[href="/accounts"]')],[p('urlPath',value='/accounts')],[net('POST','/api/v1/accounts',absent=True)],'validation',source='fe/src/pages/AddAccountPage.tsx')
        add('account-create','/accounts/new',[nav('/accounts/new','#bank_name'),fill('#bank_name',fixture='accountMarker'),fill('#account_type','Checking'),fill('#branch_name','Owned FE branch'),fill('#account_number_full',fixture='accountNumber'),fill('#balance','123.45'),click('button[type="submit"]',p('urlPath',value='/accounts')),{'action':'reload','predicate':p('exists','button[aria-label^="View details"]')},{'action':'identity-probe'}],[p('exists','button[aria-label^="View details"]')],[net('POST','/api/v1/accounts',[201]),net('GET','/api/v1/accounts')],'mutation',[{'kind':'owned-readback','ref':'account-create'}],source='fe/src/pages/AddAccountPage.tsx')
        add('account-detail','/accounts/{ownedAccountId}',[nav('/accounts/{ownedAccountId}','#account-summary-title'),{'action':'identity-probe'}],[p('text','section[aria-labelledby="account-summary-title"]','Owned')],[net('GET','/api/v1/accounts/{ownedAccountId}')],source='fe/src/pages/AccountDetailPage.tsx',setup=('owned-account',))
        add('account-invalid-id','/accounts/invalid',[nav('/accounts/invalid','#accounts-heading'),{'action':'identity-probe'}],[p('urlPath',value='/accounts')],[net('GET','/api/v1/accounts/invalid',absent=True)],source='fe/src/pages/AccountDetailPage.tsx')
        detail='section[aria-labelledby="account-summary-title"]';edit=detail+' button:first-of-type';remove=detail+' button:last-of-type'
        add('account-edit-validation','/accounts/{ownedAccountId}',[nav('/accounts/{ownedAccountId}','#account-summary-title'),click(edit,p('exists','#edit-account-title')),fill('#bank_name',''),fill('#balance','-1'),click('form button[type="submit"]')],[p('text','form','Bank is required.'),p('text','form','Current balance must be between')],[net('PUT','/api/v1/accounts/{ownedAccountId}',absent=True)],'validation',source='fe/src/components/accounts/AccountEditForm.tsx',setup=('owned-account',))
        add('account-edit-cancel','/accounts/{ownedAccountId}',[nav('/accounts/{ownedAccountId}','#account-summary-title'),click(edit,p('exists','#edit-account-title')),fill('#bank_name','Unsaved owned name'),click('form button[type="button"]',p('exists','#account-summary-title'))],[p('exists','#account-summary-title')],[net('PUT','/api/v1/accounts/{ownedAccountId}',absent=True)],'validation',source='fe/src/components/accounts/AccountEditForm.tsx',setup=('owned-account',))
        add('account-edit-save','/accounts/{ownedAccountId}',[nav('/accounts/{ownedAccountId}','#account-summary-title'),click(edit,p('exists','#edit-account-title')),fill('#bank_name',fixture='editedAccountMarker'),click('form button[type="submit"]',p('exists','#account-summary-title')),{'action':'reload','predicate':p('exists','#account-summary-title')},{'action':'identity-probe'}],[p('text',detail,fixtureField='editedAccountMarker')],[net('PUT','/api/v1/accounts/{ownedAccountId}'),net('GET','/api/v1/accounts/{ownedAccountId}')],'mutation',[{'kind':'owned-readback','ref':'account-edit-save'}],source='fe/src/components/accounts/AccountEditForm.tsx',setup=('owned-account',))
        add('account-delete-cancel','/accounts/{ownedAccountId}',[nav('/accounts/{ownedAccountId}','#account-summary-title'),click(remove,p('exists','#delete-account-title')),click('[role="dialog"] button:first-of-type',p('absent','#delete-account-title'))],[p('exists','#account-summary-title')],[net('DELETE','/api/v1/accounts/{ownedAccountId}',absent=True)],'validation',source='fe/src/components/accounts/DeleteAccountModal.tsx',setup=('owned-account',))
        add('native-body-ui-baseline','/accounts/{nativeAccountId}',[nav('/accounts/{nativeAccountId}','#account-summary-title'),{'action':'identity-probe'},click(edit,p('exists','#edit-account-title')),fill('#bank_name',fixture='nativeAccountMarker'),click('form button[type="submit"]',p('exists','#account-summary-title')),{'action':'reload','predicate':p('text',detail,fixtureField='nativeAccountMarker')},{'action':'identity-probe'},post('/api/v1/accounts/{nativeAccountId}','/data/bank_name',fixture='nativeAccountMarker')],[p('text',detail,fixtureField='nativeAccountMarker')],[net('PUT','/api/v1/accounts/{nativeAccountId}'),net('GET','/api/v1/accounts/{nativeAccountId}')],'mutation',[{'kind':'owned-readback','ref':'native-body-ui-baseline'}],setup=('native-account',))
        add('native-body-ui-readback','/accounts/{nativeAccountId}',[nav('/accounts/{nativeAccountId}','#account-summary-title'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','#account-summary-title')},post('/api/v1/accounts/{nativeAccountId}','/data/bank_name',fixture='nativeObservedBankName')],[p('text',detail,fixtureField='nativeObservedBankName')],[net('GET','/api/v1/accounts/{nativeAccountId}')],setup=('native-account',))
        add('transactions-populated','/transactions',[nav('/transactions','#transactions-heading'),{'action':'identity-probe'}],[p('exists','[role="tab"]')],[net('GET','/api/v1/transactions')],state='populated',source='fe/src/pages/TransactionsPage.tsx',setup=('paged-transactions',))
        for typ,nth in [('revenue',2),('expense',3)]:
            add('transactions-tab-'+typ,'/transactions',[nav('/transactions','#transactions-heading'),click('[role="tab"]:nth-of-type('+str(nth)+')'),{'action':'identity-probe'}],[p('attribute','[role="tab"]:nth-of-type('+str(nth)+')','true',attribute='aria-selected')],[net('GET','/api/v1/transactions')],state='populated',source='fe/src/pages/TransactionsPage.tsx',setup=('paged-transactions',))
        add('transactions-page','/transactions',[nav('/transactions','main section button:not([role="tab"])'),click('main section button:not([role="tab"])',p('absent','main section button:not([role="tab"])')),{'action':'identity-probe'}],[p('exists','#transactions-heading')],[net('GET','/api/v1/transactions')],state='populated-multiple-pages',source='fe/src/pages/TransactionsPage.tsx',setup=('paged-transactions',))
        add('transaction-options-validation','/transactions/new',[nav('/transactions/new','#categoryId option:nth-child(2)'),{'action':'wait','predicate':p('exists','#accountId option:nth-child(2)')},{'action':'identity-probe'},click('button[type="submit"]')],[p('exists','#categoryId option:nth-child(2)'),p('exists','#accountId option:nth-child(2)'),p('text','form','required')],[net('GET','/api/v1/accounts/options'),net('GET','/api/v1/categories/options'),net('POST','/api/v1/transactions',absent=True)],'validation',source='fe/src/pages/AddTransactionPage.tsx',setup=('category','owned-account'))
        for typ in ('Revenue','Expense'):
            steps=[nav('/transactions/new','#categoryId option:nth-child(2)'),{'action':'wait','predicate':p('exists','#accountId option:nth-child(2)')},fill('#itemDescription',fixture='transactionMarker'+typ),{'action':'select','selector':'#categoryId','fixtureField':'categoryId'},fill('#amount','7.25'),{'action':'select','selector':'#type','value':typ},{'action':'select','selector':'#accountId','fixtureField':'ownedAccountId'},fill('#transactionDate',fixture='today'),fill('#shopName','Owned FE merchant'),fill('#paymentMethod','Cash'),click('button[type="submit"]',p('urlPath',value='/transactions')),{'action':'reload','predicate':p('exists','#transactions-heading')},{'action':'identity-probe'}]
            add('transaction-create-'+typ.lower(),'/transactions/new',steps,[p('exists','#transactions-heading')],[net('POST','/api/v1/transactions',[201]),net('GET','/api/v1/transactions')],'mutation',[{'kind':'owned-readback','ref':'transaction-create-'+typ.lower()}],source='fe/src/pages/AddTransactionPage.tsx',setup=('category','owned-account'))
        add('transaction-create-cancel','/transactions/new',[nav('/transactions/new','#add-transaction-heading'),fill('#itemDescription','Unsaved owned transaction'),click('section[aria-labelledby="add-transaction-heading"] > div button')],[p('urlPath',value='/transactions')],[net('POST','/api/v1/transactions',absent=True)],'validation',setup=('category','owned-account'))
        add('expenses-populated','/expenses',[nav('/expenses','#breakdown-title'),{'action':'identity-probe'}],[p('exists','[aria-label="Monthly expense chart"]'),p('exists','article h3')],[net('GET','/api/v1/expenses/summary'),net('GET','/api/v1/expenses/breakdown')],state='populated',source='fe/src/pages/ExpenseSummaryPage.tsx',setup=('expense-transaction',))
        add('expenses-month','/expenses',[nav('/expenses','article h3'),fill('input[type="month"]',fixture='previousMonth'),{'action':'identity-probe'}],[p('exists','#breakdown-title')],[net('GET','/api/v1/expenses/breakdown')],source='fe/src/pages/ExpenseSummaryPage.tsx')
        add('bills-populated','/bills',[nav('/bills','#bills-title'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','[role="table"]')}],[p('exists','[role="table"]')],[net('GET','/api/v1/bills')],state='populated',source='fe/src/pages/BillsPage.tsx',setup=('bill',))
        add('bills-unavailable-create','/bills/new',[nav('/bills/new','#new-bill-title'),click('a[href="/bills"]',p('exists','#bills-title'))],[p('exists','#bills-title')],[net('POST','/api/v1/bills',absent=True)],source='fe/src/pages/NewBillPage.tsx')
        add('goals-empty','/goals',[nav('/goals','h1'),{'action':'identity-probe'}],[p('text','main','No savings goal for this month.')],[net('GET','/api/v1/goals'),net('GET','/api/v1/savings/summary')],state='empty',source='fe/src/pages/GoalsPage.tsx')
        add('goal-create-validation','/goals/new',[nav('/goals/new','[role="dialog"]'),click('[role="dialog"] button[type="submit"]')],[p('text','[role="dialog"]','Target amount must be greater than 0.')],[net('POST','/api/v1/goals',absent=True)],'validation',source='fe/src/components/goals/CreateGoalModal.tsx')
        add('goal-create-cancel','/goals/new',[nav('/goals/new','[role="dialog"]'),click('[aria-label="Close create goal dialog"]')],[p('absent','[role="dialog"]')],[net('POST','/api/v1/goals',absent=True)],'validation',source='fe/src/components/goals/CreateGoalModal.tsx')
        for typ in ('Saving','Expense'):
            steps=[nav('/goals/new','[role="dialog"]')]
            if typ=='Expense':steps +=[click('input[name="goalType"][value="Expense"]'),{'action':'select','selector':'[role="dialog"] select','fixtureField':'categoryId'}]
            steps +=[fill('[role="dialog"] input[inputmode="decimal"]','500'),fill('[role="dialog"] input[type="date"]:first-of-type',fixture='monthStart'),fill('[role="dialog"] label:last-of-type input[type="date"]',fixture='monthEnd'),click('[role="dialog"] button[type="submit"]',p('absent','[role="dialog"]')),{'action':'reload','predicate':p('exists','h1')},{'action':'identity-probe'}]
            add('goal-create-'+typ.lower(),'/goals/new',steps,[p('absent','[role="dialog"]')],[net('POST','/api/v1/goals',[201]),net('GET','/api/v1/goals')],'mutation',[{'kind':'owned-readback','ref':'goal-create-'+typ.lower()}],source='fe/src/components/goals/CreateGoalModal.tsx',setup=('category',) if typ=='Expense' else ())
        adjust='main section button'
        add('goal-adjust-cancel','/goals',[nav('/goals','h1'),click(adjust,p('exists','[role="dialog"]')),fill('[role="dialog"] input','0'),click('[role="dialog"] button[type="submit"]'),click('[aria-label="Close adjust goal dialog"]')],[p('absent','[role="dialog"]')],[net('PUT','/api/v1/goals/{ownedGoalId}',absent=True)],'validation',source='fe/src/components/goals/AdjustGoalModal.tsx')
        add('goal-adjust-save','/goals',[nav('/goals','h1'),click(adjust,p('exists','[role="dialog"]')),fill('[role="dialog"] input','650'),click('[role="dialog"] button[type="submit"]',p('absent','[role="dialog"]')),{'action':'reload','predicate':p('exists','h1')},{'action':'identity-probe'}],[p('text','main','$650.00')],[net('PUT','/api/v1/goals/{ownedGoalId}'),net('GET','/api/v1/goals')],'mutation',[{'kind':'owned-readback','ref':'goal-adjust-save'}],source='fe/src/components/goals/AdjustGoalModal.tsx')
        add('goals-chart-year','/goals',[nav('/goals','#saving-summary-heading'),{'action':'select','selector':'section[aria-labelledby="saving-summary-heading"] select:not(:disabled)','fixtureField':'previousYear'},{'action':'identity-probe'}],[p('exists','#saving-summary-heading'),p('text','section[aria-labelledby="saving-summary-heading"]','There is no transaction data for this year to calculate savings.')],[net('GET','/api/v1/savings/summary')],source='fe/src/components/goals/SavingsSummaryChart.tsx')
        add('goal-edit-unavailable','/goals/{ownedGoalId}/edit',[nav('/goals/{ownedGoalId}/edit','h1'),click('a[href="/goals"]')],[p('urlPath',value='/goals')],[net('PUT','/api/v1/goals/{ownedGoalId}',absent=True)],source='fe/src/pages/GoalDestinationUnavailablePage.tsx')
    # Add bounded ownership extraction and exact persistence oracles to the reviewed UI operations.
    by_id={j['id']:j for j in js}
    by_id['native-body-ui-baseline']['expectedUi'] += [p('absent','[data-fe-owned]')]
    by_id['native-body-ui-readback']['expectedUi'] += [p('absent','[data-fe-owned]')]
    by_id['account-create']['steps'] += [bind('/api/v1/accounts','/data/accounts','/id','uiAccountId','/bank_name','accountMarker'),post('/api/v1/accounts/{uiAccountId}','/data/bank_name',fixture='accountMarker'),post('/api/v1/accounts/{uiAccountId}','/data/balance',123.45)]
    by_id['account-edit-save']['steps'] += [post('/api/v1/accounts/{ownedAccountId}','/data/bank_name',fixture='editedAccountMarker')]
    for typ in ('Revenue','Expense'):
        item=by_id['transaction-create-'+typ.lower()]
        item['steps'] += [bind('/api/v1/transactions?type=All&limit=100&offset=0','/data/data','/transactionId','ui'+typ+'TransactionId','/itemDescription','transactionMarker'+typ),post('/api/v1/accounts/{ownedAccountId}','/data/balance',fixture='expectedBalanceAfter'+typ)]
        item['expectedUi'] += [p('text','body',fixtureField='transactionMarker'+typ)]
    by_id['goal-create-saving']['steps'] += [bind('/api/v1/goals','/data/savingGoal','/goal_id','ownedGoalId'),post('/api/v1/goals','/data/savingGoal/target_amount',500)]
    by_id['goal-create-saving']['expectedUi'] += [p('text','main','$500.00')]
    by_id['goal-create-expense']['steps'] += [bind('/api/v1/goals','/data/expenseGoals','/goal_id','expenseGoalId','/category','categoryMarker'),post('/api/v1/goals','/data/expenseGoals/0/target_amount',500)]
    by_id['goal-create-expense']['expectedUi'] += [p('text','main',fixtureField='categoryMarker')]
    by_id['goal-adjust-save']['steps'] += [post('/api/v1/goals','/data/savingGoal/target_amount',650)]
    by_id['transactions-populated']['expectedUi'] += [p('text','body',fixtureField='lastPageMarker'),p('text','body','$1.00')]
    by_id['expenses-month']['expectedUi'] += [p('text','body','You have no expenses recorded this month.')]
    by_id['expenses-month']['expectedNetwork']=[net('GET','/api/v1/expenses/breakdown',[200,404])]
    by_id['transactions-populated']['steps'] += [post('/api/v1/transactions?type=All&limit=10&offset=0','/data/total',11),post('/api/v1/transactions?type=All&limit=10&offset=0','/data/hasMore',True)]
    by_id['transactions-page']['steps'] += [post('/api/v1/transactions?type=All&limit=10&offset=10','/data/data/0/itemDescription',fixture='firstPageMarker')]
    by_id['transactions-page']['expectedUi'] += [p('text','body',fixtureField='firstPageMarker')]
    by_id['expenses-populated']['steps'] += [post('/api/v1/expenses/breakdown?month={currentMonth}','/data/data/0/Total',12.25)]
    by_id['expenses-populated']['expectedUi'] += [p('text','body',fixtureField='transactionMarkerExpense')]
    by_id['bills-populated']['expectedUi'] += [p('text','[role="table"]',fixtureField='billMarker'),p('text','[role="table"]','$12.5'),p('attribute','img[alt="Bill provider logo"]',fixtureField='billLogo',attribute='src'),p('imageLoaded','img[alt="Bill provider logo"]'),p('attribute','[role="table"] time.due-tile',fixtureField='billDueDate',attribute='datetime')]
    add('native-query-ui-readback','/transactions',[nav('/transactions','#transactions-heading'),{'action':'identity-probe'},{'action':'reload','predicate':p('exists','#transactions-heading')},post('/api/v1/transactions?type=All&limit=10&offset=0','/data/total',13)],[p('text','body',fixtureField='transactionMarkerExpense')],[net('GET','/api/v1/transactions')])
    add('account-delete-confirm','/accounts/{uiAccountId}',[nav('/accounts/{uiAccountId}','#account-summary-title'),{'action':'identity-probe'},click(remove,p('exists','#delete-account-title')),click('[role="dialog"] button:last-of-type',p('urlPath',value='/accounts')),{'action':'reload','predicate':p('exists','a[href="/accounts/new"]')},post('/api/v1/accounts','/data/accounts/0/id',fixture='ownedAccountId')],[p('textAbsent','body',fixtureField='accountMarker')],[net('DELETE','/api/v1/accounts/{uiAccountId}'),net('GET','/api/v1/accounts')],'mutation',[{'kind':'owned-readback','ref':'account-delete-confirm'}])
    # Same owned browser transitions A logout -> guarded reload/back -> B UI login.
    add('main-a-new-tab','/accounts',[{'action':'new-tab','path':'/accounts','predicate':p('exists','a[href="/accounts/new"]')},{'action':'identity-probe'}],[p('storagePresent',key=key[1]),p('exists','a[href="/accounts/new"]')],[net('GET','/api/v1/accounts')],effect='lifecycle')
    add('main-a-reopen','/accounts',[{'action':'reopen','path':'/accounts','predicate':p('exists','a[href="/accounts/new"]')},{'action':'identity-probe'}],[p('storagePresent',key=key[1]),p('exists','a[href="/accounts/new"]')],[net('GET','/api/v1/accounts')],effect='lifecycle')
    add('main-a-logout','/',[nav('/','#starter-heading'),click('section[aria-labelledby="starter-heading"] button'),{'action':'logout-boundary'},nav('/accounts','#login-email'),{'action':'back'},{'action':'reload'},nav('/accounts','#login-email')],[p('urlPath',value='/login'),p('storageAbsent',key=key[1]),p('storageAbsent',key=key[1],area='session')],[net('GET','/api/v1/accounts',absent=True)],effect='lifecycle',phase='logout')
    add('main-a-login-b','/login',[nav('/login','#login-email'),fill('#login-email',fixture='username'),fill('#login-password',fixture='password'),click('button[type="submit"]',p('urlPath',value='/')),{'action':'identity-probe'},nav('/accounts','a[href="/accounts/new"]'),{'action':'identity-probe'}],[p('exists','a[href="/accounts/new"]'),p('textAbsent','body',fixtureField='previousActorMarker')],[net('POST','/api/auth/login'),net('GET','/api/v1/accounts')],effect='lifecycle',phase='login-pending',actor_override='actor-b')
    for group_id,actor_ref in [('main-a','actor-b'),('isolation-b','actor-b')]:
        add('logout-'+group_id+'-terminal','/',[nav('/','#starter-heading'),click('section[aria-labelledby="starter-heading"] button'),{'action':'logout-boundary'},nav('/accounts','#login-email'),{'action':'reload','predicate':p('exists','#login-email')}],[p('urlPath',value='/login'),p('storageAbsent',key=key[1]),p('storageAbsent',key=key[1],area='session')],[net('GET','/api/v1/accounts',absent=True)],effect='lifecycle',group=group_id,phase='logout',actor_override=actor_ref)
    # All discovered obligations have executable journeys; unavailable destinations retain navigation-only semantics.
    policies=[]
    def policy(method,path,phase='protected',effect='read',**kw):policies.append({'method':method,'path':path,'phase':phase,'effect':effect,'provenance':prov,**kw})
    for path in ('/','/login','/register','/accounts','/accounts/new','/accounts/invalid','/accounts/{ownedAccountId}','/transactions','/transactions/new','/expenses','/bills','/bills/new','/goals','/goals/new','/goals/{ownedGoalId}/edit','/owned-fe-missing','/favicon.ico'):policy('GET',path,'public')
    # Asset filenames come from binding; unresolved build asset inventory remains a plan prerequisite.
    policy('POST','/api/auth/login','bootstrap','bootstrap',jsonFields=['email','password'])
    for path,query in [('/api/v1/accounts',[]),('/api/v1/accounts/{ownedAccountId}',[]),('/api/v1/accounts/options',[]),('/api/v1/categories/options',[]),('/api/v1/transactions',['type','limit','offset']),('/api/v1/expenses/summary',[]),('/api/v1/expenses/breakdown',['month']),('/api/v1/bills',[]),('/api/v1/goals',[]),('/api/v1/savings/summary',['year'])]:policy('GET',path,'identity' if path=='/api/v1/accounts' else 'protected',queryKeys=query)
    for field in ('uiAccountId','nativeAccountId'):
        policy('GET','/accounts/{'+field+'}','public')
        policy('GET','/api/v1/accounts/{'+field+'}')
        policy('PUT','/api/v1/accounts/{'+field+'}',effect='mutation',jsonFields=['bank_name','account_type','branch_name','balance'])
        policy('DELETE','/api/v1/accounts/{'+field+'}',effect='mutation')
    policy('POST','/api/v1/accounts',effect='mutation',jsonFields=['bank_name','account_type','branch_name','account_number_full','balance'])
    policy('PUT','/api/v1/accounts/{ownedAccountId}',effect='mutation',jsonFields=['bank_name','account_type','branch_name','balance'])
    policy('DELETE','/api/v1/accounts/{ownedAccountId}',effect='mutation')
    policy('POST','/api/v1/transactions',effect='mutation',jsonFields=['accountId','transactionDate','type','itemDescription','category_id','shopName','amount','paymentMethod','status'])
    policy('POST','/api/v1/goals',effect='mutation',jsonFields=['goal_type','category_id','target_amount','start_date','end_date'])
    policy('PUT','/api/v1/goals/{ownedGoalId}',effect='mutation',jsonFields=['target_amount'])
    campaigns=[{'id':'native-account-body','journeyIds':['native-body-ui-baseline'],'actorRef':'actor-a','authKind':'json-bearer','method':'PUT','path':'/api/v1/accounts/{nativeAccountId}','body':{'bank_name':'reviewed-owned-name','account_type':'Checking','branch_name':'Owned setup','balance':1000},'bodyBindings':{'bank_name':'nativeAccountMarker'},'resultBindings':{'nativeObservedBankName':'/data/account/bank_name'},'vector':'json-body','vectorFields':['bank_name'],'ruleIds':[40018],'maxDelivered':4,'maxAppRequests':12,'postState':[{'kind':'ui-reload','ref':'native-body-ui-readback'},{'kind':'owned-readback','ref':'native-body-ui-readback'}],'sinkProvenance':[source_ids['be/src/modules/accounts/accounts.service.ts']],'depth':'owned text scalar SQLi delivery and React escaped markup; no exploit/execution claim','effect':'mutation'},
        {'id':'native-transaction-query','journeyIds':['transactions-populated'],'actorRef':'actor-a','authKind':'json-bearer','method':'GET','path':'/api/v1/transactions','query':{'type':'All','limit':10,'offset':0},'vector':'query','vectorFields':['type'],'ruleIds':[40018],'maxDelivered':4,'maxAppRequests':12,'postState':[{'kind':'ui-reload','ref':'native-query-ui-readback'},{'kind':'owned-readback','ref':'native-query-ui-readback'}],'sinkProvenance':[source_ids['be/src/modules/transactions/transactions.service.ts']],'depth':'validated filter query; SQLi error delivery; no exploit claim','effect':'read'}]
    return validate_journeys({'schemaVersion':'fe-authenticated-journeys/1.0','recipe':'finalsource-fe-auth/1.0','sources':sources,'auth':{'maxLoginsPerActor':4,'kind':'json-bearer','loginPath':'/api/auth/login','usernameField':'email','passwordField':'password','tokenPointer':'/data/accessToken','storageKey':key[1],'identity':{'path':'/api/v1/accounts','subjectPointer':'/data/user_id','expectedRole':'user','roleProvenance':[source_ids['be/src/modules/auth/auth.service.ts']]},'loginSelectors':{'username':'#login-email','password':'#login-password','submit':'button[type="submit"]','remember':'label:has(input[type="checkbox"])'}},'sessionGroups':groups,'journeys':js,'responsibilities':rs,'requestPolicies':policies,'campaigns':campaigns})


def materialize(journeys,selection):
    """Read-only compiled asset inventory from the verified running build, never guessed asset paths."""
    import re
    if not selection.get('publicAssets') or not selection.get('buildEvidence'):raise ValueError('verified runtime build/assets are a plan prerequisite')
    provenance=[s['id'] for s in journeys['sources'] if s['path'].endswith('/fe/nginx.conf')]
    if not provenance:raise ValueError('static asset source provenance absent')
    for row in selection['publicAssets']:
        path=row['path']
        if not re.fullmatch(r'/assets/[A-Za-z0-9_.-]{1,180}',path):raise ValueError('unexpected build asset path')
        journeys['requestPolicies'].append({'method':'GET','path':path,'phase':'public','effect':'read','provenance':provenance})
    return journeys


def responsibility_inventory(product,sources):
    """Read API call sites and router directly, before executor selection.

    This adapter recognizes this product's TS client. Unparsed dynamic calls keep
    discovery incomplete; unsupported shapes never disappear into an empty list.
    UI branch/state questions are supplemented by reviewed product observations.
    """
    root=Path(product);by_path={s['path']:s['id'] for s in sources};cases=[];unparsed=[]
    for file in sorted((root/'fe/src/api').glob('*.ts')):
        text=file.read_text();ref=by_path.get(str(file))
        for i,call in enumerate(re.finditer(r"httpClient\.(get|post|put|patch|delete)(?:<[^;]*?>)?\(\s*([`'\"])(.*?)\2",text,re.S)):
            method=call[1].upper();raw=call[3]
            path=re.sub(r'\$\{.*?\}', '{id}',raw)
            if not path.startswith('/v1/'):
                continue  # public auth handled by UI/session questions in this track
            path='/api'+path
            cid='api-'+method.lower()+'-'+re.sub(r'[^a-z0-9]+','-',path.lower()).strip('-')
            if any(c['caseId']==cid for c in cases):continue
            cases.append({'caseId':cid,'method':method,'path':path,'evidenceRefs':[ref],
                'requiredEvidence':['technique-decision','security-result'],
                'question':'Choose and execute security techniques for API/input used by FE',
                'role':'user','state':'product-defined','prerequisites':[]})
        if len(re.findall(r'httpClient\.(?:get|post|put|patch|delete)',text))>len(list(re.finditer(r"httpClient\.(?:get|post|put|patch|delete)(?:<[^;]*?>)?\(\s*([`'\"])(.*?)\1",text,re.S))):unparsed.append(str(file))
    router=root/'fe/src/router/AppRouter.tsx'
    for route in dict.fromkeys(re.findall(r"path: '([^']+)'",router.read_text())):
        if route in ('/login','/register'):continue
        cases.append({'caseId':'ui-route-'+__import__('hashlib').sha256(route.encode()).hexdigest()[:12],'path':route,'role':'user',
            'evidenceRefs':[by_path[str(router)]],'requiredEvidence':['ui','result-read'],
            'question':'Review route actions, state and role branches against product source','prerequisites':[]})
    return {'productLocation':str(root.resolve()),'track':'fe-authenticated','complete':False,
        'discoveryGaps':['Review UI branches, roles and technique selection before declaring inventory complete']+unparsed,'cases':cases}
