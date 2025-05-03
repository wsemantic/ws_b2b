# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class ProductAttributeReport(models.Model):
    _name = 'product.attribute.report'
    _description = 'Product Attribute Report'
    _auto = False
    _rec_name = 'product_name'
    _order = 'product_name, attribute_name, attribute_value'

    # Core fields
    id = fields.Integer(readonly=True)
    product_id = fields.Many2one('product.product', string='Product Variant', readonly=True)
    product_template_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    product_default_code = fields.Char(string='Internal Reference', readonly=True)
    
    # Essential stock quantities
    qty_available = fields.Float(string='Quantity On Hand', readonly=True, digits='Product Unit of Measure')
    virtual_available = fields.Float(string='Forecast Quantity', readonly=True, digits='Product Unit of Measure')
    reserved_qty = fields.Float(string='Reserved', readonly=True, digits='Product Unit of Measure')
    
    # Essential attribute fields
    attribute_id = fields.Many2one('product.attribute', string='Attribute', readonly=True)
    attribute_name = fields.Char(string='Attribute Name', readonly=True)
    attribute_value = fields.Char(string='Value', readonly=True)
    
    # Status indicator
    stock_status = fields.Selection([
        ('in_stock', 'In Stock'),
        ('reserved', 'Reserved'),
        ('out_of_stock', 'Out of Stock')
    ], string='Stock Status', compute='_compute_stock_status', store=False, readonly=True)

    @api.depends('qty_available', 'reserved_qty')
    def _compute_stock_status(self):
        for record in self:
            if record.qty_available > record.reserved_qty:
                record.stock_status = 'in_stock'
            elif record.reserved_qty > 0:
                record.stock_status = 'reserved'
            else:
                record.stock_status = 'out_of_stock'

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW product_attribute_report AS (
                WITH stock_data AS (
                    SELECT 
                        sq.product_id,
                        SUM(CASE WHEN sq.reserved_quantity = 0 THEN sq.quantity ELSE 0 END) as qty_available,
                        SUM(sq.reserved_quantity) as reserved_qty
                    FROM stock_quant sq
                    JOIN stock_location sl ON sq.location_id = sl.id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                )
                
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    pp.id AS product_id,
                    pp.product_tmpl_id AS product_template_id,
                    pp.default_code AS product_default_code,
                    pt.name AS product_name,
                    pa.id AS attribute_id,
                    pa.name AS attribute_name,
                    pav.name AS attribute_value,
                    COALESCE(sd.qty_available, 0) AS qty_available,
                    COALESCE(sd.qty_available - sd.reserved_qty, 0) AS virtual_available,
                    COALESCE(sd.reserved_qty, 0) AS reserved_qty
                FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                JOIN product_template_attribute_value ptav ON pt.id = ptav.product_tmpl_id
                JOIN product_attribute_value pav ON ptav.product_attribute_value_id = pav.id
                JOIN product_attribute pa ON pav.attribute_id = pa.id
                LEFT JOIN stock_data sd ON pp.id = sd.product_id
                WHERE pt.active = true
            )
        """)

    @api.model
    def get_real_stock_report_data(self):
        result = {'products': []}
        
        product_templates = self.env['product.template'].search([
            ('active', '=', True),
            ('type', '=', 'product')
        ])
        
        for template in product_templates:
            variants = template.product_variant_ids.filtered(lambda v: v.type == 'product')
            
            if not variants:
                continue
                
            if not template.attribute_line_ids:
                template_image = False
                if template.image_1920:
                    try:
                        template_image = template.image_1920.decode('utf-8')
                    except:
                        template_image = False
                        
                product_data = {
                    'id': template.id,
                    'name': template.name,
                    'product_url': f'/web#id={template.id}&model=product.template&view_type=form',
                    'image': template_image,
                    'primary_attribute': {
                        'name': 'No Attribute',
                        'values': [{'name': 'No Variant', 'color': '#CCCCCC'}]
                    },
                    'secondary_attribute': {
                        'name': 'No Attribute',
                        'values': ['No Variant']
                    },
                    'variants': []
                }
                
                for variant in variants:
                    qty_available = variant.qty_available
                    reserved = variant.reserved_quantity if hasattr(variant, 'reserved_quantity') else 0
                    incoming = variant.incoming_qty if hasattr(variant, 'incoming_qty') else 0
                    outgoing = variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                    
                    qty_type = 'available'
                    if reserved > 0:
                        qty_type = 'reserved'
                    
                    variant_image = False
                    if variant.image_1920:
                        try:
                            variant_image = variant.image_1920.decode('utf-8')
                        except:
                            variant_image = False
                    
                    product_data['variants'].append({
                        'color': 'No Variant',
                        'size': 'No Variant',
                        'qty': qty_available,
                        'qty_type': qty_type,
                        'image': variant_image or template_image,
                        'reserved_qty': reserved,
                        'incoming_qty': incoming,
                        'outgoing_qty': outgoing,
                        'product_url': f'/web#id={variant.id}&model=product.product&view_type=form'
                    })
                
                if product_data['variants']:
                    result['products'].append(product_data)
                continue
            
            if len(template.attribute_line_ids) == 1:
                attribute_line = template.attribute_line_ids[0]
                attribute = attribute_line.attribute_id
                
                primary_values = []
                for value in attribute_line.value_ids:
                    primary_values.append({
                        'name': value.name,
                        'color': value.html_color or '#CCCCCC'
                    })
                
                template_image = False
                if template.image_1920:
                    try:
                        template_image = template.image_1920.decode('utf-8')
                    except:
                        template_image = False
                        
                product_data = {
                    'id': template.id,
                    'name': template.name,
                    'product_url': f'/web#id={template.id}&model=product.template&view_type=form',
                    'image': template_image,
                    'primary_attribute': {
                        'name': attribute.name,
                        'values': primary_values
                    },
                    'secondary_attribute': {
                        'name': 'No Attribute',
                        'values': ['No Variant']
                    },
                    'variants': []
                }
                
                for variant in variants:
                    primary_value = None
                    for ptav in variant.product_template_attribute_value_ids:
                        if ptav.attribute_id.id == attribute.id:
                            primary_value = ptav.product_attribute_value_id.name
                            break
                    
                    if not primary_value:
                        continue
                    
                    qty_available = variant.qty_available
                    reserved = variant.reserved_quantity if hasattr(variant, 'reserved_quantity') else 0
                    incoming = variant.incoming_qty if hasattr(variant, 'incoming_qty') else 0
                    outgoing = variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                    
                    qty_type = 'available'
                    if reserved > 0:
                        qty_type = 'reserved'
                    
                    variant_image = False
                    if variant.image_1920:
                        try:
                            variant_image = variant.image_1920.decode('utf-8')
                        except:
                            variant_image = False
                    
                    product_data['variants'].append({
                        'color': primary_value,
                        'size': 'No Variant',
                        'qty': qty_available,
                        'qty_type': qty_type,
                        'image': variant_image or template_image,
                        'reserved_qty': reserved,
                        'incoming_qty': incoming,
                        'outgoing_qty': outgoing,
                        'product_url': f'/web#id={variant.id}&model=product.product&view_type=form'
                    })
                
                if product_data['variants']:
                    result['products'].append(product_data)
                continue
            
            attribute_lines = template.attribute_line_ids
            primary_attr = None
            secondary_attr = None
            
            color_attr_line = attribute_lines.filtered(
                lambda l: 'color' in l.attribute_id.name.lower() or 'colour' in l.attribute_id.name.lower()
            )
            if color_attr_line:
                primary_attr = color_attr_line[0].attribute_id
                
            size_attr_line = attribute_lines.filtered(
                lambda l: 'size' in l.attribute_id.name.lower()
            )
            if size_attr_line:
                secondary_attr = size_attr_line[0].attribute_id
            
            if not primary_attr and attribute_lines:
                primary_attr = attribute_lines[0].attribute_id
                
            if not secondary_attr and len(attribute_lines) > 1:
                for line in attribute_lines:
                    if line.attribute_id.id != primary_attr.id:
                        secondary_attr = line.attribute_id
                        break
            
            if not primary_attr or not secondary_attr:
                continue
                
            primary_values = []
            primary_line = attribute_lines.filtered(lambda l: l.attribute_id.id == primary_attr.id)
            if primary_line:
                for value in primary_line[0].value_ids:
                    primary_values.append({
                        'name': value.name,
                        'color': value.html_color or '#CCCCCC'
                    })
            
            secondary_values = []
            secondary_line = attribute_lines.filtered(lambda l: l.attribute_id.id == secondary_attr.id)
            if secondary_line:
                for value in secondary_line[0].value_ids:
                    secondary_values.append(value.name)
            
            template_image = False
            if template.image_1920:
                try:
                    template_image = template.image_1920.decode('utf-8')
                except:
                    template_image = False
                    
            product_data = {
                'id': template.id,
                'name': template.name,
                'product_url': f'/web#id={template.id}&model=product.template&view_type=form',
                'image': template_image,
                'primary_attribute': {
                    'name': primary_attr.name,
                    'values': primary_values
                },
                'secondary_attribute': {
                    'name': secondary_attr.name,
                    'values': secondary_values
                },
                'variants': []
            }
            
            primary_value_map = {}
            for primary_value in primary_line[0].value_ids:
                primary_value_map[primary_value.id] = primary_value.name
                
            secondary_value_map = {}
            for secondary_value in secondary_line[0].value_ids:
                secondary_value_map[secondary_value.id] = secondary_value.name
            
            for variant in variants:
                primary_value = None
                secondary_value = None
                
                for ptav in variant.product_template_attribute_value_ids:
                    attribute_id = ptav.attribute_id.id
                    value_id = ptav.product_attribute_value_id.id
                    
                    if attribute_id == primary_attr.id:
                        primary_value = primary_value_map.get(value_id)
                    elif attribute_id == secondary_attr.id:
                        secondary_value = secondary_value_map.get(value_id)
                
                if not primary_value or not secondary_value:
                    continue
                
                qty_available = variant.qty_available
                reserved = variant.reserved_quantity if hasattr(variant, 'reserved_quantity') else 0
                incoming = variant.incoming_qty if hasattr(variant, 'incoming_qty') else 0
                outgoing = variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                
                qty_type = 'available'
                if reserved > 0:
                    qty_type = 'reserved'
                
                variant_image = False
                if variant.image_1920:
                    try:
                        variant_image = variant.image_1920.decode('utf-8')
                    except:
                        variant_image = False
                
                product_data['variants'].append({
                    'color': primary_value,
                    'size': secondary_value,
                    'qty': qty_available,
                    'qty_type': qty_type,
                    'image': variant_image or template_image,
                    'reserved_qty': reserved,
                    'incoming_qty': incoming,
                    'outgoing_qty': outgoing,
                    'product_url': f'/web#id={variant.id}&model=product.product&view_type=form'
                })
            
            if product_data['variants']:
                result['products'].append(product_data)
        
        return result
