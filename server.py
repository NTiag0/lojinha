"""Lojinha: servidor local sem dependências externas, com transações SQLite."""
import argparse
import calendar
import datetime as dt
import json
import math
import os
import database
import security
import threading
import uuid
import webbrowser
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LOJINHA_DATA', ROOT / 'data'))
ENTITIES = {'products','clients','suppliers','categories','financialCategories','variations','deliveries','paymentMethods','coupons','banners','users','orderFields','clientFields','paymentDiscounts','tables','purchases','cash','orders','entries','movements'}
CRUD = ENTITIES - {'cash','orders','entries','movements','purchases'}
def now(): return dt.datetime.now().astimezone().isoformat()
def uid(): return uuid.uuid4().hex[:16]
def number(value, label='Valor', minimum=0):
    try: value = float(value)
    except (ValueError, TypeError): raise ValueError(label + ' inválido.')
    if not math.isfinite(value) or value < minimum: raise ValueError(label + ' inválido.')
    return value
def cents(value): return round(number(value) * 100)
def date(value):
    try: return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError: raise ValueError('Data inválida.')
def connect():
    return database.open_connection(DATA)
@contextmanager
def transaction():
    c = connect()
    try:
        database.begin(c)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally: c.close()
def all_rows(c,kind):
    order='seq' if getattr(c,'postgres',False) else 'rowid'
    return [json.loads(r[0]) for r in c.execute('SELECT doc FROM records WHERE kind=? ORDER BY '+order+' DESC',(kind,))]
def get(c, kind, key):
    row = c.execute('SELECT doc FROM records WHERE kind=? AND id=?', (kind,str(key))).fetchone()
    if not row: raise ValueError('Registro não encontrado: ' + kind)
    return json.loads(row[0])
def put(c, kind, doc):
    doc = dict(doc)
    doc.setdefault('id', uid()); doc.setdefault('createdAt', now()); doc['updatedAt'] = now()
    c.execute('INSERT INTO records (kind,id,doc) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET doc=excluded.doc', (kind,doc['id'],json.dumps(doc,ensure_ascii=False)))
    return doc
def settings(c):
    r = c.execute('SELECT doc FROM settings WHERE id=1').fetchone()
    return json.loads(r[0]) if r else {}
def save_settings(c,conf):
    c.execute('INSERT INTO settings (id,doc) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET doc=excluded.doc',(json.dumps(conf,ensure_ascii=False),))
def ensure_expense_categories(c):
    conf=settings(c)
    if conf.get('expenseCategoriesVersion',0)>=2: return
    categories=all_rows(c,'financialCategories')
    legacy=conf.get('expenseCategoriesVersion')==1
    for category in categories:
        if not category.get('type') and category['name'] in ['Vendas','Outras entradas','Compras','Despesas operacionais']:
            category['type']='Entrada' if category['name'] in ['Vendas','Outras entradas'] else 'Despesa'
            put(c,'financialCategories',category)
    def ensure(name,parent_id=''):
        existing=next((x for x in categories if not x.get('archived') and x['name'].casefold()==name.casefold() and x.get('parentId','')==parent_id and x.get('type')!='Entrada'),None)
        if existing: return existing
        category=put(c,'financialCategories',{'name':name,'type':'Despesa','parentId':parent_id})
        categories.append(category)
        return category
    operations=ensure('Despesas operacionais')
    travel=next((x for x in categories if x['name']=='Viagem' and not x.get('parentId') and not x.get('archived')),None) if legacy else None
    choices=[('Frete de mercadoria','Frete para buscar produtos',travel['id'] if travel else None),('Aluguel','Aluguel',''),('Conta de água','Água',''),('Conta de energia','Luz',''),('Conta de internet','Internet',''),('Despesa viagem — Alimentação','Alimentação',travel['id'] if travel else None),('Despesa viagem — Gasolina','Combustível',travel['id'] if travel else None)]
    for title,old_title,old_parent in choices:
        existing=next((x for x in categories if not x.get('archived') and x['name']==title and x.get('parentId')==operations['id']),None)
        old=next((x for x in categories if legacy and not x.get('archived') and x['name']==old_title and old_parent is not None and x.get('parentId','')==old_parent),None)
        if old and not existing:
            old.update({'name':title,'parentId':operations['id'],'type':'Despesa'})
            put(c,'financialCategories',old)
        else: ensure(title,operations['id'])
    if travel:
        # Hide superseded groupings while keeping all historical references.
        for category in categories:
            if category['id']==travel['id'] or category.get('parentId')==travel['id']:
                category['archived']=True;put(c,'financialCategories',category)
    conf['expenseCategoriesVersion']=2
    save_settings(c,conf)

