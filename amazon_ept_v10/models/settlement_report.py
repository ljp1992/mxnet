from openerp import models, fields, api,_
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,DictWrapper
from openerp.exceptions import Warning
from datetime import datetime, timedelta
import time
import base64
from StringIO import StringIO
from collections import defaultdict
import dateutil.parser


class settlement_report_ept(models.Model):
    _name="settlement.report.ept"
    _inherits={"report.request.history":'report_history_id'}
    _order = 'id desc'
    _inherit = ['mail.thread']
    _description = "Settlement Report"

    def check_process_statement(self):
        for statement in self:
            if statement.statement_id and statement.statement_id.all_lines_reconciled:
                statement.is_processed=True                
            else:
                statement.is_processed=False

    name = fields.Char(size=256, string='Name',default='XML Settlement Report')
    report_history_id = fields.Many2one('report.request.history', string='Report',required=True,ondelete="cascade",index=True, auto_join=True)
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    auto_generated = fields.Boolean('Auto Genrated Record ?', default=False)    
    statement_id = fields.Many2one('account.bank.statement', string="Bank Statement")
    instance_id = fields.Many2one('amazon.instance.ept', string="Instance")
    currency_id = fields.Many2one('res.currency', string="Currency")
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')    
    is_processed=fields.Boolean("Processed ?",compute="check_process_statement",store=False)
    
    @api.multi
    def closed_statement(self):    
        self.statement_id.button_confirm_bank()
        return True

    @api.onchange('instance_id')
    def on_change_instnace(self):
        currency_id=False
        if self.instance_id and self.instance_id.settlement_report_journal_id:
            currency_id=self.instance_id and self.instance_id.settlement_report_journal_id and self.instance_id.settlement_report_journal_id.currency_id.id 
        if not currency_id:
            currency_id=self.seller_id.company_id.currency_id.id
        self.currency_id=currency_id
    @api.multi
    def on_change_seller_id(self, seller_id,start_date,end_date):
        value = {}
        domain = {}
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            value.update({'start_date':seller.settlement_report_last_sync_on,'end_date':datetime.now()})
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller_id)])
            domain['instance_id'] = [('id','in',instances.ids)]
        else:
            domain['instance_id'] = [('id','in',[])]
        return {'value': value,'domain' : domain }

    @api.multi
    def unlink(self):
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(settlement_report_ept, self).unlink()
        
    @api.multi
    def find_unreconcile_lines(self,seller_id,bank_statement,amazon_code=False):
        account_bank_statement_line_obj=self.env['account.bank.statement.line']
        if amazon_code:
            statement_lines=account_bank_statement_line_obj.search([('statement_id','=',self.statement_id.id),('journal_entry_ids','=',False),('amazon_code','!=',False)])
        else:
            statement_lines=account_bank_statement_line_obj.search([('statement_id','=',self.statement_id.id),('journal_entry_ids','=',False),('amazon_code','=',False)])
        return statement_lines
       
    @api.multi
    def process_configute_transactions(self,line,amazon_code,seller_id):
        transaction_obj = self.env['amazon.transaction.line.ept']
        trans_line = transaction_obj.search([('amazon_code','=',amazon_code),('seller_id','=',seller_id)],limit=1)
        if trans_line and trans_line[0].account_id:
            account_id = trans_line[0].account_id.id
            mv_dicts = {
                        'account_id':account_id,
                        'debit': line.amount < 0 and -line.amount or 0.0,
                        'credit': line.amount > 0 and line.amount or 0.0,
                        'tax_ids':trans_line.tax_id and trans_line.tax_id.ids or []
                        }
            if line.amount<0.0:
                mv_dicts.update({'debit':-line.amount})
            else:
                mv_dicts.update({'credit':line.amount})
            line.process_reconciliation(new_aml_dicts=[mv_dicts])
        return True
    
    @api.model
    def remaining_order_lines(self):
        amz_order_obj = self.env['amazon.sale.order.ept']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        
        """ Case 1 : When sale order is imported at that time sale order is in quotation state, 
        so after Importing Settlement report it will receive payment line for that invoice, system will not reconcile invoice of those orders,
        because pending quotation."""

        domain = ['!',('name','=like','Refund_%'),('journal_entry_ids','=',False),('amazon_code','=',False),('statement_id','=',self.statement_id.id)]
        order_statement_lines = bank_statement_line_obj.search(domain)
        for line in order_statement_lines:
            orders = amz_order_obj.search([('amazon_reference','=',line.name),('state','not in',['draft','cancel'])])
            if orders :
                if len(orders) == 1:
                    line.write({'amazon_order_ids':[(4,orders.id)]})
                else:
                    for order in orders:
                        if order.amount_total == line.amount:
                            line.write({'amazon_order_ids':[(4,order.id)]})
                            break
        return True
    @api.model
    def remianing_refund_lines(self):
        amz_order_obj = self.env['amazon.sale.order.ept']
        amz_order_line_obj = self.env['amazon.sale.order.line.ept']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        refund_invoice_dict = defaultdict(dict)
        refund_stement_line_order_dict = {}
        imp_file = StringIO(base64.decodestring(self.attachment_id.datas).decode(self.instance_id.amazon_encodings))
        content = imp_file.read()
        response = DictWrapper( content, "Message")
        result = response.parsed
        settlement_reports = []

        if not isinstance(result.get('SettlementReport',[]),list):
            settlement_reports.append(result.get('SettlementReport',[])) 
        else:
            settlement_reports = result.get('SettlementReport',[])
        
        refunds = []
        for report in settlement_reports:
            if not isinstance(report.get('Refund',{}),list):
                refunds.append(report.get('Refund',{})) 
            else:
                refunds += report.get('Refund',[])

        domain = [('name','=like','Refund_%'),('journal_entry_ids','=',False),('amazon_code','=',False),('statement_id','=',self.statement_id.id)]
        refund_lines = bank_statement_line_obj.search(domain)


        refund_order_name=[]
        refund_line_dict={}
        for refund_line in refund_lines:
            name=str(refund_line.name).replace('Refund_','')
            refund_order_name.append(name)
            refund_line_dict.update({name:refund_line})
        if not refund_order_name:
            return True
        for refund in refunds:
            if not refund:
                continue
            order_ref = refund.get('AmazonOrderID',{}).get('value','')
            if order_ref not in refund_order_name:
                continue
            statement_line=refund_line_dict.get(order_ref)
            fulfillment = refund.get('Fulfillment',{})
            
            item = fulfillment.get('AdjustedItem',{})
            date_posted = fulfillment.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            items=[]
            amzon_orders = amz_order_obj.search([('amazon_reference','=',order_ref),('state','!=','cancel')], order="id")
                    
            if not isinstance(item,list):
                items.append(item) 
            else:
                items = item
            refund_total_amount = 0.0
            orders = amz_order_obj.browse()
            for item in items:
                order_item_code = item.get('AmazonOrderItemCode',{}).get('value','')
                merchant_adjustment_item_id = item.get('MerchantAdjustmentItemID',{}).get('value','')
                order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ('merchant_adjustment_item_id','=',merchant_adjustment_item_id)
                                                    ])
                if not order_line:
                    order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ('merchant_adjustment_item_id','=',False)
                                                    ])
                    
                if not order_line:
                    order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ])                    
                if order_line:
                    order_line = order_line[0]
                if order_line:
                    amz_order = order_line.amazon_order_id
                         
                if not order_line:
                    continue
                item_price = item.get('ItemPriceAdjustments',{})                        
                component = item_price.get('Component',{})
                components=[]
                if not isinstance(component,list):
                    components.append(component) 
                else:
                    components = component
                product_total_amount = 0.0
                for component in components:
                    amount_refund = float(component.get('Amount',{}).get('value',0.0))
                    product_total_amount+= -amount_refund
                    refund_total_amount +=  amount_refund
                promotion_adjustment=item.get('PromotionAdjustment',{})
                promotions=[]
                if promotion_adjustment and not isinstance(promotion_adjustment,list):
                    promotions.append(promotion_adjustment) 
                else:
                    promotions = promotion_adjustment
                     
                for promotion in promotions:                    
                    product_total_amount+= - float(promotion.get('Amount',{}).get('value',0.0))
                    refund_total_amount +=  float(promotion.get('Amount',{}).get('value',0.0))

                if order_line:
                    if refund_invoice_dict.has_key(amz_order):
                        product_total_amount+=refund_invoice_dict.get(amz_order,{}).get(order_line.product_id.id,0.0)
                        refund_invoice_dict.get(amz_order).update({order_line.product_id.id:product_total_amount}) 
                    else:
                        refund_invoice_dict[amz_order].update({order_line.product_id.id:product_total_amount})
                    if not refund_invoice_dict.get(amz_order,{}).has_key('date_posted'):                   
                        refund_invoice_dict.get(amz_order).update({'date_posted':date_posted})
                    if amz_order not in orders:
                        orders+=amz_order
                if order_line:
                    order_line.write({'merchant_adjustment_item_id':merchant_adjustment_item_id})
            if not refund_total_amount:
                continue              
            if orders:
                if refund_stement_line_order_dict.has_key(orders):
                    statement_line+=refund_stement_line_order_dict.get(orders)
                refund_stement_line_order_dict.update({orders:statement_line})
                order_ids=[]
                for line in statement_line:
                    order_ids+=line.amazon_order_ids.ids+orders.ids
                statement_line.write({'amazon_order_ids':[(6,0,list(set(order_ids)))]})
            
        """ Create manually refund in ERP whose returned not found in the system"""         
        if refund_invoice_dict:
            self.create_refund_invoices(refund_invoice_dict,self.statement_id)
        return True
    
    @api.multi
    def reconcile_remaining_transactions(self):
        transaction_obj = self.env['amazon.transaction.line.ept']
        account_statement=self.statement_id
        if account_statement.state!='open':
            return True
         
        self.remaining_order_lines()
        self.remianing_refund_lines()
        self._cr.commit()
         
        statement_lines=self.find_unreconcile_lines(self.seller_id.id, account_statement,True)
        for x in xrange(0, len(statement_lines),20):  
            lines = statement_lines[x:x +20]  
            for line in lines:
                trans_line = transaction_obj.search([('amazon_code','=',line.amazon_code),('seller_id','=',self.seller_id.id)],limit=1)
                if trans_line and trans_line[0].account_id:
                    account_id = trans_line[0].account_id.id
                    mv_dicts = {
                                'name':line.name,
                                'account_id':account_id,
                                'debit': line.amount < 0 and -line.amount or 0.0,
                                'credit': line.amount > 0 and line.amount or 0.0,
                                'tax_ids':trans_line.tax_id and trans_line.tax_id.ids or []
                                }
                    line.process_reconciliation(new_aml_dicts=[mv_dicts])        
            self._cr.commit()
        statement_lines=self.find_unreconcile_lines(self.seller_id.id, account_statement,False) 
        for x in xrange(0, len(statement_lines),20):  
            lines = statement_lines[x:x +20]  
            self.reconcile_bank_statement(lines)
            self._cr.commit()        
        return True
    @api.multi
    def reconcile_bank_statement(self,statement_lines):
        statement_line_obj=self.env['account.bank.statement.line']
        move_line_obj = self.env['account.move.line']
        invoice_obj=self.env['account.invoice']
        bank_statement=self.statement_id
        for statement_line in statement_lines:
            if statement_line.amazon_order_ids and not statement_line.refund_invoice_ids:
                invoices = invoice_obj.browse()
                for order in statement_line.amazon_order_ids:
                    invoices += order.invoice_ids

                invoices = invoices.filtered(lambda record: record.type == 'out_invoice' and record.state in ['open'])
                account_move_ids = map(lambda x:x.move_id.id,invoices)
                move_lines = move_line_obj.search([('move_id','in',account_move_ids),
                                                   ('user_type_id.type','=','receivable'),
                                                   ('reconciled','=',False)])
                mv_line_dicts = []
                move_line_total_amount = 0.0
                currency_ids = []                        
                for moveline in move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency,amount_currency = self.convert_move_amount_currency(bank_statement,moveline,amount)
                        if currency:
                            currency_ids.append(currency)
                            
                    if amount_currency:
                        amount = amount_currency 
                    mv_line_dicts.append({
                                          'credit':abs(amount) if amount >0.0 else 0.0,
                                          'name':moveline.invoice_id.number,
                                          'move_line':moveline,
                                          'debit':abs(amount) if amount < 0.0 else 0.0
                                          })
                    move_line_total_amount += amount
                                        
                if round(statement_line.amount,10) == round(move_line_total_amount,10) and (not statement_line.currency_id or  statement_line.currency_id.id==bank_statement.currency.id):
                    if currency_ids:
                        currency_ids = list(set(currency_ids))
                        if len(currency_ids)==1:
                            statement_line.write({'amount_currency':move_line_total_amount,'currency_id':currency_ids[0]})
                    statement_line.process_reconciliation(mv_line_dicts)
            elif statement_line.refund_invoice_ids:    
                account_move_ids = []
                invoices = statement_line.refund_invoice_ids
                for invoice in invoices:
                    if invoice and invoice.move_id:
                        account_move_ids.append(invoice.move_id.id)
                move_lines = move_line_obj.search([('move_id','in',account_move_ids),
                                                   ('user_type_id.type','=','receivable'),
                                                   ('reconciled','=',False)])
                mv_line_dicts = []
                move_line_total_amount = 0.0
                currency_ids = []                        
                for moveline in move_lines:
                    amount = moveline.debit - moveline.credit
                    amount_currency = 0.0
                    if moveline.amount_currency:
                        currency,amount_currency = self.convert_move_amount_currency(bank_statement,moveline,amount)
                        if currency:
                            currency_ids.append(currency)
                    if amount_currency:
                        amount = amount_currency 
                    mv_line_dicts.append({
                                          'credit':abs(amount) if amount >0.0 else 0.0,
                                          'name':moveline.invoice_id.number,
                                          'move_line':moveline,
                                          'debit':abs(amount) if amount < 0.0 else 0.0
                                          })
                                                                
                    move_line_total_amount += amount
    
                        
                if round(statement_line.amount,10) == round(move_line_total_amount,10) and (not statement_line.currency_id or  statement_line.currency_id.id==bank_statement.currency.id):
                    if currency_ids:
                        currency_ids = list(set(currency_ids))
                        if len(currency_ids)==1:
                            statement_line.write({'amount_currency':move_line_total_amount,'currency_id':currency_ids[0]})
                    statement_line.process_reconciliation(mv_line_dicts)
            if not statement_line_obj.search([('journal_entry_ids','=',False),('statement_id','=',bank_statement.id)]):
                self.write({'state':'processed'})
            elif statement_line_obj.search([('journal_entry_ids','!=',False),('statement_id','=',bank_statement.id)]):
                if self.state!='partially_processed':
                    self.write({'state':'partially_processed'})
        return True
        
    @api.model
    def auto_import_settlement_report(self,args={}):
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id','=',seller_id)])
            if not seller:
                return True
            today = datetime.now()
            if seller.settlement_report_last_sync_on:
                start_date = seller.settlement_report_last_sync_on
            else:                
                earlier = today - timedelta(days=30)
                start_date = earlier.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()    
            report_wiz_rec= self.env['amazon.report.wizard'].create({
                                                     'seller_id':seller_id,
                                                     'start_date' : start_date,
                                                     'end_date' : date_end,
                                                     'report_type':'_GET_V2_SETTLEMENT_REPORT_DATA_XML_'
                                                     })
            report_ids = report_wiz_rec.get_reports()
            self.browse(report_ids).write({'auto_generated' : True})
            seller.write({'settlement_report_last_sync_on':date_end})
        return True
    
    @api.model
    def auto_process_settlement_report(self,args={}):
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id','=',seller_id)])
            return_reports = self.search([('seller_id','=',seller.id),
                                          ('state','=','_DONE_'),
                                          ('auto_generated','=',True),
                                          ('report_id','!=',False)
                                          ])
            for report in return_reports:
                report.get_report()
                if report.instance_id:
                    report.process_settlement_report_file()
                    self._cr.commit()
                    report.reconcile_remaining_transactions()
                else:
                    report.write({'state':'processed'})
        return True 
    
    @api.multi
    def get_report(self):
        self.ensure_one()
        seller = self.seller_id
        if not seller:
            raise Warning('Please select seller')
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not self.report_id:
            return True
        try:
            result = mws_obj.get_report(report_id=self.report_id)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
        
        if hasattr(mws_obj,'response') and hasattr(mws_obj.response,'status_code') and mws_obj.response.status_code!=400:
            data = mws_obj.response.content
            if not data:
                raise Warning('There is no Data in the report %s'%(self.name))
            
            response = DictWrapper( data, "Message")
            result = response.parsed
            if isinstance(result.get('SettlementReport',[]),list):
                settlement_report = result.get('SettlementReport',[])[0] 
            else:
                settlement_report = result.get('SettlementReport',{})
            orders = []
            if not isinstance(settlement_report.get('Order',{}),list):
                orders.append(settlement_report.get('Order',{})) 
            else:
                orders = settlement_report.get('Order',[])
                            
            settlement_data = settlement_report.get('SettlementData',{})
            currency = settlement_data.get('TotalAmount',{}).get('currency',{}).get('value','')
            start_date = settlement_data.get('StartDate',{}).get('value','')
            end_date = settlement_data.get('EndDate',{}).get('value','')
            start_date = dateutil.parser.parse(start_date)
            end_date = dateutil.parser.parse(end_date)
            currency_rec = self.env['res.currency'].search([('name','=',currency)])
            marketplace = orders and orders[0].get('MarketplaceName',{}).get('value','') or ''
            instance = self.env['amazon.marketplace.ept'].find_instance(seller,marketplace)

            result = base64.b64encode(data)
            file_name = "Settlement_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.xml'
            attachment = self.env['ir.attachment'].create({
                                               'name': file_name,
                                               'datas': result,
                                               'datas_fname': file_name,
                                               'res_model': 'mail.compose.message', 
                                               'type': 'binary'
                                             })
            self.message_post(body=_("<b>Settlement Report Downloaded</b>"),attachment_ids=attachment.ids)
            self.write({'attachment_id':attachment.id,
                        'start_date':start_date and start_date.strftime('%Y-%m-%d'),
                        'end_date':end_date and end_date.strftime('%Y-%m-%d'),
                        'currency_id':currency_rec and currency_rec[0].id or False,
                        'instance_id': instance and instance[0].id or False
                        })
        return True
    
    @api.multi
    def download_report(self):
        self.ensure_one()
        if self.attachment_id:
            return {
                    'type' : 'ir.actions.act_url',
                    'url' : '/web/content/%s?download=true' % ( self.attachment_id.id ),
                    'target': 'self',
                    }
        return True       
    @api.multi 
    def make_amazon_advertising_transactions(self,seller,bank_statement,advertising_transactions):
        for transaction in advertising_transactions:
            trans_type = transaction.get('TransactionType',{}).get('value','')
            amount = float(transaction.get('TransactionAmount',{}).get('value',0.0))
            date_posted = transaction.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            invoice_id=transaction.get('InvoiceId',{}).get('value',time.strftime('%Y-%m-%d'))
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,{trans_type:amount},order_ref=invoice_id)
        return True
    @api.multi
    def make_amazon_other_transactions(self,seller,bank_statement,other_transactions):
        for transaction in other_transactions:
            trans_type = transaction.get('TransactionType',{}).get('value','')
            amount = float(transaction.get('Amount',{}).get('value',0.0))
            date_posted = transaction.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,{trans_type:amount})            
        return True

    @api.multi
    def make_amazon_charge_back(self,seller,bank_statement,charge_back_list,settlement_id):
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for charge_back in charge_back_list:
            charge_back_item=[]            
            order_ref=charge_back.get('AmazonOrderID',{}).get('value')
            amazon_order=self.env['amazon.sale.order.ept'].search([('amazon_reference','=',order_ref)])
            price=0.0
            if not isinstance(charge_back.get('Fulfillment',{}).get('AdjustedItem',[]),list):
                charge_back_item.append(charge_back.get('Fulfillment',{}).get('AdjustedItem',[]))
            else:
                charge_back_item=charge_back.get('Fulfillment',{}).get('AdjustedItem')
            
            for item in charge_back_item:
                item_price = item.get('ItemPriceAdjustments',{})                        
                component = item_price.get('Component',{})
                components=[]
                if not isinstance(component,list):
                    components.append(component) 
                else:
                    components = component
                for component in components:
                    amount_refund = float(component.get('Amount',{}).get('value',0.0))
                    price +=  amount_refund                        
            date_posted = charge_back.get('Fulfillment').get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            bank_line_vals = {
                              'name':'Charge Back-'+order_ref,
                              'ref':settlement_id,
                              'partner_id': amazon_order and amazon_order.partner_id and amazon_order.partner_id.id,
                              'amount':price,
                              'statement_id':bank_statement.id,
                              'date':date_posted,
                              'amazon_code':'Chargeback'
                              }
            bank_statement_line_obj.create(bank_line_vals)            
            fees_type_dict={}
            for item in charge_back_item:
                item_fees = item.get('ItemFeeAdjustments',{})
                fees = item_fees.get('Fee',[])
                fees_list = []
                if not isinstance(fees,list):
                    fees_list.append(fees)
                else:
                    fees_list = fees
    
                for fee in fees_list:
                    fee_type = fee.get('Type').get('value')
                    fee_amount = float(fee.get('Amount',{}).get('value',0.0))
                    if fee_type in fees_type_dict:
                        fees_type_dict[fee_type] = fees_type_dict[fee_type]+fee_amount
                    else:
                        fees_type_dict.update({fee_type:fee_amount})
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,fees_type_dict,order_ref)

        return True
    @api.multi
    def make_amazon_guarantee_claim(self,seller,bank_statement,guarantee_claim,settlement_id):
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for claim_record in guarantee_claim:
            adjust_item=[]            
            order_ref=claim_record.get('AmazonOrderID',{}).get('value')
            amazon_order=self.env['amazon.sale.order.ept'].search([('amazon_reference','=',order_ref)])
            price=0.0
            if not isinstance(claim_record.get('Fulfillment',{}).get('AdjustedItem',[]),list):
                adjust_item.append(claim_record.get('Fulfillment',{}).get('AdjustedItem',[]))
            else:
                adjust_item=claim_record.get('Fulfillment',{}).get('AdjustedItem')

            for item in adjust_item:
                item_price = item.get('ItemPriceAdjustments',{})                        
                component = item_price.get('Component',{})
                components=[]
                if not isinstance(component,list):
                    components.append(component) 
                else:
                    components = component
                for component in components:
                    amount_refund = float(component.get('Amount',{}).get('value',0.0))
                    price +=  amount_refund                        
            date_posted = claim_record.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            bank_line_vals = {
                              'name':'GuaranteeClaim-'+order_ref,
                              'ref':settlement_id,
                              'partner_id': amazon_order and amazon_order.partner_id and amazon_order.partner_id.id,
                              'amount':price,
                              'statement_id':bank_statement.id,
                              'date':date_posted,
                              'amazon_code':'GuaranteeClaim'
                              }
            bank_statement_line_obj.create(bank_line_vals)
            fees_type_dict={}
            for item in adjust_item:
                item_fees = item.get('ItemFeeAdjustments',{})
                fees = item_fees.get('Fee',[])
                fees_list = []
                if not isinstance(fees,list):
                    fees_list.append(fees)
                else:
                    fees_list = fees
    
                for fee in fees_list:
                    fee_type = fee.get('Type').get('value')
                    fee_amount = float(fee.get('Amount',{}).get('value',0.0))
                    if fee_type in fees_type_dict:
                        fees_type_dict[fee_type] = fees_type_dict[fee_type]+fee_amount
                    else:
                        fees_type_dict.update({fee_type:fee_amount})
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,fees_type_dict,order_ref)
        return True

    @api.multi
    def create_retro_charge(self,seller,bank_statement,retro_charge_list,settlement_id,amazon_code='Retrocharge'):
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for retro_charge in retro_charge_list:
            order_ref=retro_charge.get('AmazonOrderID',{}).get('value')
            amazon_order=self.env['amazon.sale.order.ept'].search([('amazon_reference','=',order_ref)])
            price=0.0
            base_tax=[]
            if not isinstance(retro_charge.get('BaseTax',{}),list):
                base_tax.append(retro_charge.get('BaseTax',{}))
            else:
                base_tax=retro_charge.get('BaseTax',{})
            shipping_tax=[]
            if not isinstance(retro_charge.get('ShippingTax',{}),list):
                shipping_tax.append(retro_charge.get('ShippingTax',{}))
            else:
                shipping_tax=retro_charge.get('ShippingTax',{})
            
            for tax in base_tax:
                price+=float(tax.get('Amount',{}).get('value',0.0))
            for tax in shipping_tax:
                price+=float(tax.get('Amount',{}).get('value',0.0))
            if price==0.0:
                continue
            date_posted=retro_charge.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            bank_line_vals = {
                              'name':amazon_code+'-'+order_ref,
                              'ref':settlement_id,
                              'partner_id': amazon_order and amazon_order.partner_id and amazon_order.partner_id.id,
                              'amount':price,
                              'statement_id':bank_statement.id,
                              'date':date_posted,
                              'amazon_code':amazon_code,
                              }
            bank_statement_line_obj.create(bank_line_vals)
        return True

    """Main method of process settlement report file"""    
    @api.multi
    def process_settlement_report_file(self):
        self.ensure_one()   
        instance=self.instance_id      
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")

        if not instance:
            raise Warning("Please select the Instance in report.")
        if not self.instance_id.settlement_report_journal_id:
            raise Warning("You have not configured Settlement report Journal in Instance. \nPlease configured it first.")
        currency_id = self.instance_id.settlement_report_journal_id.currency_id.id or self.seller_id.company_id.currency_id.id or False
        if currency_id != self.currency_id.id:
            raise Warning("Report currency and Currency in Instance Journal are different. \nMake sure Report currency and Instance Journal currency must be same.")
                        
        bank_statement_obj = self.env['account.bank.statement']
        imp_file = StringIO(base64.decodestring(self.attachment_id.datas).decode(instance.amazon_encodings))
        content = imp_file.read()
        response = DictWrapper( content, "Message")
        result = response.parsed
        settlement_reports = []
        journal = self.instance_id.settlement_report_journal_id
        if not isinstance(result.get('SettlementReport',[]),list):
            settlement_reports.append(result.get('SettlementReport',[])) 
        else:
            settlement_reports = result.get('SettlementReport',[])
            
        
                       
        seller = self.seller_id
        ctx = self._context and self._context.copy() or {}
        ctx.update({'journal_type':'bank'})
        bank_statement = False
        
        for report in settlement_reports:
            settlement_data = report.get('SettlementData',{})
            settlement_id = settlement_data.get('AmazonSettlementID',{}).get('value','')
            total_amount = settlement_data.get('TotalAmount',{}).get('value','')
            start_date=settlement_data.get('StartDate',{}).get('value','')
            deposit_date=settlement_data.get('DepositDate',{}).get('value')
            end_date=settlement_data.get('EndDate',{}).get('value','')
            start_date=datetime.strptime(start_date,"%Y-%m-%dT%H:%M:%S+00:00").date()
            end_date=datetime.strptime(end_date,"%Y-%m-%dT%H:%M:%S+00:00").date()
            
            settlement_exist = bank_statement_obj.search([('settlement_ref','=',settlement_id)])
            if settlement_exist:
                continue 
            name='%s %s to %s '%(self.instance_id.marketplace_id.name,start_date,end_date)
            vals = {
                    'settlement_ref':settlement_id,
                    'journal_id':journal.id, 
                    'date':end_date,
                    'name':name,
                    'balance_end_real':total_amount,
                    }
            if self.instance_id.ending_balance_account_id:
                vals.update({'balance_end_real':0.0})
            bank_statement = bank_statement_obj.create(vals)
            if self.instance_id.ending_balance_account_id and float(total_amount)!=0.0:  
                bank_statement_line_obj=self.env['account.bank.statement.line']
                bank_line_vals = {
                                  'name':self.instance_id.ending_balance_description or "Ending Balance Description",
                                  'ref':settlement_id,
                                  'partner_id':False,
                                  'amount':-float(total_amount),
                                  'statement_id':bank_statement.id,
                                  'date':deposit_date,
                                  'amazon_code':self.instance_id.ending_balance_description or "Ending Balance Description",
                                  'sequence':1000
                                  }
                line=bank_statement_line_obj.create(bank_line_vals)
                mv_dicts = {
                            'name':self.instance_id.ending_balance_description or "Ending Balance Description",
                            'account_id':self.instance_id.ending_balance_account_id.id,
                            'credit':0.0,
                            'debit':0.0,
                            }
                if float(total_amount)<0.0:
                    mv_dicts.update({'credit':-float(total_amount)})
                else:
                    mv_dicts.update({'debit':float(total_amount)})
                line.process_reconciliation(new_aml_dicts=[mv_dicts])                                                

            orders = []
            refunds = []
            other_transactions = []
            advertising_transactions=[]
            guarantee_claim=[]
            charge_back=[]
            retrocharge=[]
            retrochargereversal=[]
            if not isinstance(report.get('Order',{}),list):
                orders.append(report.get('Order',{})) 
            else:
                orders = report.get('Order',[])
                
            if not isinstance(report.get('GuaranteeClaim',[]),list):
                guarantee_claim.append(report.get('GuaranteeClaim',{}))
            else:
                guarantee_claim=report.get('GuaranteeClaim',[])

            if not isinstance(report.get('Retrocharge'),list):
                retrocharge.append(report.get('Retrocharge',{}))
            else:
                retrocharge=report.get('Retrocharge')
            
            if not isinstance(report.get('RetrochargeReversal'),list):
                retrochargereversal.append(report.get('RetrochargeReversal',{}))
            else:
                retrochargereversal=report.get('RetrochargeReversal')    
                
            if not isinstance(report.get('Chargeback',[]),list):
                charge_back.append(report.get('Chargeback',{}))
            else:
                charge_back=report.get('Chargeback',[])

            if not isinstance(report.get('Refund',{}),list):
                refunds.append(report.get('Refund',{})) 
            else:
                refunds = report.get('Refund',[])
                
            if not isinstance(report.get('OtherTransaction',{}),list):
                other_transactions.append(report.get('OtherTransaction',{})) 
            else:
                other_transactions = report.get('OtherTransaction',[])
                
            if not isinstance(report.get('AdvertisingTransactionDetails',{}),list):
                advertising_transactions.append(report.get('AdvertisingTransactionDetails',{})) 
            else:
                advertising_transactions = report.get('AdvertisingTransactionDetails',[])

            """Process Advertising Transactions"""
            advertising_transactions and self.make_amazon_advertising_transactions(seller,bank_statement,advertising_transactions)
            """Process of make order transactions"""
            other_transactions and self.make_amazon_other_transactions(seller, bank_statement,other_transactions)

            """Update A-Z Guarantee claim"""            
            guarantee_claim and self.make_amazon_guarantee_claim(seller,bank_statement,guarantee_claim,settlement_id)

            """ Update Charge back"""
            charge_back and self.make_amazon_charge_back(seller, bank_statement, charge_back, settlement_id)

            """ Update Retrocharge """           
            retrocharge and self.create_retro_charge(seller,bank_statement,retrocharge,settlement_id)
            
            """Update Retrocharge Reversal"""
            amazon_code='RetrochargeReversal'
            retrochargereversal and self.create_retro_charge(seller, bank_statement, retrochargereversal, settlement_id,amazon_code)        
            
            """Process of orders"""
            orders and self.process_settlement_orders(seller,bank_statement,settlement_id,orders) or {}

            """Process of refunds
                Picking Moves : dict of move which have returned but 2binvoiced
                Picking Products : dict of picking products which have returned but 2binvoiced
                refund invoice dict:dict of refund invoice which not returned & not refunded in ERP system
                refund_stement_line_picking_dict: dict of pickings which have refunds
                refund_stement_line_order_dict :dict of orders which have refunds            
            """
            refund_invoice_dict= self.process_settlement_refunds(seller,bank_statement,settlement_id,refunds)


            """ Create manually refund in ERP whose returned not found in the system"""         
            if refund_invoice_dict:
                self.create_refund_invoices(refund_invoice_dict,bank_statement) 
        vals={}           
        if bank_statement:
            vals={'statement_id':bank_statement.id,'state':'imported'}           
            self.write(vals)
        return True
    
    @api.model
    def convert_move_amount_currency(self,bank_statement,moveline,amount):
        amount_currency = 0.0
        if moveline.company_id.currency_id.id != bank_statement.currency_id.id:
            # In the specific case where the company currency and the statement currency are the same
            # the debit/credit field already contains the amount in the right currency.
            # We therefore avoid to re-convert the amount in the currency, to prevent Gain/loss exchanges
            amount_currency = moveline.currency_id.compute(moveline.amount_currency,bank_statement.currency_id)            
        elif (moveline.invoice_id and moveline.invoice_id.currency_id.id != bank_statement.currency_id.id):                            
            amount_currency = moveline.invoice_id.currency_id.compute(amount,bank_statement.currency_id)
        currency = moveline.currency_id.id
        return currency,  amount_currency
    
    @api.model
    def process_settlement_refunds(self,seller,bank_statement,settlement_id,refunds):
        amz_order_obj = self.env['amazon.sale.order.ept']
        amz_order_line_obj = self.env['amazon.sale.order.line.ept']
        partner_obj = self.env['res.partner']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        amazon_order_fee_obj=self.env['amazon.sale.order.fee.ept']
        refund_invoice_dict = defaultdict(dict)
        refund_stement_line_order_dict = {}
        
        for refund in refunds:
            if not refund:
                continue
            
            order_ref = refund.get('AmazonOrderID',{}).get('value','')
            fulfillment = refund.get('Fulfillment',{})
            item = fulfillment.get('AdjustedItem',{})
            date_posted = fulfillment.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            items=[]
            amzon_orders = amz_order_obj.search([('amazon_reference','=',order_ref),('state','!=','cancel')], order="id")
            partner = False
            if amzon_orders:
                partner = partner_obj._find_accounting_partner(amzon_orders[0].partner_id)
                    
            if not isinstance(item,list):
                items.append(item) 
            else:
                items = item
            refund_total_amount = 0.0
            orders = amz_order_obj.browse()
            fees_type_dict = {}
            amazon_refund_fees_dict={}
            for item in items:
                order_item_code = item.get('AmazonOrderItemCode',{}).get('value','')
                merchant_adjustment_item_id = item.get('MerchantAdjustmentItemID',{}).get('value','')
                order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ('merchant_adjustment_item_id','=',merchant_adjustment_item_id)
                                                    ])
                if not order_line:
                    order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ('merchant_adjustment_item_id','=',False)
                                                    ])
                if not order_line:
                    order_line = amz_order_line_obj.search([('amazon_order_id','in',amzon_orders.ids),
                                                    ('amazon_order_item_id','=',order_item_code),
                                                    ])                    
                if order_line:
                    order_line = order_line[0]
                if order_line:
                    amz_order = order_line.amazon_order_id
                
                item_fees = item.get('ItemFeeAdjustments',{})
                fees = item_fees.get('Fee',[])
                fees_list = []
                if not isinstance(fees,list):
                    fees_list.append(fees)
                else:
                    fees_list = fees

                for fee in fees_list:
                    fee_type = fee.get('Type').get('value')
                    fee_amount = float(fee.get('Amount',{}).get('value',0.0))
                    if fee_type in fees_type_dict:
                        fees_type_dict[fee_type] = fees_type_dict[fee_type]+fee_amount
                    else:
                        fees_type_dict.update({fee_type:fee_amount})
                amazon_refund_fees_dict.update({order_item_code:[fees_type_dict]})                       
                item_price = item.get('ItemPriceAdjustments',{})                        
                component = item_price.get('Component',{})
                components=[]
                if not isinstance(component,list):
                    components.append(component) 
                else:
                    components = component
                product_total_amount = 0.0
                for component in components:
                    amount_refund = float(component.get('Amount',{}).get('value',0.0))
                    product_total_amount+= -amount_refund
                    refund_total_amount +=  amount_refund
                                        
                promotion_adjustment=item.get('PromotionAdjustment',{})
                promotions=[]
                if promotion_adjustment and not isinstance(promotion_adjustment,list):
                    promotions.append(promotion_adjustment) 
                else:
                    promotions = promotion_adjustment
                    
                for promotion in promotions:                    
                    product_total_amount+= - float(promotion.get('Amount',{}).get('value',0.0))
                    refund_total_amount +=  float(promotion.get('Amount',{}).get('value',0.0))
                if order_line:
                    if refund_invoice_dict.has_key(amz_order):
                        product_total_amount+=refund_invoice_dict.get(amz_order,{}).get(order_line.product_id.id,0.0)
                        refund_invoice_dict.get(amz_order).update({order_line.product_id.id:product_total_amount}) 
                    else:
                        refund_invoice_dict[amz_order].update({order_line.product_id.id:product_total_amount})
                    if not refund_invoice_dict.get(amz_order,{}).has_key('date_posted'):                   
                        refund_invoice_dict.get(amz_order).update({'date_posted':date_posted})
                    if amz_order not in orders:
                        orders+=amz_order
                if order_line:
                    #For Performance Reason, we have update order line by executing query.
                    self._cr.execute("update amazon_sale_order_line_ept set merchant_adjustment_item_id=%s where id=%s"%(merchant_adjustment_item_id,str(order_line.id)))
                     
            if not refund_total_amount:
                continue    
            bank_line_vals = {
                              'name':'Refund_'+order_ref,
                              'ref':settlement_id,
                              'partner_id': partner and partner.id,
                              'amount':refund_total_amount,
                              'statement_id':bank_statement.id,
                              'date':date_posted,
                              'is_refund_line':True,
                              }
            
            statement_line = bank_statement_line_obj.create(bank_line_vals)
            if orders:
                if refund_stement_line_order_dict.has_key(orders):
                    statement_line+=refund_stement_line_order_dict.get(orders)
                refund_stement_line_order_dict.update({orders:statement_line})
                order_ids=[]
                for line in statement_line:
                    order_ids+=line.amazon_order_ids.ids+orders.ids
                statement_line.write({'amazon_order_ids':[(6,0,list(set(order_ids)))]})
                for amazon_order_item_code,fees in amazon_refund_fees_dict.iteritems():
                    for fee in fees:
                        amazon_order_lines=amz_order_line_obj.search([('amazon_order_item_id','=',amazon_order_item_code)])
                        for amazon_order_line in amazon_order_lines:
                            for fee_type,amount in fee.iteritems(): 
                                vals={'fee_type':fee_type,
                                      'amount':amount,
                                      'amazon_sale_order_line_id':amazon_order_line.id,
                                      'is_refund':True
                                      }
                                amazon_order_fee_obj.create(vals)   
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,fees_type_dict,order_ref)            
        return refund_invoice_dict    
    @api.multi
    def filter_orders_based_on_payment(self,amz_orders,order_dict):
        fulfillment = order_dict.get('Fulfillment',{})
        item = fulfillment.get('Item',{})
        items=[]
        if not isinstance(item,list):
            items.append(item) 
        else:
            items = item
        order_total_amount = 0.0
        amazon_fees_dict={}
        fees_type_dict={}
        for item in items:
            item_price = item.get('ItemPrice',{})
            amazon_order_item_code=item.get('AmazonOrderItemCode').get('value')
            item_fees = item.get('ItemFees',{})
            fees = item_fees.get('Fee',[])
            fees_list = []
            if not isinstance(fees,list):
                fees_list.append(fees) 
            else:
                fees_list = fees
            for fee in fees_list:
                fee_type = fee.get('Type').get('value')
                fee_amount = float(fee.get('Amount',{}).get('value',0.0))
                if fee_type in fees_type_dict:
                    fees_type_dict[fee_type] = fees_type_dict[fee_type]+fee_amount
                else:
                    fees_type_dict.update({fee_type:fee_amount})
            amazon_fees_dict.update({amazon_order_item_code:[fees_type_dict]})     
                
            component = item_price.get('Component',{})
            components=[]
            if not isinstance(component,list):
                components.append(component) 
            else:
                components = component
            for component in components:
                order_total_amount +=  float(component.get('Amount',{}).get('value',0.0))                        
            promotion_list=item.get('Promotion',{})                         
            if not isinstance(promotion_list,list):
                promotion_list=[promotion_list]
            promotion_amount=0
            for promotion in promotion_list:
                promotion_amount=promotion_amount+float(promotion.get('Amount',{}).get('value',0.0))
            order_total_amount=order_total_amount+promotion_amount
        amazon_order_sub_total=0.0
        for amazon_order in amz_orders:
            if amazon_order.amount_total==order_total_amount:
                return amazon_order,order_total_amount,fees_type_dict,amazon_fees_dict
            amazon_order_sub_total+=amazon_order.amount_total
        if amazon_order_sub_total == order_total_amount:
            return amz_orders,order_total_amount,fees_type_dict,amazon_fees_dict
        return amz_orders,order_total_amount,fees_type_dict,amazon_fees_dict

    @api.model
    def process_settlement_orders(self,seller,bank_statement,settlement_id,orders):
        amz_order_obj = self.env['amazon.sale.order.ept']
        partner_obj = self.env['res.partner']
        product_product_obj=self.env['product.product']
        bank_statement_line_obj = self.env['account.bank.statement.line']     
        amazon_order_fee_obj=self.env['amazon.sale.order.fee.ept']   
        for order in orders:
            if not order:
                continue
            order_ref = order.get('AmazonOrderID',{}).get('value','')
            fulfillment = order.get('Fulfillment',{})
            shipment_fees=order.get('ShipmentFees',[])
            if not isinstance(shipment_fees,list):
                shipment_fees=[shipment_fees]
            date_posted = fulfillment.get('PostedDate',{}).get('value',time.strftime('%Y-%m-%d'))
            amz_orders = amz_order_obj.search([('amazon_reference','=',order_ref)], order="id desc")
            amz_orders,order_total_amount,fees_type_dict,amazon_fees_dict=self.filter_orders_based_on_payment(amz_orders,order)
            partner = False
            for shipment_fee in shipment_fees:
                fees=shipment_fee.get('Fee')
                if not isinstance(fees,list):
                    fees=[fees]
                for fee in fees:
                    fee_value=float(fee.get('Amount',{}).get('value',0.0))
                    self.make_amazon_fee_entry(seller,bank_statement,date_posted,{fee.get('Type',{}).get('value'):fee_value},order_ref)
            if amz_orders:
                partner = partner_obj._find_accounting_partner(amz_orders[0].partner_id)
            if order_total_amount > 0.0:
                bank_line_vals = {
                                  'name':order_ref,
                                  'ref':settlement_id,
                                  'partner_id': partner and partner.id,
                                  'amount':order_total_amount,
                                  'statement_id':bank_statement.id,
                                  'date':date_posted,
                                  'amazon_order_ids':[(6,0,amz_orders.ids)]
                                  }

                bank_statement_line_obj.create(bank_line_vals)
            if amz_orders:                
                for amazon_order_item_code,fees in amazon_fees_dict.iteritems():
                    for fee in fees:
                        products=product_product_obj.search([('type','in',['service','consu'])])
                        amazon_order_lines=self.env['amazon.sale.order.line.ept'].search([('product_id','not in',products.ids),('amazon_order_item_id','=',amazon_order_item_code),('amazon_order_id','in',amz_orders.ids)])
                        for amazon_order_line in amazon_order_lines:
                            for fee_type,amount in fee.iteritems() : 
                                vals={'fee_type':fee_type,
                                                          'amount':amount,
                                                          'amazon_sale_order_line_id':amazon_order_line.id} 
                                amazon_order_fee_obj.create(vals)             
                self.check_or_create_invoice_if_not_exist(amz_orders)
            self.make_amazon_fee_entry(seller,bank_statement,date_posted,fees_type_dict,order_ref)
        return True             
        
    @api.model
    def make_amazon_fee_entry(self,seller,bank_statement,date_posted,fees_type_dict,order_ref='',rei_name=False):
        bank_statement_line_obj = self.env['account.bank.statement.line']
        for fee_type, amount in fees_type_dict.iteritems():
            if amount==0.0:
                continue
            if rei_name:
                name=rei_name
            else:
                name=order_ref and "%s-%s"%(order_ref,fee_type) or fee_type
            bank_line_vals = {
                              'name':name,
                              'ref':bank_statement.settlement_ref,
                              'amount':amount,
                              'statement_id':bank_statement.id,
                              'date':date_posted,  
                              'amazon_code':fee_type                                         
                             }
            bank_statement_line_obj.create(bank_line_vals)
        return True
    
    @api.model
    def check_or_create_invoice_if_not_exist(self,amz_orders):
        for order in amz_orders:
            if order.state=='draft':
                order.action_confirm()

            for picking in order.picking_ids:
                if picking.state in ['confirmed','partially_available','assigned']:
                    picking.action_confirm()
                    picking.action_assign()
                    self.env['stock.immediate.transfer'].create({'pick_id':picking.id}).process()
            if not order.invoice_ids:
                order.sale_order_id.action_invoice_create()                                
            for invoice in order.invoice_ids:
                if invoice.state=='draft' and invoice.type=='out_invoice':
                    invoice.action_invoice_open()                    
        return True
             
    @api.model
    def check_amazon_mws_refund_exist_or_not(self,order):
        refund=self.env['amazon.order.refund.ept'].search([('order_id','=',order.id),('state','=','validate')])
        return refund and {order:refund.invoice_id} or {}
            
    @api.model
    def create_refund_invoices(self,refund_invoice_dict,bank_statement):
        obj_invoice_line = self.env['account.invoice.line']
        bank_statement_line_obj=self.env['account.bank.statement.line']
        obj_invoice = self.env['account.invoice']
        picking_obj = self.env['stock.picking']
        order_invoices_dict = {}
        for order, product_amount in refund_invoice_dict.iteritems():
            date_posted=product_amount.get('date_posted')
            if product_amount.has_key('date_posted'):
                del product_amount['date_posted']
            if order.fulfillment_by=='MFN':
                mws_refund=self.check_amazon_mws_refund_exist_or_not(order)
                refund=mws_refund and mws_refund.get(order)
                mws_refund and order_invoices_dict.update(mws_refund)
                if refund:
                    lines=bank_statement_line_obj.search([('amazon_order_ids','in',order.ids),('statement_id','=',bank_statement.id),('is_refund_line','=',True)])
                    for line in lines:
                        line and line.write({'refund_invoice_ids':[(6,0,line.refund_invoice_ids.ids+refund.ids)]})
                continue
            product_ids = product_amount.keys()
            if order.state in ['draft','sent']:
                self.check_or_create_invoice_if_not_exist([order])
            invoices = obj_invoice.search([('id','in',order.invoice_ids.ids),('type','=','out_invoice'),('invoice_line_ids.product_id','in',product_ids)],limit=1)
            if not invoices:
                if order.invoice_policy and order.invoice_policy=='delivery':
                    pickings = picking_obj.search([('id','in',order.picking_ids.ids),('move_lines.product_id','in',product_ids),('picking_type_id.code','=','outgoing')],limit=1)
                    invoices = obj_invoice.browse()
                    for picking in pickings: 
                        if picking.state!='done':
                            continue
                        invoice_ids = picking.sale_id.action_invoice_create()
                        for invoice in obj_invoice.browse(invoice_ids):
                            invoice.action_invoice_open()
                            invoices +=invoice            
                else:
                    invoice_ids =order.sale_order_id.action_invoice_create()
                    for invoice in obj_invoice.browse(invoice_ids):
                        invoice.action_invoice_open()
                        invoices +=invoice                                
            if not invoices:
                continue
            invoice_browse = obj_invoice.browse()
            for invoice in invoices:
                journal_id = invoice.journal_id.id
                refund_invoice = invoice.refund(date_posted, date_posted, invoice.name, journal_id)
                refund_invoice.compute_taxes()
                refund_invoice.write({'date_invoice':date_posted,'origin':order.name})
                extra_invoice_lines = obj_invoice_line.search([('invoice_id','=',refund_invoice.id),('product_id','not in',product_ids)])
                if extra_invoice_lines:
                    extra_invoice_lines.unlink()
                for product_id,amount in product_amount.iteritems():
                    invoice_lines = obj_invoice_line.search([('invoice_id','=',refund_invoice.id),('product_id','=',product_id)])
                    exact_line=False
                    if len(invoice_lines.ids)>1: 
                        exact_line=obj_invoice_line.search([('invoice_id','=',refund_invoice.id),('product_id','=',product_id)],limit=1)
                        if exact_line:
                            other_lines=obj_invoice_line.search([('invoice_id','=',refund_invoice.id),('product_id','=',product_id),('id','!=',exact_line.id)])  
                            other_lines.unlink()
                            exact_line.write({'quantity':1,'price_unit':amount})
                    else:
                        invoice_lines.write({'quantity':1,'price_unit':amount})  
                refund_invoice.action_invoice_open()
                invoice_browse = invoice_browse + refund_invoice
            order_invoices_dict.update({order:invoice_browse})               
            lines=bank_statement_line_obj.search([('amazon_order_ids','in',order.ids),('statement_id','=',bank_statement.id),('is_refund_line','=',True)])
            for line in lines:
                line and line.write({'refund_invoice_ids':[(6,0,line.refund_invoice_ids.ids+invoice_browse.ids)]})
        return order_invoices_dict    
    @api.multi
    def view_bank_statement(self):
        self.ensure_one()
        action = self.env.ref('account.action_bank_statement_tree',False)
        form_view = self.env.ref('account.view_bank_statement_form',False)
        result = action and action.read()[0] or {}
        result['views'] = [(form_view and form_view.id or False, 'form')]
        result['res_id'] = self.statement_id and self.statement_id.id or False
        
        return result        
        
