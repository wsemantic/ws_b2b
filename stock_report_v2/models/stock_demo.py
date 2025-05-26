# models/stock_demo_simple.py
import random
from odoo import models, api


class StockDemoSimple(models.TransientModel):
    _name = 'stock.demo.simple'
    _description = 'Stock Demo Simple'

    @api.model
    def generate_stock_demo(self):
        """Genera stock demo con un solo clic"""
        
        # Buscar productos con variantes
        templates = self.env['product.template'].search([
            ('product_variant_count', '>', 1),
            ('detailed_type', '=', 'product')
        ])
        
        if not templates:
            return {'type': 'ir.actions.act_window_close'}
        
        # Buscar ubicaciones
        locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', self.env.company.id)
        ])
        
        # Identificar central
        central = locations.filtered(lambda l: 'central' in l.name.lower())
        central = central[0] if central else locations[0]
        delegaciones = locations - central
        
        # Generar stock
        count = 0
        for template in templates:
            for variant in template.product_variant_ids:
                
                # Central (70% probabilidad)
                if random.random() > 0.3:
                    qty = random.randint(50, 500)
                    self.env['stock.quant'].create({
                        'product_id': variant.id,
                        'location_id': central.id,
                        'quantity': qty,
                        'reserved_quantity': 0,
                    })
                    count += 1
                
                # Delegaciones
                for delegacion in delegaciones:
                    if random.random() > 0.3:
                        qty = random.randint(0, 50)
                        if qty > 0:  # Solo crear si cantidad > 0
                            self.env['stock.quant'].create({
                                'product_id': variant.id,
                                'location_id': delegacion.id,
                                'quantity': qty,
                                'reserved_quantity': 0,
                            })
                            count += 1
        
        # Mostrar resultado
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Stock Demo Generado',
                'message': f'{count} quants creados exitosamente',
                'type': 'success',
                'sticky': False,
            }
        }