def init():
    with transaction() as c:
        database.prepare_schema(c)
        if not c.execute('SELECT 1 FROM settings').fetchone():
            conf={'name':'Tiago','company':'Minha Lojinha','receiptMessage':'Obrigado pela preferência!','chargeMessage':'Olá, {cliente}! Há um pagamento de {valor} pendente do pedido {pedido}.','theme':'dark','catalogActive':True,'catalogModel':'grid','catalogColor':'#ed3127','stockPolicy':'soldout','paper':'80','tableMode':'none','minOrder':0}
            c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps(conf),))
            put(c,'categories',{'name':'Sem categoria'})
            for name in ['Vendas','Outras entradas','Compras','Despesas operacionais']: put(c,'financialCategories',{'name':name})
            for name in ['Dinheiro','Pix','Cartão de Crédito','Cartão de Débito','TED','VR/VA','Outro','Link','Cheque','Boleto']: put(c,'paymentMethods',{'name':name,'active':True,'fee':0})
            for name in ['A combinar','Retirada na Loja','Entrega']: put(c,'deliveries',{'name':name,'value':0,'active':True})
        ensure_expense_categories(c)
def restore_backup(c, backup):
    if not isinstance(backup,dict) or backup.get('version')!=1 or set(backup.get('records',{}))!=ENTITIES or not isinstance(backup.get('settings'),dict): raise ValueError('Este arquivo não é um backup válido da Lojinha.')
    records=backup['records'];known={}
    for kind,rows in records.items():
        if not isinstance(rows,list) or len(rows)>100000: raise ValueError('Backup inválido.')
        known[kind]=set()
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or row['id'] in known[kind]: raise ValueError('Registro inválido no backup.')
            known[kind].add(row['id'])
            if kind=='products': validate_product(dict(row))
            if kind in ['orders','entries','cash','purchases']:
                for field in ['total','paid','value','opening','counted','cost']:
                    if field in row and (not isinstance(row[field],int) or row[field]<0): raise ValueError('Valores monetários inválidos no backup.')
            if kind=='orders' and (not isinstance(row.get('items'),list) or row.get('paid',0)>row.get('total',0)): raise ValueError('Pedido inválido no backup.')
    for o in records['orders']:
        for item in o['items']:
            if not isinstance(item,dict) or item.get('productId') and item['productId'] not in known['products']: raise ValueError('Produto do pedido não encontrado no backup.')
    # Preserve the complete previous state inside the same database transaction.
    c.execute('CREATE TABLE IF NOT EXISTS restore_history (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)')
    current={'version':1,'settings':settings(c),'records':{k:all_rows(c,k) for k in ENTITIES}}
    stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uid()
    c.execute('INSERT INTO restore_history VALUES(?,?)',(stamp,json.dumps(current,ensure_ascii=False)))
    if not getattr(c,'postgres',False):
        backup_dir=DATA/'backups';backup_dir.mkdir(exist_ok=True)
        target=backup_dir/('antes-restauracao-'+stamp+'.json')
        target.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
    c.execute('DELETE FROM records')
    for kind,rows in records.items():
        for row in rows: put(c,kind,row)
    save_settings(c,backup['settings'])
    ensure_expense_categories(c)
    return {'ok':True}
def stock(c, product_id, delta, reason, ref='', variant=''):
    p=get(c,'products',product_id)
    if p.get('type')=='Serviço' or not p.get('trackStock',True): return
    if variant:
        variants=p.get('variants',[])
        v=next((v for v in variants if v['name']==variant),None)
        if not v: raise ValueError('Variação inexistente.')
        q=number(v.get('stock',0))+delta
        if q < -0.00001: raise ValueError('Estoque insuficiente: '+p['name']+' / '+variant)
        v['stock']=round(q,6);p['stock']=sum(float(x['stock']) for x in variants)
    else:
        if p.get('variants'): raise ValueError('Selecione a variação de '+p['name'])
        q=number(p.get('stock',0))+delta
        if q < -0.00001: raise ValueError('Estoque insuficiente: '+p['name'])
        p['stock']=round(q,6)
    put(c,'products',p)
    put(c,'movements',{'productId':p['id'],'name':p['name'],'variant':variant,'delta':delta,'balance':p['stock'],'reason':reason,'ref':ref,'date':dt.date.today().isoformat()})
