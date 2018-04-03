# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _

active_attr =  [
    {'amazon_attr': 'Color', 'odoo_attr': u'颜色'},
    {'amazon_attr': 'Size', 'odoo_attr': u'尺寸'},
    {'amazon_attr': 'Capacity', 'odoo_attr': u'容量'},
    {'amazon_attr': 'Design', 'odoo_attr': u'设计'},
    {'amazon_attr': 'Edition', 'odoo_attr': u'版本'},
    {'amazon_attr': 'Flavor', 'odoo_attr': u'口味'},
    {'amazon_attr': 'Material', 'odoo_attr': u'材料'},
    {'amazon_attr': 'Pattern', 'odoo_attr': u'图案'},
    {'amazon_attr': 'Shape', 'odoo_attr': u'形状'},
    {'amazon_attr': 'Scent', 'odoo_attr': u'气味'},
    # {'amazon_attr': 'Shape', 'odoo_attr': u'样式'},
    {'amazon_attr': 'UnitCount', 'odoo_attr': u'单位数'},
    {'amazon_attr': 'Wattage', 'odoo_attr': u'瓦数'},
    {'amazon_attr': 'Weight', 'odoo_attr': u'重量'},
]


class AmazonAttributeEpt(models.Model):
    _inherit = "amazon.attribute.ept"

    attribute_value_ids = fields.One2many('amazon.attribute.value.ept', 'attribute_id', string=u'属性值')

    def create_product_attribute(self):
        '''根据亚马逊属性及属性值，创建odoo属性及属性值'''
        odoo_attr_obj = self.env['product.attribute']
        amazon_attr_obj = self.env['amazon.attribute.ept']
        # amazon_attr_val_obj = self.env['amazon.attribute.value.ept']
        odoo_attr_val_obj = self.env['product.attribute.value']
        for attr in active_attr:
            odoo_attr_name = attr['odoo_attr']
            amazon_attr_name = attr['amazon_attr']
            print odoo_attr_name,amazon_attr_name
            odoo_attr = odoo_attr_obj.search([('name', '=', odoo_attr_name)], limit=1)
            if not odoo_attr:
                odoo_attr = odoo_attr_obj.create({
                    'name': odoo_attr_name,
                    'amazon_name': amazon_attr_name,
                    'create_variant': True,
                })
            amazon_attrs = amazon_attr_obj.search([('name', '=', amazon_attr_name)])
            print 'amazon_attrs',amazon_attrs
            amazon_categs = []
            attr_vals = []
            for amazon_attr in amazon_attrs:
                if amazon_attr.amazon_categ_id:
                    amazon_categs.append(amazon_attr.amazon_categ_id.id)
                for attr_val in amazon_attr.attribute_value_ids:
                    attr_vals.append(attr_val.name)
            amazon_categs = list(set(amazon_categs))
            attr_vals = list(set(attr_vals))
            odoo_attr.amazon_categ_ids = [[6, 0, amazon_categs]]
            print 'attr_vals:', attr_vals
            for attr_val in attr_vals:
                odoo_attr_val = odoo_attr_val_obj.search([
                    ('attribute_id', '=', odoo_attr.id),
                    ('name', '=', attr_val),
                ])
                if not odoo_attr_val:
                    odoo_attr_val_obj.create({
                        'name': attr_val,
                        'attribute_id': odoo_attr.id,
                    })
        print 'over'
        return

