# -*- coding: utf-8 -*-

from odoo import models, api
import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('order_line')
    def _onchange_propagate_price_unit(self):
        # Para cada product.template presente en las líneas, buscamos si alguna línea tiene un precio asignado y lo propagamos a las demás
        for tmpl in self.order_line.mapped('product_id.product_tmpl_id'):
            # Filtramos las líneas que pertenezcan a este product.template
            lines = self.order_line.filtered(lambda l: l.product_id.product_tmpl_id == tmpl)
            # Buscamos un precio definido (distinto de 0) en alguna de las líneas
            defined_price = next((l.price_unit for l in lines if l.price_unit and l.price_unit != 0), False)
            if defined_price:
                for line in lines:
                    if not line.price_unit or line.price_unit == 0:
                        _logger.info(f"Propagando precio {defined_price} en línea {line.id if line.id else 'nueva'}")
                        line.price_unit = defined_price
        return {}

    
    