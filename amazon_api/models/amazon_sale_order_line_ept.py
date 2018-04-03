# -*- encoding: utf-8 -*-

from odoo import models, fields, api

class AmazonSaleOrderLineEpt(models.Model):
    _inherit = 'amazon.sale.order.line.ept'

    @api.multi
    def create_sale_order_line(self, order_line, instance, amazon_order, create_service_line=True):
        print 'create_sale_order_line...'
        fulfillment_by = amazon_order.fulfillment_by
        product_details = self.search_or_create_or_update_product(order_line, instance, fulfillment_by)
        """selling Product Line"""
        amazon_product = product_details.get('sale_product', False)
        if amazon_product:
            item_price = self.get_item_price(order_line)
            # print 'item_price',item_price
            order_qty = order_line.get('QuantityOrdered', {}).get('value', 0.0)
            title = order_line.get('Title', {}).get('value', False)
            qty_price_dict = self.calculate_order_qty_and_price_based_on_asin_qty(amazon_product, float(item_price),
                                                                                  float(order_qty))
            # print 'qty_price_dict',qty_price_dict
            tax_amount = self.get_item_tax_amount(order_line, item_price)
            tax_id = False
            order_line_vals = self.create_sale_order_line_vals(order_line, qty_price_dict, tax_id, amazon_product,
                                                               amazon_product.product_id and amazon_product.product_id.id,
                                                               amazon_order, instance, title)
            order_line_vals.update({'order_line_tax': tax_amount})
            prod_order_line = self.create(order_line_vals)
        return True

    def create_sale_order_line_vals(self, order_line, qty_price_dict, tax_id, amazon_product=False, odoo_product=False,
                                    amazon_order=False, instance=False, title=False):
        """修改原方法 product_id shop_product"""
        # print '111111111111'
        shop_product = amazon_product and amazon_product.product_id or odoo_product or False
        product_id = shop_product and shop_product.master_product and shop_product.master_product.id \
                     or shop_product.id

        # print shop_product,product_id
        new_record = self.env['sale.order.line'].new({
            'order_id': amazon_order.sale_order_id.id,
            'company_id': amazon_order.company_id.id,
            'product_id': product_id,
            'shop_product': shop_product.id,
            'price_unit': self.shop_product.master_product.lst_price,
            'product_uom': amazon_product and amazon_product.product_tmpl_id.uom_id or odoo_product and odoo_product.product_tmpl_id.uom_id,
            'name': title,
            'shop_unit_price': float(order_line.get('ItemPrice', {}).get('Amount', {}).get('value', 0)),
            'amazon_price_tax': float(order_line.get('ItemTax', {}).get('Amount', {}).get('value', 0)),
            'amazon_shipping_price': float(order_line.get('ShippingPrice', {}).get('Amount', {}).get('value', 0)),
            'amazon_shipping_tax': float(order_line.get('ShippingTax', {}).get('Amount', {}).get('value', 0)),
            'amazon_shipping_discount': float(order_line.get('ShippingDiscount', {}).get('Amount', {}).get('value', 0)),
            })
        new_record.product_id_change()
        order_vals = new_record._convert_to_write({name: new_record[name] for name in new_record._cache})
        order_qty = qty_price_dict.get('order_qty')
        order_vals.update({
            'amazon_order_id': amazon_order.id,
            'instance_id': instance.id,
            'product_uom_qty': order_qty,
            'amazon_order_qty': order_line.get('QuantityOrdered', {}).get('value', 0.0),
            # 'price_unit': qty_price_dict.get('amount_per_unit'),
            # 'shop_unit_price': qty_price_dict.get('amount_per_unit'),
            'customer_lead': amazon_product and amazon_product.sale_delay or False,
            'invoice_status': False,
            'state': 'draft',
            'amazon_order_item_id': order_line.get('OrderItemId', {}).get('value'),
            'discount': 0.0,
            'amazon_product_id': amazon_product and amazon_product.id or False,
            'product_uom': new_record.product_uom.id
        })
        # print order_vals
        return order_vals
