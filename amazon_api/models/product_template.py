# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports
from odoo.exceptions import UserError
import time, base64, uuid, csv, urllib2
from StringIO import StringIO
from odoo.osv import osv

class ProductTemplate(models.Model):
    _inherit = "product.template"

    default_code = fields.Char(compute='', inverse='')
    upc_code = fields.Char(string=u'UPC编码')
    parent_sku = fields.Char(compute='compute_parent_sku', store=False, required=False)
    attribute_ids = fields.Char(compute='_get_attribute_ids')
    main_image_url = fields.Char(compute='get_main_image_url', string=u'主图url')
    main_image = fields.Binary(compute='get_main_image', string=u'主图', store=False)

    parent_categ_id = fields.Many2one('amazon.category.ept', compute='_get_parent_child_categ', store=False)
    child_categ_id = fields.Many2one('amazon.category.ept', compute='_get_parent_child_categ', store=False)

    main_images = fields.One2many('product.image', 'product_tmpl_id', string=u'主图', domain=[('tmpl_main', '=', True)])
    minor_images = fields.One2many('product.image', 'product_tmpl_id', string=u'主图', domain=[('tmpl_main', '=', False)])



    @api.multi
    def _get_parent_child_categ(self):
        '''get parent and child amazon category'''
        for template in self:
            categ = template.amazon_categ_id
            if categ:
                if categ.parent_id:
                    template.parent_categ_id = categ.parent_id.id
                    template.child_categ_id = categ.id
                else:
                    template.parent_categ_id = categ.id
                    template.child_categ_id = False

    @api.multi
    def get_main_image(self):
        for template in self:
            if template.main_image_url:
                template.main_image = base64.encodestring(urllib2.urlopen(template.main_image_url, timeout=3).read())

    @api.depends('attribute_line_ids')
    def _get_attribute_ids(self):
        for template in self:
            attribute_ids = []
            for attribute_line in template.attribute_line_ids:
                attribute_ids.append(attribute_line.attribute_id.id)
            template.attribute_ids = str(attribute_ids)

    @api.multi
    def get_main_image_url(self):
        for template in self:
            main_images = template.main_images
            if len(main_images) == 1:
                template.main_image_url = template.main_images[0].oss2_url
            elif len(main_images) == 0:
                template.main_image_url = '/web/static/src/img/placeholder.png'
            else:
                template.main_image_url = ''

    @api.multi
    def compute_parent_sku(self):
        for record in self:
            if record.variation_theme_id:
                for product in record.product_variant_ids:
                    if not product.attribute_value_ids:
                        record.parent_sku = product.default_code
            else:
                record.parent_sku = ''

    @api.multi
    def check_categ_attribute(self):
        '''校验该模板是否可以填写这些属性'''
        for template in self:
            attrs = template.parent_categ_id.odoo_attribute_ids.ids
            attrs += template.child_categ_id.odoo_attribute_ids.ids
            attrs = set(attrs)
            for attr_line in template.attribute_line_ids:
                if attr_line.attribute_id.id not in attrs:
                    raise UserError(u'该模板没有%s属性!' % (attr_line.attribute_id.name))

    @api.model
    def handle_history_data(self):
        '''处理历史数据。对供应商、经销商、店铺产品单独设置一个字段b2b_type进行区分'''
        templates = self.env['product.template'].sudo().search([])
        for template in templates:
            if template.master_product:
                if template.product_owner.type == 'shop':
                    b2b_type = 'shop'
                else:
                    b2b_type = 'seller'
            else:
                b2b_type = 'supplier'
            template.with_context(collection_mark='collected').b2b_type = b2b_type

    @api.model
    def create(self, val):
        template = super(ProductTemplate, self).create(val)
        return template

    @api.multi
    def write(self, val):
        result = super(ProductTemplate, self).write(val)
        return result

    @api.multi
    def sync_supplier_tmpl_images(self):
        '''复制供应商产品图片至该产品'''
        if len(self) == 0:
            return
        image_obj = self.env['product.image']
        for child_tmpl in self:
            supplier_tmpl = child_tmpl.master_product
            if not supplier_tmpl:
                continue
            supplier_images = supplier_tmpl.images
            #创建经销商产品和店铺产品图片
            for supplier_image in supplier_images:
                child_image = image_obj.search([
                    ('product_tmpl_id', '=', child_tmpl.id),
                    ('parent_id', '=', supplier_image.id)], limit=1)
                if not child_image:
                    child_image = image_obj.create({
                        'name': supplier_image.name,
                        'oss2_url': supplier_image.oss2_url,
                        'product_tmpl_id': child_tmpl.id,
                        'tmpl_main': supplier_image.tmpl_main,
                        'parent_id': supplier_image.id,
                    })
            #添加产品 、图片映射关系
            for child_product in child_tmpl.product_variant_ids:
                supplier_main_images = child_product.master_product.main_images
                if len(supplier_main_images) > 1:
                    raise UserError(u'每个变体只能有一个主图！')
                if supplier_main_images:
                    child_main_image = image_obj.search([
                        ('product_tmpl_id', '=', child_tmpl.id),
                        ('parent_id', '=', supplier_main_images.id),], limit=1)
                    child_product.main_images = [(6, 0, child_main_image.ids)]
                else:
                    child_product.main_images = [(6, 0, [])]
                supplier_other_images = child_product.master_product.images
                if supplier_other_images:
                    child_other_images = image_obj.search([
                        ('product_tmpl_id', '=', child_tmpl.id),
                        ('parent_id', 'in', supplier_other_images.ids), ])
                    child_product.images = [(6, 0, child_other_images.ids)]
                else:
                    child_product.images = [(6, 0, [])]
        return

    @api.multi
    def btn_shop_multi_tmpl_upload(self, cr, uid, active_ids):
        '''上传变体'''
        for id in active_ids:
            template = self.browse(id)
            instance = template.product_owner.amazon_instance_id
            amazon_products = self.env['amazon.product.ept'].search([
                ('product_tmpl_id', '=', template.id),
                ('variation_data', '=', 'parent'),
            ])
            if not amazon_products:
                amazon_products = self.env['amazon.product.ept'].search([
                    ('product_tmpl_id', '=', template.id),
                    ('variation_data', '=', False),
                ])
            if not amazon_products:
                raise UserError(u'amazon_products is Null!')
            self.env['amazon.product.ept'].export_product_amazon(instance, amazon_products)
            if len(template.product_variant_ids) == 1:
                template.write({
                    'product_status': 'updating',
                    'relation_update': 'done',
                })
            else:
                template.write({
                    'product_status': 'updating',
                    'relation_update': 'updating',
                })

    @api.multi
    def view_upload_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': u'上传记录',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'feed.submission.history',
            'views': [(self.env.ref('amazon_ept_v10.amazon_feed_submission_history_tree_view_ept').id, 'tree'),
                      (self.env.ref('amazon_ept_v10.amazon_feed_submission_history_form_view_ept').id, 'form')],
            'domain': [('model_name', '=', 'product.template'), ('record_id', '=', self.id)],
            'target': 'current',
        }

    def upload_product_all_data(self):
        self.upload_product_ljp()
        self.upload_image_ljp()
        self.upload_price_ljp()
        self.upload_stock_ljp()

    def upload_product_ljp(self):
        template_obj = self.env['product.template']
        for id in self._context.get('active_ids'):
            template = template_obj.browse(id)
            instance = template.product_owner.amazon_instance_id
            amazon_products = self.env['amazon.product.ept'].search([
                ('product_tmpl_id', '=', template.id),
                ('variation_data', '=', 'parent'),
            ])
            if not amazon_products:
                amazon_products = self.env['amazon.product.ept'].search([
                    ('product_tmpl_id', '=', template.id),
                    ('variation_data', '=', False),
                ])
            if not amazon_products:
                raise UserError(u'amazon_products is Null!')
            self.env['amazon.product.ept'].export_product_amazon(instance, amazon_products)
            if len(template.product_variant_ids) == 1:
                template.write({
                    'product_status': 'updating',
                    'relation_update': 'done',
                })
            else:
                template.write({
                    'product_status': 'updating',
                    'relation_update': 'updating',
                })

    def upload_price_ljp(self):
        template_obj = self.env['product.template']
        for id in self._context.get('active_ids'):
            template = template_obj.browse(id)
            instance = template.product_owner.amazon_instance_id
            amazon_products = self.env['amazon.product.ept'].search([
                ('product_tmpl_id', '=', template.id),
                ('variation_data', 'in', ['', 'parent']),
            ])
            amazon_products.update_price(instance)
            template.write({
                'price_update': 'updating',
                'image_update': 'updating',
                'stock_update': 'updating',
            })

    def upload_image_ljp(self):
        template_obj = self.env['product.template']
        for id in self._context.get('active_ids'):
            template = template_obj.browse(id)
            instance = template.product_owner.amazon_instance_id
            amazon_products = self.env['amazon.product.ept'].search([
                ('product_tmpl_id', '=', template.id),
                ('variation_data', 'in', ['', 'parent']),
            ])
            self.env['amazon.product.ept'].update_images(template)
            template.write({
                'price_update': 'updating',
                'image_update': 'updating',
                'stock_update': 'updating',
            })

    def upload_stock_ljp(self):
        template_obj = self.env['product.template']
        for id in self._context.get('active_ids'):
            template = template_obj.browse(id)
            instance = template.product_owner.amazon_instance_id
            amazon_products = self.env['amazon.product.ept'].search([
                ('product_tmpl_id', '=', template.id),
                ('variation_data', 'in', ['', 'parent']),
            ])
            self.env['amazon.product.ept'].export_stock_levels(instance, amazon_products.ids)
            template.write({
                'price_update': 'updating',
                'image_update': 'updating',
                'stock_update': 'updating',
            })

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        '''同一model 不同action 显示不同的下拉菜单
            xml_ids = {
                u'供应商批量发布产品': 'b2b_platform.platform_products_publish_collect',
                u'经销商批量收录产品': 'b2b_platform.platform_products_distributor_collect',
                u'经销商产品发布到店铺': 'b2b_platform.distributor_products_shop_collect',
                u'经销商指定产品内部分类': 'b2b_platform.distributor_products_assign_categ',
                u'上传产品、图片、价格和库存': 'b2b_platform.shop_products_upload_amazon',
                u'上传产品': 'amazon_api.upload_product_server_ljp',
                u'上传图片': 'amazon_api.upload_image_server_ljp',
                u'上传价格': 'amazon_api.upload_price_server_ljp',
                u'上传库存': 'amazon_api.upload_stock_server_ljp',
            }
        '''
        result = super(ProductTemplate, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                           submenu=submenu)
        if result.has_key('toolbar') and result['toolbar'].has_key('action'):
            actions = result['toolbar']['action']
            menu_name = self._context.get('menu_name')
            xml_ids = [
                'b2b_platform.platform_products_publish_collect',
                'b2b_platform.platform_products_distributor_collect',
                'b2b_platform.distributor_products_shop_collect',
                'b2b_platform.distributor_products_assign_categ',
                'b2b_platform.shop_products_upload_amazon',
                'amazon_api.upload_product_server_ljp',
                'amazon_api.upload_image_server_ljp',
                'amazon_api.upload_price_server_ljp',
                'amazon_api.upload_stock_server_ljp',
            ]
            info = {
                u'未发布产品': [xml_ids[1], xml_ids[2], xml_ids[3], xml_ids[4], xml_ids[5], xml_ids[6], xml_ids[7], xml_ids[8],],
                u'已发布产品': [xml_ids[0], xml_ids[1], xml_ids[2], xml_ids[3], xml_ids[4], xml_ids[5], xml_ids[6], xml_ids[7], xml_ids[8],],
                u'我的产品库': [xml_ids[0], xml_ids[1], xml_ids[4], xml_ids[5], xml_ids[6], xml_ids[7], xml_ids[8]],
                u'店铺中产品列表': [xml_ids[0], xml_ids[1], xml_ids[2], xml_ids[3]],
                u'产品变更': [xml_ids[0], xml_ids[1], xml_ids[2], xml_ids[3]],
                u'平台产品库': [xml_ids[0], xml_ids[2], xml_ids[3], xml_ids[4], xml_ids[5], xml_ids[6], xml_ids[7], xml_ids[8],],
            }
            new_actions = []
            for action in actions:
                xml_id = action.get('xml_id', '')
                if xml_id in ['amazon_ept_v10.action_view_prepare_product_ept']:
                    continue
                hide_xml_ids = info.get(menu_name, [])
                if xml_id in hide_xml_ids:
                    continue
                new_actions.append(action)
            result['toolbar']['action'] = new_actions
        return result


        # for id in active_ids:
        #     template = self.browse(id)
        #     instance = template.product_owner.amazon_instance_id
        #     amazon_products = self.env['amazon.product.ept'].search([
        #         ('product_tmpl_id', '=', template.id),
        #         ('variation_data', '=', 'parent'),
        #     ])
        #     if not amazon_products:
        #         amazon_products = self.env['amazon.product.ept'].search([
        #             ('product_tmpl_id', '=', template.id),
        #             ('variation_data', '=', False),
        #         ])
        #     if not amazon_products:
        #         raise UserError(u'amazon_products is Null!')
        #     self.env['amazon.product.ept'].export_product_amazon(instance, amazon_products)
        #     if len(template.product_variant_ids) == 1:
        #         template.write({
        #             'product_status': 'updating',
        #             'relation_update': 'done',
        #         })
        #     else:
        #         template.write({
        #             'product_status': 'updating',
        #             'relation_update': 'updating',
        #         })

    @api.one
    def button_shop_collect_product(self, product_id, shop_id, convert_id=None):
        '''根据经销商产品生成店铺产品'''
        print '根据经销商产品生成店铺产品'
        if not product_id:
            product_id = self
        if not shop_id:
            raise UserError(u'请指定要收录该产品的店铺')

        context = self._context.copy()
        context['collection_mark'] = 'collected'

        supplier_name = ''
        brand = ''
        prefix = ''
        suffix = ''
        declaration = ''
        key_points = ''
        keywords = ''
        prefix_description = ''
        suffix_description = ''
        if convert_id:
            convert = self.env['b2b.shop.collect.convert'].browse(convert_id)
            supplier_name = convert.supplier_name if convert.supplier_name else ''
            brand = convert.brand if convert.brand else ''
            prefix = (convert.prefix + ' ') if convert.prefix else ''
            suffix = (' ' + convert.suffix) if convert.suffix else ''
            declaration = convert.declaration if convert.declaration else ''
            key_points = convert.key_points if convert.key_points else ''
            keywords = (convert.keywords + ' ') if convert.keywords else ''
            prefix_description = (convert.prefix_description + '\n') if convert.prefix_description else ''
            suffix_description = ('\n' + convert.suffix_description) if convert.suffix_description else ''

        prod_tmpl_obj = self.env['product.template'].sudo()
        prod_attr_ln_obj = self.env['product.attribute.line']
        prod_prod_obj = self.env['product.product']
        prod_attr_price_obj = self.env['product.attribute.price'].sudo()
        prod_image_obj = self.env['product.image'].sudo()
        currency = self.env.user.company_id.currency_id
        # 查看是否已被本店收录
        if product_id.shop_collected:
            raise UserError("该产品已被%s收录，不必重复。" % shop_id.name)
        # 复制出新产品模板
        freight_line = []
        freights = self.env['b2b.product.freight.line'].search([('product_id', '=', self.id)])
        if freights:
            for freight in freights:
                freight_line.append((0, 0, {'country_id': freight.country_id.id,
                                            'cny_amount': freight.cny_amount,
                                            'foreigh_currency': freight.foreigh_currency.id,
                                            'foreign_amount': freight.foreign_amount,
                                            }))
        supplierinfo = {
            'name': self.master_product.product_owner.id,
            'sequence': max(self.seller_ids.mapped('sequence')) + 1 if self.seller_ids else 1,
            'product_uom': self.uom_id.id,
            'min_qty': 1.0,
            'price': self.master_product.dist_price,
            'currency_id': currency.id,
            'delay': 0,
        }
        vals = {'seller_ids': [(0, 0, supplierinfo)]}

        # markup_lines = self.env['b2b.trader.markup'].search(
        #     [('partner', '=', shop_id.id), ('categ_id', '=', self.categ_id.id)], limit=1)
        # markup = markup_lines.rate or 0
        markup = shop_id.shop_markup or 0
        shop_price = product_id.list_price * (1 + markup / 100)

        if not shop_id.shop_language:
            raise UserError(u'该店铺未指定亚马逊所用语言。')
        language = shop_id.shop_language

        product_chinese = False
        product_english = False
        product_german = False
        product_french = False
        product_spanish = False
        product_italian = False
        product_japanese = False

        product_title = ''
        product_keyword = ''
        product_briefing = ''
        product_description = ''

        product_title_english = ''
        product_keyword_english = ''
        product_briefing_english = ''
        product_description_english = ''

        product_title_german = ''
        product_keyword_german = ''
        product_briefing_german = ''
        product_description_german = ''

        product_title_french = ''
        product_keyword_french = ''
        product_briefing_french = ''
        product_description_french = ''

        product_title_spanish = ''
        product_keyword_spanish = ''
        product_briefing_spanish = ''
        product_description_spanish = ''

        product_title_italian = ''
        product_keyword_italian = ''
        product_briefing_italian = ''
        product_description_italian = ''

        product_title_japanese = ''
        product_keyword_japanese = ''
        product_briefing_japanese = ''
        product_description_japanese = ''

        if language == 'chinese':
            product_chinese = True
            product_title = product_id.product_title or ''
            product_title = prefix + product_title + suffix
            product_keyword = product_id.product_keyword or ''
            product_keyword = keywords + product_keyword
            product_briefing = product_id.product_briefing or ''
            product_briefing = key_points + product_briefing
            product_description = product_id.product_description or ''
            product_description = prefix_description + product_description + suffix_description
        elif language == 'english':
            product_english = True
            product_title = product_id.product_title_english or ''
            product_title_english = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_english or ''
            product_keyword_english = keywords + product_keyword
            product_briefing = product_id.product_briefing_english or ''
            product_briefing_english = key_points + product_briefing
            product_description = product_id.product_description_english or ''
            product_description_english = prefix_description + product_description + suffix_description
        elif language == 'german':
            product_german = True
            product_title = product_id.product_title_german or ''
            product_title_german = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_german or ''
            product_keyword_german = keywords + product_keyword
            product_briefing = product_id.product_briefing_german or ''
            product_briefing_german = key_points + product_briefing
            product_description = product_id.product_description_german or ''
            product_description_german = prefix_description + product_description + suffix_description
        elif language == 'french':
            product_french = True
            product_title = product_id.product_title_french or ''
            product_title_french = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_french or ''
            product_keyword_french = keywords + product_keyword
            product_briefing = product_id.product_briefing_french or ''
            product_briefing_french = key_points + product_briefing
            product_description = product_id.product_description_french or ''
            product_description_french = prefix_description + product_description + suffix_description
        elif language == 'spanish':
            product_spanish = True
            product_title = product_id.product_title_spanish or ''
            product_title_spanish = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_spanish or ''
            product_keyword_spanish = keywords + product_keyword
            product_briefing = product_id.product_briefing_spanish or ''
            product_briefing_spanish = key_points + product_briefing
            product_description = product_id.product_description_spanish or ''
            product_description_spanish = prefix_description + product_description + suffix_description
        elif language == 'italian':
            product_italian = True
            product_title = product_id.product_title_italian or ''
            product_title_italian = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_italian or ''
            product_keyword_italian = keywords + product_keyword
            product_briefing = product_id.product_briefing_italian or ''
            product_briefing_italian = key_points + product_briefing
            product_description = product_id.product_description_italian or ''
            product_description_italian = prefix_description + product_description + suffix_description
        elif language == 'japanese':
            product_japanese = True
            product_title = product_id.product_title_japanese or ''
            product_title_japanese = prefix + product_title + suffix
            product_keyword = product_id.product_keyword_japanese or ''
            product_keyword_japanese = keywords + product_keyword
            product_briefing = product_id.product_briefing_japanese or ''
            product_briefing_japanese = key_points + product_briefing
            product_description = product_id.product_description_japanese or ''
            product_description_japanese = prefix_description + product_description + suffix_description

        new_prod_tmpl = prod_tmpl_obj.with_context(context).create({
            'seller_template_id': product_id.id,
            'name': prefix + product_id.name + suffix,
            'image_medium': self.image_medium,
            'sale_ok': True,
            'purchase_ok': True,
            'type': product_id.type,
            'hs_code': product_id.hs_code,
            'customs_unit_price': product_id.customs_unit_price,
            'declaration_chinese': product_id.declaration_chinese,
            'declaration_english': product_id.declaration_english,
            'brand': self.brand,
            'pack_weight': self.pack_weight,
            'pack_method': self.pack_method,
            'material': self.material,
            'has_battery': self.has_battery,
            'target_users': self.target_users,
            'categ_id': product_id.categ_id.id,
            'trader_categ_id': product_id.trader_categ_id.id,
            'product_owner': shop_id.id,
            # 'shop_currency': shop_id.shop_currency.id,
            'list_price': shop_price,
            'standard_price': product_id.master_product.list_price or product_id.standard_price,
            'dist_price': product_id.master_product.list_price or product_id.standard_price,
            'uom_id': product_id.uom_id.id,
            'uom_po_id': product_id.uom_po_id.id,
            'purchase_method': product_id.purchase_method,
            'platform_published': False,
            'master_product': product_id.master_product.id,
            'distributor': product_id.distributor.id,
            'product_status': 'pending',
            'image_update': 'pending',
            'price_update': 'pending',
            'stock_update': 'pending',
            'relation_update': 'pending',
            'product_mod_time': fields.Datetime.now(),
            'image_mod_time': fields.Datetime.now(),
            'price_mod_time': fields.Datetime.now(),
            'stock_mod_time': fields.Datetime.now(),
            'relation_mod_time': fields.Datetime.now(),
            'product_chinese': product_chinese,
            'product_english': product_english,
            'product_german': product_german,
            'product_french': product_french,
            'product_spanish': product_spanish,
            'product_italian': product_italian,
            'product_japanese': product_japanese,
            'product_title': product_title,
            'product_keyword': product_keyword,
            'product_briefing': product_briefing,
            'product_description': self.product_description,
            'product_title_english': product_title_english,
            'product_keyword_english': product_keyword_english,
            'product_briefing_english': product_briefing_english,
            'product_description_english': product_description_english,
            'product_title_german': product_title_german,
            'product_keyword_german': product_keyword_german,
            'product_briefing_german': product_briefing_german,
            'product_description_german': product_description_german,
            'product_title_french': product_title_french,
            'product_keyword_french': product_keyword_french,
            'product_briefing_french': product_briefing_french,
            'product_description_french': product_description_french,
            'product_title_spanish': product_title_spanish,
            'product_keyword_spanish': product_keyword_spanish,
            'product_briefing_spanish': product_briefing_spanish,
            'product_description_spanish': product_description_spanish,
            'product_title_italian': product_title_italian,
            'product_keyword_italian': product_keyword_italian,
            'product_briefing_italian': product_briefing_italian,
            'product_description_italian': product_description_italian,
            'product_title_japanese': product_title_japanese,
            'product_keyword_japanese': product_keyword_japanese,
            'product_briefing_japanese': product_briefing_japanese,
            'product_description_japanese': product_description_japanese,
            'freight_line': freight_line,
            'supplier_name':supplier_name,
            'brand':brand,
            'declaration':declaration,
            # 'default_code':str(uuid.uuid4()).upper(),
            'system_id': self.system_id,
            'modify_state':'new',
            'prod_mod_state':'new',
            'image_mod_state':'new',
            'stock_mod_state':'new',
            'variant_mod_state':'new',
            })
        new_prod_tmpl.write(vals)
        # 复制出新产品的属性
        if product_id.attribute_line_ids:
            for line in product_id.attribute_line_ids:
                # 复制产品属性
                new_attr_line = prod_attr_ln_obj.create({'product_tmpl_id': new_prod_tmpl.id,
                                                         'attribute_id': line.attribute_id.id,
                                                         })
                # 复制属性值
                sql = "INSERT INTO product_attribute_line_product_attribute_value_rel " \
                      "SELECT %s, product_attribute_value_id " \
                      "FROM product_attribute_line_product_attribute_value_rel " \
                      "WHERE product_attribute_line_id = %s;" % (new_attr_line.id, line.id)
                self._cr.execute(sql)
        # 根据属性生成变体产品
        new_prod_tmpl.create_variant_ids()
        # 获取店铺的加价率和币种
        currency_id = shop_id.shop_currency
        markup = shop_id.shop_markup
        # 将产品中产品变体的价格附加价格复制到店铺收录的产品中
        for product in new_prod_tmpl.product_variant_ids:
            # 将产品默认置为无效
            # product.update({'master_product': False,'active': False,})

            attr_val = product.mapped('attribute_value_ids')
            m_products = prod_prod_obj.sudo().search([('product_tmpl_id', '=', self.id)])
            for m_product in m_products:
                m_attr_val = m_product.mapped('attribute_value_ids')
                if m_attr_val == attr_val:
                    # 关联平台主产品
                    barcode = product.get_upc_code(shop_id.parent_id, shop_id, product_id)
                    product.update({
                        'master_product': m_product.master_product.id,
                        'seller_product_id': m_product.id,
                        'active': m_product.active,
                        'barcode': barcode.name if barcode else False,
                        'shop_currency': currency_id.id,
                        'shop_currency2': currency_id.id,
                        'standard_price': m_product.standard_price})
                    if barcode:
                        barcode.write({'state': 'taken','shop_id': shop_id.id,'product': product.id})
                    # 复制变体的附加价格
                    rate = 0

                    for value in m_attr_val:
                        vlu = value[0].id
                        amt = 0
                        attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', m_product.product_tmpl_id.id),
                                                                 ('value_id', '=', vlu)])
                        if attr_price:
                            for rec in attr_price:
                                amt += rec.price_extra
                            list_price = amt * (1 + rate / 100.0) * (1 + markup / 100.0)
                            if not prod_attr_price_obj.search([('product_tmpl_id', '=', new_prod_tmpl.id),
                                                               ('value_id', '=', vlu),
                                                               ('price_extra', '=', list_price)
                                                               ]):
                                prod_attr_price_obj.create({'product_tmpl_id': new_prod_tmpl.id,
                                                            'value_id': vlu,
                                                            'price_extra': list_price})
                # 更新价格
                shop_cny_price = m_product.lst_price * (1 + markup / 100) + product.variant_adj_price
                shop_foreign_price = self.env.user.company_id.currency_id.compute(shop_cny_price,currency_id)
                product.update({'lst_price': shop_cny_price, 'shop_retail_price': shop_foreign_price})
        # 复制产品图片
        new_prod_tmpl.sync_supplier_tmpl_images()
        new_prod_tmpl.b2b_type = 'shop'
        #加价
        shop_rate = (new_prod_tmpl.product_owner.shop_markup or 0) / 100
        new_prod_tmpl.shop_price = new_prod_tmpl.seller_template_id.seller_price * (1 + shop_rate)
        for product in new_prod_tmpl.product_variant_ids:
            product.shop_price_cny = product.seller_product_id.seller_price * (1 + shop_rate)
        return new_prod_tmpl

    @api.one
    def button_collect_product(self):
        '''经销商从平台收录产品'''
        print '经销商从平台收录产品...'
        context = self._context.copy()
        context['collection_mark']='collected'
        if self.collected_mark:
            raise osv.except_osv("该产品已被收录，不必重复。")
        prod_tmpl_obj = self.env['product.template']
        prod_attr_ln_obj = self.env['product.attribute.line']
        prod_prod_obj = self.env['product.product']
        prod_attr_price_obj = self.env['product.attribute.price'].sudo()
        prod_image_obj = self.env['product.image'].sudo()
        partner = self.env['res.users'].sudo().search([('id', '=', self._uid)], limit=1).partner_id
        distributor = partner.parent_id or partner
        currency = self.env.user.company_id.currency_id

        # 复制出新产品模板
        freight_line = []
        freights = self.env['b2b.product.freight.line'].search([('product_id','=',self.id)])
        if freights:
            for freight in freights:
                freight_line.append((0, 0, {'country_id': freight.country_id.id,
                                     'cny_amount':freight.cny_amount,
                                     'foreigh_currency':freight.foreigh_currency.id,
                                     'foreign_amount':freight.foreign_amount,
                                     }))

        supplierinfo = {
            'name': self.product_owner.id,
            'sequence': max(self.seller_ids.mapped('sequence')) + 1 if self.seller_ids else 1,
            'product_uom': self.uom_id.id,
            'min_qty': 1.0,
            'price': self.currency_id.compute(self.list_price, currency),
            'currency_id': currency.id,
            'delay': 0,
            }
        vals = {'seller_ids': [(0, 0, supplierinfo)]}

        markup_lines = self.env['b2b.trader.markup'].search([('partner','=',distributor.id),('id','=',self.trader_categ_id.id)],limit=1)
        markup = markup_lines.rate or 0
        dist_price = self.list_price * (1 + markup/100)

        new_prod_tmpl = prod_tmpl_obj.with_context(context).create({
            'name': self.name,
            'image_medium': self.image_medium,
            'sale_ok': True,
            'purchase_ok': True,
            'type': self.type,
            'system_id': self.system_id,
            'hs_code': self.hs_code,
            'customs_unit_price': self.customs_unit_price,
            'declaration_chinese': self.declaration_chinese,
            'declaration_english': self.declaration_english,
            'brand': self.brand,
            'pack_weight': self.pack_weight,
            'pack_method': self.pack_method,
            'material': self.material,
            'has_battery': self.has_battery,
            'target_users': self.target_users,
            'categ_id': self.categ_id.id,
            'product_owner': distributor.id,

            'list_price':dist_price,
            'standard_price':self.list_price,
            'dist_price':self.list_price,

            'uom_id':self.uom_id.id,
            'uom_po_id':self.uom_po_id.id,
            'purchase_method':self.purchase_method,
            'platform_published':False,
            'master_product':self.id,
            'product_chinese':self.product_chinese,
            'product_english':self.product_english,
            'product_german':self.product_german,
            'product_french':self.product_french,
            'product_spanish':self.product_spanish,
            'product_italian':self.product_italian,
            'product_japanese':self.product_japanese,
            'product_title':self.product_title,
            'product_keyword':self.product_keyword,
            'product_briefing':self.product_briefing,
            'product_description':self.product_description,
            'product_title_english':self.product_title_english,
            'product_keyword_english':self.product_keyword_english,
            'product_briefing_english':self.product_briefing_english,
            'product_description_english':self.product_description_english,
            'product_title_german':self.product_title_german,
            'product_keyword_german':self.product_keyword_german,
            'product_briefing_german':self.product_briefing_german,
            'product_description_german':self.product_description_german,
            'product_title_french':self.product_title_french,
            'product_keyword_french':self.product_keyword_french,
            'product_briefing_french':self.product_briefing_french,
            'product_description_french':self.product_description_french,
            'product_title_spanish':self.product_title_spanish,
            'product_keyword_spanish':self.product_keyword_spanish,
            'product_briefing_spanish':self.product_briefing_spanish,
            'product_description_spanish':self.product_description_spanish,
            'product_title_italian':self.product_title_italian,
            'product_keyword_italian':self.product_keyword_italian,
            'product_briefing_italian':self.product_briefing_italian,
            'product_description_italian':self.product_description_italian,
            'product_title_japanese':self.product_title_japanese,
            'product_keyword_japanese':self.product_keyword_japanese,
            'product_briefing_japanese':self.product_briefing_japanese,
            'product_description_japanese':self.product_description_japanese,
            'freight_line':freight_line,
            })
        #复制出category  variation theme  brand
        vals.update({
            'amazon_categ_id': self.amazon_categ_id.id,
            'child_categ_id': self.child_categ_id.id,
            'variation_theme_id': self.variation_theme_id.id,
            'product_brand_id': self.product_brand_id.id,
        })

        new_prod_tmpl.write(vals)
        # 如果是供应商收录自己的产品，则复制已指定的产品内部分类
        if new_prod_tmpl.product_owner == self.product_owner:
            new_prod_tmpl.write({'trader_categ_id': self.trader_categ_id.id})
        # 复制出新产品的属性
        if self.attribute_line_ids:
            for line in self.attribute_line_ids:
                # 复制产品属性
                new_attr_line = prod_attr_ln_obj.create({'product_tmpl_id':new_prod_tmpl.id,
                                                         'attribute_id':line.attribute_id.id,
                                                        })
                # 复制属性值
                sql = "INSERT INTO product_attribute_line_product_attribute_value_rel " \
                      "SELECT %s, product_attribute_value_id " \
                      "FROM product_attribute_line_product_attribute_value_rel " \
                      "WHERE product_attribute_line_id = %s;" % (new_attr_line.id, line.id)
                self._cr.execute(sql)
        # 根据属性生成变体产品
        new_prod_tmpl.create_variant_ids()
        # 将产品中产品变体的价格附加价格复制到经销商收录的产品中
        for product in new_prod_tmpl.product_variant_ids:
            # 将产品默认置为无效
            # product.update({'master_product': False,'active': False,})

            attr_val = product.mapped('attribute_value_ids')
            m_products = prod_prod_obj.sudo().search([('product_tmpl_id', '=', self.id)])
            for m_product in m_products:
                m_attr_val = m_product.mapped('attribute_value_ids')
                if m_attr_val == attr_val:
                    # 关联平台主产品
                    product.update({'master_product': m_product.id, 'active': m_product.active})
                    # 复制变体的附加价格
                    rate = 0
                    if self.categ_id and self.categ_id.commission_rate:
                        rate = self.categ_id.commission_rate
                    else:
                        categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                        if categ:
                            rate = categ.commission_rate

                    for value in m_attr_val:
                        vlu = value[0].id
                        amt = 0
                        attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', self.id),
                                                                 ('value_id', '=', vlu)])
                        if attr_price:
                            for rec in attr_price:
                                amt += rec.price_extra
                            list_price = amt * (1 + rate / 100.0) * (1 + markup / 100.0)

                            if not prod_attr_price_obj.search([('product_tmpl_id','=',new_prod_tmpl.id),
                                                        ('value_id', '=', vlu),
                                                        ('price_extra', '=', list_price)
                                                        ]):
                                prod_attr_price_obj.create({'product_tmpl_id': new_prod_tmpl.id,
                                                            'value_id': vlu,
                                                            'price_extra': list_price})
                        # 将供应商产品的平台价写入经销商的成本价
                        product.update({'standard_price': m_product.lst_price})
        # 复制产品图片及映射关系
        new_prod_tmpl.sync_supplier_tmpl_images()
        #复制品牌
        new_prod_tmpl.product_brand_id = self.product_brand_id.id
        new_prod_tmpl.b2b_type = 'seller'
        #复制价格
        new_prod_tmpl.seller_price = new_prod_tmpl.master_product.platform_price
        for product in new_prod_tmpl.product_variant_ids:
            product.seller_price = product.master_product.platform_price

