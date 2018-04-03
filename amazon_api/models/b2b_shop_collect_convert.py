# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.exceptions import UserError
import uuid

class B2bShopCollectConvert(models.TransientModel):
    _inherit = "b2b.shop.collect.convert"

    @api.model
    def create(self, val):
        result = super(B2bShopCollectConvert, self).create(val)
        result.check_template_data()
        return result

    @api.multi
    def write(self, val):
        result = super(B2bShopCollectConvert, self).write(val)
        self.check_template_data()
        return result

    @api.multi
    def check_template_data(self):
        '''检查模板数据是否合法'''
        for record in self:
            if record.shop_id.country_id != record.browse_node_id.country_id:
                raise UserError(u'店铺与商品类别所属国家不一致！')
            if record.amazon_categ_id and record.amazon_categ_id.child_categ_ids:
                raise UserError('所选择的模板有子模板，请选择子模板！')

    @api.multi
    def create_variation_theme(self, shop_template):
        '''根据category attribute 自动生成variation theme'''
        theme_id = False
        themes = self.env['amazon.variation.theme.ept'].search(['|',
            ('amazon_categ_id', '=', shop_template.parent_categ_id.id),
            ('amazon_categ_id', '=', shop_template.child_categ_id.id)])
        attrs = []
        for line in shop_template.attribute_line_ids:
            attrs.append(line.attribute_id.amazon_name)
        sort_themes = []
        for theme in themes:
            priority = 0
            for attr in attrs:
                if attr in theme.name:
                    priority += 1
            sort_themes.append((theme, priority))
        if sort_themes:
            new_sort_themes = sorted(sort_themes, key=lambda item:item[1], reverse=True)
            theme_id = new_sort_themes[0][0].id
        return theme_id

    @api.multi
    def btn_collect(self):
        '''经销商产品发布到店铺'''
        shop_template_ids = []
        for template_id in self._context.get('active_ids'):
            distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
            saler_template = self.env['product.template'].browse(template_id)
            shop_templates = self.env['product.template'].search([
                ('product_owner.parent_id', '=', distributor.id),
                ('product_owner.type', '=', 'shop'),
                ('product_owner', '=', self.shop_id.id),
                ('master_product', '=', saler_template.master_product.id)])
            if not shop_templates:
                # if len(saler_template.product_variant_ids) > 1 and not self.variation_theme_id:
                #     raise UserError(u'产品%s有变体，Variation Theme不能为空！' % saler_template.name)
                shop_templates = saler_template.button_shop_collect_product(saler_template, self.shop_id, self.id)
                for shop_template in shop_templates:
                    # shop_template.check_categ_attribute(self.amazon_categ_id.id, self.child_categ_id.id)
                    val = {
                        'browse_node_id': self.browse_node_id.id,
                        'amazon_categ_id': self.amazon_categ_id.id,
                        'product_brand_id': self.product_brand_id.id
                    }
                    shop_template.write(val)
                    theme_id = self.create_variation_theme(shop_template)
                    if theme_id:
                        shop_template.variation_theme_id = theme_id
                    shop_template.check_categ_attribute()
                # 创建亚马逊产品
                self.create_or_update_amazon_product(shop_templates)
                for shop_template in shop_templates:
                    self.add_seller_sku(shop_template)
            for shop_template in shop_templates:
                shop_template_ids.append(shop_template.id)
        return {
            'name': '店铺中发布的产品',
            'view_type': 'form',
            "view_mode": 'tree,form',
            'res_model': 'product.template',
            'type': 'ir.actions.act_window',
            'views': [(False, 'tree'), (False, 'form')],
            'context': {'create': False, 'collection_mark': 'collected'},
            'domain': [('id', 'in', shop_template_ids)]
        }

    def add_seller_sku(self, shop_template):
        '''店铺产品添加sku'''
        print 'add_seller_sku'
        parent_sku = self.env['ir.sequence'].get_seller_sku()
        if shop_template.variation_theme_id:
            count = 0
            for product in shop_template.product_variant_ids:
                print product
                if not product.attribute_value_ids:
                    product.default_code = parent_sku
                    print product.default_code
                else:
                    count += 1
                    if count < 10:
                        count_str = '00' + str(count)
                    elif count < 100:
                        count_str = '0' + str(count)
                    else:
                        raise UserError(u'变体数过多！')
                    product.default_code = parent_sku + '-' + count_str
                    print product.default_code
        else:
            if len(shop_template.product_variant_ids) == 1 and \
                    not shop_template.product_variant_ids[0].attribute_value_ids:
                shop_template.product_variant_ids[0].default_code = parent_sku


    @api.multi
    def create_or_update_amazon_product(self, templates):
        active_ids = [template.id for template in templates]
        instance = self.shop_id.amazon_instance_id
        wizard = self.env['amazon.product.wizard'].create({'instance_id': instance.id,})
        wizard.with_context(active_ids=active_ids, key='prepare_selective_product_for_export').prepare_product()
        return

