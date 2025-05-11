# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    attribute_serie_id = fields.Many2one('attribute.serie', string='Serie Tallas')  

    @api.onchange('attribute_serie_id')
    def _onchange_attribute_serie_id(self):
        if self.attribute_serie_id:
            attribute_id = self.env['product.attribute'].search([('name', '=', 'Talla')], limit=1)
            if attribute_id:
                existing_line = self.attribute_line_ids.filtered(lambda line: line.attribute_id == attribute_id)

                # Obtener los valores de atributo ordenados por secuencia y nombre
                sorted_attribute_values = self.attribute_serie_id.item_ids.sorted(key=lambda item: (item.sequence or 0, item.attribute_value_id.name))
                attribute_value_ids = sorted_attribute_values.mapped('attribute_value_id').ids

                if existing_line:
                    _logger.info(f"WSEM existia linea serie")
                    existing_line.value_ids = [(6, 0, attribute_value_ids)]
                else:
                    _logger.info(f"WSEM creando serie")
                    self.attribute_line_ids = [(0, 0, {
                        'attribute_id': attribute_id.id,
                        'value_ids': [(6, 0, attribute_value_ids)]
                    })]
    
    @api.constrains('type', 'serie_tallas', 'list_price', 'seller_ids', 'attribute_line_ids')
    def _check_custom_fields(self):
        # Se ejecuta para cada producto
        for product in self:
            if product.type == 'product':  # Solo para productos almacenable
                # Validar que se haya completado el campo serie_tallas
                if not product.attribute_serie_id:
                    raise ValidationError(_("Para los productos almacenable, el campo 'Serie Tallas' es obligatorio."))

                # Validar que se haya ingresado un precio de venta mayor que cero
                if not product.list_price or product.list_price <= 0:
                    raise ValidationError(_("Para los productos almacenable, el precio de venta debe ser mayor que cero."))
                '''
                if not product.seller_ids:
                    raise ValidationError(_(
                        "Para los productos almacenable debe existir al menos un registro de precio de compra en los Proveedores."
                    ))
                # Opcional: verifica que al menos uno de los registros tenga un precio mayor que cero
                if not any(s.price > 0 for s in product.seller_ids):
                    raise ValidationError(_(
                        "Para los productos almacenable, al menos uno de los registros en Proveedores debe tener un precio de compra mayor que cero."
                    ))
                '''
                # Validar que exista al menos una línea de atributo para el Color
                # Suponiendo que tienes un atributo para Color y que puedes obtener su referencia,
                # por ejemplo, mediante un XML ID en tu módulo:
                color_lines = product.attribute_line_ids.filtered(lambda l: l.attribute_id.name.lower() == 'color')
                if not color_lines or not any(line.value_ids for line in color_lines):
                    raise ValidationError(_("Debe agregarse al menos un valor para el atributo 'Color' en el producto."))                   


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.depends('name', 'default_code', 'product_template_attribute_value_ids')
    def _compute_display_name(self):
        super()._compute_display_name()
        for product in self:
            base_name = product.display_name.split(" (")[0]

            attribute_values = product.product_template_attribute_value_ids.mapped('name')
            if attribute_values:
                combo = ", ".join(attribute_values)
                product.display_name = "%s (%s)" % (base_name, combo)
            else:
                product.display_name = base_name

