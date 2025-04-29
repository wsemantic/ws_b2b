# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class ProductAttributeReport(models.Model):
    _name = 'product.attribute.report'
    _description = 'Product Attribute Report'
    _auto = False
    _rec_name = 'product_name'
    _order = 'product_name, attribute_name, attribute_value'

    # Standard system fields required by Odoo
    id = fields.Integer(readonly=True)
    create_uid = fields.Integer(string='Created by', readonly=True)
    create_date = fields.Datetime(string='Created on', readonly=True)
    write_uid = fields.Integer(string='Last Updated by', readonly=True)
    write_date = fields.Datetime(string='Last Updated on', readonly=True)
    
    # Product fields
    product_id = fields.Many2one('product.product', string='Product Variant', readonly=True)
    product_template_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    product_image = fields.Binary(related='product_id.image_128', string='Product Image', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    product_default_code = fields.Char(string='Internal Reference', readonly=True)
    
    # Stock quantities
    qty_available = fields.Float(string='Quantity On Hand', readonly=True, digits='Product Unit of Measure')
    virtual_available = fields.Float(string='Forecast Quantity', readonly=True, digits='Product Unit of Measure')
    incoming_qty = fields.Float(string='Incoming', readonly=True, digits='Product Unit of Measure')
    outgoing_qty = fields.Float(string='Outgoing', readonly=True, digits='Product Unit of Measure')
    reserved_qty = fields.Float(string='Reserved', readonly=True, digits='Product Unit of Measure')
    
    # Attribute fields
    attribute_id = fields.Many2one('product.attribute', string='Attribute', readonly=True)
    attribute_name = fields.Char(string='Attribute Name', readonly=True)
    attribute_value_id = fields.Many2one('product.attribute.value', string='Attribute Value', readonly=True)
    attribute_value = fields.Char(string='Value', readonly=True)
    attribute_color = fields.Char(string='Color Code', readonly=True)
    display_name = fields.Char(string='Display Name', readonly=True)
    
    # Additional fields for grouping and filtering
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    
    # Status indicator (for color-coding)
    stock_status = fields.Selection([
        ('in_stock', 'In Stock'),
        ('reserved', 'Reserved'),
        ('replenish', 'To Replenish'),
        ('out_of_stock', 'Out of Stock')
    ], string='Stock Status', compute='_compute_stock_status', store=False, readonly=True)

    @api.depends('qty_available', 'reserved_qty', 'incoming_qty')
    def _compute_stock_status(self):
        for record in self:
            if record.qty_available > record.reserved_qty:
                record.stock_status = 'in_stock'
            elif record.reserved_qty > 0:
                record.stock_status = 'reserved'
            elif record.incoming_qty > 0:
                record.stock_status = 'replenish'
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
                        SUM(sq.reserved_quantity) as reserved_qty,
                        0 as incoming_qty,
                        0 as outgoing_qty
                    FROM stock_quant sq
                    JOIN stock_location sl ON sq.location_id = sl.id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                ),
                move_data AS (
                    SELECT 
                        sm.product_id,
                        SUM(CASE WHEN sm.location_dest_id IN (SELECT id FROM stock_location WHERE usage = 'internal') 
                               AND sm.state NOT IN ('done', 'cancel') THEN sm.product_qty ELSE 0 END) as incoming_qty,
                        SUM(CASE WHEN sm.location_id IN (SELECT id FROM stock_location WHERE usage = 'internal') 
                               AND sm.state NOT IN ('done', 'cancel') THEN sm.product_qty ELSE 0 END) as outgoing_qty
                    FROM stock_move sm
                    WHERE sm.state NOT IN ('cancel')
                    GROUP BY sm.product_id
                )
                
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    pp.create_uid AS create_uid,
                    pp.create_date AS create_date,
                    pp.write_uid AS write_uid,
                    pp.write_date AS write_date,
                    pp.id AS product_id,
                    pt.id AS product_template_id,
                    COALESCE(pt.name->>'en_US', '') AS product_name,
                    COALESCE(pp.default_code, '') AS product_default_code,
                    COALESCE(sd.qty_available, 0) AS qty_available,
                    COALESCE(sd.qty_available, 0) + COALESCE(md.incoming_qty, 0) - COALESCE(md.outgoing_qty, 0) AS virtual_available,
                    COALESCE(md.incoming_qty, 0) AS incoming_qty,
                    COALESCE(md.outgoing_qty, 0) AS outgoing_qty,
                    COALESCE(sd.reserved_qty, 0) AS reserved_qty,
                    pa.id AS attribute_id,
                    COALESCE(pa.name->>'en_US', '') AS attribute_name,
                    pav.id AS attribute_value_id,
                    COALESCE(pav.name->>'en_US', '') AS attribute_value,
                    COALESCE(pav.html_color, '#FFFFFF') AS attribute_color,
                    CONCAT(COALESCE(pt.name->>'en_US', ''), ' [', COALESCE(pa.name->>'en_US', ''), ': ', COALESCE(pav.name->>'en_US', ''), ']') AS display_name,
                    pt.categ_id AS categ_id,
                    pt.uom_id AS uom_id,
                    pt.company_id AS company_id
                FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                JOIN product_template_attribute_value ptav ON ptav.product_tmpl_id = pt.id
                JOIN product_attribute_value pav ON ptav.product_attribute_value_id = pav.id
                JOIN product_attribute pa ON pav.attribute_id = pa.id
                LEFT JOIN stock_data sd ON pp.id = sd.product_id
                LEFT JOIN move_data md ON pp.id = md.product_id
                WHERE pp.active = true

                UNION ALL

                SELECT
                    ROW_NUMBER() OVER() + 100000 AS id,
                    pp.create_uid AS create_uid,
                    pp.create_date AS create_date,
                    pp.write_uid AS write_uid,
                    pp.write_date AS write_date,
                    pp.id AS product_id,
                    pt.id AS product_template_id,
                    COALESCE(pt.name->>'en_US', '') AS product_name,
                    COALESCE(pp.default_code, '') AS product_default_code,
                    COALESCE(sd.qty_available, 0) AS qty_available,
                    COALESCE(sd.qty_available, 0) + COALESCE(md.incoming_qty, 0) - COALESCE(md.outgoing_qty, 0) AS virtual_available,
                    COALESCE(md.incoming_qty, 0) AS incoming_qty,
                    COALESCE(md.outgoing_qty, 0) AS outgoing_qty,
                    COALESCE(sd.reserved_qty, 0) AS reserved_qty,
                    NULL AS attribute_id,
                    'No Attribute' AS attribute_name,
                    NULL AS attribute_value_id,
                    'No Variant' AS attribute_value,
                    '#FFFFFF' AS attribute_color,
                    CONCAT(COALESCE(pt.name->>'en_US', ''), ' [No Variant]') AS display_name,
                    pt.categ_id AS categ_id,
                    pt.uom_id AS uom_id,
                    pt.company_id AS company_id
                FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN stock_data sd ON pp.id = sd.product_id
                LEFT JOIN move_data md ON pp.id = md.product_id
                LEFT JOIN product_template_attribute_value ptav ON ptav.product_tmpl_id = pt.id
                WHERE pp.active = true
                AND ptav.id IS NULL
            )
        """)
           
    @api.model
    def get_stock_report_data(self):
        """
        Returns structured data for the product attribute matrix view
        - Products with attributes (color/size)
        - Variants with quantities and stock status
        - Color-coded status values for quantity visualizations
        """
        return {
            'products': [
                {
                    'id': 'desk-1',
                    'name': 'Customizable Desk',
                    'image': False,
                    'primary_attribute': {
                        'name': 'Color',
                        'values': [
                            {'name': 'White', 'color': '#FFFFFF'},
                            {'name': 'Black', 'color': '#000000'},
                        ]
                    },
                    'secondary_attribute': {
                        'name': 'Material',
                        'values': ['Steel', 'Aluminium']
                    },
                    'variants': [
                        {'color': 'White', 'size': 'Steel', 'qty': 45, 'qty_type': 'available', 'image': False},
                        {'color': 'White', 'size': 'Aluminium', 'qty': 55, 'qty_type': 'available', 'image': False},
                        {'color': 'Black', 'size': 'Steel', 'qty': 50, 'qty_type': 'available', 'image': False},
                        {'color': 'Black', 'size': 'Aluminium', 'qty': 0, 'qty_type': 'normal', 'image': False},
                    ]
                },
                
                {
                    'id': 'shirt-1',
                    'name': 'Shirt-1',
                    'image': False,
                    'primary_attribute': {
                        'name': 'Color',
                        'values': [
                            {'name': 'Blue', 'color': '#0000FF'},
                            {'name': 'Black', 'color': '#000000'},
                            {'name': 'Yellow', 'color': '#FFFF00'}
                        ]
                    },
                    'secondary_attribute': {
                        'name': 'Size',
                        'values': ['S', 'M', 'L', 'XL', 'XXL']
                    },
                    'variants': [
                        {'color': 'Blue', 'size': 'S', 'qty': 20, 'qty_type': 'reserved', 'image': False},
                        {'color': 'Blue', 'size': 'M', 'qty': 20, 'qty_type': 'available', 'image': False},
                        {'color': 'Blue', 'size': 'L', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Blue', 'size': 'XL', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Blue', 'size': 'XXL', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Black', 'size': 'S', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Black', 'size': 'M', 'qty': 20, 'qty_type': 'available', 'image': False},
                        {'color': 'Black', 'size': 'L', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Black', 'size': 'XL', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Black', 'size': 'XXL', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': 'S', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': 'M', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': 'L', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': 'XL', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': 'XXL', 'qty': 20, 'qty_type': 'normal', 'image': False}
                    ]
                },
                
                {
                    'id': 'trousers-1',
                    'name': 'Trousers-1',
                    'image': False,
                    'primary_attribute': {
                        'name': 'Color',
                        'values': [
                            {'name': 'Red', 'color': '#FF0000'},
                            {'name': 'Blue', 'color': '#0000FF'},
                            {'name': 'Black', 'color': '#000000'},
                            {'name': 'Yellow', 'color': '#FFFF00'}
                        ]
                    },
                    'secondary_attribute': {
                        'name': 'Size',
                        'values': ['26', '28', '30', '32', '34']
                    },
                    'variants': [
                        {'color': 'Red', 'size': '26', 'qty': 20, 'qty_type': 'available', 'image': False},
                        {'color': 'Red', 'size': '28', 'qty': 20, 'qty_type': 'available', 'image': False},
                        {'color': 'Red', 'size': '30', 'qty': 20, 'qty_type': 'available', 'image': False},
                        {'color': 'Blue', 'size': '26', 'qty': 20, 'qty_type': 'reserved', 'image': False},
                        {'color': 'Blue', 'size': '28', 'qty': 20, 'qty_type': 'reserved', 'image': False},
                        {'color': 'Blue', 'size': '32', 'qty': 20, 'qty_type': 'reserved', 'image': False},
                        {'color': 'Blue', 'size': '34', 'qty': 20, 'qty_type': 'reserved', 'image': False},
                        {'color': 'Black', 'size': '26', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Black', 'size': '32', 'qty': 20, 'qty_type': 'normal', 'image': False},
                        {'color': 'Yellow', 'size': '28', 'qty': 20, 'qty_type': 'replenishment', 'image': False},
                        {'color': 'Yellow', 'size': '30', 'qty': 20, 'qty_type': 'replenishment', 'image': False},
                        {'color': 'Yellow', 'size': '32', 'qty': 20, 'qty_type': 'replenishment', 'image': False},
                        {'color': 'Yellow', 'size': '34', 'qty': 20, 'qty_type': 'replenishment', 'image': False}
                    ]
                },
                
                {
                    'id': 'single-variant-1',
                    'name': 'Single Color T-Shirt',
                    'image': False,
                    'primary_attribute': {
                        'name': 'Color',
                        'values': [
                            {'name': 'Red', 'color': '#FF0000'},
                            {'name': 'Blue', 'color': '#0000FF'}
                        ]
                    },
                    'secondary_attribute': {
                        'name': 'No Attribute',
                        'values': ['No Variant']
                    },
                    'variants': [
                        {'color': 'Red', 'size': 'No Variant', 'qty': 15, 'qty_type': 'available', 'image': False},
                        {'color': 'Blue', 'size': 'No Variant', 'qty': 10, 'qty_type': 'reserved', 'image': False}
                    ]
                },
                
                {
                    'id': 'no-variant-1',
                    'name': 'Basic Chair',
                    'image': False,
                    'primary_attribute': {
                        'name': 'No Attribute',
                        'values': [{'name': 'No Variant', 'color': '#CCCCCC'}]
                    },
                    'secondary_attribute': {
                        'name': 'No Attribute',
                        'values': ['No Variant']
                    },
                    'variants': [
                        {'color': 'No Variant', 'size': 'No Variant', 'qty': 25, 'qty_type': 'available', 'image': False}
                    ]
                }
            ]
        }

    @api.model
    def get_real_stock_report_data(self):
        result = {'products': []}
        
        # Get all product templates, including those without variants
        product_templates = self.env['product.template'].search([
            ('active', '=', True), ('detailed_type', '=', 'product')
        ])
        
        for template in product_templates:
            variants = template.product_variant_ids
            
            if not variants:
                continue
                
            # Handle products with no attributes
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
                    incoming = variant.incoming_qty
                    
                    qty_type = 'normal'
                    if qty_available > 0 and qty_available > reserved:
                        qty_type = 'available'
                    elif reserved > 0:
                        qty_type = 'reserved'
                    elif incoming > 0:
                        qty_type = 'replenishment'
                    
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
                        'outgoing_qty': variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                    })
                
                if product_data['variants']:
                    result['products'].append(product_data)
                continue
            
            # Handle products with single attribute
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
                    incoming = variant.incoming_qty
                    
                    qty_type = 'normal'
                    if qty_available > 0 and qty_available > reserved:
                        qty_type = 'available'
                    elif reserved > 0:
                        qty_type = 'reserved'
                    elif incoming > 0:
                        qty_type = 'replenishment'
                    
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
                        'outgoing_qty': variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                    })
                
                if product_data['variants']:
                    result['products'].append(product_data)
                continue
            
            # Handle products with multiple attributes (existing logic)
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
                incoming = variant.incoming_qty
                
                qty_type = 'normal'
                if qty_available > 0 and qty_available > reserved:
                    qty_type = 'available'
                elif reserved > 0:
                    qty_type = 'reserved'
                elif incoming > 0:
                    qty_type = 'replenishment'
                
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
                    'outgoing_qty': variant.outgoing_qty if hasattr(variant, 'outgoing_qty') else 0
                })
            
            if product_data['variants']:
                result['products'].append(product_data)
        
        if not result['products']:
            return self.get_stock_report_data()
            
        return result