def validate_product(doc):
    if not str(doc.get('name','')).strip(): raise ValueError('Informe o título.')
    for k in ['price','cost','stock','minStock','wholesalePrice','wholesaleQty','offerPrice','reserved']: doc[k]=number(doc.get(k,0),k)
    if not doc.get('fractional') and doc['stock']%1: raise ValueError('Ative a venda fracionada para quantidades decimais.')
    names=set()
    for v in doc.get('variants',[]):
        if not v.get('name') or v['name'] in names: raise ValueError('Variações precisam de nomes únicos.')
        names.add(v['name']);v['stock']=number(v.get('stock',0))
        if not doc.get('fractional') and v['stock']%1: raise ValueError('Quantidade da variação deve ser inteira.')
    if doc.get('variants'): doc['stock']=sum(v['stock'] for v in doc['variants'])
    if doc.get('offer') and doc['offerPrice']>doc['price']: raise ValueError('Oferta deve ser menor que o preço de venda.')
def save_entity(c, kind, data, key=None):
    if kind not in CRUD: raise ValueError('Cadastro inválido.')
    if key: data={**get(c,kind,key),**data,'id':key}
    else: data={k:v for k,v in data.items() if k not in ('id','createdAt','updatedAt')}
    if not str(data.get('name','')).strip(): raise ValueError('Informe o nome ou título.')
    if kind=='financialCategories':
        parent_id=data.get('parentId','')
        if parent_id:
            parent=get(c,kind,parent_id)
            if parent_id==key or parent.get('parentId') or parent.get('archived'): raise ValueError('Escolha uma categoria principal ativa; subcategorias têm apenas um nível.')
            if key and any(x.get('parentId')==key for x in all_rows(c,kind)): raise ValueError('Uma categoria com subcategorias não pode ser movida para dentro de outra.')
            if parent.get('type','Ambos') not in ['Ambos',data.get('type','Ambos')]: raise ValueError('A subcategoria deve ter o mesmo tipo da categoria principal.')
    if kind=='products':
        validate_product(data)
        code=data.get('barcode','').strip()
        if code and any(p.get('barcode')==code and p['id']!=key for p in all_rows(c,'products')): raise ValueError('Código de barras já cadastrado.')
        if key:
            old=get(c,kind,key)
            if old.get('variants')!=data.get('variants') or float(old.get('stock',0))!=data['stock']:
                raise ValueError('Para mudar quantidades ou variações de um produto existente, use a movimentação de estoque. Crie as variações no cadastro inicial.')
    saved=put(c,kind,data)
    if kind=='products' and not key and data.get('stock'):
        put(c,'movements',{'productId':saved['id'],'name':data['name'],'delta':data['stock'],'balance':data['stock'],'reason':'Estoque inicial','date':dt.date.today().isoformat()})
    return saved
def prepare_items(c, data):
    items=[]; base=0; cost=0
    for raw in data.get('items',[]):
        p=get(c,'products',raw['productId']);q=number(raw.get('qty'), 'Quantidade',0.000001)
        if p.get('archived'): raise ValueError('Produto arquivado: '+p['name'])
        if not p.get('fractional') and q%1: raise ValueError('Quantidade fracionada não permitida: '+p['name'])
        variant=str(raw.get('variant',''))
        if p.get('variants') and variant not in [v['name'] for v in p['variants']]: raise ValueError('Selecione a variação de '+p['name'])
        price=cents(p.get('offerPrice') if p.get('offer') else p['price'])
        if p.get('wholesaleQty',0)>0 and q>=p['wholesaleQty']: price=cents(p['wholesalePrice'])
        items.append({'productId':p['id'],'name':p['name'],'qty':q,'price':price,'cost':cents(p.get('cost',0)),'variant':variant,'receiptNote':p.get('receiptNote','')})
        base+=round(price*q);cost+=round(cents(p.get('cost',0))*q)
    if data.get('manual'):
        if not str(data.get('title','')).strip(): raise ValueError('Informe o título da venda.')
        base=cents(data.get('value'));items=[{'name':data['title'],'qty':1,'price':base,'cost':0}]
    if not items or base<=0: raise ValueError('Adicione itens com valor positivo.')
    return items,base,cost
