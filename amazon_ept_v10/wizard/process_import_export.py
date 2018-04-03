from openerp import models, fields, api, _
from openerp.exceptions import RedirectWarning,Warning
from ..amazon_emipro_api.api import AmazonAPI
from datetime import datetime
import time
import logging
_logger = logging.getLogger(__name__)
from collections import defaultdict

class amazon_process_import_export(models.TransientModel):
    _name = 'amazon.process.import.export'
   
    instance_ids = fields.Many2many("amazon.instance.ept",'amazon_instance_import_export_rel','process_id','instance_id',"Instances")
    browse_node_ids = fields.Many2many("amazon.browse.node.ept",'amazon_browse_node_import_export_rel',
                                       'process_id','browse_node_id',"Browse Nodes")    
    import_sale_order = fields.Boolean('Sale order')
    import_browse_node = fields.Boolean('Browse Node')    
    export_product = fields.Boolean('Export Products')
    export_product_price = fields.Boolean('Update Product Price')
    export_product_images = fields.Boolean('Update Product Images')
    export_inventory = fields.Boolean('Export Inventory')
    export_order_status = fields.Boolean('Update Order Status')
    
    start_date=fields.Datetime(string="Start Date")#for flat report
    end_date=fields.Datetime(string="End Date")#for flat report
#     import_all_fbm_sales_order=fields.Boolean(string="Sales Orders(Shipped/Unshipped)")#for flat report   
#     shipped_sales_order=fields.Boolean(string="Sales Orders(Shipped)")
        
    @api.model
    def default_get(self,fields):
        res = super(amazon_process_import_export,self).default_get(fields)
        if self._context.has_key('default_instance_id'):
            res.update({'instance_ids':[(6,0,[self._context.get('default_instance_id')])]})
        elif 'instance_ids' in fields:
            instance_ids = self.env['amazon.instance.ept'].search([])
            res.update({'instance_ids':[(6,0,instance_ids.ids)]})
        return res
    
    @api.multi
    def import_export_processes(self):
        amazon_product_obj=self.env['amazon.product.ept']
        sale_order_obj = self.env['amazon.sale.order.ept']     
        saleorder_report_obj=self.env['sale.order.report.ept']   
        seller_import_order_marketplaces = defaultdict(list)
        seller_export_order_marketplaces = defaultdict(list)
        result=True
        for instance in self.instance_ids:    
            if self.import_sale_order:
                seller_import_order_marketplaces[instance.seller_id].append(instance.market_place_id)
                
            if self.import_browse_node:
                browse_nodes = self.browse_node_ids and self.browse_node_ids
                self.import_category(browse_nodes)
            if self.export_product:
                amazon_products=amazon_product_obj.search([('instance_id','=',instance.id)])
                if amazon_products:
                    amazon_product_obj.export_product_amazon(instance,amazon_products)
                
            if self.export_product_price:
                amazon_products=amazon_product_obj.search([('instance_id','=',instance.id),('exported_to_amazon','=',True)])
                if amazon_products:
                    amazon_products.update_price(instance)
            if self.export_product_images:
                amazon_products=amazon_product_obj.search([('instance_id','=',instance.id),('exported_to_amazon','=',True)])
                amazon_products.update_images(instance)
                instance.write({'image_last_sync_on':datetime.now()})
                
            if self.export_inventory:
                instance.export_stock_levels()
            if self.export_order_status:
                seller_export_order_marketplaces[instance.seller_id].append(instance.market_place_id)
#             if self.shipped_sales_order:  
#                 seller_import_order_marketplaces[instance.seller_id].append(instance.market_place_id)
        if self.start_date:
            db_import_time = time.strptime(self.start_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date)+'Z'
        else:
            start_date=False
        if self.end_date:
            db_import_time = time.strptime(self.end_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date)+'Z'
        else:
            end_date=False
        
        if seller_import_order_marketplaces:
            for seller,marketplaces in seller_import_order_marketplaces.iteritems():
                flag=False
                if seller.create_sale_order_from_flat_or_xml_report=='api':
                    flag=True
                    sale_order_obj.import_sales_order(seller,marketplaces,end_date,start_date)                                
                if seller.create_sale_order_from_flat_or_xml_report=='xml':   
                    flag=True            
                    sale_order_obj.import_sales_order_by_xml_report(seller,marketplaces,start_date,end_date)
                    saleorder_report_obj.with_context({'seller_id':seller.id}).auto_process_fbm_xml_report()
                if seller.create_sale_order_from_flat_or_xml_report=='flat':    
                    flag=True                    
                    sale_order_obj.import_sales_order_by_flat_report(seller,marketplaces,start_date,end_date)
                    saleorder_report_obj.with_context({'seller_id':seller.id}).auto_process_fbm_flat_report()
                 
                flag and seller.write({'order_last_sync_on':datetime.now()})
                
                action=self.env.ref('amazon_ept_v10.action_amazon_sale_order_report_ept')
                result = action and action.read()[0] or {}
                saleorder_report_obj = self.env['sale.order.report.ept']
                odoo_report_ids=saleorder_report_obj.search([('seller_id','=',seller.id),('state','in',('_SUBMITTED_','_IN_PROGRESS_'))])
                if odoo_report_ids and seller.create_sale_order_from_flat_or_xml_report!='api':
                    if len(odoo_report_ids)>1:         
                        result['domain'] = "[('id','in',["+','.join(map(str, odoo_report_ids.ids))+"])]"
                    else:
                        res = self.env.ref('amazon_ept_v10.amazon_sale_order_report_form_view_ept', False)
                        result['views'] = [(res and res.id or False, 'form')]
                        result['res_id'] = odoo_report_ids and odoo_report_ids[0].id or False            
            
        if seller_export_order_marketplaces:
            for seller,marketplaces in seller_export_order_marketplaces.iteritems():
                sale_order_obj.update_order_status(seller,marketplaces)
        
        return result
#         return True

    @api.multi
    def import_category(self,root_nodes):
        browse_node=self.env['amazon.browse.node.ept'] 
        instances=self.env['amazon.instance.ept'].search([])
        existing_instance_ids=[]
        for instance in instances:
            if not instance.pro_advt_access_key or not instance.pro_advt_scrt_access_key or not instance.pro_advt_associate_tag:
                continue
            if instance.id in existing_instance_ids:
                continue         
            existing_instance_ids.append(instance.id)
            instance_country_id=instance.country_id.id                              
            for node in root_nodes:
                if node.country_id.id!=instance_country_id:
                    continue  
                     
                Instance=AmazonAPI(str(instance.pro_advt_access_key),str(instance.pro_advt_scrt_access_key),aws_associate_tag=str(instance.pro_advt_associate_tag),region=str(instance.country_id.amazon_marketplace_code or instance.country_id.code),MaxQPS=0.5,Timeout=10)
                ancestor=False
                results=[]
                try:
                    results=Instance.browse_node_lookup(BrowseNodeId=int(node.ama_category_code))
                except Exception,e:
                    _logger.error('Importing Error in %s Browse Node'%(node.name))
                    pass
                if not results:
                    continue
                                 
                for result in results:
                    if result.is_category_root:
                        ancestor=browse_node.check_ancestor_exist_or_not(result,node)
                        try:                                                                                             
                            for children in result.children:
                                parent=ancestor and ancestor.id or node.id
                                browse_node.check_children_exist_or_not(children, node, parent)
                        except Exception,e:
                            raise Warning(str(e))   
        return True 
