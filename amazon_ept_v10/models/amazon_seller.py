from openerp import models,fields,api
from ..amazon_emipro_api.mws import Sellers
from datetime import datetime
from odoo.exceptions import Warning
from __builtin__ import True
class amazon_seller_ept(models.Model):
    _name = "amazon.seller.ept"
    
    def _get_default_company_id(self):
        return self.env.user.company_id.id
    
    name = fields.Char(size=120, string='Name', required=True)
    access_key = fields.Char("Access Key")
    secret_key = fields.Char("Secret Key")
    merchant_id = fields.Char("Merchant Id")
    company_id = fields.Many2one('res.company',string='Company', required=True,default=_get_default_company_id)    
    order_last_sync_on = fields.Datetime("Last FBM Order Sync Time")
    pro_advt_access_key = fields.Char("Access Key")
    pro_advt_scrt_access_key = fields.Char("Secret Access Key")
    pro_advt_associate_tag = fields.Char("Associate Tag")    
    country_id = fields.Many2one('res.country',string = "Region", domain="[('amazon_marketplace_code','!=',False)]")
    warehouse_ids = fields.One2many('stock.warehouse','seller_id', string='Warehouses')
    marketplace_ids = fields.One2many('amazon.marketplace.ept', 'seller_id', string='Marketplaces')
    order_auto_import = fields.Boolean(string='Auto Order Import?')
    stock_auto_export=fields.Boolean(string="Stock Auto Export?")
    settlement_report_auto_create = fields.Boolean("Auto Create Settlement Report ?",default=False)
    settlement_report_auto_process = fields.Boolean("Auto Process Settlement Report ?",default=False)
    auto_send_invoice=fields.Boolean("Auto Send Invoice Via Email ?",default=False)
    shipment_last_sync_on = fields.Datetime("Last Shipment Sync Time")
    order_auto_update = fields.Boolean("Auto Update Order Shipment ?",default=False)
    settlement_report_last_sync_on = fields.Datetime("Settlement Report Last Sync Time")
    transaction_line_ids = fields.One2many('amazon.transaction.line.ept','seller_id','Transactions')    
    create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?', default=False)
    auto_send_refund=fields.Boolean("Auto Send Refund Via Email ?",default=False)    
    #Proxy Server Fields
    proxy_server_type=fields.Selection([('http','Http'),
                                        ('https','Https'),
                                        ('ftp','Ftp')],string='Server Type')
    proxy_server_url=fields.Char('URL')
    proxy_server_port=fields.Char('Port')
