from openerp import models, fields,api
from openerp.osv import expression
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from ..amazon_emipro_api.mws import Feeds
import math
import datetime
import re
import cgi
import time
    
class DataDict(dict):
    def __missing__(self, key):
        return ''            
class product_product(models.Model):
    _inherit="product.product"

    ept_image_ids = fields.One2many('product.image.ept', 'product_id', string='Images')    
    variation_data=fields.Selection([('parent','Parent'),('child','Child'),('collection-parent','collection-parent'),('variation-parent','variation-parent')],string="Variation Data",default=False)
    @api.one
    def _get_amazon_variant_count(self):
        self.amazon_variant_count = len(self.amazon_product_ids)
        
    amazon_product_ids = fields.One2many('amazon.product.ept', 'product_id', 'Amazon Products', required=True)
    amazon_variant_count = fields.Integer(string='# of Amazon Products',compute="_get_amazon_variant_count")
    is_amazon_virtual_variant=fields.Boolean("Is Amazon Virtual Variant",default=False,copy=False)
    @api.multi
    def action_view_amazon_products(self):
        self.ensure_one()
        res = self.env.ref('amazon_ept_v10.action_amazon_product_ept')
        result = res and res.read()[0] or {}
        result['domain'] = "[('product_id','='," +str(self.id) + ")]"
        return result
            