def order_create(c, data):
    order_id=uid()
    items,base,cost=prepare_items(c,data)
    discount=cents(data.get('discount',0))+round(base*number(data.get('discountPct',0))/100)
    coupon_code=str(data.get('coupon','')).strip().upper()
    if coupon_code:
        coupon=next((x for x in all_rows(c,'coupons') if x['name'].upper()==coupon_code and x.get('active',True) and not x.get('archived')),None)
        if not coupon: raise ValueError('Cupom inválido.')
        if coupon.get('expires') and date(coupon['expires'])<dt.date.today().isoformat(): raise ValueError('Cupom expirado.')
        if base<cents(coupon.get('minimum',0)): raise ValueError('Valor mínimo do cupom não atingido.')
        used=sum(o.get('coupon')==coupon_code and not o.get('quote') and o['status']!='Cancelado' for o in all_rows(c,'orders'))
        if number(coupon.get('limit',0)) and used>=number(coupon['limit']): raise ValueError('Limite de usos do cupom atingido.')
        discount+=round(base*number(coupon.get('value',0))/100) if coupon.get('mode')=='Percentual' else cents(coupon.get('value',0))
    method_discount=next((x for x in all_rows(c,'paymentDiscounts') if not x.get('archived') and x.get('active',True) and x.get('methodId')==data.get('methodId')),None)
    if method_discount: discount+=round(base*number(method_discount.get('percent',0))/100)
    service=cents(data.get('service',0))+round(base*number(data.get('servicePct',0))/100)
    delivery=cents(data.get('deliveryValue',0))
    if discount>base: raise ValueError('Desconto maior que o subtotal.')
    total=base-discount+service+delivery
    if total<=0: raise ValueError('O total precisa ser positivo.')
    client=data.get('clientId','');seller=data.get('sellerId','');table=data.get('tableId','')
    if client: get(c,'clients',client)
    if seller: get(c,'users',seller)
    quote=bool(data.get('quote'))
    if table:
        get(c,'tables',table)
        if not quote and any(o.get('tableId')==table and not o.get('quote') and o.get('status') not in ['Concluído','Cancelado'] for o in all_rows(c,'orders')): raise ValueError('Mesa já possui um pedido aberto.')
    order={'id':order_id,'number':max([o.get('number',0) for o in all_rows(c,'orders')]+[0])+1,'items':items,'subtotal':base,'discount':discount,'service':service,'delivery':delivery,'total':total,'cost':cost,'paid':0,'clientId':client,'sellerId':seller,'tableId':table,'date':date(data.get('date',dt.date.today().isoformat())),'dueDate':date(data.get('dueDate') or data.get('date') or dt.date.today().isoformat()),'notes':str(data.get('notes','')),'internal':str(data.get('internal','')),'deliveryMethod':str(data.get('deliveryMethod','')),'quote':quote,'status':'Orçamento' if quote else data.get('status','Concluído'),'coupon':coupon_code,'custom':data.get('custom',{})}
    if order['status'] not in ['Orçamento','Aberto','Em preparo','Pronto','Em entrega','Concluído']: raise ValueError('Status inválido.')
    if not quote:
        for item in items:
            if item.get('productId'): stock(c,item['productId'],-item['qty'],'Venda',order_id,item.get('variant',''))
    put(c,'orders',order)
    if not quote:
        for payment in data.get('payments',[]): order=pay_order(c,order_id,payment)
    return order
