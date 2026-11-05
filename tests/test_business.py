import json
import tempfile
import unittest
from pathlib import Path
import server as app

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name);app.init()
        with app.transaction() as c:
            self.product=app.save_entity(c,'products',{'name':'Café','price':10,'cost':4,'stock':10,'trackStock':True,'fractional':False})
            self.method=next(m for m in app.all_rows(c,'paymentMethods') if m['name']=='Dinheiro')
            self.supplier=app.save_entity(c,'suppliers',{'name':'Fornecedor teste'})
    def tearDown(self): app.DATA=self.old;self.tmp.cleanup()
    def order(self,c,quantity=2,**extra):
        return app.order_create(c,{'items':[{'productId':self.product['id'],'qty':quantity}],**extra})
    def test_sale_partial_payments_and_cash(self):
        with app.transaction() as c:
            cash=app.dispatch(c,'/api/cash/open',{'opening':50})
            o=self.order(c,payments=[{'value':5,'methodId':self.method['id']}])
            self.assertEqual(o['total'],2000);self.assertEqual(o['paid'],500)
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],8)
            o=app.pay_order(c,o['id'],{'value':15,'methodId':self.method['id']})
            self.assertEqual(o['paid'],2000);self.assertEqual(app.expected_cash(c,cash),7000)
            closed=app.dispatch(c,'/api/cash/'+cash['id']+'/close',{'counted':69})
            self.assertEqual(closed['difference'],-100)
    def test_oversell_rolls_back(self):
        with self.assertRaises(ValueError):
            with app.transaction() as c:
                self.order(c,items=[{'productId':self.product['id'],'qty':8},{'productId':self.product['id'],'qty':8}])
        with app.transaction() as c:
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],10)
            self.assertEqual(len(app.all_rows(c,'orders')),0)
    def test_invalid_payment_rolls_back_entire_sale(self):
        with self.assertRaises(ValueError):
            with app.transaction() as c:self.order(c,payments=[{'value':30,'methodId':self.method['id']}])
        with app.transaction() as c:
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],10)
            self.assertEqual(app.all_rows(c,'orders'),[])
    def test_quote_conversion_and_cancel(self):
        with app.transaction() as c:
            o=self.order(c,quote=True)
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],10)
            app.dispatch(c,'/api/orders/'+o['id']+'/convert',{})
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],8)
            app.cancel_order(c,o['id'])
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],10)
            with self.assertRaises(ValueError):app.cancel_order(c,o['id'])
    def test_cancellation_after_closed_cash_refunds_current_cash(self):
        with app.transaction() as c:
            cash=app.dispatch(c,'/api/cash/open',{'opening':0})
            o=self.order(c,payments=[{'value':20,'methodId':self.method['id']}])
            app.dispatch(c,'/api/cash/'+cash['id']+'/close',{'counted':20})
            new_cash=app.dispatch(c,'/api/cash/open',{'opening':30})
            app.cancel_order(c,o['id'])
            self.assertEqual(app.get(c,'cash',cash['id'])['expected'],2000)
            self.assertEqual(app.expected_cash(c,new_cash),1000)
            self.assertEqual(len(app.all_rows(c,'entries')),2)
    def test_purchase_received_once_and_paid(self):
        with app.transaction() as c:
            p=app.dispatch(c,'/api/purchases',{'supplierId':self.supplier['id'],'items':[{'productId':self.product['id'],'qty':3,'cost':4}]})
            app.dispatch(c,'/api/purchases/'+p['id']+'/receive',{})
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],13)
            with self.assertRaises(ValueError):app.dispatch(c,'/api/purchases/'+p['id']+'/receive',{})
            e=app.all_rows(c,'entries')[0];self.assertFalse(e['paid']);self.assertEqual(e['value'],1200)
            app.dispatch(c,'/api/purchase-payment',{'entryId':e['id'],'methodId':self.method['id']})
            self.assertTrue(app.get(c,'entries',e['id'])['paid'])
    def test_variant_and_fractional_validation(self):
        with app.transaction() as c:
            p=app.save_entity(c,'products',{'name':'Camiseta','price':30,'stock':0,'variants':[{'name':'M','stock':2},{'name':'G','stock':3}]})
            with self.assertRaises(ValueError):app.stock(c,p['id'],-1,'Teste')
            app.stock(c,p['id'],-1,'Teste',variant='M')
            self.assertEqual(app.get(c,'products',p['id'])['stock'],4)
            with self.assertRaises(ValueError):self.order(c,quantity=0.5)
    def test_discount_coupon_fees_and_delivery(self):
        with app.transaction() as c:
            app.save_entity(c,'coupons',{'name':'TESTE','mode':'Percentual','value':10,'active':True})
            o=self.order(c,discount=1,discountPct=5,service=2,deliveryValue=3,coupon='teste')
            self.assertEqual(o['total'],2100)
    def test_wholesale_and_offer(self):
        with app.transaction() as c:
            app.save_entity(c,'products',{'offer':True,'offerPrice':9,'wholesaleQty':3,'wholesalePrice':8},self.product['id'])
            self.assertEqual(self.order(c,quantity=2)['total'],1800)
            self.assertEqual(self.order(c,quantity=3)['total'],2400)
    def test_recurring_month_end(self):
        with app.transaction() as c:
            app.entry_create(c,{'name':'Aluguel','type':'Despesa','value':100,'date':'2026-01-31','methodId':self.method['id'],'recurrence':'Mensal','occurrences':3})
            entries=app.all_rows(c,'entries');self.assertEqual(sorted(e['date'] for e in entries),['2026-01-31','2026-02-28','2026-03-31'])
            self.assertEqual(sum(e['paid'] for e in entries),1)
    def test_restore_and_previous_snapshot(self):
        with app.transaction() as c:
            backup={'version':1,'settings':app.settings(c),'records':{k:app.all_rows(c,k) for k in app.ENTITIES}}
            app.save_entity(c,'clients',{'name':'Depois do backup'})
            app.restore_backup(c,backup)
            self.assertEqual(app.all_rows(c,'clients'),[])
            self.assertEqual(c.execute('SELECT count(*) FROM restore_history').fetchone()[0],1)
            self.assertEqual(len(list((app.DATA/'backups').glob('*.json'))),1)
    def test_invalid_restore_preserves_data(self):
        with self.assertRaises(ValueError):
            with app.transaction() as c:app.restore_backup(c,{'version':1,'records':{},'settings':{}})
        with app.transaction() as c:self.assertEqual(len(app.all_rows(c,'products')),1)
    def test_duplicate_barcode_and_stock_edit(self):
        with app.transaction() as c:
            app.save_entity(c,'products',{'barcode':'123'},self.product['id'])
            with self.assertRaises(ValueError):app.save_entity(c,'products',{'name':'Outro','price':5,'barcode':'123'})
            with self.assertRaises(ValueError):app.save_entity(c,'products',{'stock':2},self.product['id'])
    def test_add_items_to_open_order(self):
        with app.transaction() as c:
            o=self.order(c,status='Aberto')
            result=app.dispatch(c,'/api/orders/'+o['id']+'/add-items',{'items':[{'productId':self.product['id'],'qty':1}]})
            self.assertEqual(result['total'],3000)
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],7)
            app.cancel_order(c,o['id'])
            self.assertEqual(app.get(c,'products',self.product['id'])['stock'],10)
    def test_payment_discount_and_split(self):
        with app.transaction() as c:
            app.save_entity(c,'paymentDiscounts',{'name':'Dinheiro 10%','methodId':self.method['id'],'percent':10,'active':True})
            pix=next(m for m in app.all_rows(c,'paymentMethods') if m['name']=='Pix')
            o=self.order(c,methodId=self.method['id'],payments=[{'value':8,'methodId':self.method['id']},{'value':10,'methodId':pix['id']}])
            self.assertEqual(o['total'],1800);self.assertEqual(o['paid'],1800)
            self.assertEqual(len(app.all_rows(c,'entries')),2)
    def test_expense_categories_migrate_once_and_preserve_records(self):
        with app.transaction() as c:
            conf=app.settings(c);conf.pop('expenseCategoriesVersion')
            c.execute('UPDATE settings SET doc=? WHERE id=1',(json.dumps(conf),))
            client=app.save_entity(c,'clients',{'name':'Cliente preservado'})
            original_ids={x['id'] for x in app.all_rows(c,'financialCategories')}
        app.init();app.init()
        with app.transaction() as c:
            categories=app.all_rows(c,'financialCategories')
            self.assertEqual({x['id'] for x in categories},original_ids)
            travel=next(x for x in categories if x['name']=='Despesas operacionais')
            self.assertEqual({x['name'] for x in categories if x.get('parentId')==travel['id']},{'Frete de mercadoria','Aluguel','Conta de água','Conta de energia','Conta de internet','Despesa viagem — Alimentação','Despesa viagem — Gasolina'})
            self.assertEqual(app.get(c,'clients',client['id'])['name'],'Cliente preservado')
    def test_travel_expense_category_and_trip_persist_on_recurrence(self):
        with app.transaction() as c:
            category=next(x for x in app.all_rows(c,'financialCategories') if x['name']=='Despesa viagem — Gasolina')
            entry=app.entry_create(c,{'name':'Abastecimento','type':'Despesa','value':250,'date':'2026-11-05','methodId':self.method['id'],'categoryId':category['id'],'trip':'Busca de produtos em São Paulo','recurrence':'Mensal','occurrences':2,'paid':False})
            entries=app.all_rows(c,'entries')
            self.assertEqual(len(entries),2)
            self.assertTrue(all(x['categoryId']==category['id'] and x['trip']==entry['trip'] and x['value']==25000 and not x['paid'] for x in entries))
    def test_expense_rejects_income_category_and_category_cycles(self):
        with app.transaction() as c:
            categories=app.all_rows(c,'financialCategories')
            income=next(x for x in categories if x['name']=='Vendas')
            travel=next(x for x in categories if x['name']=='Despesas operacionais')
            fuel=next(x for x in categories if x['name']=='Despesa viagem — Gasolina')
            with self.assertRaises(ValueError):app.entry_create(c,{'name':'Aluguel','type':'Despesa','value':100,'methodId':self.method['id'],'categoryId':income['id']})
            with self.assertRaises(ValueError):app.save_entity(c,'financialCategories',{'parentId':fuel['id']},travel['id'])
            with self.assertRaises(ValueError):app.save_entity(c,'financialCategories',{'parentId':travel['id']},travel['id'])
    def test_legacy_expenses_are_reorganized_without_losing_payments(self):
        with app.transaction() as c:
            operations=next(x for x in app.all_rows(c,'financialCategories') if x['name']=='Despesas operacionais')
            for category in app.all_rows(c,'financialCategories'):
                if category.get('parentId')==operations['id']: c.execute('DELETE FROM records WHERE kind=? AND id=?',('financialCategories',category['id']))
            travel=app.save_entity(c,'financialCategories',{'name':'Viagem','type':'Despesa'})
            fuel=app.save_entity(c,'financialCategories',{'name':'Combustível','type':'Despesa','parentId':travel['id']})
            rent=app.save_entity(c,'financialCategories',{'name':'Aluguel','type':'Despesa'})
            entry=app.entry_create(c,{'name':'Abastecimento já registrado','type':'Despesa','value':175,'methodId':self.method['id'],'categoryId':fuel['id'],'paid':True})
            conf=app.settings(c);conf['expenseCategoriesVersion']=1;c.execute('UPDATE settings SET doc=? WHERE id=1',(json.dumps(conf),))
        app.init();app.init()
        with app.transaction() as c:
            updated=app.get(c,'financialCategories',fuel['id'])
            self.assertEqual(updated['name'],'Despesa viagem — Gasolina');self.assertEqual(updated['parentId'],operations['id'])
            self.assertEqual(app.get(c,'financialCategories',rent['id'])['parentId'],operations['id'])
            saved=app.get(c,'entries',entry['id']);self.assertEqual(saved['value'],17500);self.assertTrue(saved['paid']);self.assertEqual(saved['categoryId'],fuel['id'])
            self.assertTrue(app.get(c,'financialCategories',travel['id'])['archived'])

if __name__=='__main__':unittest.main()
