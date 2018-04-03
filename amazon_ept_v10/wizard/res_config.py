# -*- coding: utf-8 -*-

from openerp import models,fields,api,_
from ..amazon_emipro_api.mws import Sellers
from openerp.exceptions import Warning
from datetime import datetime
from dateutil.relativedelta import relativedelta

_intervalTypes = {
    'work_days': lambda interval: relativedelta(days=interval),
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(days=7*interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}

class amazon_seller_config(models.TransientModel):
    _name = 'res.config.amazon.seller'
    
    name = fields.Char("Seller Name")
    access_key = fields.Char("Access Key")
    secret_key = fields.Char("Secret Key")
    merchant_id = fields.Char("Merchant Id")
    country_id = fields.Many2one('res.country',string = "Country")
    
    @api.multi
    def test_amazon_connection(self):
        seller_exist = self.env['amazon.seller.ept'].search([('access_key','=', self.access_key),
                                                ('secret_key','=',self.secret_key),
                                                ('merchant_id','=',self.merchant_id)
                                                ])
        if seller_exist:
            raise Warning('Seller already exist with given Credential.')
        
        mws_obj=Sellers(access_key=str(self.access_key),secret_key=str(self.secret_key),account_id=str(self.merchant_id),region=self.country_id.amazon_marketplace_code or self.country_id.code)
        flag = False
        try:
            result = mws_obj.list_marketplace_participations()
            paticipants = result.parsed.get('ListParticipations',{})
            if paticipants:
                flag=True
        except Exception,e:
            raise Warning('Given Credential is incorrect, please provide correct Credential.')
        if flag:
            vals = {
                    'name':self.name,'access_key':self.access_key,
                    'access_key' : self.access_key,
                    'secret_key':self.secret_key,
                    'merchant_id':self.merchant_id,
                    'country_id':self.country_id.id,
                    }        
            try:
                seller = self.env['amazon.seller.ept'].create(vals)
                seller.load_marketplace()
            except Exception,e:
                raise Warning('Exception during instance creation.\n %s'%(str(e)))
                    
            action = self.env.ref('amazon_ept_v10.action_amazon_config', False)
            result = action and action.read()[0] or {}
            ctx = eval(result.get('context',{}))
            ctx.update({'default_seller_id': seller.id})
            result['context'] = ctx
            return result
            
        return True
        
class amazon_instance_config(models.TransientModel):
    _name = 'res.config.amazon.instance'
    
    name = fields.Char("Instance Name")
    seller_id = fields.Many2one('amazon.seller.ept',string='Seller')
    marketplace_id = fields.Many2one('amazon.marketplace.ept',string='Marketplace',
                                     domain="[('seller_id','=',seller_id),('is_participated','=',True)]")
    
    @api.multi
    def create_amazon_instance(self):
        instance_exist = self.env['amazon.instance.ept'].search([('seller_id','=', self.seller_id.id),
                                                ('marketplace_id','=',self.marketplace_id.id),
                                                ])
        if instance_exist:
            raise Warning('Instance already exist with given Credential.')
        
        user = self.env.user
        if user.company_id:
            company_id = user.company_id.id
        else:
            company = self.env['res.company'].search([('parent_id', '=', False)])
            company_id = company and company[0].id
        
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_id)])
        if warehouse:
            warehouse_id = warehouse[0].id
        else:
            warehouse = self.env['stock.warehouse'].search([])
            warehouse_id = warehouse and warehouse[0].id
        marketplace=self.marketplace_id
        if marketplace.market_place_id in ['ATVPDKIKX0DER','A1PA6795UKMFR9','APJ6JRA9NG5V4','A13V1IB3VIYZZH','A1RKKUPIHCS9HS','A1F83G8C2ARO7P','A2EUQ1WTGCTBG2']:
            amazon_encoding='iso-8859-1'
        elif marketplace.market_place_id in ['A1VC38T7YXB528']:    
            amazon_encoding='Shift_JIS'
        else:# marketplace.name in ['Amazon.cn']:
            amazon_encoding='UTF-8'
        vals = {
                'name':self.name,
                'marketplace_id' :marketplace.id,
                'seller_id' : self.seller_id.id,
                'warehouse_id':warehouse_id,
                'company_id' : company_id,
                'amazon_encodings':amazon_encoding,
                }
        try:
            instance = self.env['amazon.instance.ept'].create(vals)
            instance.import_browse_node_ept() #Import the browse node for selected country
        except Exception,e:
            raise Warning('Exception during instance creation.\n %s'%(str(e)))

        # 创建B2B中的店铺
        shop_language = False
        shop_currency = False
        currency_obj = self.env['res.currency']
        country_id = self.seller_id.country_id if self.seller_id.country_id else False
        if country_id:
            if country_id.name == u'美国':
                shop_language = 'english'
                shop_currency = currency_obj.search([('name','=','USD')])
            elif country_id.name == u'加拿大':
                shop_language = 'english'
                shop_currency = currency_obj.search([('name','=','CAD')])
            elif country_id.name == u'日本':
                shop_language = 'japanese'
                shop_currency = currency_obj.search([('name','=','JPY')])
            elif country_id.name == u'中国':
                shop_language = 'chinese'
                shop_currency = currency_obj.search([('name','=','CNY')])
            elif country_id.name == u'德国':
                shop_language = 'german'
                shop_currency = currency_obj.search([('name','=','EUR')])
            elif country_id.name == u'法国':
                shop_language = 'french'
                shop_currency = currency_obj.search([('name','=','EUR')])
            elif country_id.name == u'西班牙':
                shop_language = 'spanish'
                shop_currency = currency_obj.search([('name','=','EUR')])
            elif country_id.name == u'意大利':
                shop_language = 'italian'
                shop_currency = currency_obj.search([('name','=','EUR')])
        partner = user.partner_id.parent_id or user.partner_id
        shop = self.env['res.partner'].create({'name': self.name,
                                               'amazon_seller_id': self.seller_id.id,
                                               'amazon_instance_id': instance.id,
                                               'is_company': False,
                                               'parent_id': partner.id,
                                               'country_id': country_id.id,
                                               'shop_currency': shop_currency.id,
                                               'shop_language': shop_language,
                                               'type': 'shop',
                                               })
                
        action = self.env.ref('amazon_ept_v10.action_amazon_config', False)
        result = action and action.read()[0] or {}
        ctx = eval(result.get('context',{}))
        ctx.update({'default_seller_id': instance.seller_id.id,'default_instance_id': instance.id})
        result['context'] = ctx
        return 
        
        