def pay_order(c, key, data):
    o=get(c,'orders',key)
    if o.get('quote') or o['status']=='Cancelado': raise ValueError('Pedido não aceita pagamento.')
    value=cents(data.get('value'))
    if value<=0 or value>o['total']-o['paid']: raise ValueError('Valor acima do saldo ou inválido.')
    method=get(c,'paymentMethods',data.get('methodId'))
    if not method.get('active',True) or method.get('archived'): raise ValueError('Forma de pagamento desativada.')
    payment_date=date(data.get('date',dt.date.today().isoformat()))
    active=next((x for x in all_rows(c,'cash') if x['status']=='Aberto'),None)
    cash_id=active['id'] if active and method['name']=='Dinheiro' and payment_date==dt.date.today().isoformat() else ''
    put(c,'entries',{'name':'Venda #'+str(o['number']),'type':'Entrada','value':value,'date':payment_date,'paid':True,'methodId':method['id'],'methodName':method['name'],'orderId':o['id'],'cashId':cash_id,'clientId':o.get('clientId',''),'fee':round(value*number(method.get('fee',0))/100)})
    o['paid']+=value
    return put(c,'orders',o)
def cancel_order(c,key):
    o=get(c,'orders',key)
    if o['status']=='Cancelado': raise ValueError('Pedido já cancelado.')
    if not o.get('quote'):
        for item in o['items']:
            if item.get('productId'): stock(c,item['productId'],item['qty'],'Cancelamento de venda',key,item.get('variant',''))
        active=next((x for x in all_rows(c,'cash') if x['status']=='Aberto'),None)
        for e in all_rows(c,'entries'):
            if e.get('orderId')==key and e['type']=='Entrada' and not e.get('voided'):
                put(c,'entries',{'name':'Estorno da venda #'+str(o['number']),'type':'Despesa','value':e['value'],'paid':True,'date':dt.date.today().isoformat(),'methodId':e.get('methodId',''),'methodName':e.get('methodName',''),'orderId':key,'refund':True,'cashId':active['id'] if active and e.get('methodName')=='Dinheiro' else ''})
    o['status']='Cancelado';o['paid']=0
    return put(c,'orders',o)
def entry_create(c,data):
    value=cents(data.get('value'))
    if value<=0 or not data.get('name','').strip(): raise ValueError('Informe título e valor positivo.')
    if data.get('type') not in ['Entrada','Despesa']: raise ValueError('Tipo inválido.')
    if data.get('categoryId'):
        category=get(c,'financialCategories',data['categoryId'])
        if category.get('archived') or category.get('type','Ambos') not in ['Ambos',data['type']]: raise ValueError('Selecione uma categoria compatível com o lançamento.')
    method=get(c,'paymentMethods',data.get('methodId'))
    if not method.get('active',True) or method.get('archived'): raise ValueError('Forma de pagamento desativada.')
    paid=bool(data.get('paid',True)); entry_date=date(data.get('date',dt.date.today().isoformat()))
    active=next((x for x in all_rows(c,'cash') if x['status']=='Aberto'),None)
    result=put(c,'entries',{'name':data['name'],'type':data['type'],'value':value,'paid':paid,'date':entry_date,'methodId':method['id'],'methodName':method['name'],'categoryId':data.get('categoryId',''),'trip':str(data.get('trip','')).strip() if data['type']=='Despesa' else '', 'supplierId':data.get('supplierId',''),'notes':data.get('notes',''),'cashId':active['id'] if active and paid and method['name']=='Dinheiro' and entry_date==dt.date.today().isoformat() else ''})
    recurrence=data.get('recurrence','Não repete');count=int(number(data.get('occurrences',1),minimum=1))
    if count>60: raise ValueError('Use até 60 ocorrências.')
    for index in range(1,count if recurrence!='Não repete' else 1):
        start=dt.date.fromisoformat(entry_date)
        if recurrence=='Mensal':
            month=start.month-1+index;year=start.year+month//12;month=month%12+1
            next_date=dt.date(year,month,min(start.day,calendar.monthrange(year,month)[1]))
        elif recurrence in ['Semanal','Diária']: next_date=start+dt.timedelta(days=index*(7 if recurrence=='Semanal' else 1))
        else: raise ValueError('Recorrência inválida.')
        future={k:v for k,v in result.items() if k not in ['id','createdAt','updatedAt']};future.update({'date':next_date.isoformat(),'paid':False,'cashId':'','recurrenceId':result['id']});put(c,'entries',future)
    return result
def expected_cash(c, cash):
    total=cash['opening']
    for e in all_rows(c,'entries'):
        if e.get('cashId')==cash['id'] and e.get('paid') and not e.get('voided'): total+=e['value']*(1 if e['type']=='Entrada' else -1)
    return total