class amazon_product_ept(models.Model):
    _name="amazon.product.ept"
    _inherits = {'product.product': 'product_id'}
    
    
    @api.onchange('amazon_browse_node_id','amazon_browse_node_id2')
    def onchange_amazon_browse_node_id(self):
        res={}
        domain=[('country_id','=',self.instance_id.country_id),('is_root_category','=',False)]
        res['domain']=domain
        return res
    
    @api.model
    def search_product(self,seller_sku):
        product = self.env['product.product'].search([('default_code','=',seller_sku)])
        if not product:
            product = self.env['product.product'].search([('default_code','=',seller_sku),('active','=',False)])
        if product and not product.active:
            product.write({'active':True})
        return product and product[0] or False
        
    @api.model
    def search_amazon_product(self,instance_id,seller_sku,fulfillment_by='MFN'):
        seller_sku=seller_sku.rstrip()
        seller_sku=seller_sku.lstrip()
        product = self.search(['|',('active','=',False),('active','=',True),('seller_sku','=',seller_sku),('instance_id','=',instance_id),('fulfillment_by','=',fulfillment_by)],limit=1)
        if not product:
            return False
        if not product.active:
            product.write({'active':True})
        return product[0]
    
    @api.one    
    def _calc_seller(self):         
        for product in self:
            product.merchant_catalog_number = ''
            seller_info_id=self._get_main_product_supplier(product.product_id)
            
            if seller_info_id:
                product.merchant_catalog_number = seller_info_id.product_code and seller_info_id.product_code or '' 
                                           
    def _get_main_product_supplier(self,product):
        sellers = [(seller_info.sequence, seller_info)
                       for seller_info in product.seller_ids or []
                       if seller_info and isinstance(seller_info.sequence, (int, long))]
        return sellers and sellers[0][1] or False
        
    @api.multi
    def get_log_count(self):
        amazon_transaction_log_obj=self.env['amazon.transaction.log']
        model_id=amazon_transaction_log_obj.get_model_id('amazon.product.ept')
        for product in self:
            records=amazon_transaction_log_obj.search([('model_id','=',model_id),('res_id','=',product.id),('job_id.request_feed_id','!=',False)])
            product.log_count=len(records.ids)
    @api.multi
    def get_variants(self):
        for record in self:
            if record.variation_data=='child':
                continue
            product_ids=record.product_id.product_tmpl_id.product_variant_ids.ids
            variants=self.search([('product_id','in',product_ids),('instance_id','=',record.instance_id.id),('variation_data','=','child')])
            record.child_variant_ids=variants.ids 
            
    @api.multi
    def unlink(self):
        for record in self:
            super(amazon_product_ept,record.child_variant_ids).unlink()        
            if record.variation_data=='parent':
                record.product_id.unlink()
        return super(amazon_product_ept,self).unlink()
    @api.one
    def get_amazon_price(self):
        instance=self.instance_id
        pricelist=instance.pricelist_id
        if pricelist:
            price =self.product_id.with_context({'pricelist':pricelist.id,'quantity':1.0}).price 
            self.amazon_price_ept=price

    related_product_type=fields.Selection([('UPC','UPC'),('EAN','EAN'),('GTIN','GTIN')])
    related_product_value=fields.Char("Related Product Value")
    promo_tag_type=fields.Selection([('Sale','Sale'),
                                ('New','New'),
                                ('NewArrival','NewArrival'),
                                ('WebOnly','WebOnly'),
                                ('Clearance','Clearance'),
                                ('LimitedOffer','LimitedOffer'),
                                ('SpecialOffer','SpecialOffer'),
                                ('SpecialPurchase','SpecialPurchase'),
                                ('OnlyInStores','OnlyInStores')
                                ])
    priority=fields.Integer("Priority",default=1)
    liquid_volume=fields.Float("LiquidVolume",digits=(16,2))
    liquid_uom=fields.Selection([('cubic-cm','Cubic-Cm'),('cubic-ft','Cubic-Ft'),('cubic-in','Cubic-In'),('cubic-m','Cubic-mM'),
                                    ('cubic-yd','Cubic-Yd'),('cup','Cup'),('fluid-oz','Fluid-Oz'),('gallon','Gallon'),
                                    ('liter','Liter'),('milliliter','Milliliter'),('ounce','Ounce'),('pint','Pint'),
                                    ('quart','Quart'),('liters','Liters'),('deciliters','Deciliters'),('centiliters','Centiliters'),
                                    ('milliliters','Milliliters'),('microliters','Microliters'),('nanoliters','Nanoliters'),
                                    ('picoliters','Picoliters')
                                    ])
    delivery_channel=fields.Selection([('in_store','In Store'),('direct_ship','Direct Ship')],default='direct_ship')
    delivery_schedule_group=fields.Char("DeliveryScheduleGroupID")
    browse_exclusion=fields.Boolean("BrowseExclusion",default=False)
    recommendation_exclusion=fields.Boolean("RecommendationExclusion",default=False)
    effective_from_date=fields.Date("Effective From Date")
    effective_through_date=fields.Date("Effective Through Date")
    rebate_start_date=fields.Datetime("Rebate Start Date")
    rebate_end_date=fields.Datetime("Rebate End Date")
    rebate_message=fields.Text("Message")
    rebate_name=fields.Char("Rebate Name")
    promotion_keywords_ids=fields.Many2many("amazon.promotion.keyword.ept",'amazon_promotion_keyword_rel','product_id','promotion_id',string="PromotionKeywords")
    used_for_ids=fields.Many2many("amazon.product.used.for",'amazon_product_used_for_rel','product_id','used_for_id',string="Used For")
    target_audience_ids=fields.Many2many("amazon.target.audience","amazon_target_audience_rel","product_id","target_id",string="Target Audience")
    subject_content_ids=fields.Many2many("amazon.subject.content","amazon_subject_content_rel","product_id","content_id",string="Subject Content")
    other_attribute_ids=fields.Many2many("amazon.other.item.attributes","amazon_other_item_attribute_rel","product_id","attribute_id",string="Other Attributes")
    platinum_keyword_ids=fields.Many2many("amazon.platinum.keyword","amazon_platinum_keyword_rel","product_id","platinum_keyword_id",string="Platinum Keywords")
    is_customizable=fields.Boolean("Is Customizable",default=False)
    merchant_shipping_group_name=fields.Char("MerchantShippingGroupName")
    customizable_template_name=fields.Char("CustomizableTemplateName")
    child_variant_ids=fields.One2many("amazon.product.ept",string="Child Variants",compute="get_variants")
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance',  required=True,copy=False)
    product_asin=fields.Char("Product ASIN",copy=False)
    product_isbn=fields.Char("ISBN",copy=False)
    product_upc=fields.Char("UPC",copy=False)
    is_memorabilia=fields.Boolean("Memorabilia",default=False)
    is_auto_graphed=fields.Boolean("Autographed",default=False)
    fedas_id=fields.Integer("FEDAS_ID")
    amazon_vendor_cost=fields.Float("Amazon Vendor Cost",digits=(16,2))
    tier=fields.Integer("Tier")
    purchasing_category=fields.Char("PurchasingCategory")
    purchasing_sub_category=fields.Char("PurchasingSubCategory")
    packaging_type=fields.Char("PackagingType")
    distribution_designation=fields.Selection([('jp_parallel_import','jp_parallel_import')])
    underlying_availability=fields.Selection([('backordered','Backordered'),
                                              ('manufacturer-out-of-stock','Manufacturer Out Of Stock'),
                                              ('pre-ordered','Pre-Ordered'),
                                              ('2-3-days','2-3-days'),
                                              ('1-2-weeks','1-2-weeks'),
                                              ('4-6-weeks','4-6-weeks')                                              
                                              ])
    replenishment_category=fields.Selection([('basic-replenishment','Basic Replenishment'),
                                             ('limited-replenishment','Limited Replenishment'),
                                             ('manufacturer-out-of-stock','Manufacturer Out Of Stock'),
                                             ('new-product','New-Product'),
                                             ('non-replenishable','Non-Replenishable'),
                                             ('non-stockupable','Non-stockupable'),
                                             ('obsolete','Obsolete'),
                                             ('planned-replenishment','Planned-Replenishment')
                                             ])
    drop_ship_status=fields.Selection([('drop-ship-disabled','Drop-Ship-Disabled'),
                                       ('drop-ship-disabled-by-buyer','Drop-Ship-Disabled-By-Buyer'),
                                       ('drop-ship-enabled','Drop-Ship-Enabled'),
                                       ('drop-ship-enabled-no-auto-pricing','Drop-Ship-Enabled-No-Auto-Pricing'),
                                       ('drop-ship-only','Drop-Ship-Only')
                                       ])
    out_of_stock_website_message=fields.Selection([('email-me-when-available','email-me-when-available'),
                                                   ('out-of-stock','out-of-stock'),
                                                   ('pre-order-ute','pre-order-ute'),
                                                   ('underlying-availability','underlying-availability')
                                                   ])
    child_display_per_page=fields.Selection([('independently_displayable','Independently'),('display_only_on_parent','Display Only On Parent')],default='display_only_on_parent')
    relation_type=fields.Selection([('Variation','Variation'),
                                    ('DisplaySet','DisplaySet'),
                                    ('Collection','Collection'),
                                    ('Accessory','Accessory'),
                                    ('Customized','Customized'),
                                    ('Part','Part'),
                                    ('Complements','Complements'),
                                    ('Piece','Piece'),
                                    ('Necessary','Necessary'),
                                    ('ReplacementPart','ReplacementPart'),
                                    ('Similar','Similar'),
                                    ('Episode','Episode'),
                                    ('Season','Season'),
                                    ('MerchantTitleAuthority','MerchantTitleAuthority'),
                                    ('Component','Component')
                                    ],default='Variation')
    fulfillment_by=fields.Selection([('MFN','Manufacturer Fulfillment Network')],string="Fulfillment By",default='MFN')
    product_extra_attributes=fields.Text("Extra Attributes")
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
    
    amazon_browse_node_id = fields.Many2one('amazon.browse.node.ept', string='Browse Node',copy=False)
    amazon_browse_node_id2 = fields.Many2one('amazon.browse.node.ept', string='Browse Node2',copy=False)

    product_id = fields.Many2one('product.product', string='Odoo Product',  required=True,ondelete="cascade")
    #ept_image_ids = fields.One2many('amazon.product.image.ept', 'ept_product_id', string='Images')
    fix_stock_type =  fields.Selection([('fix','Fix'),('percentage','Percentage')], string='Fix Stock Type')
    fix_stock_value = fields.Float(string='Fix Stock Value',digits=dp.get_precision("Product UoS"))
    asin_qty=fields.Integer("Number Of Items In One Package",default=1)
    exported_to_amazon=fields.Boolean("Exported In Amazon",default=False,copy=False)
    error_in_export_product=fields.Boolean("Error In Export Product",default=False,copy=False)
    error_in_export_image=fields.Boolean("Error In Export Image",default=False,copy=False)
    error_in_export_price=fields.Boolean("Error In Export Price",default=False,copy=False)    
    allow_package_qty=fields.Boolean("Allow Package Qty",default=False)
    launch_date=fields.Datetime("Launch Date",help="Controls when the product appears in search and browse on the Amazon website")
    release_date=fields.Datetime("Release Date",help="The date a product is released for sale")
    discontinue_date=fields.Datetime("Discontinue Date",help="The date a product is Discontinue for sale")
    title=fields.Char("Title",help="Short description of the product")
    designer=fields.Char("Designer",help="Designer of the product")
    long_description=fields.Text("Description",help="Long description of the product")
    package_weight=fields.Float("Package Weight",help="Weight of the package",digits=dp.get_precision("Stock Weight"))
    package_weight_uom=fields.Selection([('GR','GR'),('KG','KG'),('OZ','OZ'),('LB','LB'),('MG','MG')],default='KG',string="Package Weight Uom")
    shipping_weight=fields.Float("Shipping Weight",help="Weight of the product when packaged to ship",digits=dp.get_precision("Stock Weight"))
    shipping_weight_uom=fields.Selection([('GR','GR'),('KG','KG'),('OZ','OZ'),('LB','LB'),('MG','MG')],default='KG',string="Shipping Weight Uom")
    max_order_quantity=fields.Integer("Max Order Quantity",help="Maximum quantity of the product that a customer can order")
    is_gift_wrap_available=fields.Boolean("Is Gift Wrap Available ?",help="Indicates whether gift wrapping is available for the product")
    is_gift_message_available=fields.Boolean("Is Gift Message Available ?",help="Indicates whether gift messaging is available for the product")
    is_discontinued_by_manufacturer=fields.Boolean("Is Discontinued By Manufacturer ?",help="Indicates that the manufacturer has stopped making the item")
    max_aggregate_ship_quantity=fields.Integer("Max Aggregate Ship Quantity",help="The maximum number of the same item that can be shipped in the same package")
    standard_product_id_type=fields.Selection([('EAN','EAN'),('ISBN','ISBN'),('UPC','UPC'),('ASIN','ASIN'),('GCID','GCID'),('GTIN','GTIN'),('PZN','PZN')],string="Standard Product ID",default='ASIN',required=True)
    pzn_number=fields.Char("PZN Number")
    tax_code_id=fields.Many2one('amazon.tax.code.ept',string="Product Tax Code",copy=False)
    item_package_qty=fields.Integer(string="Item Package Quantity",help="Number of the same product contained within one package. For example, if you are selling\
a case of 10 packages of socks, ItemPackageQuantity would be 10.",default=1)
    bullet_point_ids=fields.One2many('amazon.product.bullet.description','amazon_product_id',string="Bullet Point Description")    
    serial_number_required=fields.Boolean("Serial Number Required",help="Indicates whether the product must have a serial number")
    legal_disclaimer=fields.Text(string="Legal Disclaimer",help="Any legal disclaimer needed with the product")
    mfr_part_number=fields.Char(string="Mfr Part Number",help="Part number provided by the original manufacturer")
    search_term_ids=fields.One2many('amazon.product.search.term','amazon_product_id',string="Search Term")    
    merchant_catalog_number=fields.Char(string="Supplier Product Code",compute="_calc_seller")
    manufacturer=fields.Char(string="Manufacturer",related='product_id.product_tmpl_id.product_brand_id.partner_id.name',readonly=True)
    brand=fields.Char(string="Brand",related='product_id.product_tmpl_id.product_brand_id.name',readonly=True)
    target_audience=fields.Selection([('male','Male'),('female','Female'),('unisex','Unisex')],string="Target Audience",default="unisex")
    last_feed_submission_id=fields.Char("Last Feed Submission Id",readonly=True,copy=False)
    seller_sku=fields.Char("Seller Sku")
    gtin_exemption_reason=fields.Selection([('bundle','Bundle'),('part','Part')],string="GtinExemptionReason")
    purchase_off_amazon_channel=fields.Selection([('advertise','advertise'),('exclude','Exclude')],string="OffAmazonChannel")
    purchase_on_amazon_channel=fields.Selection([('sell','Sell'),('advertise','Advertise'),('exclude','Exclude')],string="OnAmazonChannel")
    item_type_keyword=fields.Char("Item Type Keyword")
    prop=fields.Boolean("Prop65")
    cspia_warning_ids=fields.Many2many('amazon.cspia.warning.ept','amazon_cspia_warning_rel','product_id','warning_id',string="CPSIAWarning")
    cpsia_warning_description=fields.Text("CPSIAWarningDescription")
    in_store_purchase_channel=fields.Boolean("In Store Purchase Channel ?")
    online_purchase_channel=fields.Boolean("Online Purchase Channel ?")

    tsd_age_warning=fields.Selection([('not_suitable_under_36_months','not_suitable_under_36_months'),
                                      ('not_suitable_under_3_years_supervision','not_suitable_under_3_years_supervision'),
                                      ('not_suitable_under_4_years_supervision','not_suitable_under_4_years_supervision'),
                                      ('not_suitable_under_5_years_supervision','not_suitable_under_5_years_supervision'),
                                      ('not_suitable_under_6_years_supervision','not_suitable_under_6_years_supervision'),
                                      ('not_suitable_under_7_years_supervision','not_suitable_under_7_years_supervision'),
                                      ('not_suitable_under_8_years_supervision','not_suitable_under_8_years_supervision'),
                                      ('not_suitable_under_9_years_supervision','not_suitable_under_9_years_supervision'),
                                      ('not_suitable_under_10_years_supervision','not_suitable_under_10_years_supervision'),
                                      ('not_suitable_under_11_years_supervision','not_suitable_under_11_years_supervision'),
                                      ('not_suitable_under_12_years_supervision','not_suitable_under_12_years_supervision'),
                                      ('not_suitable_under_13_years_supervision','not_suitable_under_13_years_supervision'),
                                      ('not_suitable_under_14_years_supervision','not_suitable_under_14_years_supervision'),
                                      ('no_warning_applicable','no_warning_applicable')                                                                            
                                      ],default="no_warning_applicable",string="TSDAgeWarning")
    tsd_warning_ids=fields.Many2many('amazon.tsd.warning.ept','amazon_tsd_warning_rel','product_id','warning_id',string="TSDWarning")
    tsd_language_ids=fields.Many2many('amazon.tsd.language.ept','amazon_tsd_language_rel','product_id','language_id',string="TSDLanguage")
    payment_option_ids=fields.Many2many('amazon.payment.type.option.ept','amazon_payment_type_option_rel','product_id','payment_id',string="Other Payment Option")
    shipped_by_freight=fields.Boolean("Shipped By Freight")
    registerd_parameter=fields.Selection([("PrivateLabel",'PrivateLabel'),('Specialized','Specialized'),('NonConsumer','NonConsumer'),('PreConfigured','PreConfigured')],string="RegisteredParameter")
    attribute_ids=fields.One2many('amazon.attribute.line.ept','product_id',string="Attributes")
    log_count=fields.Integer("Log Count",compute="get_log_count")
    amazon_price_ept=fields.Float("Amazon Price",compute="get_amazon_price",digits=dp.get_precision("Product Price"))
    currency_id=fields.Many2one("res.currency",related="instance_id.pricelist_id.currency_id",store=False,readonly=True)
    _sql_constraints=[('amazon_instance_seller_sku_unique_constraint','unique(instance_id,seller_sku,fulfillment_by)',"Seller sku must be unique per instance & Fulfullment By")]

    @api.multi
    def list_of_logs(self):
        amazon_transaction_log_obj=self.env['amazon.transaction.log']
        model_id=amazon_transaction_log_obj.get_model_id('amazon.product.ept')
        records=amazon_transaction_log_obj.search([('model_id','=',model_id),('res_id','=',self.id),('job_id.request_feed_id','!=',False)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Feed Logs',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'amazon.transaction.log',
            'type': 'ir.actions.act_window',
                  }
        return action

    @api.multi
    def copy(self,default={}):
        default.update({'product_id':self.product_id.id})
        return super(amazon_product_ept,self).copy(default)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            recs = self.browse()
            if operator in positive_operators:
                recs = self.search(['|',('seller_sku','=',name),('default_code','=',name)]+ args, limit=limit)
                if not recs:
                    recs = self.search([('barcode','=',name)]+ args, limit=limit)
                    
            if not recs and operator not in expression.NEGATIVE_TERM_OPERATORS:
                # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                # on a database with thousands of matching products, due to the huge merge+unique needed for the
                # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                # Performing a quick memory merge of recs in Python will give much better performance
                recs = self.search(args + ['|',('seller_sku',operator,name),('default_code', operator, name)], limit=limit)
                if not limit or len(recs) < limit:
                    # we may underrun the limit because of dupes in the results, that's fine
                    limit2 = (limit - len(recs)) if limit else False
                    recs += self.search(args + [('name', operator, name), ('id', 'not in', recs.ids)], limit=limit2)
            elif not recs and operator in expression.NEGATIVE_TERM_OPERATORS:
                recs = self.search(args + ['&','|',('seller_sku',operator,name),('default_code', operator, name), ('name', operator, name)], limit=limit)
            if not recs and operator in positive_operators:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    recs = self.search(['|',('seller_sku','=',res.group(2)),('default_code','=', res.group(2))] + args, limit=limit)
        else:
            recs = self.search(args, limit=limit)
        
        return recs.name_get()
                        
    @api.multi
    def export_product_amazon(self,instance,amazon_products):
        amazon_process_log_obj=self.env['amazon.process.log.book']
        feed_submission_obj=self.env['feed.submission.history']
        proxy_data=instance.seller_id.get_proxy_server()
        mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)
        data=self.create_product_envelope(amazon_products,instance)
        try:
            results=mws_obj.submit_feed(data,'_POST_PRODUCT_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
        except Exception,e:
            raise Warning(str(e))
        results=results.parsed
        last_feed_submission_id=False
        if results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False):
            last_feed_submission_id=results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False)
            for amazon_product in amazon_products:
                amazon_product.write({'exported_to_amazon':True,'last_feed_submission_id':last_feed_submission_id,'error_in_export_product':False})
                amazon_product.child_variant_ids and amazon_product.child_variant_ids.write({'exported_to_amazon':True,'last_feed_submission_id':last_feed_submission_id,'error_in_export_product':False})
            feed=feed_submission_obj.search([('feed_result_id','=',last_feed_submission_id)],order="id desc",limit=1)
            amazon_process_log_obj.create({'instance_id':instance.id,
                                           'application':'product',
                                           'operation_type':'export',
                                           'request_feed_id':feed and feed.id or False
                                           })
        data=self.create_relation_dict(amazon_products, instance)
        if data:
            try:
                results=mws_obj.submit_feed(data,'_POST_PRODUCT_RELATIONSHIP_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
            except Exception,e:
                raise Warning(str(e)) 
        return True   
    @api.multi
    def create_relation_dict(self,amazon_products,instance):
        header="""<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>Relationship</MessageType>
            <PurgeAndReplace>false</PurgeAndReplace>
         """%(instance.merchant_id)
        message=1
        data=''
        for amazon_product in amazon_products:
            if not amazon_product.child_variant_ids:
                continue
            data="""<Message>
                    <MessageID>%s</MessageID>
                    <Relationship>
                    <ParentSKU>%s</ParentSKU>
                """%(message,amazon_product.seller_sku)
            for variant in amazon_product.child_variant_ids:
                data="%s %s"%(data,"""<Relation>
                                        <SKU>%s</SKU>
                                        <ChildDetailPageDisplay>%s</ChildDetailPageDisplay>
                                        <Type>%s</Type>
                                     </Relation>"""%(variant.seller_sku,amazon_product.child_display_per_page,amazon_product.relation_type))
            message=message+1
        if data:
            data="%s %s"%(data,"</Relationship></Message>")
            header="%s %s %s"%(header,data,"</AmazonEnvelope>")
            return header
        else:
            return False
    """Here we update the image's in amazon, instance wise whose exported_to_amazon field is true"""        

    @api.multi
    def create_image_dict(self,amazon_product,image_obj,message_information,message_id):
        seller_sku=amazon_product.seller_sku                                     
        amazon_image_type=image_obj.image_type or 'Main'
        amazon_image_url=image_obj.url
                        
        message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><ProductImage><SKU>%s</SKU><ImageType>%s</ImageType><ImageLocation>%s</ImageLocation></ProductImage></Message>""" % (message_id,seller_sku,amazon_image_type,amazon_image_url)
       
        return message_information

    @api.multi
    def update_images(self,instance):
        amazon_process_log_obj=self.env['amazon.process.log.book']
        feed_submission_obj=self.env['feed.submission.history']

        message_id=1 
        merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance.merchant_id)
        message_information = ''                                  
        for amazon_product in self:
            if not amazon_product.exported_to_amazon:
                continue
            for image_obj in amazon_product.product_id.ept_image_ids:
                message_information=self.create_image_dict(amazon_product, image_obj, message_information, message_id)
                message_id = message_id + 1
            for child_product in amazon_product.child_variant_ids:
                for image_obj in child_product.product_id.ept_image_ids:
                    message_information=self.create_image_dict(child_product, image_obj, message_information, message_id)
                    message_id = message_id + 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>"""+ merchant_string.encode("utf-8") +"""</Header><MessageType>ProductImage</MessageType>""" + message_information.encode("utf-8") + """</AmazonEnvelope>"""
            proxy_data=instance.seller_id.get_proxy_server()
            mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)        
            try:
                results=mws_obj.submit_feed(data,'_POST_PRODUCT_IMAGE_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
                results=results.parsed
                last_feed_submission_id=False
                if results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False):
                    last_feed_submission_id=results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False)
                    self.write({'error_in_export_image':False,'last_feed_submission_id':last_feed_submission_id})
                    feed=feed_submission_obj.search([('feed_result_id','=',last_feed_submission_id)],order="id desc",limit=1)
                    amazon_process_log_obj.create({'instance_id':instance.id,
                                                   'application':'image',
                                                   'operation_type':'export',
                                                   'request_feed_id':feed and feed.id or False
                                                   })

            except Exception,e:
                raise Warning(str(e))
        return True
    @api.multi
    def update_price_dict(self,instance,amazon_product,message_information,message_id):
        price = instance.pricelist_id.get_product_price(amazon_product.product_id,1.0,partner=False,uom_id=amazon_product.product_id.uom_id.id)
        price = price or 0.0
        seller_sku=amazon_product.seller_sku
        price_string = """<Message><MessageID>%(message_id)s</MessageID><Price><SKU>%(sku)s</SKU><StandardPrice currency="%(currency)s">%(price)s</StandardPrice></Price></Message>"""
        price_string = price_string % {'currency':instance.pricelist_id.currency_id.name,'message_id':message_id,'sku': seller_sku,'price':price}
        message_information+=price_string                    
        return message_information
    @api.multi
    def update_price(self,instance):        
        amazon_process_log_obj=self.env['amazon.process.log.book']
        feed_submission_obj=self.env['feed.submission.history']
        message_id=1 
        merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance.merchant_id)
        message_type = """<MessageType>Price</MessageType>"""
        message_information = ''                                  
        for amazon_product in self:
            message_information=self.update_price_dict(instance, amazon_product, message_information, message_id)
            message_id = message_id + 1
            for child_product in amazon_product.child_variant_ids:
                message_information=self.update_price_dict(instance, child_product, message_information, message_id)
                message_id = message_id + 1            
        if message_information:            
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>"""+merchant_string.encode("utf-8") +"""</Header>"""+message_type.encode("utf-8")+""""""+message_information.encode("utf-8") + """</AmazonEnvelope>"""
            proxy_data=instance.seller_id.get_proxy_server()
            mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)        
            try:
                results=mws_obj.submit_feed(data,'_POST_PRODUCT_PRICING_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
                results=results.parsed
                last_feed_submission_id=False
                if results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False):
                    last_feed_submission_id=results.get('FeedSubmissionInfo',{}).get('FeedSubmissionId',{}).get('value',False)
                    self.write({'last_feed_submission_id':last_feed_submission_id,'error_in_export_price':False})
                    feed=feed_submission_obj.search([('feed_result_id','=',last_feed_submission_id)],order="id desc",limit=1)
                    amazon_process_log_obj.create({'instance_id':instance.id,
                                                   'application':'price',
                                                   'operation_type':'export',
                                                   'request_feed_id':feed and feed.id or False
                                                   })

            except Exception,e:
                raise Warning(str(e))
        return True

    @api.multi
    def get_bullet_points(self,product):
        bullet_points=''
        for bullet in product.bullet_point_ids:                
            bullet_point="""<BulletPoint>%s</BulletPoint>"""%(cgi.escape(bullet.name).encode("utf-8"))
            bullet_points='%s %s'%(bullet_points,bullet_point)
        if product.bullet_point_ids:
            return bullet_points
    @api.multi
    def get_cpsia_warning(self,product):
        cpsia_warnings=''
        for warning in product.cspia_warning_ids:
            cpsia_warning="<CPSIAWarning>%s</CPSIAWarning>"%(warning.name)
            cpsia_warnings="%s %s"%(cpsia_warnings,cpsia_warning)
        if cpsia_warnings:
            return cpsia_warnings
    @api.multi
    def get_search_terms(self,product):
        search_terms=''
        for search_term in product.search_term_ids:
            search_term="""<SearchTerms>%s</SearchTerms>"""%(cgi.escape(search_term.name).encode("utf-8"))
            search_terms="%s %s"%(search_terms,search_term)
        return search_terms

    @api.multi
    def get_platinum_keywords(self,product):
        platinum_keywords=''
        for platinum_keyword in product.platinum_keyword_ids:
            pla_key="""<PlatinumKeywords>%s</PlatinumKeywords>"""%(cgi.escape(platinum_keyword.name).encode("utf-8"))
            platinum_keywords="%s %s"%(platinum_keywords,pla_key)
        return platinum_keywords
    @api.multi
    def get_used_for(self,product):
        used_fors=''
        for used_for in product.used_for_ids:
            us_f="""<PlatinumKeywords>%s</PlatinumKeywords>"""%(cgi.escape(used_for.name).encode("utf-8"))
            used_fors="%s %s"%(used_fors,us_f)
        return used_fors
    @api.multi
    def get_other_item_attributes(self,product):
        other_attributes=''
        for other_attribute in product.other_attribute_ids:
            other_att="""<OtherItemAttributes>%s</OtherItemAttributes>"""%(cgi.escape(other_attribute.name).encode("utf-8"))
            other_attributes="%s %s"%(other_attributes,other_att)
        return other_attributes
            
    @api.multi
    def get_target_audience(self,product):
        target_audiences=''
        for target_audience in product.target_audience_ids:
            targent_audi="""<TargetAudience>%s</TargetAudience>"""%(cgi.escape(target_audience.name).encode("utf-8"))
            target_audiences="%s %s"%(target_audiences,targent_audi)
        return target_audiences
    @api.multi
    def get_subject_content(self,product):
        subject_contents=''
        for subject_content in product.subject_content_ids:
            subject_con="""<SubjectContent>%s</SubjectContent>"""%(cgi.escape(subject_content.name).encode("utf-8"))
            subject_contents="%s %s"%(subject_contents,subject_con)
        return subject_contents
    @api.multi
    def get_promotion_keywords(self,product):
        promotion_keywords=''
        for promotion_keyword in product.promotion_keywords_ids:
            promotion_key="""<PromotionKeywords>%s</PromotionKeywords>"""%(cgi.escape(promotion_keyword.name).encode("utf-8"))
            promotion_keywords="%s %s"%(promotion_keywords,promotion_key)
        return promotion_keywords
             
    """If You Set PurgeAndReplace True Then System Will Replace All Products In Amazon"""
    @api.multi
    def get_header(self,instnace):
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>Product</MessageType>
            <PurgeAndReplace>false</PurgeAndReplace>
         """%(instnace.merchant_id)
         
    @api.multi
    def standard_product_code(self,product):
            product_code,product_type ='',''
            if product.standard_product_id_type in ['GCID','GTIN']:
                return """<SKU>%s</SKU>
                    """%(product.seller_sku)                           
            if product.standard_product_id_type=='ASIN':
                product_code,product_type = product.product_asin,'ASIN'
            elif product.standard_product_id_type=='ISBN':
                product_code,product_type = product.product_isbn, 'ISBN'
            elif product.standard_product_id_type=='EAN':
                product_code,product_type = product.barcode,'EAN'
            elif product.standard_product_id_type=='UPC':
                product_code,product_type = product.product_upc,'UPC'
            return """<SKU>%s</SKU>
                      <StandardProductID>
                          <Type>%s</Type>
                          <Value>%s</Value>
                      </StandardProductID>
                    """%(product.seller_sku,product_type,product_code)               

    @api.multi
    def get_lanuch_date(self,product):
        launch_date=product.launch_date and datetime.date.strftime(datetime.datetime.strptime(product.launch_date,"%Y-%m-%d %H:%M:%S"),"%Y-%m-%dT%H:%M:%S") or False       
        return launch_date and " <LaunchDate>%s</LaunchDate>"%(launch_date) or False 
    @api.multi
    def get_discontinue_date(self,product):
        discontinue_date=product.discontinue_date and datetime.date.strftime(datetime.datetime.strptime(product.discontinue_date,"%Y-%m-%d %H:%M:%S"),"%Y-%m-%dT%H:%M:%S") or False       
        return discontinue_date and " <DiscontinueDate>%s</DiscontinueDate>"%(discontinue_date) or False 

    @api.multi
    def get_release_date(self,product):
        release_date=product.release_date and datetime.date.strftime(datetime.datetime.strptime(product.release_date,"%Y-%m-%d %H:%M:%S"),"%Y-%m-%dT%H:%M:%S") or False
        return release_date and " <ReleaseDate>%s</ReleaseDate>"%(release_date) or False 
    @api.multi
    def get_condition(self,product):
        if product.condition:
            return """
                    <Condition>
                        <ConditionType>%s</ConditionType>
                    </Condition>
                    """%(product.condition)
        else:
            return False
    @api.multi
    def item_package_qty_and_no_of_items(self,product):
        item_pack=''
        if product.item_package_qty>0: 
            item_pack="%s %s"%(item_pack,"<ItemPackageQuantity>%s</ItemPackageQuantity>"%(product.item_package_qty))
        if product.asin_qty>0:
            item_pack="%s %s"%(item_pack,"<NumberOfItems>%s</NumberOfItems>"%(product.asin_qty))
        return item_pack
    @api.multi
    def get_description_data(self,product):
        data=[]
        if product.title:
            data.append("<Title>%s</Title>"%(cgi.escape(product.title).encode("utf-8")))
        else:
            data.append("<Title>%s</Title>"%(cgi.escape(product.name).encode("utf-8")))                
        product.brand and data.append("<Brand>%s</Brand>"%(cgi.escape(product.brand).encode("utf-8")))
        product.designer and data.append("<Designer>%s</Designer>"%(cgi.escape(product.designer).encode("utf-8"))) 
        description=product.long_description or product.description or False
        description and data.append("<Description>%s</Description>"%(cgi.escape(description).encode("utf-8")))

        product.bullet_point_ids and data.append(self.get_bullet_points(product))
        if product.package_weight > 0.0:
            data.append("""<PackageWeight unitOfMeasure='%s'>%s</PackageWeight>"""%(product.package_weight_uom,product.package_weight)) 
          
        if product.shipping_weight>0.0:
            data.append("""<ShippingWeight unitOfMeasure='%s'>%s</ShippingWeight>"""%(product.shipping_weight_uom,product.shipping_weight)) 
        product.merchant_catalog_number and data.append("<MerchantCatalogNumber>%s</MerchantCatalogNumber>"%(product.merchant_catalog_number)) 
        if product.max_order_quantity>0:
            data.append("<MaxOrderQuantity>%s</MaxOrderQuantity>"%(product.max_order_quantity)) 
        if product.serial_number_required:
            data.append("<SerialNumberRequired>true</SerialNumberRequired>") 
        if product.prop:
            data.append("<Prop65>true</Prop65>")   
        product.cspia_warning_ids and data.append(self.get_cpsia_warning(product))   
        product.cpsia_warning_description and data.append(cgi.escape(product.cpsia_warning_description))       
        product.legal_disclaimer and data.append("<LegalDisclaimer>%s</LegalDisclaimer>"%(cgi.escape(product.legal_disclaimer).encode("utf-8"))) 
        product.manufacturer and data.append("<Manufacturer>%s</Manufacturer>"%(cgi.escape(product.manufacturer).encode("utf-8"))) 
        product.mfr_part_number and data.append("<MfrPartNumber>%s</MfrPartNumber>"%(product.mfr_part_number))
        product.search_term_ids and data.append(self.get_search_terms(product))
        product.platinum_keyword_ids and data.append(self.get_platinum_keywords(product))
        product.is_memorabilia and data.append("<Memorabilia>true</Memorabilia>")
        product.is_auto_graphed and data.append("<Autographed>true</Autographed>")
        product.used_for_ids and data.append(self.get_used_for(product))
        product.item_type_keyword and data.append("<ItemType>%s</ItemType>"%(product.item_type_keyword)) 
        product.other_attribute_ids and data.append(self.get_other_item_attributes(product))
        product.target_audience_ids and data.append(self.get_target_audience(product))
        product.subject_content_ids and data.append(self.get_subject_content(product))
        data.append("<IsGiftWrapAvailable>%s</IsGiftWrapAvailable>"%(str(product.is_gift_wrap_available).lower()))
        data.append("<IsGiftMessageAvailable>%s</IsGiftMessageAvailable>"%(str(product.is_gift_message_available).lower()))
        product.promotion_keywords_ids and data.append(self.get_promotion_keywords(product))
        data.append("<IsDiscontinuedByManufacturer>%s</IsDiscontinuedByManufacturer>"%str(product.is_discontinued_by_manufacturer).lower())
        product.delivery_schedule_group and data.append("<DeliveryScheduleGroupID>%s</DeliveryScheduleGroupID>"%(product.delivery_schedule_group))
        product.delivery_channel and data.append("<DeliveryChannel>%s</DeliveryChannel>"%(product.delivery_channel))
        if product.purchase_off_amazon_channel:
            data.append("<PurchasingChannel>in_store</PurchasingChannel>")
        if product.purchase_on_amazon_channel:
            data.append("<PurchasingChannel>online</PurchasingChannel>")

        if product.max_aggregate_ship_quantity > 0:
            data.append("<MaxAggregateShipQuantity>%s</MaxAggregateShipQuantity>"%(product.max_aggregate_ship_quantity))
        product.customizable_template_name and data.append("<IsCustomizable>true</IsCustomizable><CustomizableTemplateName>%s</CustomizableTemplateName>"%(product.customizable_template_name))
        product.amazon_browse_node_id and data.append("<RecommendedBrowseNode>%s</RecommendedBrowseNode>"%(product.amazon_browse_node_id.ama_category_code))   
        product.amazon_browse_node_id2 and data.append("<RecommendedBrowseNode>%s</RecommendedBrowseNode>"%(product.amazon_browse_node_id2.ama_category_code))   
        product.merchant_shipping_group_name and data.append("<MerchantShippingGroupName>%s</MerchantShippingGroupName>"%(product.merchant_shipping_group_name))
        product.fedas_id and data.append("<FEDAS_ID>%s</FEDAS_ID>"%(product.fedas_id))
        if product.tsd_age_warning:
            data.append("<TSDAgeWarning>%s</TSDAgeWarning>"%(product.tsd_age_warning))            
        if product.tsd_warning_ids:
            data.append(self.get_tsd_warning(product))
        if product.tsd_language_ids:
            data.append(self.get_tsd_language(product))
        if product.payment_option_ids:
            data.append(self.get_payment_options(product))
        product.distribution_designation and data.append("<DistributionDesignation>%s</DistributionDesignation>"%(product.distribution_designation))
        product.promo_tag_type and data.append(self.get_promo_tag(product))
        #data.append(self.get_discovery_data(product))
        description_data=''
        for tag in data:
            description_data="%s %s"%(description_data,tag)        
        return "<DescriptionData>%s</DescriptionData>"%(str(description_data))

    @api.multi
    def get_discovery_data(self,product):
        discovery="<DiscoveryData> <Priority>%s</Priority>"%(product.priority or 1)
        if product.browse_exclusion: 
            discovery="%s %s"%(discovery,"<BrowseExclusion>true</BrowseExclusion>")
        if product.recommendation_exclusion:
            discovery="%s %s"%(discovery,"<RecommendationExclusion>true</RecommendationExclusion>")
        discovery="%s %s"%(discovery,"</DiscoveryData>")
        return discovery
    @api.multi
    def get_promo_tag(self,product):
        return """ 
            <PromoTag>
                <PromoTagType>%s</PromoTagType>
                <EffectiveFromDate>%s</EffectiveFromDate>
                <EffectiveThroughDate>%s</EffectiveThroughDate>
            </PromoTag>        
        """%(product.promo_tag_type,product.effective_from_date,product.effective_through_date)
    @api.multi
    def get_payment_options(self,product):
        payment_options=''
        for option in product.payment_option_ids:
            payment_option="<OptionalPaymentTypeExclusion>%s</OptionalPaymentTypeExclusion>"%(option.name)
            payment_options="%s %s"%(payment_options,payment_option)
        return payment_options
    @api.multi
    def get_tsd_language(self,product):
        tsd_languages=''
        for language in product.tsd_language_ids:
            tsd_language="<TSDLanguage>%s</TSDLanguage>"%(language.name)
            tsd_languages="%s %s"%(tsd_languages,tsd_language)
        return tsd_languages
    @api.multi
    def get_tsd_warning(self,product):
        tsd_warnings=''
        for warning in product.tsd_warning_ids:
            tsd_warning="<TSDWarning>%s</TSDWarning>"%(warning.name)
            tsd_warnings="%s %s"%(tsd_warnings,tsd_warning)
        return tsd_warnings
    @api.multi
    def get_tax_code(self,product):
        if product.tax_code_id:
            return """<ProductTaxCode>%s</ProductTaxCode>"""%(product.tax_code_id.name)
        elif product.instance_id.default_amazon_tax_code_id:
            return """<ProductTaxCode>%s</ProductTaxCode>"""%(product.instance_id.default_amazon_tax_code_id.name)
        else:
            return False
    @api.multi
    def get_related_product_type(self,product):
        return """<RelatedProductID>
                      <Type>%s</Type>
                      <Value>%s</Value>
                  </RelatedProductID>"""%(product.related_product_type,product.related_product_value)
    @api.multi
    def get_rebate(self,product):
        rebate_start_date=product.rebate_start_date and datetime.date.strftime(datetime.datetime.strptime(product.rebate_start_date,"%Y-%m-%d %H:%M:%S"),"%Y-%m-%dT%H:%M:%S") or False       
        rebate_end_date=product.rebate_end_date and datetime.date.strftime(datetime.datetime.strptime(product.rebate_end_date,"%Y-%m-%d %H:%M:%S"),"%Y-%m-%dT%H:%M:%S") or False       

        return """ 
            <Rebate>
                <RebateStartDate>%s</RebateStartDate>
                <RebateEndDate>%s</RebateEndDate>
                <RebateMessage>%s</RebateMessage>
                <RebateName>%s</RebateName>
            </Rebate>        
        """%(rebate_start_date,rebate_end_date,cgi.escape(product.rebate_message),product.rebate_name)
    @api.multi
    def get_message(self,message_id,product):
        message="""
                <MessageID>%s</MessageID>
                <OperationType>Update</OperationType>
                <Product>"""%(message_id)
        message="%s %s"%(message,self.standard_product_code(product))
        if product.standard_product_id_type=='GTIN':
            message="%s %s"%(message,"<GtinExemptionReason>%s</GtinExemptionReason>"%(product.gtin_exemption_reason))    
        if product.related_product_type:
            message="%s %s"%(message,self.get_related_product_type(product))
            
        tax_code=self.get_tax_code(product)
        if tax_code:
            message="%s %s"%(message,tax_code)
        luanch_date=self.get_lanuch_date(product)
        if luanch_date:
            message="%s %s"%(message,luanch_date)
        discontinue_date=self.get_discontinue_date(product)
        if discontinue_date:
            message="%s %s"%(message,discontinue_date)            
        release_date=self.get_release_date(product)
        if release_date:
            message="%s %s"%(message,release_date)
        if product.purchase_off_amazon_channel:
            message="%s %s"%(message,"<OffAmazonChannel>%s</OffAmazonChannel>"%(product.purchase_off_amazon_channel))
        if product.purchase_on_amazon_channel:
            message="%s %s"%(message,"<OnAmazonChannel>%s</OnAmazonChannel>"%(product.purchase_on_amazon_channel))

        condition=self.get_condition(product)
        if condition:
            message="%s %s"%(message,condition)
        if product.rebate_start_date:
            message="%s %s"%(message,self.get_rebate(product))
        message="%s %s"%(message,self.item_package_qty_and_no_of_items(product))
        if product.liquid_volume:
            message="%s %s"%(message,"<LiquidVolume unitOfMeasure='%s'>%s</LiquidVolume>"%(product.liquid_uom,product.liquid_volume))
        description_data=self.get_description_data(product)
        message="%s %s"%(message,description_data)
        if product.amazon_categ_id:            
            message="%s <ProductData>%s</ProductData>"%(message,self.get_product_data(product))
        if product.amazon_vendor_cost:
            message="%s <Amazon-Vendor-Only>%s</Amazon-Vendor-Only>"%(message,product.amazon_vendor_cost)
        if product.shipped_by_freight:
            message="%s <ShippedByFreight>true</ShippedByFreight>"%(message)
        amazon_only="<Amazon-Only>"
        if product.tier:
            amazon_only="%s %s"%(amazon_only,"<Tier>%s</Tier>"%(product.tier))
        if product.purchasing_category:
            amazon_only="%s %s"%(amazon_only,"<PurchasingCategory>%s</PurchasingCategory>"%(product.purchasing_category))
        if product.purchasing_sub_category:
            amazon_only="%s %s"%(amazon_only,"<PurchasingSubCategory>%s</PurchasingSubCategory>"%(product.purchasing_sub_category))
        if product.packaging_type:
            amazon_only="%s %s"%(amazon_only,"<PackagingType>%s</PackagingType>"%(product.packaging_type))
        if product.underlying_availability:
            amazon_only="%s %s"%(amazon_only,"<UnderlyingAvailability>%s</UnderlyingAvailability>"%(product.underlying_availability))
        if product.replenishment_category:
            amazon_only="%s %s"%(amazon_only,"<ReplenishmentCategory>%s</ReplenishmentCategory>"%(product.replenishment_category))
        if product.drop_ship_status:
            amazon_only="%s %s"%(amazon_only,"<DropShipStatus>%s</DropShipStatus>"%(product.drop_ship_status))
        if product.out_of_stock_website_message:
            amazon_only="%s %s"%(amazon_only,"<OutOfStockWebsiteMessage>%s</OutOfStockWebsiteMessage>"%(product.out_of_stock_website_message))
        if len(amazon_only)>14:
            amazon_only="%s %s"%(amazon_only,"</Amazon-Only>")   
            message="%s %s"%(message,amazon_only)
        if product.registerd_parameter:
            message="%s %s"%(message,"<RegisteredParameter>%s</RegisteredParameter>"%product.registerd_parameter)
        message="%s </Product>"%(message)
        return "<Message>%s</Message>"%(message)

    @api.multi
    def get_product_data(self,product):
        categ_dict={'ProductClothing':'Clothing'}
        dict_categ_sequence={}
        if product.child_categ_id:            
            category_structure=product.child_categ_id.category_structure
        else:
            category_structure=product.amazon_categ_id.category_structure
        for attribute_line in product.attribute_ids:            
            count=1
            for value in attribute_line.value_ids:  
                attribute_name=attribute_line.attribute_id.name       
                if attribute_line.attribute_id.max_occurs>1:
                    attribute_name="%s_%s"%(attribute_name,count)
                    count=count+1
                dict_categ_sequence.update({attribute_name:value.name})
            if attribute_line.uom_type_id:
                if attribute_line.attribute_id.max_occurs > 0:                
                    count=1
                    for value in attribute_line.value_ids:  
                        attribute_name="%s_%s_%s"%(attribute_line.uom_type,attribute_line.attribute_id.name,count)
                        dict_categ_sequence.update({attribute_name:attribute_line.value_id.name})   
                        count=count+1                 
                else:
                    attribute_name="%s_%s"%(attribute_line.uom_type,attribute_line.attribute_id.name)
                    dict_categ_sequence.update({attribute_name:attribute_line.value_id.name})
        try:
            category_structure=category_structure%DataDict(dict_categ_sequence)
            from lxml import etree
            doc=etree.XML(category_structure)
            elements=doc.xpath('//%s'%(categ_dict.get(product.amazon_categ_id.name,product.amazon_categ_id.name)))
            for root in elements:
                context = etree.iterwalk(root)
                for action, elem in context:
                    parent = elem.getparent()
                    if self.recursively_empty(elem):
                        parent.remove(elem)
            while True:
                flag=False
                elements=doc.xpath('//%s'%(categ_dict.get(product.amazon_categ_id.name,product.amazon_categ_id.name)))
                for element in elements:
                    context = etree.iterwalk(element)
                    for action, elem in context:
                        parent = elem.getparent()
                        for child in elem.iterchildren():
                            if child.getchildren():
                                continue
                            if not child.text.strip():
                                flag=True
                                elem.remove(child)  
                                                  
                if not flag:
                    break
            category_structure=etree.tostring(doc)
        except:
            raise Warning("Invalid Element")
        return category_structure

    @api.multi
    def recursively_empty(self,xml_element):
        if xml_element.text:
            return False
        return all((self.recursively_empty(xe) for xe in xml_element.iterchildren()))
    @api.multi
    def create_product_envelope(self,amazon_products,instance):
        message_id=0
        messages=''
        for product in amazon_products:
            message_id=message_id+1
            messages="%s %s"%(messages,self.get_message(message_id,product))
            for child_product in product.child_variant_ids:
                message_id=message_id+1
                messages="%s %s"%(messages,self.get_message(message_id,child_product))                
        header=self.get_header(instance)                    
        data="%s %s %s"%(header,messages,'</AmazonEnvelope>')
        return data.encode("utf-8")
    
    @api.multi
    def prepare_export_stock_level_dict(self,amazon_product,location_id,instance,message_information,message_id):
        stock = 0.00
        asin_qty = 1.00
        seller_sku=amazon_product.seller_sku
        
        if instance.stock_field:
            stock=self.get_stock(amazon_product,amazon_product.product_id.id,location_id,instance.stock_field.name)
        else:
            stock=self.get_stock(amazon_product,amazon_product.product_id.id,location_id)
        if amazon_product.allow_package_qty:
            asin_qty=amazon_product.asin_qty
            if asin_qty>0.0:
                stock = math.floor(stock / asin_qty)
            if stock < 1.00:
                stock = 0.00
        stock = int(stock)
        message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><Inventory><SKU>%s</SKU><Quantity>%s</Quantity></Inventory></Message>""" % (message_id,seller_sku,stock)        
        return message_information
    @api.multi
    def export_stock_levels(self,instance,product_ids=[]):
        if not product_ids:
            amazon_products=self.search([('exported_to_amazon','=',True),('instance_id','=',instance.id),('fulfillment_by','=','MFN')])
        else:
            amazon_products=self.browse(product_ids)
        if not amazon_products:
            return True
        location_id=instance.warehouse_id.lot_stock_id.id
        message_information = ''
        message_id = 1
        merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance.merchant_id)
        for amazon_product in amazon_products:
            message_information=self.prepare_export_stock_level_dict(amazon_product, location_id, instance, message_information, message_id)
            message_id = message_id + 1            
            for child_product in amazon_product.child_variant_ids:
                message_id = message_id + 1                
                message_information=self.prepare_export_stock_level_dict(child_product, location_id, instance, message_information, message_id)                
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>"""+ merchant_string.encode("utf-8") +"""</Header><MessageType>Inventory</MessageType>""" + message_information.encode("utf-8") + """</AmazonEnvelope>"""
            proxy_data=instance.seller_id.get_proxy_server()
            mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)        
            try:
                feed_result=mws_obj.submit_feed(data,'_POST_INVENTORY_AVAILABILITY_DATA_',marketplaceids=[instance.market_place_id],instance_id=instance.id)
                seller_id = self._context.get('seller_id',False)
                if seller_id:
                    result = feed_result.parsed
                    last_feed_submission_id = result.get( 'FeedSubmissionInfo', {} ).get( 'FeedSubmissionId', {} ).get( 'value', False )
                    vals = {'message':data, 'feed_result_id':last_feed_submission_id,
                            'feed_submit_date':time.strftime( "%Y-%m-%d %H:%M:%S" ),
                            'instance_id':instance.id, 'user_id':self._uid}
                    self.env['feed.submission.history'].create(vals, )
            except Exception,e:
                raise Warning(str(e))
        return True

    @api.multi
    def get_stock(self,amazon_product,odoo_product_id,location_id,stock_type='virtual_available'):
        actual_stock=0.0
        product=self.env['product.product'].with_context(location=location_id).browse(odoo_product_id)
        if stock_type == 'virtual_available':
            if product.virtual_available>0.0:
                actual_stock = product.virtual_available-product.incoming_qty
            else:
                actual_stock=0.0
        else:
            actual_stock = product.qty_available
        if actual_stock >= 1.00:
            if amazon_product.fix_stock_type=='fix':
                if amazon_product.fix_stock_value >=actual_stock:
                    return actual_stock
                else:
                    return amazon_product.fix_stock_value  
                              
            elif amazon_product.fix_stock_type == 'percentage':
                quantity = int(actual_stock * amazon_product.fix_stock_value)
                if quantity >= actual_stock:
                    return actual_stock
                else:
                    return quantity
        return actual_stock         
