from odoo import models, fields, api, _
from ..amazon_emipro_api.api import AmazonAPI
from odoo.exceptions import RedirectWarning,Warning
from datetime import datetime

class amazon_prepare_product_wizard(models.TransientModel):
    _name = 'amazon.product.wizard'
   
    instance_id=fields.Many2one("amazon.instance.ept","Instance")
    amazon_product_ids=fields.Many2many('amazon.product.ept','amazon_product_copy_rel','wizard_id','amazon_product_id',"Amazon Product")
    from_instance_id=fields.Many2one("amazon.instance.ept","From Instance")
    to_instance_id=fields.Many2one("amazon.instance.ept","To Instance")
    copy_all_products=fields.Boolean("Copy All Products",default=True)

    @api.onchange("from_instance_id")
    def on_change_instance(self):
        for record in self:
            record.to_instance_id=False

    @api.multi
    def export_product_in_amazon(self):
        amazon_instance_obj=self.env['amazon.instance.ept']
        amazon_product_obj=self.env['amazon.product.ept']

        if self._context.get('key')=='export_selective_products_in_amazon':
            amazon_instances=amazon_instance_obj.search([])
            active_ids=self._context.get('active_ids',[])
            for instance in amazon_instances:
                amazon_products=amazon_product_obj.search([('id','in',active_ids),('instance_id','=',instance.id)])
                if not amazon_products:
                    continue
                self.env['amazon.product.ept'].export_product_amazon(instance,amazon_products)
        elif self._context.get('key')=='export_category_wise_products_in_amazon':
            amazon_instances=amazon_instance_obj.search([])
            active_ids=self._context.get('active_ids',[])
            for instance in amazon_instances:
                amazon_products=amazon_product_obj.search([('amazon_browse_node_id','in',active_ids),('instance_id','=',instance.id)])
                if not amazon_products:
                    continue
                self.env['amazon.product.ept'].export_product_amazon(instance,amazon_products)
        return True

    @api.multi
    def prepare_product(self):
        template_obj=self.env['product.template']
        if self._context.get('key')=='prepare_selective_product_for_export':
            template_ids=self._context.get('active_ids',[])
            templates=template_obj.browse(template_ids)
            for template in templates:
                if template.type=='service':
                    continue
                odoo_products=template.product_variant_ids
                if template.variation_theme_id:                    
                    self.create_or_update_amazon_product(False, template,template.parent_sku,template.description,'parent')
                if len(template.product_variant_ids.ids)==1:
                    odoo_product=template.product_variant_ids
                    self.create_or_update_amazon_product(odoo_product, template,odoo_product.default_code,template.description,False)
                else:                    
                    for odoo_product in odoo_products:
                        if odoo_product.is_amazon_virtual_variant:
                            continue
                        self.create_or_update_amazon_product(odoo_product, template,odoo_product.default_code,template.description,'child')
        return True

    """This method prepare amazon product by product category for the export in amazon"""
    @api.multi
    def create_or_update_amazon_product(self,odoo_product,template,default_code,description,parentage):
        amazon_product_ept_obj=self.env['amazon.product.ept']
        amazon_attribute_line_obj=self.env['amazon.attribute.line.ept']
        amazon_attribute_value_obj=self.env['amazon.attribute.value.ept']
        amazon_attribute_obj=self.env['amazon.attribute.ept']
        browse_node_obj=self.env['amazon.browse.node.ept']  
        domain=[('country_id','=',self.instance_id.country_id.id)]
        odoo_product and domain.append(('odoo_category_id','=',odoo_product.categ_id.id))
        browse_node=browse_node_obj.search(domain,limit=1)
        vals={
              'instance_id':self.instance_id.id,
              'product_id':odoo_product and odoo_product.id or False,
              'seller_sku':default_code or False,
              'amazon_browse_node_id':browse_node and browse_node.id or False,
              'condition':self.instance_id.condition or 'New',
              'tax_code_id':self.instance_id.default_amazon_tax_code_id and self.instance_id.default_amazon_tax_code_id.id or False,
              'long_description':description or False,
              'variation_data': parentage
              }                    
        if not odoo_product:
            vals.update({'name':template.name,'product_tmpl_id':template.id})
        amazon_product=odoo_product and amazon_product_ept_obj.search([('instance_id','=',self.instance_id.id),('product_id','=',odoo_product.id)]) or False               
        if amazon_product:
            amazon_product.write({'long_description':description or False,'variation_data':parentage})
        else:
            amazon_product=amazon_product_ept_obj.create(vals)              
        if odoo_product:
            for attribute_value in odoo_product.attribute_value_ids:
                if attribute_value.attribute_id.amazon_attribute_id:
                    amazon_attribute_line=amazon_attribute_line_obj.search([('product_id','=',amazon_product.id),('attribute_id','=',attribute_value.attribute_id.amazon_attribute_id.id)])
                    value=amazon_attribute_value_obj.search([('attribute_id','=',attribute_value.attribute_id.amazon_attribute_id.id),('name','=',attribute_value.name)],limit=1)
                    if not value:
                        value=amazon_attribute_value_obj.create({'attribute_id':attribute_value.attribute_id.amazon_attribute_id.id,'name':attribute_value.name})
                    if amazon_attribute_line:
                        amazon_attribute_line.write({'value_ids':[(6,0,value.ids)]})
                    else:
                        amazon_attribute_line_obj.create({'product_id':amazon_product.id,'attribute_id':attribute_value.attribute_id.amazon_attribute_id.id,'value_ids':[(6,0,value.ids)]})
        if template.variation_theme_id:
                categ_ids=template.amazon_categ_id.ids+template.child_categ_id.ids
                attributes=amazon_attribute_obj.search([('amazon_categ_id','in',categ_ids),('name','=','Parentage')])
                amazon_attribute_line=amazon_attribute_line_obj.search([('product_id','=',amazon_product.id),('attribute_id','in',attributes.ids)],limit=1)                        
                value=amazon_attribute_value_obj.search([('attribute_id','in',attributes.ids),('name','=',parentage)],limit=1)
                if not value:
                    value=amazon_attribute_value_obj.create({'attribute_id':attributes.ids[0],'name':parentage})
                if amazon_attribute_line:
                    amazon_attribute_line.write({'value_ids':[(6,0,value.ids)]}) 
                else:
                    amazon_attribute_line_obj.create({'product_id':amazon_product.id,'attribute_id':attributes.ids[0],'value_ids':[(6,0,value.ids)]})                                

                attributes=amazon_attribute_obj.search([('amazon_categ_id','in',categ_ids),('name','=','VariationTheme')])
                amazon_attribute_line=amazon_attribute_line_obj.search([('product_id','=',amazon_product.id),('attribute_id','in',attributes.ids)],limit=1)                        
                value=amazon_attribute_value_obj.search([('attribute_id','in',attributes.ids),('name','=',template.variation_theme_id.name)],limit=1)
                if not value:
                    value=amazon_attribute_value_obj.create({'attribute_id':attributes.ids[0],'name':template.variation_theme_id.name})
                if amazon_attribute_line:
                    amazon_attribute_line.write({'value_ids':[(6,0,value.ids)]}) 
                else:
                    amazon_attribute_line_obj.create({'product_id':amazon_product.id,'attribute_id':attributes.ids[0],'value_ids':[(6,0,value.ids)]})
        return True
    
    @api.multi
    def copy_product(self):
        amazon_product_ept_obj=self.env['amazon.product.ept']
        from_instance=self.from_instance_id
        to_instance=self.to_instance_id
        odoo_product_ids=[]
        amazon_products=[]
        if self.copy_all_products:
            amazon_products=amazon_product_ept_obj.search([('instance_id','=',from_instance.id)])
            for amazon_product in amazon_products:
                amazon_product.product_id and odoo_product_ids.append(amazon_product.product_id.id)
            
        else:
            amazon_products=self.amazon_product_ids
            for amazon_product in amazon_products:
                amazon_product.product_id and odoo_product_ids.append(amazon_product.product_id.id)
        exist_products=amazon_product_ept_obj.search([('instance_id','=',to_instance.id),('product_id','in',odoo_product_ids)])
        odoo_product_ids=[]
        for amazon_product in exist_products:    
            amazon_product.product_id and odoo_product_ids.append(amazon_product.product_id.id)
        for amazon_product in amazon_products:
            if amazon_product.product_id.id in odoo_product_ids:
                continue
            amazon_product.copy({'instance_id':to_instance.id})
        return True

    
    
    "This method is called based on condition when it is called from\
    product wizard it calls,'update_selective_image'(IF part)   \
    else it will call,update_categ_wise_image(ELIF part) if it is called from \
    product category wizard "
    @api.multi
    def update_image(self):
        amazon_product_obj=self.env['amazon.product.ept']
        amazon_browse_node_obj=self.env['amazon.browse.node.ept']
        amazon_instance_obj=self.env['amazon.instance.ept']
              
        if self._context.get('key',False)=='update_selective_image':                         
            amazon_product_ids=self._context.get('active_ids',[])
            instances=amazon_instance_obj.search([('ept_product_ids','in',amazon_product_ids)])                    
            for instance in instances:
                amazon_products=amazon_product_obj.search([('instance_id','=',instance.id),('id','in',amazon_product_ids),('exported_to_amazon','=',True)])              
                amazon_products.update_images(instance)
                instance.write({'image_last_sync_on':datetime.now()})                
        elif self._context.get('key',False)=='update_categ_wise_image':                      
            amazon_categ_ids=self._context.get('active_ids',[])                                            
            instances=amazon_instance_obj.search([])                    
            for instance in instances:                                              
                amazon_browse_categs=amazon_browse_node_obj.search([('id','in',amazon_categ_ids),('instance_id','=',instance.id)])
                amazon_product_ids=[]
                for amazon_browse_categ in amazon_browse_categs:
                    amazon_products=amazon_product_obj.search([('amazon_browse_node_id','=',amazon_browse_categ.id),
                                                               ('exported_to_amazon','=',True)])
                    amazon_product_ids+=amazon_products.ids                   
                amazon_products=amazon_product_obj.browse(amazon_product_ids)                
                amazon_products.update_images(instance)
                instance.write({'image_last_sync_on':datetime.now()}) 
        
        return True
    
    
    @api.multi
    def update_price(self):
        amazon_instance_obj=self.env['amazon.instance.ept']
        amazon_product_obj=self.env['amazon.product.ept']
        amazon_browse_node_obj=self.env['amazon.browse.node.ept']
        
        if self._context.get('key',False)=='update_selective_price':
            amazon_product_ids=self._context.get('active_ids',[])
            instances=amazon_instance_obj.search([('ept_product_ids','in',amazon_product_ids)])                    
            for instance in instances:
                amazon_products=amazon_product_obj.search([('instance_id','=',instance.id),('id','in',amazon_product_ids),('exported_to_amazon','=',True)])              
                amazon_products.update_price(instance)            
        elif self._context.get('key',False)=='update_categ_wise_price':
            amazon_categ_ids=self._context.get('active_ids',[])                                            
            instances=amazon_instance_obj.search([])                    
            for instance in instances:                                              
                amazon_browse_categs=amazon_browse_node_obj.search([('id','in',amazon_categ_ids),('instance_id','=',instance.id)])
                amazon_product_ids=[]
                for amazon_browse_categ in amazon_browse_categs:
                    amazon_products=amazon_product_obj.search([('amazon_browse_node_id','=',amazon_browse_categ.id),
                                                               ('exported_to_amazon','=',True)])
                    amazon_product_ids+=amazon_products.ids                   
                amazon_products=amazon_product_obj.browse(amazon_product_ids)                
                amazon_products.update_price(instance)
        return True
    
    @api.multi
    def update_stock_ept(self):
        product_obj=self.env['amazon.product.ept']
        product_ids=self._context.get('active_ids')
        for instance in self.env['amazon.instance.ept'].search([]):            
            products=product_obj.search([('id','in',product_ids),('instance_id','=',instance.id),('fulfillment_by','=','MFN')])
            products and product_obj.export_stock_levels(instance,products.ids)
        return True
    """This method is used to import category from amazon based on root category,\
    it checks if the category is root OR not child then it will import all the \
    child categories"""
    @api.multi
    def import_category(self):
        browse_node=self.env['amazon.browse.node.ept']
        root_node_ids=self._context.get('active_ids',[])
        instance_obj=self.env['amazon.instance.ept']
        records=browse_node.search([('id','in',root_node_ids),('parent_id','=',False)])
        
        if len(root_node_ids) != len(records.ids):
            raise Warning(_("You have selected the category which is not root category..."))              
        for node in records:
            country_id=node.country_id.id
            if not country_id:
                raise Warning(_("Browse node '%s' not have country")%(node.name)) 
            instance=instance_obj.search([('country_id','=',country_id)])
            if instance:
                if not instance.pro_advt_access_key or not instance.pro_advt_scrt_access_key or not instance.pro_advt_associate_tag:
                    action = self.env.ref('amazon_ept_v11.action_amazon_config')
                    msg = _('You have not configure Product Advertising Account, You should configure it. \nPlease go to Amazon Configuration.')
                    raise RedirectWarning(msg, action.id, _('Go to the configuration panel'))            
            Instance=AmazonAPI(str(instance.pro_advt_access_key),str(instance.pro_advt_scrt_access_key),aws_associate_tag=str(instance.pro_advt_associate_tag),region=str(instance.country_id.amazon_marketplace_code or instance.country_id.code),MaxQPS=0.5,Timeout=10)
            ancestor=False
            results=[]
            try:
                results=Instance.browse_node_lookup(BrowseNodeId=int(node.ama_category_code))
            except Exception as e:
                raise Warning(str(e))
            if not results:
                continue
                             
            for result in results:
                if result.is_category_root:
                    ancestor=browse_node.check_ancestor_exist_or_not(result,node)
                    try:                                                                                             
                        for children in result.children:
                            parent=ancestor and ancestor.id or node.id
                            browse_node.check_children_exist_or_not(children, node, parent)
                    except Exception as e:
                        raise Warning(str(e))
        return True        