def dispatch(c, path, data):
    parts=path.strip('/').split('/')[1:]
    if parts==['restore']: return restore_backup(c,data.get('backup'))
    if parts==['settings']:
        s={**settings(c),**data};save_settings(c,s);return s
    if parts==['orders']: return order_create(c,data)
    if len(parts)==3 and parts[0]=='orders':
        key,action=parts[1:]
        if action=='add-items':
            o=get(c,'orders',key)
            if o.get('quote') or o['status'] in ['Cancelado','Concluído']: raise ValueError('Adicione itens somente a pedidos abertos.')
            items,base,cost=prepare_items(c,data)
            for item in items:
                if item.get('productId'): stock(c,item['productId'],-item['qty'],'Item adicionado ao pedido',key,item.get('variant',''))
            o['items']+=items;o['subtotal']+=base;o['total']+=base;o['cost']+=cost
            if data.get('notes'): o['internal']=(o.get('internal','')+'\n'+str(data['notes'])).strip()
            return put(c,'orders',o)
        if action=='pay': return pay_order(c,key,data)
        if action=='cancel': return cancel_order(c,key)
        if action=='status':
            o=get(c,'orders',key)
            if o.get('quote') or o['status']=='Cancelado' or data.get('status') not in ['Aberto','Em preparo','Pronto','Em entrega','Concluído']: raise ValueError('Transição inválida.')
            o['status']=data['status'];return put(c,'orders',o)
        if action=='convert':
            o=get(c,'orders',key)
            if not o.get('quote') or o['status']=='Cancelado': raise ValueError('Orçamento já convertido ou cancelado.')
            for item in o['items']:
                if item.get('productId'): stock(c,item['productId'],-item['qty'],'Conversão de orçamento',key,item.get('variant',''))
            o['quote']=False;o['status']='Aberto';return put(c,'orders',o)
    if parts==['entries']: return entry_create(c,data)
    if len(parts)==3 and parts[0]=='entries':
        e=get(c,'entries',parts[1])
        if e.get('orderId') or e.get('purchaseId'): raise ValueError('Use o pedido associado para alterar este lançamento.')
        if e.get('voided'): raise ValueError('Lançamento já cancelado.')
        if parts[2]=='settle':
            if e['paid']: raise ValueError('Lançamento já pago.')
            e['paid']=True;e['date']=date(data.get('date',dt.date.today().isoformat()))
            active=next((x for x in all_rows(c,'cash') if x['status']=='Aberto'),None)
            e['cashId']=active['id'] if active and e.get('methodName')=='Dinheiro' and e['date']==dt.date.today().isoformat() else ''
        elif parts[2]=='cancel': e['voided']=True
        else: raise ValueError('Ação inválida.')
        return put(c,'entries',e)
    if parts==['stock']:
        delta=number(abs(float(data.get('delta',0))))*(1 if float(data.get('delta',0))>0 else -1)
        if not delta: raise ValueError('Informe uma quantidade diferente de zero.')
        p=get(c,'products',data.get('productId'))
        if not p.get('fractional') and delta%1: raise ValueError('Quantidade deve ser inteira.')
        stock(c,p['id'],delta,str(data.get('reason','Ajuste manual')),variant=data.get('variant',''));return {'ok':True}
    if parts==['cash','open']:
        if any(x['status']=='Aberto' for x in all_rows(c,'cash')): raise ValueError('Já existe um caixa aberto.')
        return put(c,'cash',{'name':data.get('name') or 'Caixa principal','opening':cents(data.get('opening',0)),'status':'Aberto','openedAt':now()})
    if len(parts)==3 and parts[0]=='cash' and parts[2]=='close':
        cash=get(c,'cash',parts[1])
        if cash['status']!='Aberto': raise ValueError('Caixa já fechado.')
        cash.update({'status':'Fechado','closedAt':now(),'counted':cents(data.get('counted',0)),'expected':expected_cash(c,cash),'notes':data.get('notes','')});cash['difference']=cash['counted']-cash['expected'];return put(c,'cash',cash)
    if parts==['purchases']:
        get(c,'suppliers',data.get('supplierId'));items=[]
        for raw in data.get('items',[]):
            p=get(c,'products',raw['productId']);q=number(raw.get('qty'),minimum=0.000001)
            if not p.get('fractional') and q%1: raise ValueError('Quantidade deve ser inteira.')
            if p.get('variants') and raw.get('variant') not in [v['name'] for v in p['variants']]: raise ValueError('Selecione a variação.')
            items.append({'productId':p['id'],'name':p['name'],'qty':q,'cost':cents(raw.get('cost',p.get('cost',0))),'variant':raw.get('variant','')})
        if not items: raise ValueError('Adicione produtos ao pedido.')
        return put(c,'purchases',{'supplierId':data['supplierId'],'items':items,'status':'Pendente','total':sum(round(i['cost']*i['qty']) for i in items),'date':date(data.get('date',dt.date.today().isoformat())),'notes':data.get('notes','')})
    if len(parts)==3 and parts[0]=='purchases':
        p=get(c,'purchases',parts[1])
        if p['status']!='Pendente': raise ValueError('Pedido já processado.')
        if parts[2]=='cancel': p['status']='Cancelado'
        elif parts[2]=='receive':
            for i in p['items']: stock(c,i['productId'],i['qty'],'Recebimento de fornecedor',p['id'],i.get('variant',''))
            p['status']='Recebido'
            if p['total']>0:
                put(c,'entries',{'name':'Compra de fornecedor','type':'Despesa','value':p['total'],'date':dt.date.today().isoformat(),'paid':False,'purchaseId':p['id'],'supplierId':p['supplierId'],'methodName':'A combinar'})
        elif parts[2]=='pay': raise ValueError('Receba o pedido primeiro.')
        else: raise ValueError('Ação inválida.')
        return put(c,'purchases',p)
    if parts==['purchase-payment']:
        e=get(c,'entries',data.get('entryId'))
        if not e.get('purchaseId') or e.get('paid'): raise ValueError('Compra já paga ou inválida.')
        method=get(c,'paymentMethods',data['methodId']);e.update({'paid':True,'methodId':method['id'],'methodName':method['name'],'date':dt.date.today().isoformat()})
        active=next((x for x in all_rows(c,'cash') if x['status']=='Aberto'),None)
        e['cashId']=active['id'] if active and method['name']=='Dinheiro' else '';return put(c,'entries',e)
    if len(parts) in [1,2] and parts[0] in CRUD: return save_entity(c,parts[0],data,parts[1] if len(parts)==2 else None)
    raise ValueError('Operação não encontrada.')

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(20)
    @property
    def access(self): return getattr(self.server,'access',security.AccessConfig())
    def log_message(self, fmt, *args): pass
    def respond(self, status, payload, content_type='application/json; charset=utf-8', attachment=None, headers=()):
        body=json.dumps(payload,ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self' blob:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        if self.access.secure:self.send_header('Strict-Transport-Security','max-age=15552000')
        if attachment: self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
        for key,value in headers:self.send_header(key,value)
        self.end_headers();self.wfile.write(body)
    def valid_host(self): return self.access.host_allowed(self.headers.get('Host',''),self.server.server_port)
    def is_authenticated(self):
        if not self.access.required:return True
        with transaction() as c:return security.authenticated(c,self.headers.get('Cookie',''),self.access)
    def reject(self,status,message):
        # Drain a bounded body so Windows does not reset an unread POST.
        try:
            length=int(self.headers.get('Content-Length',0))
            if 0<=length<=20_000_000:self.rfile.read(length)
        except (ValueError,OSError):pass
        return self.respond(status,{'error':message})
    def do_GET(self):
        if not self.valid_host(): return self.respond(403,{'error':'Endereço não autorizado.'})
        path=urlsplit(self.path).path
        if path=='/healthz':return self.respond(200,{'ok':True})
        public={'/login','/login.js','/style.css','/favicon.svg'}
        if path not in public and not self.is_authenticated():
            if path.startswith('/api/'):return self.respond(401,{'error':'Entre na sua conta para continuar.'})
            return self.respond(303,b'','text/plain',headers=[('Location','/login')])
        if path=='/api/backup/previous':
            with transaction() as c: row=c.execute('SELECT snapshot FROM restore_history ORDER BY id DESC LIMIT 1').fetchone()
            if not row:return self.respond(404,{'error':'Ainda não há restauração anterior.'})
            return self.respond(200,json.loads(row[0]),attachment='lojinha-antes-da-restauracao.json')
        if path in ['/api/state','/api/backup']:
            with transaction() as c:
                records={k:all_rows(c,k) for k in ENTITIES}
                for cash in records['cash']:
                    if cash['status']=='Aberto': cash['expected']=expected_cash(c,cash)
                state={'version':1,'settings':settings(c),'records':records}
                if path=='/api/state':
                    state['auth']={'enabled':self.access.required,'username':self.access.username if self.access.required else ''}
                    state['storage']='postgres' if getattr(c,'postgres',False) else 'sqlite'
            return self.respond(200,state,attachment='lojinha-backup-'+dt.date.today().isoformat()+'.json' if path.endswith('backup') else None)
        files={'/':'index.html','/login':'login.html','/login.js':'login.js','/app.js':'app.js','/branding.js':'branding.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
        if path not in files: return self.respond(404,{'error':'Página não encontrada.'})
        file=ROOT/'public'/files[path];types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
        return self.respond(200,file.read_bytes(),types[file.suffix])
    def mutate(self, delete=False):
        if not self.valid_host(): return self.reject(403,'Endereço não autorizado.')
        if not self.access.origin_allowed(self.headers.get('Origin'),self.server.server_port):return self.reject(403,'Origem não permitida.')
        if not self.headers.get('Content-Type','').startswith('application/json'):return self.reject(415,'Envie JSON.')
        try:
            length=int(self.headers.get('Content-Length',0))
            if length<0 or length>20_000_000: raise ValueError('Tamanho de arquivo inválido ou acima de 20 MB.')
            data=json.loads(self.rfile.read(length) or b'{}');path=urlsplit(self.path).path
            if not isinstance(data,dict): raise ValueError('Dados inválidos.')
            if path=='/api/auth/login' and not delete:
                if not self.access.required:return self.respond(200,{'ok':True})
                username=data.get('username','');password=data.get('password','')
                if not isinstance(username,str) or not isinstance(password,str) or len(username)>100 or len(password)>1024:return self.respond(400,{'error':'Acesso inválido.'})
                with transaction() as c:token,error=security.login(c,username,password,self.client_address[0],self.access)
                if error:return self.respond(429 if error=='locked' else 401,{'error':'Muitas tentativas. Aguarde 15 minutos.' if error=='locked' else 'Usuário ou senha incorretos.'})
                return self.respond(200,{'ok':True},headers=[('Set-Cookie',self.access.cookie(token))])
            if not self.is_authenticated():return self.respond(401,{'error':'Entre na sua conta para continuar.'})
            if path=='/api/auth/logout' and not delete:
                with transaction() as c:security.logout(c,self.headers.get('Cookie',''),self.access)
                return self.respond(200,{'ok':True},headers=[('Set-Cookie',self.access.cookie(clear=True))])
            with transaction() as c:
                if delete:
                    parts=path.strip('/').split('/')
                    if len(parts)!=3 or parts[1] not in CRUD: raise ValueError('Exclusão indisponível.')
                    kind,key=parts[1:];get(c,kind,key)
                    doc=get(c,kind,key);doc['archived']=True;result=put(c,kind,doc)
                else: result=dispatch(c,path,data)
            self.respond(200,result)
        except (ValueError,KeyError,TypeError,OverflowError) as e:self.respond(400,{'error':str(e)})
        except Exception as e:
            print('Erro:',type(e).__name__,str(e));self.respond(500,{'error':'Não foi possível concluir. Nenhuma alteração parcial foi salva.'})
    def do_POST(self): self.mutate()
    def do_DELETE(self): self.mutate(True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765')));parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--open',action='store_true');args=parser.parse_args()
    access=security.AccessConfig.from_environment(args.host)
    init();httpd=ThreadingHTTPServer((args.host,args.port),Handler);httpd.access=access
    print('Lojinha disponível em '+(access.origin or f'http://127.0.0.1:{args.port}'),flush=True)
    if args.open and args.host in ['127.0.0.1','localhost']:threading.Timer(0.7,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try:httpd.serve_forever()
    except KeyboardInterrupt:httpd.server_close()
