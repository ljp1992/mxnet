# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError
import threading, time

class amazon_prepare_product_wizard(models.TransientModel):
    _inherit = 'amazon.product.wizard'

    @api.multi
    def prepare_product(self):
        template_obj = self.env['product.template']
        if self._context.get('key') == 'prepare_selective_product_for_export':
            template_ids = self._context.get('active_ids', [])
            templates = template_obj.browse(template_ids)
            for template in templates:
                if template.type == 'service':
                    continue
                odoo_products = template.product_variant_ids
                if template.variation_theme_id:
                    self.create_or_update_amazon_product(False, template, template.parent_sku, template.description,
                                                         'parent')
                if len(template.product_variant_ids.ids) == 1:
                    odoo_product = template.product_variant_ids
                    self.create_or_update_amazon_product(odoo_product, template, odoo_product.default_code,
                                                         template.description, False)
                else:
                    for odoo_product in odoo_products:
                        if odoo_product.is_amazon_virtual_variant:
                            continue
                        self.create_or_update_amazon_product(odoo_product, template, odoo_product.default_code,
                                                             template.description, 'child')
        return True

    @api.multi
    def create_or_update_amazon_product(self, odoo_product, template, default_code, description, parentage):
        amazon_product_ept_obj = self.env['amazon.product.ept']
        amazon_attribute_line_obj = self.env['amazon.attribute.line.ept']
        amazon_attribute_value_obj = self.env['amazon.attribute.value.ept']
        amazon_attribute_obj = self.env['amazon.attribute.ept']
        browse_node_obj = self.env['amazon.browse.node.ept']
        domain = [('country_id', '=', self.instance_id.country_id.id)]
        odoo_product and domain.append(('odoo_category_id', '=', odoo_product.categ_id.id))
        browse_node = browse_node_obj.search(domain, limit=1)
        vals = {
            'title': template.name,
            'instance_id': self.instance_id.id,
            'product_id': odoo_product and odoo_product.id or False,
            # 'seller_sku': default_code or False,
            'standard_product_id_type': 'UPC',
            'product_upc': odoo_product and odoo_product.barcode or '',
            'amazon_browse_node_id': browse_node and browse_node.id or False,
            'condition': self.instance_id.condition or 'New',
            'tax_code_id': self.instance_id.default_amazon_tax_code_id and self.instance_id.default_amazon_tax_code_id.id or False,
            'long_description': description or False,
            'variation_data': parentage
        }
        if not odoo_product:
            shop = self.env['res.partner'].search([('amazon_instance_id', '=', self.instance_id.id)])
            barcode = self.env['b2b.upc.list'].search([
                ('owner', '=', shop.parent_id.id),
                ('state', '=', 'vacant')], limit=1)
            barcode.write({'state': 'taken'})
            vals.update({
                'product_tmpl_id': template.id,
                # 'default_code': default_code,
                'barcode': barcode.name,
                'standard_product_id_type': 'UPC',
                'product_upc': barcode.name,
            })
        amazon_product = odoo_product and amazon_product_ept_obj.search(
            [('instance_id', '=', self.instance_id.id), ('product_id', '=', odoo_product.id)]) or False
        if amazon_product:
            amazon_product.write({'long_description': description or False, 'variation_data': parentage})
        else:
            amazon_product = amazon_product_ept_obj.create(vals)
        if odoo_product:
            for attribute_value in odoo_product.attribute_value_ids:
                if attribute_value.attribute_id.amazon_attribute_id:
                    amazon_attribute_line = amazon_attribute_line_obj.search([('product_id', '=', amazon_product.id), (
                    'attribute_id', '=', attribute_value.attribute_id.amazon_attribute_id.id)])
                    value = amazon_attribute_value_obj.search(
                        [('attribute_id', '=', attribute_value.attribute_id.amazon_attribute_id.id),
                         ('name', '=', attribute_value.name)], limit=1)
                    if not value:
                        value = amazon_attribute_value_obj.create(
                            {'attribute_id': attribute_value.attribute_id.amazon_attribute_id.id,
                             'name': attribute_value.name})
                    if amazon_attribute_line:
                        amazon_attribute_line.write({'value_ids': [(6, 0, value.ids)]})
                    else:
                        amazon_attribute_line_obj.create({'product_id': amazon_product.id,
                                                          'attribute_id': attribute_value.attribute_id.amazon_attribute_id.id,
                                                          'value_ids': [(6, 0, value.ids)]})
        if template.variation_theme_id:
            categ_ids = template.amazon_categ_id.ids + template.child_categ_id.ids
            attributes = amazon_attribute_obj.search([('amazon_categ_id', 'in', categ_ids), ('name', '=', 'Parentage')])
            amazon_attribute_line = amazon_attribute_line_obj.search(
                [('product_id', '=', amazon_product.id), ('attribute_id', 'in', attributes.ids)], limit=1)
            value = amazon_attribute_value_obj.search(
                [('attribute_id', 'in', attributes.ids), ('name', '=', parentage)], limit=1)
            if not value:
                value = amazon_attribute_value_obj.create({'attribute_id': attributes.ids[0], 'name': parentage})
            if amazon_attribute_line:
                amazon_attribute_line.write({'value_ids': [(6, 0, value.ids)]})
            else:
                amazon_attribute_line_obj.create({'product_id': amazon_product.id, 'attribute_id': attributes.ids[0],
                                                  'value_ids': [(6, 0, value.ids)]})

            attributes = amazon_attribute_obj.search(
                [('amazon_categ_id', 'in', categ_ids), ('name', '=', 'VariationTheme')])
            amazon_attribute_line = amazon_attribute_line_obj.search(
                [('product_id', '=', amazon_product.id), ('attribute_id', 'in', attributes.ids)], limit=1)
            value = amazon_attribute_value_obj.search(
                [('attribute_id', 'in', attributes.ids), ('name', '=', template.variation_theme_id.name)], limit=1)
            if not value:
                value = amazon_attribute_value_obj.create(
                    {'attribute_id': attributes.ids[0], 'name': template.variation_theme_id.name})
            if amazon_attribute_line:
                amazon_attribute_line.write({'value_ids': [(6, 0, value.ids)]})
            else:
                amazon_attribute_line_obj.create({'product_id': amazon_product.id, 'attribute_id': attributes.ids[0],
                                                  'value_ids': [(6, 0, value.ids)]})
        return True
