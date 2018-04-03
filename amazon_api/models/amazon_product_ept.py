# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products,Feeds
from odoo.addons.amazon_ept_v10.models.product import DataDict
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, cgi
from StringIO import StringIO
from lxml import etree


class AmazonProduct(models.Model):
    _inherit = "amazon.product.ept"

    seller_sku = fields.Char(related='product_id.default_code', store=False)
    product_upc = fields.Char(related='product_id.barcode', store=False, string=u'UPC')

    @api.multi
    def export_stock_levels(self, instance, product_ids=[]):
        if not product_ids:
            amazon_products = self.search(
                [('exported_to_amazon', '=', True), ('instance_id', '=', instance.id), ('fulfillment_by', '=', 'MFN')])
        else:
            amazon_products = self.browse(product_ids)
        if not amazon_products:
            return True

        templates = []
        for amazon_product in amazon_products:
            if amazon_product.product_tmpl_id not in templates:
                templates.append(amazon_product.product_tmpl_id)
        if len(templates) == 1:
            template = templates[0]
        else:
            raise UserError(u'len(templates) != 1')

        location_id = instance.warehouse_id.lot_stock_id.id
        message_information = ''
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        for amazon_product in amazon_products:
            message_information = self.prepare_export_stock_level_dict(amazon_product, location_id, instance,
                                                                       message_information, message_id)
            message_id = message_id + 1
            for child_product in amazon_product.child_variant_ids:
                message_id = message_id + 1
                message_information = self.prepare_export_stock_level_dict(child_product, location_id, instance,
                                                                           message_information, message_id)
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string.encode(
                "utf-8") + """</Header><MessageType>Inventory</MessageType>""" + message_information.encode(
                "utf-8") + """</AmazonEnvelope>"""
            proxy_data = instance.seller_id.get_proxy_server()
            mws_obj = Feeds(access_key=str(instance.access_key), secret_key=str(instance.secret_key),
                            account_id=str(instance.merchant_id),
                            region=instance.country_id.amazon_marketplace_code or instance.country_id.code,
                            proxies=proxy_data)
            try:
                feed_result = mws_obj.submit_feed(data, '_POST_INVENTORY_AVAILABILITY_DATA_',
                                                  marketplaceids=[instance.market_place_id], instance_id=instance.id,
                                                  model_name='product.template', record_id=template.id)
                result = feed_result.parsed
                last_feed_submission_id = result.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get(
                    'value', False)
                template.stock_feed_id = last_feed_submission_id
                seller_id = self._context.get('seller_id', False)
                if seller_id:
                    result = feed_result.parsed
                    last_feed_submission_id = result.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get(
                        'value', False)
                    template.stock_feed_id = last_feed_submission_id
                    vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                            'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                            'instance_id': instance.id, 'user_id': self._uid}
                    self.env['feed.submission.history'].create(vals, )
            except Exception, e:
                raise Warning(str(e))
        return True

    @api.multi
    def create_image_dict(self, product, message_information, message_id):
        '''构建上传图片xml'''
        message_template = """
            <Message>
                <MessageID>%s</MessageID>
                <OperationType>Update</OperationType>
                <ProductImage>
                    <SKU>%s</SKU>
                    <ImageType>%s</ImageType>
                    <ImageLocation>%s</ImageLocation>
                </ProductImage>
            </Message>"""
        seller_sku = product.default_code
        main_images = product.main_images
        if main_images:
            main_image = main_images[0]
            message_information += message_template % (message_id, seller_sku, 'Main', main_image.oss2_url)
            message_id += 1
        pt_num = 1
        for image in product.images:
            message_information += message_template % (message_id, seller_sku, 'PT' + str(pt_num), image.oss2_url)
            pt_num += 1
            message_id += 1
        return {
            'message_information': message_information,
            'message_id': message_id,
        }

    @api.multi
    def update_images(self, shop_template):
        if len(shop_template) != 1:
            raise UserError(u'len(shop_template) != 1')
        instance = shop_template.product_owner.amazon_instance_id
        amazon_process_log_obj = self.env['amazon.process.log.book']
        feed_submission_obj = self.env['feed.submission.history']
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        message_information = ''
        for shop_product in shop_template.product_variant_ids:
            xml_info = self.create_image_dict(shop_product, message_information, message_id)
            message_information = xml_info['message_information']
            message_id = xml_info['message_id']
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string.encode(
                "utf-8") + """</Header><MessageType>ProductImage</MessageType>""" + message_information.encode(
                "utf-8") + """</AmazonEnvelope>"""
            proxy_data = instance.seller_id.get_proxy_server()
            mws_obj = Feeds(access_key=str(instance.access_key), secret_key=str(instance.secret_key),
                            account_id=str(instance.merchant_id),
                            region=instance.country_id.amazon_marketplace_code or instance.country_id.code,
                            proxies=proxy_data)
            try:
                results = mws_obj.submit_feed(data, '_POST_PRODUCT_IMAGE_DATA_',
                                              marketplaceids=[instance.market_place_id], instance_id=instance.id,
                                              model_name='product.template', record_id=shop_template.id)
                results = results.parsed
                last_feed_submission_id = False
                if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
                    last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get(
                        'value', False)
                    shop_template.image_feed_id = last_feed_submission_id
                    self.write({'error_in_export_image': False, 'last_feed_submission_id': last_feed_submission_id})
                    feed = feed_submission_obj.search([('feed_result_id', '=', last_feed_submission_id)],
                                                      order="id desc", limit=1)
                    amazon_process_log_obj.create({'instance_id': instance.id,
                                                   'application': 'image',
                                                   'operation_type': 'export',
                                                   'request_feed_id': feed and feed.id or False
                                                   })
            except Exception, e:
                raise Warning(str(e))
        return True

    @api.multi
    def update_price(self, instance):
        templates = []
        for amazon_product in self:
            if amazon_product.product_tmpl_id not in templates:
                templates.append(amazon_product.product_tmpl_id)
        if len(templates) == 1:
            template = templates[0]
        else:
            raise UserError(u'len(templates) != 1')

        amazon_process_log_obj = self.env['amazon.process.log.book']
        feed_submission_obj = self.env['feed.submission.history']
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        message_type = """<MessageType>Price</MessageType>"""
        message_information = ''
        for amazon_product in self:
            message_information = self.update_price_dict(instance, amazon_product, message_information, message_id)
            message_id = message_id + 1
            for child_product in amazon_product.child_variant_ids:
                message_information = self.update_price_dict(instance, child_product, message_information, message_id)
                message_id = message_id + 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string.encode(
                "utf-8") + """</Header>""" + message_type.encode("utf-8") + """""" + message_information.encode(
                "utf-8") + """</AmazonEnvelope>"""
            proxy_data = instance.seller_id.get_proxy_server()
            mws_obj = Feeds(access_key=str(instance.access_key), secret_key=str(instance.secret_key),
                            account_id=str(instance.merchant_id),
                            region=instance.country_id.amazon_marketplace_code or instance.country_id.code,
                            proxies=proxy_data)
            try:
                results = mws_obj.submit_feed(data, '_POST_PRODUCT_PRICING_DATA_',
                                              marketplaceids=[instance.market_place_id], instance_id=instance.id,
                                              model_name='product.template', record_id=template.id)
                results = results.parsed
                last_feed_submission_id = False
                if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
                    last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get(
                        'value', False)
                    template.price_feed_id = last_feed_submission_id
                    self.write({'last_feed_submission_id': last_feed_submission_id, 'error_in_export_price': False})
                    feed = feed_submission_obj.search([('feed_result_id', '=', last_feed_submission_id)],
                                                      order="id desc", limit=1)
                    amazon_process_log_obj.create({'instance_id': instance.id,
                                                   'application': 'price',
                                                   'operation_type': 'export',
                                                   'request_feed_id': feed and feed.id or False
                                                   })
            except Exception, e:
                raise Warning(str(e))
        return True

    @api.multi
    def export_product_amazon(self, instance, amazon_products):
        templates = []
        for amazon_product in amazon_products:
            if amazon_product.product_tmpl_id not in templates:
                templates.append(amazon_product.product_tmpl_id)
        if len(templates) == 1:
            template = templates[0]
        else:
            raise UserError(u'len(templates) != 1')

        amazon_process_log_obj = self.env['amazon.process.log.book']
        feed_submission_obj = self.env['feed.submission.history']
        proxy_data = instance.seller_id.get_proxy_server()
        mws_obj = Feeds(access_key=str(instance.access_key), secret_key=str(instance.secret_key),
                        account_id=str(instance.merchant_id),
                        region=instance.country_id.amazon_marketplace_code or instance.country_id.code,
                        proxies=proxy_data)
        data = self.create_product_envelope(amazon_products, instance)
        try:
            results = mws_obj.submit_feed(data, '_POST_PRODUCT_DATA_', marketplaceids=[instance.market_place_id],
                                          instance_id=instance.id, model_name='product.template', record_id=template.id)
        except Exception, e:
            raise Warning(str(e))
        results = results.parsed
        last_feed_submission_id = False
        if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
            last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value',
                                                                                                            False)
            template.product_feed_id = last_feed_submission_id
            for amazon_product in amazon_products:
                amazon_product.write({'exported_to_amazon': True, 'last_feed_submission_id': last_feed_submission_id,
                                      'error_in_export_product': False})
                amazon_product.child_variant_ids and amazon_product.child_variant_ids.write(
                    {'exported_to_amazon': True, 'last_feed_submission_id': last_feed_submission_id,
                     'error_in_export_product': False})
            feed = feed_submission_obj.search([('feed_result_id', '=', last_feed_submission_id)], order="id desc",
                                              limit=1)
            amazon_process_log_obj.create({'instance_id': instance.id,
                                           'application': 'product',
                                           'operation_type': 'export',
                                           'request_feed_id': feed and feed.id or False
                                           })
        data = self.create_relation_dict(amazon_products, instance)
        if data:
            try:
                results = mws_obj.submit_feed(data, '_POST_PRODUCT_RELATIONSHIP_DATA_',
                                              marketplaceids=[instance.market_place_id], instance_id=instance.id,
                                              model_name='product.template', record_id=template.id)
                last_feed_submission_id = results.parsed.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {})\
                    .get('value', False)
                template.relation_feed_id = last_feed_submission_id
            except Exception, e:
                raise Warning(str(e))
        return True

    @api.multi
    def update_price_dict(self, instance, amazon_product, message_information, message_id):
        '''取的价格、币种不是从价格表中取得'''
        if amazon_product.variation_data == 'parent':
            return message_information
        price = amazon_product.product_id.shop_price
        instance_partner = self.env['res.partner'].search([('amazon_instance_id', '=', instance.id)])
        if instance_partner and len(instance_partner) == 1:
            currency = instance_partner.shop_currency.name
            country = instance_partner.country_id
        else:
            raise UserError(u'instance_partner error!')
        shipping_cny = 0
        for freight in amazon_product.freight_line:
            if freight.country_id == country:
                shipping_cny = freight.cny_amount
                break
        shipping = shipping_cny * instance_partner.shop_currency.rate
        price += shipping
        price = round(price, 2)
        seller_sku = amazon_product.seller_sku
        price_string = """<Message><MessageID>%(message_id)s</MessageID><OperationType>Update</OperationType><Price><SKU>%(sku)s</SKU><StandardPrice currency="%(currency)s">%(price)s</StandardPrice></Price></Message>"""
        price_string = price_string % {'currency': currency, 'message_id': message_id, 'sku': seller_sku,
                                       'price': price}
        message_information += price_string
        return message_information

    @api.multi
    def prepare_export_stock_level_dict(self, amazon_product, location_id, instance, message_information,
                                        message_id):
        seller_sku = amazon_product.seller_sku
        qty = amazon_product.master_product.qty_available
        deal_days = amazon_product.product_id.product_tmpl_id.deal_days
        message_information += """
            <Message>
                <MessageID>%s</MessageID>
                <OperationType>Update</OperationType>
                <Inventory>
                    <SKU>%s</SKU>
                    <FulfillmentCenterID>DEFAULT</FulfillmentCenterID>
                    <Quantity>%s</Quantity>
                    <FulfillmentLatency>%s</FulfillmentLatency>
                    <SwitchFulfillmentTo>MFN</SwitchFulfillmentTo>
                </Inventory>
            </Message>""" % (message_id, seller_sku, str(int(qty)), str(deal_days))
        return message_information

    # @api.multi
    # def unlink(self):
    #     '''亚马逊产品与odoo的店铺产品是一一对应的关系 若删除亚马逊产品 odoo的店铺产品也要删除'''
    #     for record in self:
    #         if record.product_id:
    #             record.product_id.unlink()

    # @api.multi
    # def get_product_data(self, product):
    #     '''多了一条属性信息 上传的时候会有warning'''
    #     result = super(AmazonProduct, self).get_product_data(product)
    #     doc = etree.XML(result)
    #     elements = doc.xpath('//ProductType')
    #     if len(elements) == 1:
    #         element = elements[0]
    #         categ_name = product.amazon_categ_id.name
    #         result = "<%s> %s </%s>" % (categ_name, etree.tostring(element), categ_name)
    #     return result

    @api.multi
    def get_product_data(self, product):
        amazon_product = product
        odoo_product = amazon_product.product_id
        template = odoo_product.product_tmpl_id
        dict_categ_sequence = {}
        if product.child_categ_id:
            category_structure = odoo_product.child_categ_id.category_structure
        else:
            category_structure = odoo_product.parent_categ_id.category_structure
        if template.variation_theme_id:
            dict_categ_sequence.update({
                'VariationTheme': template.variation_theme_id.name,
                'Parentage': odoo_product.variation_data,
            })
        else:
            dict_categ_sequence.update({
                'Parentage': odoo_product.variation_data,
            })
        for attribute_value in odoo_product.attribute_value_ids:
            dict_categ_sequence.update({
                attribute_value.attribute_id.amazon_name: attribute_value.name,
            })
        try:
            category_structure = category_structure % DataDict(dict_categ_sequence)
            doc = etree.XML(category_structure)
            elements = doc.xpath('//%s' % (odoo_product.parent_categ_id.name))
            for root in elements:
                context = etree.iterwalk(root)
                for action, elem in context:
                    parent = elem.getparent()
                    if self.recursively_empty(elem):
                        parent.remove(elem)
            while True:
                flag = False
                elements = doc.xpath(
                    '//%s' % (odoo_product.parent_categ_id.name))
                for element in elements:
                    context = etree.iterwalk(element)
                    for action, elem in context:
                        parent = elem.getparent()
                        for child in elem.iterchildren():
                            if child.getchildren():
                                continue
                            if not child.text.strip():
                                flag = True
                                elem.remove(child)

                if not flag:
                    break
            category_structure = etree.tostring(doc)
        except:
            raise Warning("Invalid Element")
        doc = etree.XML(category_structure)
        elements = doc.xpath('//ProductType')
        if len(elements) == 1:
            element = elements[0]
            categ_name = odoo_product.parent_categ_id.name
            category_structure = "<%s> %s </%s>" % (categ_name, etree.tostring(element), categ_name)
        return category_structure

    @api.multi
    def create_relation_dict(self, amazon_products, instance):
        '''上传关系时，xml多了这条信息会引起警告
           <ChildDetailPageDisplay>display_only_on_parent</ChildDetailPageDisplay>'''
        header = """<?xml version="1.0"?>
                <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
                <Header>
                    <DocumentVersion>1.01</DocumentVersion>
                    <MerchantIdentifier>%s</MerchantIdentifier>
                </Header>
                <MessageType>Relationship</MessageType>
                <PurgeAndReplace>false</PurgeAndReplace>
             """ % (instance.merchant_id)
        message = 1
        data = ''
        for amazon_product in amazon_products:
            if not amazon_product.child_variant_ids:
                continue
            data = """<Message>
                        <MessageID>%s</MessageID>
                        <Relationship>
                        <ParentSKU>%s</ParentSKU>
                    """ % (message, amazon_product.seller_sku)
            for variant in amazon_product.child_variant_ids:
                data = "%s %s" % (data, """<Relation>
                                            <SKU>%s</SKU>
                                            <Type>%s</Type>
                                         </Relation>""" % ( variant.seller_sku, amazon_product.relation_type)
                                  )
            message = message + 1
        if data:
            data = "%s %s" % (data, "</Relationship></Message>")
            header = "%s %s %s" % (header, data, "</AmazonEnvelope>")
            return header
        else:
            return False


    @api.multi
    def get_description_data(self, product):
        data = []
        #目前只上传英文 其他后期完善
        odoo_product = product.product_id
        data.append("<Title>%s</Title>" % (cgi.escape(odoo_product.product_title_english).encode("utf-8")))
        description = odoo_product.product_description_english
        keyword = odoo_product.product_keyword_english

        product.brand and data.append("<Brand>%s</Brand>" % (cgi.escape(product.brand).encode("utf-8")))
        product.designer and data.append("<Designer>%s</Designer>" % (cgi.escape(product.designer).encode("utf-8")))
        description and data.append("<Description>%s</Description>" % (cgi.escape(description).encode("utf-8")))
        product.bullet_point_ids and data.append(self.get_bullet_points(product))
        if product.package_weight > 0.0:
            data.append("""<PackageWeight unitOfMeasure='%s'>%s</PackageWeight>""" % (
            product.package_weight_uom, product.package_weight))
        if product.shipping_weight > 0.0:
            data.append("""<ShippingWeight unitOfMeasure='%s'>%s</ShippingWeight>""" % (
            product.shipping_weight_uom, product.shipping_weight))
        product.merchant_catalog_number and data.append(
            "<MerchantCatalogNumber>%s</MerchantCatalogNumber>" % (product.merchant_catalog_number))
        if product.max_order_quantity > 0:
            data.append("<MaxOrderQuantity>%s</MaxOrderQuantity>" % (product.max_order_quantity))
        if product.serial_number_required:
            data.append("<SerialNumberRequired>true</SerialNumberRequired>")
        if product.prop:
            data.append("<Prop65>true</Prop65>")
        product.cspia_warning_ids and data.append(self.get_cpsia_warning(product))
        product.cpsia_warning_description and data.append(cgi.escape(product.cpsia_warning_description))
        product.legal_disclaimer and data.append(
            "<LegalDisclaimer>%s</LegalDisclaimer>" % (cgi.escape(product.legal_disclaimer).encode("utf-8")))
        product.manufacturer and data.append(
            "<Manufacturer>%s</Manufacturer>" % (cgi.escape(product.manufacturer).encode("utf-8")))
        product.mfr_part_number and data.append("<MfrPartNumber>%s</MfrPartNumber>" % (product.mfr_part_number))
        product.search_term_ids and data.append(self.get_search_terms(product))
        product.platinum_keyword_ids and data.append(self.get_platinum_keywords(product))
        product.is_memorabilia and data.append("<Memorabilia>true</Memorabilia>")
        product.is_auto_graphed and data.append("<Autographed>true</Autographed>")
        product.used_for_ids and data.append(self.get_used_for(product))
        product.item_type_keyword and data.append("<ItemType>%s</ItemType>" % (keyword))
        product.other_attribute_ids and data.append(self.get_other_item_attributes(product))
        product.target_audience_ids and data.append(self.get_target_audience(product))
        product.subject_content_ids and data.append(self.get_subject_content(product))
        data.append("<IsGiftWrapAvailable>%s</IsGiftWrapAvailable>" % (str(product.is_gift_wrap_available).lower()))
        data.append(
            "<IsGiftMessageAvailable>%s</IsGiftMessageAvailable>" % (str(product.is_gift_message_available).lower()))
        product.promotion_keywords_ids and data.append(self.get_promotion_keywords(product))
        data.append("<IsDiscontinuedByManufacturer>%s</IsDiscontinuedByManufacturer>" % str(
            product.is_discontinued_by_manufacturer).lower())
        product.delivery_schedule_group and data.append(
            "<DeliveryScheduleGroupID>%s</DeliveryScheduleGroupID>" % (product.delivery_schedule_group))
        product.delivery_channel and data.append("<DeliveryChannel>%s</DeliveryChannel>" % (product.delivery_channel))
        if product.purchase_off_amazon_channel:
            data.append("<PurchasingChannel>in_store</PurchasingChannel>")
        if product.purchase_on_amazon_channel:
            data.append("<PurchasingChannel>online</PurchasingChannel>")

        if product.max_aggregate_ship_quantity > 0:
            data.append("<MaxAggregateShipQuantity>%s</MaxAggregateShipQuantity>" % (product.max_aggregate_ship_quantity))
        product.customizable_template_name and data.append(
            "<IsCustomizable>true</IsCustomizable><CustomizableTemplateName>%s</CustomizableTemplateName>" % (
            product.customizable_template_name))
        product.amazon_browse_node_id and data.append(
            "<RecommendedBrowseNode>%s</RecommendedBrowseNode>" % (odoo_product.browse_node_id.ama_category_code))
        # product.amazon_browse_node_id2 and data.append(
        #     "<RecommendedBrowseNode>%s</RecommendedBrowseNode>" % (product.amazon_browse_node_id2.ama_category_code))
        product.merchant_shipping_group_name and data.append(
            "<MerchantShippingGroupName>%s</MerchantShippingGroupName>" % (product.merchant_shipping_group_name))
        product.fedas_id and data.append("<FEDAS_ID>%s</FEDAS_ID>" % (product.fedas_id))
        if product.tsd_age_warning:
            data.append("<TSDAgeWarning>%s</TSDAgeWarning>" % (product.tsd_age_warning))
        if product.tsd_warning_ids:
            data.append(self.get_tsd_warning(product))
        if product.tsd_language_ids:
            data.append(self.get_tsd_language(product))
        if product.payment_option_ids:
            data.append(self.get_payment_options(product))
        product.distribution_designation and data.append(
            "<DistributionDesignation>%s</DistributionDesignation>" % (product.distribution_designation))
        product.promo_tag_type and data.append(self.get_promo_tag(product))
        # data.append(self.get_discovery_data(product))
        description_data = ''
        for tag in data:
            description_data = "%s %s" % (description_data, tag)
        return "<DescriptionData>%s</DescriptionData>" % (str(description_data))