class amazon_config_settings(models.TransientModel):
    _name = 'amazon.config.settings'
    _inherit = 'res.config.settings'
    
    @api.model
    def _default_seller(self):
        sellers = self.env['amazon.seller.ept'].search([])
        return sellers and sellers[0].id or False
     
    @api.model
    def _default_instance(self):
        if self.seller_id:
            seller_id = self.seller_id.id
        else:
            seller_id = self._default_seller()
        instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller_id)])
        return instances and instances[0].id or False
     
    @api.model
    def _get_default_company(self):
        company_id = self.env.user._get_company()
        if not company_id:
            raise Warning(_('There is no default company for the current user!'))
        return company_id
    
    seller_id = fields.Many2one('amazon.seller.ept',string='Seller',default=_default_seller)     
    instance_id = fields.Many2one('amazon.instance.ept', 'Instance',default=_default_instance) 
    warehouse_id = fields.Many2one('stock.warehouse',string = "Warehouse")
    company_id = fields.Many2one('res.company',string='Company')
    country_id = fields.Many2one('res.country',string = "Country")
    partner_id = fields.Many2one('res.partner', string='Default Customer')
    lang_id = fields.Many2one('res.lang', string='Language')
    team_id=fields.Many2one('crm.team', 'Sales Team')
    fulfillment_by = fields.Selection([('MFN','Manufacturer Fulfillment Network'),('AFN','Amazon Fulfillment Network')],string="Fulfillment By",default='MFN')
    auto_workflow_id = fields.Many2one('sale.workflow.process.ept', string='Auto Workflow')
    order_prefix = fields.Char(size=10, string='Order Prefix')
    
    price_tax_included = fields.Boolean(string='Is Price Tax Included?')
    auto_send_invoice=fields.Boolean("Auto Send Invoice Via Email ?",default=False)
    
    stock_field = fields.Many2one('ir.model.fields', string='Stock Field', 
        domain="[('model', 'in', ['product.product', 'product.template']), ('ttype', '=', 'float')]",)
    
    update_stock_on_fly = fields.Boolean("Auto Update Stock On the Fly ?",default=False,help='If it is ticked, real time stock updated in Amazon.')
    customer_is_company = fields.Boolean("Customer is Company ?",default=False)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    
    shipment_charge_product_id=fields.Many2one("product.product","Shipment Fee",domain=[('type','=','service')])
    gift_wrapper_product_id=fields.Many2one("product.product","Gift Wrapper Fee",domain=[('type','=','service')])
    promotion_discount_product_id=fields.Many2one("product.product","Promotion Discount",domain=[('type','=','service')])
    ship_discount_product_id = fields.Many2one("product.product","Shipment Discount",domain=[('type','=','service')])
    
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position')
    tax_id = fields.Many2one('account.tax', string='Default Sales Tax')
    settlement_report_journal_id = fields.Many2one('account.journal',string='Settlement Report Journal')

    condition = fields.Selection([('New','New'),
                                  ('UsedLikeNew','UsedLikeNew'),
                                  ('UsedVeryGood','UsedVeryGood'),
                                  ('UsedGood','UsedGood'),
                                  ('UsedAcceptable','UsedAcceptable'),
                                  ('CollectibleLikeNew','CollectibleLikeNew'),
                                  ('CollectibleVeryGood','CollectibleVeryGood'),
                                  ('CollectibleGood','CollectibleGood'),
                                  ('CollectibleAcceptable','CollectibleAcceptable'),
                                  ('Refurbished','Refurbished'),
                                  ('Club','Club')],string="Condition",default='New',copy=False)
    
    auto_create_return_picking=fields.Boolean("Auto Create Return Picking ?",default=False)
    auto_create_refund=fields.Boolean("Auto Create Refund ?",default=False)
    send_order_acknowledgment=fields.Boolean("Order Acknowledgment required ?")
    allow_order_adjustment=fields.Boolean("Allow Order Adjustment ?")
    
    product_ads_account = fields.Boolean('Configure Product Advertising Account ?')
    pro_advt_access_key=fields.Char("Access Key")
    pro_advt_scrt_access_key=fields.Char("Secret Access Key")
    pro_advt_associate_tag=fields.Char("Associate Tag")
    
    stock_auto_export=fields.Boolean(string="Stock Auto Export?")
    inventory_export_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    inventory_export_interval_number = fields.Integer('Export stock Interval Number',help="Repeat every x.")
    inventory_export_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Export Stock Interval Unit')
    inventory_export_user_id=fields.Many2one("res.users",string="User")
    
    order_auto_update = fields.Boolean("Auto Update FBM Order Status?",default=False)
    order_update_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    order_update_interval_number = fields.Integer('Update Order Interval Number',help="Repeat every x.")
    order_update_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Update Order Interval Unit')    
    order_update_user_id=fields.Many2one("res.users",string="User")
    settlement_report_auto_create = fields.Boolean("Auto Import Settlement Report ?",default=False)
    settlement_report_create_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    settlement_report_create_interval_number = fields.Integer('Update Order Interval Number',help="Repeat every x.")
    settlement_report_create_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Update Order Interval Unit')    
    settlement_report_create_user_id=fields.Many2one("res.users",string="User")

    settlement_report_auto_process = fields.Boolean("Auto Process Settlement Report ?",default=False)
    settlement_report_process_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    settlement_report_process_interval_number = fields.Integer('Update Order Interval Number',help="Repeat every x.")
    settlement_report_process_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Update Order Interval Unit')    
    settlement_report_process_user_id=fields.Many2one("res.users",string="User")
            
    auto_send_invoice=fields.Boolean("Auto Send Invoice Via Email ?",default=False)
    auto_send_invoice_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    auto_send_invoice_interval_number = fields.Integer('Update Order Interval Number',help="Repeat every x.")
    auto_send_invoice_process_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Update Order Interval Unit')    
    auto_send_invoice_user_id=fields.Many2one("res.users",string="User")
    invoice_tmpl_id=fields.Many2one("mail.template",string="Invoice Template",default=False)
    #auto send refund
    auto_send_refund=fields.Boolean("Auto Send Refund Via Email ?", default=False)
    auto_send_refund_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    auto_send_refund_interval_number = fields.Integer('Update Order Interval Number',help="Repeat every x.")
    auto_send_refund_process_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Update Order Interval Unit')    
    auto_send_refund_user_id=fields.Many2one("res.users",string="User")
    refund_tmpl_id=fields.Many2one("mail.template",string="Refund Template",default=False)

    create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?', default=False)

    manage_multi_tracking_number_in_delivery_order=fields.Boolean("One order can have multiple Tracking Number ?",default=False)
    is_default_odoo_sequence_in_sales_order=fields.Boolean("Is default Odoo Sequence in Sales Orders ?")
    ending_balance_account_id=fields.Many2one('account.account',string="Ending Balance Account")
    ending_balance_description=fields.Char("Ending Balance Description")
    create_sale_order_from_flat_or_xml_report=fields.Selection([('api','API'),('xml', 'Xml'),('flat','Flat')],default='api',string="Create FBM Sale Order From?")    
    order_auto_import=fields.Boolean(string='Auto Import FBM Order?')#import  order  
    order_import_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    order_import_interval_number = fields.Integer('Import Order Interval Number',help="Repeat every x.")
    order_import_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Import Order Interval Unit')
    order_import_user_id=fields.Many2one("res.users",string="User")

    import_shipped_fbm_orders=fields.Boolean("Import FBM Shipped Orders")# import shipped 
       
    auto_process_sale_order_report = fields.Boolean(string='Auto Process FBM Sale Order Report?')#process report   
    order_process_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    order_process_interval_number = fields.Integer('Import Order Interval Number',help="Repeat every x.")
    order_process_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Import Order Interval Unit')
    
    order_auto_import_xml_or_flat=fields.Boolean(string='Auto Import FBM Order?')#import  order  
    order_auto_import_xml_or_flat_next_execution = fields.Datetime('Next Execution', help='Next execution time')
    order_auto_import_xml_or_flat_interval_number = fields.Integer('Import Order Interval Number',help="Repeat every x.")
    order_auto_import_xml_or_flat_interval_type = fields.Selection( [('minutes', 'Minutes'),
            ('hours','Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Import Order Interval Unit')
    order_auto_import_xml_or_flat_user_id=fields.Many2one("res.users",string="User")
    is_another_soft_create_fbm_reports=fields.Boolean(string="Does another software create the FBM reports?",default=False)
    group_hide_sale_order_report_menu=fields.Boolean('Hide Sale Order Report Menu',compute='hide_menu',implied_group='amazon_ept_v10.group_hide_order_report_menu',default=False)
   
    @api.multi
    def hide_menu(self):  
        if self.create_sale_order_from_flat_or_xml_report=='api' and not self.seller_id.hide_menu() :           
            self.update({'group_hide_sale_order_report_menu':False})
            return  
        self.update({'group_hide_sale_order_report_menu':True})
    @api.multi   
    def setup_xml_or_flat_report_process_cron(self,seller):
        if self.create_sale_order_from_flat_or_xml_report=='flat' and self.auto_process_sale_order_report:           
            if self.auto_process_sale_order_report:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_flat_seller_%d'%(seller.id),raise_if_not_found=False)
                vals = {
                        'active' : True,
                        'interval_number':self.order_process_interval_number,
                        'interval_type':self.order_process_interval_type,
                        'nextcall':self.order_process_next_execution,
                        'args':"([{'seller_id':%d}])"%(seller.id)}
                        
                if cron_exist:
                    #vals.update({'name' : cron_exist.name})
                    cron_exist.write(vals)
                else:
                    import_order_cron = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_flat',raise_if_not_found=False)
                    if not import_order_cron:
                        raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                    
                    name = 'FBM-'+seller.name + ' : Process Amazon FBM Orders Report'
                    vals.update({'name' : name})
                    new_cron = import_order_cron.copy(default=vals)
                    self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                      'name':'ir_cron_process_amazon_orders_flat_seller_%d'%(seller.id),
                                                      'model': 'ir.cron',
                                                      'res_id' : new_cron.id,
                                                      'noupdate' : True
                                                      })
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_flat_seller_%d'%(seller.id),raise_if_not_found=False)
                if cron_exist:
                    cron_exist.write({'active':False})
            return True
        
        if self.create_sale_order_from_flat_or_xml_report=='xml':
            if self.auto_process_sale_order_report:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_xml_seller_%d'%(seller.id),raise_if_not_found=False)
                vals = {
                        'active' : True,
                        'interval_number':self.order_process_interval_number,
                        'interval_type':self.order_process_interval_type,
                        'nextcall':self.order_process_next_execution,
                        'args':"([{'seller_id':%d}])"%(seller.id)}
                        
                if cron_exist:
                    #vals.update({'name' : cron_exist.name})
                    cron_exist.write(vals)
                else:
                    import_order_cron = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_xml',raise_if_not_found=False)
                    if not import_order_cron:
                        raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                    
                    name = 'FBM-'+seller.name + ' : Process Amazon FBM Orders Report'
                    vals.update({'name' : name})
                    new_cron = import_order_cron.copy(default=vals)
                    self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                      'name':'ir_cron_process_amazon_orders_xml_seller_%d'%(seller.id),
                                                      'model': 'ir.cron',
                                                      'res_id' : new_cron.id,
                                                      'noupdate' : True
                                                      })
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_xml_seller_%d'%(seller.id),raise_if_not_found=False)
                if cron_exist:
                    cron_exist.write({'active':False})
            return True
        return False
    @api.one
    @api.constrains('warehouse_id','company_id')
    def onchange_company_warehouse_id(self):
        if self.warehouse_id and self.company_id and self.warehouse_id.company_id.id != self.company_id.id:
            raise Warning("Company in warehouse is different than the selected company. Selected Company and Company in Warehouse must be same.")
   
   
                     
    @api.multi
    def onchange_seller_id(self,seller_id,instance_id,product_ads_account):
        vals = {}
        domain = {}
        ctx = self._context and self._context.copy() or {}
        if ctx.get('params',{}).get('model','')=='amazon.config.settings':
            rec_id = ctx.get('params',{}).get('id')
            if rec_id:
                config_rec = self.browse(rec_id)
                seller_id = config_rec.seller_id.id 
        
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id','=',seller_id)])
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller_id)])
            if instance_id and instance_id in instances.ids:
                vals = self.onchange_instance_id(instance_id,False)
            else:
                vals = self.onchange_instance_id(instances and instances[0].id,False)
            vals['value']['seller_id'] = seller.id or False                                     
            vals['value']['order_auto_update'] = seller.order_auto_update or False
            vals['value']['stock_auto_export'] = seller.stock_auto_export or False
            vals['value']['settlement_report_auto_create'] = seller.settlement_report_auto_create or False
            vals['value']['settlement_report_auto_process'] = seller.settlement_report_auto_process or False
            vals['value']['auto_send_invoice']=seller.auto_send_invoice or False
            vals['value']['auto_send_refund']=seller.auto_send_refund or False
            vals['value']['create_new_product']=seller.create_new_product or False                
            vals['value']['order_auto_import']=seller.order_auto_import or False  
            vals['value']['order_auto_import_xml_or_flat']=seller.order_auto_import_xml_or_flat or False         
            vals['value']['import_shipped_fbm_orders'] = seller.import_shipped_fbm_orders or False        
            vals['value']['auto_process_sale_order_report'] = seller.auto_process_sale_order_report or False #process report
            vals['value']['is_another_soft_create_fbm_reports']=seller.is_another_soft_create_fbm_reports or False
            vals['value']['create_sale_order_from_flat_or_xml_report']=seller.create_sale_order_from_flat_or_xml_report or False
            not instance_id and vals['value'].update({'instance_id':instances and instances[0].id})
            domain['instance_id'] = [('id','in',instances.ids)]
            
            order_process_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            if order_process_cron_exist:
                vals['value']['order_process_interval_number'] = order_process_cron_exist.interval_number or False
                vals['value']['order_process_interval_type'] = order_process_cron_exist.interval_type or False
                vals['value']['order_process_next_execution'] = order_process_cron_exist.nextcall or False
        
            order_import_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            if order_import_cron_exist:
                vals['value']['order_import_interval_number'] = order_import_cron_exist.interval_number or False
                vals['value']['order_import_interval_type'] = order_import_cron_exist.interval_type or False
                vals['value']['order_import_next_execution'] = order_import_cron_exist.nextcall or False
                vals['value']['order_import_user_id']=order_import_cron_exist.user_id.id or False
            order_update_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_update_order_status_seller_%d'%(seller.id),raise_if_not_found=False)
            if order_update_cron_exist:
                vals['value']['order_update_interval_number'] = order_update_cron_exist.interval_number or False
                vals['value']['order_update_interval_type'] = order_update_cron_exist.interval_type or False
                vals['value']['order_update_next_execution'] = order_update_cron_exist.nextcall or False
                vals['value']['order_update_user_id']=order_update_cron_exist.user_id.id or False

            inventory_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_export_inventory_seller_%d'%(seller.id),raise_if_not_found=False)
            if inventory_cron_exist:
                vals['value']['inventory_export_interval_number'] = inventory_cron_exist.interval_number or False
                vals['value']['inventory_export_interval_type'] = inventory_cron_exist.interval_type or False
                vals['value']['inventory_export_next_execution'] = inventory_cron_exist.nextcall or False                                            
                vals['value']['inventory_export_user_id']=inventory_cron_exist.user_id.id or False
            settlement_report_create_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_import_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            if settlement_report_create_cron_exist:
                vals['value']['settlement_report_create_next_execution'] = settlement_report_create_cron_exist.nextcall or False
                vals['value']['settlement_report_create_interval_number'] = settlement_report_create_cron_exist.interval_number or False
                vals['value']['settlement_report_create_interval_type'] = settlement_report_create_cron_exist.interval_type or False                                            
                vals['value']['settlement_report_create_user_id'] = settlement_report_create_cron_exist.user_id.id or False                                            

            settlement_report_process_cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_process_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            if settlement_report_process_cron_exist:
                vals['value']['settlement_report_process_next_execution'] = settlement_report_process_cron_exist.nextcall or False
                vals['value']['settlement_report_process_interval_number'] = settlement_report_process_cron_exist.interval_number or False
                vals['value']['settlement_report_process_interval_type'] = settlement_report_process_cron_exist.interval_type or False                                            
                vals['value']['settlement_report_process_user_id'] = settlement_report_process_cron_exist.user_id.id or False                                            

            send_auto_invoice_cron_exist=self.env.ref('amazon_ept_v10.ir_cron_send_amazon_invoice_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            if send_auto_invoice_cron_exist:
                vals['value']['auto_send_invoice_next_execution'] = send_auto_invoice_cron_exist.nextcall or False
                vals['value']['auto_send_invoice_interval_number'] = send_auto_invoice_cron_exist.interval_number or False
                vals['value']['auto_send_invoice_process_interval_type'] = send_auto_invoice_cron_exist.interval_type or False                                            
                vals['value']['auto_send_invoice_user_id']=send_auto_invoice_cron_exist.user_id.id or False
            
            send_auto_refund_cron_exist=self.env.ref('amazon_ept_v10.ir_cron_send_amazon_refund_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            if send_auto_refund_cron_exist:
                vals['value']['auto_send_refund_next_execution'] = send_auto_refund_cron_exist.nextcall or False
                vals['value']['auto_send_refund_interval_number'] = send_auto_refund_cron_exist.interval_number or False
                vals['value']['auto_send_refund_process_interval_type'] = send_auto_refund_cron_exist.interval_type or False                                            
                vals['value']['auto_send_refund_user_id']=send_auto_refund_cron_exist.user_id.id or False
            
            order_auto_import_xml_or_flat_cron_exist=self.env.ref('amazon_ept_v10.ir_cron_xml_or_flat_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            if order_auto_import_xml_or_flat_cron_exist:
                vals['value']['order_auto_import_xml_or_flat_next_execution'] = order_auto_import_xml_or_flat_cron_exist.nextcall or False
                vals['value']['order_auto_import_xml_or_flat_interval_number'] = order_auto_import_xml_or_flat_cron_exist.interval_number or False
                vals['value']['order_auto_import_xml_or_flat_interval_type'] = order_auto_import_xml_or_flat_cron_exist.interval_type or False                                            
                vals['value']['order_auto_import_xml_or_flat_user_id']=order_auto_import_xml_or_flat_cron_exist.user_id.id or False
            
            auto_process_sale_order_report_cron_exist=False
            if seller.create_sale_order_from_flat_or_xml_report=='flat':                
                auto_process_sale_order_report_cron_exist=self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_flat_seller_%d'%(seller.id),raise_if_not_found=False)
            elif seller.create_sale_order_from_flat_or_xml_report=='xml':
                auto_process_sale_order_report_cron_exist=self.env.ref('amazon_ept_v10.ir_cron_process_amazon_orders_xml_seller_%d'%(seller.id),raise_if_not_found=False)
            if auto_process_sale_order_report_cron_exist:
                vals['value']['order_process_next_execution'] = auto_process_sale_order_report_cron_exist.nextcall or False
                vals['value']['order_process_interval_number'] = auto_process_sale_order_report_cron_exist.interval_number or False                                            
                vals['value']['order_process_interval_type']=auto_process_sale_order_report_cron_exist.interval_type or False
                        
        else:
            vals = self.onchange_instance_id(False,False)            
            vals['value']['order_auto_update'] = False
            vals['value']['stock_auto_export'] = False
            vals['value']['settlement_report_auto_create'] = False
            vals['value']['settlement_report_auto_process'] = False
            vals['value']['auto_send_invoice'] = False
            vals['value']['auto_send_refund'] = False
            domain['instance_id'] = [('id','in',[])]
        vals.update({'domain' : domain})    
        return vals
        
    @api.multi
    def onchange_instance_id(self,instance,product_ads_account):
        values = {} 
        if instance:
            instance = self.env['amazon.instance.ept'].browse(instance)
            values['instance_id'] = instance.id or False
            values['company_id'] = instance.company_id and instance.company_id.id or False
            values['warehouse_id'] = instance.warehouse_id and instance.warehouse_id.id or False
            values['country_id'] = instance.country_id and instance.country_id.id or False
            values['partner_id'] = instance.partner_id and instance.partner_id.id or False 
            values['lang_id'] = instance.lang_id and instance.lang_id.id or False
            values['auto_workflow_id'] = instance.auto_workflow_id and instance.auto_workflow_id.id or False
            values['order_prefix'] = instance.order_prefix and instance.order_prefix
            values['team_id']=instance.team_id and instance.team_id.id or False
            values['price_tax_included'] = instance.price_tax_included or False
            values['stock_field'] = instance.stock_field and instance.stock_field.id or False
            values['pricelist_id'] = instance.pricelist_id and instance.pricelist_id.id or False
            values['payment_term_id'] = instance.payment_term_id and instance.payment_term_id.id or False 
            values['shipment_charge_product_id'] = instance.shipment_charge_product_id and instance.shipment_charge_product_id.id or False
            values['gift_wrapper_product_id'] = instance.gift_wrapper_product_id and instance.gift_wrapper_product_id.id or False
            values['promotion_discount_product_id'] = instance.promotion_discount_product_id and instance.promotion_discount_product_id.id or False
            values['ship_discount_product_id'] = instance.ship_discount_product_id and instance.ship_discount_product_id.id or False
            values['auto_create_return_picking'] = instance.auto_create_return_picking or False
            values['auto_create_refund'] = instance.auto_create_refund or False
            values['send_order_acknowledgment'] = instance.send_order_acknowledgment or False
            values['allow_order_adjustment'] = instance.allow_order_adjustment or False
            values['fiscal_position_id'] = instance.fiscal_position_id and instance.fiscal_position_id.id or False
            values['tax_id'] = instance.tax_id and instance.tax_id.id or False
            values['condition'] = instance.condition or 'New'
            values['update_stock_on_fly'] = instance.update_stock_on_fly or False
            values['customer_is_company'] = instance.customer_is_company or False
            values['settlement_report_journal_id']=instance.settlement_report_journal_id or False
            values['manage_multi_tracking_number_in_delivery_order']=instance.manage_multi_tracking_number_in_delivery_order or False
            values['invoice_tmpl_id']=instance.invoice_tmpl_id.id or False
            values['refund_tmpl_id']=instance.refund_tmpl_id.id or False
            
            if instance.pro_advt_access_key and instance.pro_advt_scrt_access_key and instance.pro_advt_associate_tag:
                values['product_ads_account'] = True
            else:
                values['product_ads_account'] = False    
            values['pro_advt_access_key'] = instance.pro_advt_access_key or False
            values['pro_advt_scrt_access_key'] = instance.pro_advt_scrt_access_key or False
            values['pro_advt_associate_tag'] = instance.pro_advt_associate_tag or False
            values['is_default_odoo_sequence_in_sales_order']=instance.is_default_odoo_sequence_in_sales_order or False
            values['ending_balance_account_id']=instance.ending_balance_account_id and instance.ending_balance_account_id.id or False
            values['ending_balance_description']=instance.ending_balance_description or False
        else:
            values = {'instance_id':False,'auto_create_refund': False, 'stock_field': False, 'country_id': False, 'price_tax_included': False, 'promotion_discount_product_id': False, 'order_prefix': False, 'auto_workflow_id': False, 'payment_term_id': False, 'lang_id': False, 'shipment_charge_product_id': False, 'warehouse_id': False, 'send_order_acknowledgment': False, 'pricelist_id': False, 'auto_create_return_picking': False, 'partner_id': False, 'gift_wrapper_product_id': False,'ship_discount_product_id':False}
        return {'value': values}
    
#     default_get_dict={}
#     @api.model
#     def default_get(self, fields):
#         res = super(amazon_config_settings, self).default_get(fields)
#         if res.get('seller_id'):
#             self.default_get_dict.update(res)
#         return res
            
    @api.multi
    def execute(self):
        instance = self.instance_id
        values = {}
        res = super(amazon_config_settings,self).execute()
        ctx = {}
#         Flag=False
#         change_fields={}
#         for field,value in self.default_get_dict.iteritems():
#             if value==False:
#                 recent_field=self.search_read([('id','=',self.id)],[field])
#                 if value!=recent_field[0].get(field):
#                     change_fields.update({field:value})
#         print change_fields
#         
#         for updated_field,updated_value in change_fields.iteritems(): 
#             if instance:
#                 ctx.update({'default_instance_id': instance.id})
#                 values[updated_field]=updated_value or False
#                 Flag=True
#             return res
        if instance:
            ctx.update({'default_instance_id': instance.id})
            values['company_id'] = self.company_id and self.company_id.id or False
            values['warehouse_id'] = self.warehouse_id and self.warehouse_id.id or False
            values['country_id'] = self.country_id and self.country_id.id or False
            values['partner_id'] = self.partner_id and self.partner_id.id or False 
            values['lang_id'] = self.lang_id and self.lang_id.id or False
            values['auto_workflow_id'] = self.auto_workflow_id and self.auto_workflow_id.id or False
            values['order_prefix'] = self.order_prefix and self.order_prefix
            values['price_tax_included'] = self.price_tax_included or False
            values['stock_field'] = self.stock_field and self.stock_field.id or False
            values['pricelist_id'] = self.pricelist_id and self.pricelist_id.id or False
            values['payment_term_id'] = self.payment_term_id and self.payment_term_id.id or False 
            values['shipment_charge_product_id'] = self.shipment_charge_product_id and self.shipment_charge_product_id.id or False
            values['gift_wrapper_product_id'] = self.gift_wrapper_product_id and self.gift_wrapper_product_id.id or False
            values['promotion_discount_product_id'] = self.promotion_discount_product_id and self.promotion_discount_product_id.id or False
            values['ship_discount_product_id'] = self.ship_discount_product_id and self.ship_discount_product_id.id or False
            values['auto_create_return_picking'] = self.auto_create_return_picking or False
            values['auto_create_refund'] = self.auto_create_refund or False
            values['send_order_acknowledgment'] = self.send_order_acknowledgment or False
            values['allow_order_adjustment'] = self.allow_order_adjustment or False            
            values['fiscal_position_id'] = self.fiscal_position_id and self.fiscal_position_id.id or False
            values['settlement_report_journal_id']=self.settlement_report_journal_id and self.settlement_report_journal_id.id or False
            values['tax_id'] = self.tax_id and self.tax_id.id or False
            values['condition'] = self.condition or 'New'
            values['update_stock_on_fly'] = self.update_stock_on_fly or False
            values['team_id']=self.team_id and self.team_id.id or False
            values['manage_multi_tracking_number_in_delivery_order']=self.manage_multi_tracking_number_in_delivery_order or False
            values['is_default_odoo_sequence_in_sales_order']=self.is_default_odoo_sequence_in_sales_order or False
            values['ending_balance_account_id']=self.ending_balance_account_id and self.ending_balance_account_id.id or False
            values['ending_balance_description']=self.ending_balance_description or False
            customer_is_company = True if self.customer_is_company and not self.partner_id else False
            values['customer_is_company'] = customer_is_company 
            values['invoice_tmpl_id']=self.invoice_tmpl_id.id or False
            values['refund_tmpl_id']=self.refund_tmpl_id.id or False
                        
            
            if self.product_ads_account:
                values['pro_advt_access_key'] = self.pro_advt_access_key or False
                values['pro_advt_scrt_access_key'] = self.pro_advt_scrt_access_key or False
                values['pro_advt_associate_tag'] = self.pro_advt_associate_tag or False            
            instance.write(values)
            self.update_user_groups_ept(self.manage_multi_tracking_number_in_delivery_order)
        if self.seller_id :
            vals = {}        
            vals['order_auto_update'] = self.order_auto_update or False
            vals['stock_auto_export'] = self.stock_auto_export or False
            vals['settlement_report_auto_create']=self.settlement_report_auto_create or False
            vals['settlement_report_auto_process']=self.settlement_report_auto_process or False
            vals['auto_send_invoice']=self.auto_send_invoice or False
            vals['auto_send_refund']=self.auto_send_refund or False            
            vals['create_new_product']=self.create_new_product or False
            vals['order_auto_import'] = self.order_auto_import or False
            vals['order_auto_import_xml_or_flat']=self.order_auto_import_xml_or_flat or False
            vals['import_shipped_fbm_orders']=self.import_shipped_fbm_orders or False                       
            vals['auto_process_sale_order_report']=self.auto_process_sale_order_report or False       
            vals['create_sale_order_from_flat_or_xml_report']=self.create_sale_order_from_flat_or_xml_report or False
            vals['is_another_soft_create_fbm_reports']=self.is_another_soft_create_fbm_reports or False    
            
            self.setup_order_import_cron(self.seller_id)
            self.setup_order_import_xml_or_flat_cron(self.seller_id)
            self.setup_xml_or_flat_report_process_cron(self.seller_id)            
            self.seller_id.write(vals)
            self.setup_order_update_cron(self.seller_id)
            self.setup_inventory_export_cron(self.seller_id)
            self.setup_settlement_report_create_cron(self.seller_id)
            self.setup_settlement_report_process_cron(self.seller_id)
            self.send_invoice_via_email_seller_wise(self.seller_id)
            self.send_refund_via_email_seller_wise(self.seller_id)
            ctx.update({'default_seller_id': self.seller_id.id})            
        if res and ctx:
            res['context']=ctx
            res['params']={'seller_id':self.seller_id and self.seller_id.id,'instance_id': instance and instance.id or False}
        return res
    @api.multi
    def update_user_groups_ept(self,allow_package_group):
        group=self.sudo().env.ref('stock.group_tracking_lot')
        amazon_user_group=self.sudo().env.ref('amazon_ept_v10.group_amazon_user_ept')
        if allow_package_group:
            if group.id not in amazon_user_group.implied_ids.ids: 
                amazon_user_group.sudo().write({'implied_ids':[(4,group.id)]})
        return True
    @api.multi   
    def setup_inventory_export_cron(self,seller):
        if self.stock_auto_export:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_export_inventory_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {'active' : True,
                    'interval_number':self.inventory_export_interval_number,
                    'interval_type':self.inventory_export_interval_type,
                    'nextcall':self.inventory_export_next_execution,
                    'user_id':self.inventory_export_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}
            if cron_exist:
                cron_exist.write(vals)
            else:
                export_stock_cron = self.env.ref('amazon_ept_v10.ir_cron_auto_export_inventory',raise_if_not_found=False)
                if not export_stock_cron:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Auto Export Inventory'
                vals.update({'name':name})
                new_cron = export_stock_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_auto_export_inventory_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_export_inventory_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})        
        return True
    
    @api.multi   
    def setup_order_import_cron(self,seller):
        if self.order_auto_import:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {
                    'active' : True,
                    'interval_number':self.order_import_interval_number,
                    'interval_type':self.order_import_interval_type,
                    'nextcall':self.order_import_next_execution,
                    'user_id':self.order_import_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept_v10.ir_cron_import_amazon_orders',raise_if_not_found=False)
                if not import_order_cron:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Import Amazon Orders'
                vals.update({'name' : name})
                new_cron = import_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_import_amazon_orders_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })     
                
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True
    
    @api.multi   
    def setup_order_import_xml_or_flat_cron(self,seller):
        if self.order_auto_import_xml_or_flat:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_xml_or_flat_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {
                    'active' : True,
                    'interval_number':self.order_auto_import_xml_or_flat_interval_number,
                    'interval_type':self.order_auto_import_xml_or_flat_interval_type,
                    'nextcall':self.order_auto_import_xml_or_flat_next_execution,
                    'user_id':self.order_auto_import_xml_or_flat_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept_v10.ir_cron_xml_or_flat_import_amazon_orders',raise_if_not_found=False)
                if not import_order_cron:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Import Amazon Orders By Report'
                vals.update({'name' : name})
                new_cron = import_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_xml_or_flat_import_amazon_orders_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        
                
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_xml_or_flat_import_amazon_orders_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True
    @api.multi   
    def setup_order_update_cron(self,seller):
        if self.order_auto_update:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_update_order_status_seller_%d'%(seller.id),raise_if_not_found=False)
#             nextcall = datetime.now()
#             nextcall += _intervalTypes[self.order_update_interval_type](self.order_update_interval_number)
            vals = {'active' : True,
                    'interval_number':self.order_update_interval_number,
                    'interval_type':self.order_update_interval_type,
                    'nextcall':self.order_update_next_execution,
                    'user_id':self.order_update_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}                    
            if cron_exist:
                #vals.update({'name' : cron_exist.name})
                cron_exist.write(vals)
            else:
                update_order_cron = self.env.ref('amazon_ept_v10.ir_cron_auto_update_order_status',raise_if_not_found=False)
                if not update_order_cron:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Update Order Status'
                vals.update({'name' : name}) 
                new_cron = update_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_auto_update_order_status_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_update_order_status_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True            
            
    @api.multi   
    def setup_settlement_report_create_cron(self,seller):
        if self.settlement_report_auto_create:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_import_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {'active' : True,
                    'interval_number':self.settlement_report_create_interval_number,
                    'interval_type':self.settlement_report_create_interval_type,
                    'nextcall':self.settlement_report_create_next_execution,
                    'user_id':self.settlement_report_create_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}
                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_import_settlement_report',raise_if_not_found=False)
                if not cron_exist:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Import Settlement Report'
                vals.update({'name' : name}) 
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_auto_import_settlement_report_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_import_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True            
    @api.multi   
    def setup_settlement_report_process_cron(self,seller):
        if self.settlement_report_auto_process:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_process_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {'active' : True,
                    'interval_number':self.settlement_report_process_interval_number,
                    'interval_type':self.settlement_report_process_interval_type,
                    'nextcall':self.settlement_report_process_next_execution,
                    'user_id':self.settlement_report_process_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)}
                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_process_settlement_report',raise_if_not_found=False)
                if not cron_exist:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Process Settlement Report'
                vals.update({'name' : name}) 
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_auto_process_settlement_report_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_auto_process_settlement_report_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True            

    @api.multi   
    def send_invoice_via_email_seller_wise(self,seller):
        if self.auto_send_invoice:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_invoice_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {'active' : True,
                    'interval_number':self.auto_send_invoice_interval_number,
                    'interval_type':self.auto_send_invoice_process_interval_type,
                    'nextcall':self.auto_send_invoice_next_execution,
                    'user_id':self.auto_send_invoice_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)
                    }                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_invoice_via_email',raise_if_not_found=False)
                if not cron_exist:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : Invoice Send By Email'
                vals.update({'name' : name}) 
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_send_amazon_invoice_via_email_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_invoice_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True            

    @api.multi   
    def send_refund_via_email_seller_wise(self,seller):
        if self.auto_send_refund:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_refund_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            vals = {'active' : True,
                    'interval_number':self.auto_send_refund_interval_number,
                    'interval_type':self.auto_send_refund_process_interval_type,
                    'nextcall':self.auto_send_refund_next_execution,
                    'user_id':self.auto_send_refund_user_id.id,
                    'args':"([{'seller_id':%d}])"%(seller.id)
                    }                    
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_refund_via_email',raise_if_not_found=False)
                if not cron_exist:
                    raise Warning('Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.')
                
                name = 'FBM-'+seller.name + ' : refund Send By Email'
                vals.update({'name' : name}) 
                new_cron = cron_exist.copy(default=vals)
                self.env['ir.model.data'].create({'module':'amazon_ept_v10',
                                                  'name':'ir_cron_send_amazon_refund_via_email_seller_%d'%(seller.id),
                                                  'model': 'ir.cron',
                                                  'res_id' : new_cron.id,
                                                  'noupdate' : True
                                                  })
        else:
            cron_exist = self.env.ref('amazon_ept_v10.ir_cron_send_amazon_refund_via_email_seller_%d'%(seller.id),raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active':False})
        return True  
    