#     saleorder_report_last_sync_on = fields.Datetime("Last Sync Sale Order Time")#for flat report    
                
    order_auto_import=fields.Boolean(string='Auto Import FBM Order?')          #import  order flat    
    order_auto_import_xml_or_flat=fields.Boolean(string='Auto Import FBM Order?')
    import_shipped_fbm_orders=fields.Boolean("Import FBM Shipped Orders")  #import shipped   order xml   
    auto_process_sale_order_report = fields.Boolean(string='Auto Process FBM Sale Order Report?')       #process report   
    is_another_soft_create_fbm_reports=fields.Boolean(string="Does another software create the FBM reports?",default=False)
    create_sale_order_from_flat_or_xml_report=fields.Selection([('api','API'),('xml', 'Xml'),('flat','Flat'),],string="Create FBM Sale order from which Report?",default='api')
    
    @api.onchange('create_sale_order_from_flat_or_xml_report')
    def hide_menu(self):
        records=self.search([('id','!=',self.id)])
        visible_menu=False
        for record in records:
            if record.create_sale_order_from_flat_or_xml_report in ['xml','flat']:
                visible_menu=True
        if visible_menu:
            return True
        return False

    @api.model
    def auto_update_order_status_ept(self,args={}):
        amazon_sale_order_obj=self.env['amazon.sale.order.ept']
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = self.search([('id','=',seller_id)])
            amazon_sale_order_obj.update_order_status(seller)
            seller.write({'shipment_last_sync_on':datetime.now()})
        return True

    @api.model
    def auto_export_inventory_ept(self,args={}):
        amazon_product_obj = self.env['amazon.product.ept']
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = self.search([('id','=',seller_id)])
            if not seller:
                return True
            instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
            for instance in instances:
                amazon_product_obj.export_stock_levels(instance)
                instance.write({'inventory_last_sync_on':datetime.now()})
        return True
                
    @api.model
    def get_proxy_server(self):
        proxy_data={}
        if self.proxy_server_type and self.proxy_server_url and self.proxy_server_port:
            url=self.proxy_server_url
            if len(url.split("//"))==2:
                proxy_data={self.proxy_server_type:"%s:%s"%(self.proxy_server_url,self.proxy_server_port)}                          
            else:
                proxy_data={self.proxy_server_type:"%s://%s:%s"%(self.proxy_server_type,self.proxy_server_url,self.proxy_server_port)}                          
        return proxy_data
    @api.multi
    def load_marketplace(self):
        proxy_data=self.get_proxy_server()
        mws_obj = Sellers(access_key=str(self.access_key),secret_key=str(self.secret_key),account_id=str(self.merchant_id),region=self.country_id.amazon_marketplace_code or self.country_id.code,proxies=proxy_data)
        marketplace_obj = self.env['amazon.marketplace.ept']
        currency_obj = self.env['res.currency']
        lang_obj = self.env['res.lang']
        country_obj = self.env['res.country']
        
        list_of_wrapper=[]
        try:
            result = mws_obj.list_marketplace_participations()
            result.parsed.get('ListParticipations',{})
        except Exception,e:
            raise Warning('Given Credentials is incorrect, please provide correct Credentials.')
        
        list_of_wrapper.append(result)
        next_token=result.parsed.get('NextToken',{}).get('value')
        while next_token:
            try:
                result=mws_obj.list_marketplace_participations_by_next_token(next_token)
            except Exception,e:
                raise Warning(str(e))
            next_token=result.parsed.get('NextToken',{}).get('value')
            list_of_wrapper.append(result)                
        
        for wrapper_obj in list_of_wrapper:
            participations = wrapper_obj.parsed.get('ListParticipations',{}).get('Participation',[])
            if not isinstance(participations,list):
                participations=[participations]
                
            marketplaces = wrapper_obj.parsed.get('ListMarketplaces',{}).get('Marketplace',[])
            if not isinstance(marketplaces,list):
                marketplaces=[marketplaces]

            participations_dict = dict(map(lambda x:(x.get('MarketplaceId',{}).get('value',''), x.get('SellerId',{}).get('value',False)),participations))
            for marketplace in marketplaces:
                country_code = marketplace.get('DefaultCountryCode',{}).get('value')
                name = marketplace.get('Name',{}).get('value','')
                domain = marketplace.get('DomainName',{}).get('value','')
                land_code = marketplace.get('DefaultLanguageCode',{}).get('value','')
                currency_code = marketplace.get('DefaultCurrencyCode',{}).get('value','')
                marketplace_id = marketplace.get('MarketplaceId',{}).get('value','')
                currency_id = currency_obj.search([('name','=',currency_code)])
                lang_id = lang_obj.search([('code','=',land_code)])
                country_id = country_obj.search([('code','=',country_code)])
                vals = {
                        'seller_id':self.id,
                        'name' : name,
                        'market_place_id':marketplace_id,
                        'is_participated':participations_dict.get(marketplace_id,False),
                        'domain' : domain,
                        'currency_id' : currency_id and currency_id[0].id or False,
                        'lang_id' : lang_id and lang_id[0].id or False,
                        'country_id' : country_id and country_id[0].id or self.country_id and self.country_id.id or False
                        }
                marketplace_rec = marketplace_obj.search([('seller_id','=',self.id),('market_place_id','=',marketplace_id)])
                if marketplace_rec:
                    marketplace_rec.write(vals)
                else:
                    marketplace_obj.create(vals)
        return True
        
    @api.model
    def auto_import_sale_order_ept(self,args):
        amazon_sale_order_obj = self.env['amazon.sale.order.ept']
        seller_id = args.get('seller_id',False)
        if seller_id:
            seller = self.search([('id','=',seller_id)])
            if seller.order_auto_import and seller.create_sale_order_from_flat_or_xml_report=='api':                    
                amazon_sale_order_obj.import_sales_order(seller)
            seller.write({'order_last_sync_on':datetime.now()})
        return True
        
    @api.model
    def auto_import_xml_or_flat_sale_order_ept(self,args={}):
        amazon_sale_order_obj = self.env['amazon.sale.order.ept']
        seller_id = args.get('seller_id',False)  
        flag=False      
        if seller_id:
            seller = self.search([('id','=',seller_id)])     
            if seller.order_auto_import_xml_or_flat:                      
                if seller.create_sale_order_from_flat_or_xml_report=='flat': 
                    flag=True
                    amazon_sale_order_obj.import_sales_order_by_flat_report(seller)      
                if seller.create_sale_order_from_flat_or_xml_report=='xml': 
                    flag=True     
                    amazon_sale_order_obj.import_sales_order_by_xml_report(seller)            
            flag and seller.write({'order_last_sync_on':datetime.now()})
        return True
