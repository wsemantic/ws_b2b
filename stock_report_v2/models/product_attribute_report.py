# -*- coding: utf-8 -*-

from odoo import api, models, fields, tools, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ProductAttributeReport(models.Model):
    _name = 'product.attribute.report'
    _description = 'Product Attribute Report'
    _auto = False
    _rec_name = 'product_name'
    _order = 'product_name, attribute_name'

    id = fields.Integer(readonly=True)
    product_id = fields.Many2one('product.product', string='Product Variant', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    default_code = fields.Char(string='Internal Reference', readonly=True)
    attribute_id = fields.Many2one('product.attribute', string='Attribute', readonly=True)
    attribute_name = fields.Char(string='Attribute Name', readonly=True)
    attribute_value_id = fields.Many2one('product.attribute.value', string='Attribute Value', readonly=True)
    attribute_value = fields.Char(string='Attribute Value', readonly=True)
    qty_available = fields.Float(string='Quantity On Hand', readonly=True, digits='Product Unit of Measure')
    virtual_available = fields.Float(string='Forecast Quantity', readonly=True, digits='Product Unit of Measure')
    incoming_qty = fields.Float(string='Incoming', readonly=True, digits='Product Unit of Measure')
    outgoing_qty = fields.Float(string='Outgoing', readonly=True, digits='Product Unit of Measure')
    reserved_qty = fields.Float(string='Reserved', readonly=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH stock_data AS (
                    SELECT 
                        sq.product_id,
                        SUM(sq.quantity) as qty_available,
                        SUM(sq.reserved_quantity) as reserved_qty
                    FROM stock_quant sq
                    JOIN stock_location sl ON sq.location_id = sl.id
                    WHERE sl.usage = 'internal'
                    GROUP BY sq.product_id
                ),
                incoming_data AS (
                    SELECT
                        product_id,
                        SUM(product_qty) as incoming_qty
                    FROM stock_move
                    WHERE state IN ('assigned', 'confirmed', 'waiting')
                      AND location_dest_id IN (SELECT id FROM stock_location WHERE usage = 'internal')
                      AND location_id NOT IN (SELECT id FROM stock_location WHERE usage = 'internal')
                    GROUP BY product_id
                ),
                outgoing_data AS (
                    SELECT
                        product_id,
                        SUM(product_qty) as outgoing_qty
                    FROM stock_move
                    WHERE state IN ('assigned', 'confirmed', 'waiting')
                      AND location_id IN (SELECT id FROM stock_location WHERE usage = 'internal')
                      AND location_dest_id NOT IN (SELECT id FROM stock_location WHERE usage = 'internal')
                    GROUP BY product_id
                )
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    pp.id AS product_id,
                    pt.id AS product_tmpl_id,
                    pt.name AS product_name,
                    pp.default_code AS default_code,
                    pa.id AS attribute_id,
                    pa.name AS attribute_name,
                    pav.id AS attribute_value_id,
                    pav.name AS attribute_value,
                    COALESCE(sd.qty_available, 0) AS qty_available,
                    COALESCE(sd.qty_available, 0) + COALESCE(id.incoming_qty, 0) - COALESCE(od.outgoing_qty, 0) AS virtual_available,
                    COALESCE(id.incoming_qty, 0) AS incoming_qty, 
                    COALESCE(od.outgoing_qty, 0) AS outgoing_qty,
                    COALESCE(sd.reserved_qty, 0) AS reserved_qty,
                    pt.uom_id AS uom_id
                FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_template_attribute_value ptav ON ptav.product_tmpl_id = pt.id AND ptav.product_attribute_value_id IS NOT NULL
                LEFT JOIN product_attribute_value pav ON ptav.product_attribute_value_id = pav.id
                LEFT JOIN product_attribute pa ON pav.attribute_id = pa.id
                LEFT JOIN stock_data sd ON pp.id = sd.product_id
                LEFT JOIN incoming_data id ON pp.id = id.product_id
                LEFT JOIN outgoing_data od ON pp.id = od.product_id
                WHERE pt.active = true AND pt.type = 'product'
            )
        """ % self._table)

    @api.model
    def get_report_data_by_config(self, config_id):
        """Get report data based on configuration ID with pagination support using read_group"""
        try:
            config = self.env['stock.report.config'].browse(config_id)
            if not config.exists():
                return self._get_empty_response()

            params = self.env.context.get('params', {})
            page = max(1, int(params.get('page', 1)))
            page_size = max(1, int(params.get('page_size', 20)))
            search_term = (params.get('search_term', '') or '').strip()
            
            # Get the use_forecast setting from the config
            use_forecast = config.use_forecast

            domain = self._get_search_domain(config, search_term)

            total_count = self.env['product.template'].search_count(domain)
            total_pages = (total_count + page_size - 1) // page_size if total_count else 1

            offset = (page - 1) * page_size
            product_templates = self.env['product.template'].search(
                domain, 
                order='name',
                limit=page_size,
                offset=offset
            )

            if not product_templates:
                return self._get_empty_response()

            variants = self.env['product.product'].search([
                ('product_tmpl_id', 'in', product_templates.ids)
            ])

            stock_data = self._get_stock_data(variants.ids, use_forecast)
            attributes = self._get_attribute_data([config.primary_attribute_id, config.secondary_attribute_id])
            products_data = self._prepare_products_data(
                product_templates, 
                variants, 
                stock_data, 
                config
            )

            return {
                'products': products_data,
                'attributes': attributes,
                'pagination': {
                    'total': total_count,
                    'page': page,
                    'page_size': page_size,
                    'pages': total_pages
                }
            }

        except Exception as e:
            _logger.error("Error in get_report_data_by_config: %s", str(e))
            return {
                'error': str(e),
                'products': [],
                'attributes': [],
                'pagination': {'total': 0, 'page': 1, 'page_size': 20, 'pages': 1}
            }

    def _get_empty_response(self):
        return {
            'products': [],
            'attributes': [],
            'pagination': {'total': 0, 'page': 1, 'page_size': 20, 'pages': 1}
        }

    def _get_search_domain(self, config, search_term):
        domain = [('type', '=', 'product'), ('active', '=', True)]

        if config.primary_attribute_id or config.secondary_attribute_id:
            domain.append('|')
            if config.primary_attribute_id:
                domain.append(('attribute_line_ids.attribute_id', '=', config.primary_attribute_id.id))
            if config.secondary_attribute_id:
                domain.append(('attribute_line_ids.attribute_id', '=', config.secondary_attribute_id.id))

        if search_term:
            domain.append('|')
            domain.append(('name', 'ilike', search_term))
            domain.append(('default_code', 'ilike', search_term))

        return domain

    def _get_stock_data(self, variant_ids, use_forecast=False):
        """
        Get detailed stock data for variants, including correct incoming and outgoing quantities.
        If use_forecast is True, virtual_available will be calculated as:
        qty_available + incoming_qty - outgoing_qty
        """
        stock_data = {}
        
        # Initialize stock data structure for all variants to ensure consistency
        for variant_id in variant_ids:
            stock_data[variant_id] = {
                'qty_available': 0.0,
                'reserved_qty': 0.0,
                'incoming_qty': 0.0,
                'outgoing_qty': 0.0,
                'virtual_available': 0.0
            }

        # Get quants data (on-hand quantities)
        quant_data = self.env['stock.quant'].read_group(
            [
                ('product_id', 'in', variant_ids),
                ('location_id.usage', '=', 'internal')
            ],
            ['product_id', 'quantity:sum', 'reserved_quantity:sum'],
            ['product_id']
        )

        for item in quant_data:
            product_id = item['product_id'][0]
            qty_available = item['quantity'] or 0.0
            reserved_qty = item['reserved_quantity'] or 0.0
            
            stock_data[product_id].update({
                'qty_available': qty_available,
                'reserved_qty': reserved_qty,
                'virtual_available': qty_available  # Initialize with on-hand qty
            })

        # Get incoming moves - all expected incoming stock
        incoming_domain = [
            ('product_id', 'in', variant_ids),
            ('state', 'in', ['assigned', 'confirmed', 'waiting']),
            ('location_dest_id.usage', '=', 'internal'),
            ('location_id.usage', '!=', 'internal')
        ]
        
        incoming_data = self.env['stock.move'].read_group(
            incoming_domain,
            ['product_id', 'product_qty:sum'],
            ['product_id']
        )

        for item in incoming_data:
            product_id = item['product_id'][0]
            incoming_qty = item['product_qty'] or 0.0
            stock_data[product_id]['incoming_qty'] = incoming_qty
            
            if use_forecast:
                stock_data[product_id]['virtual_available'] += incoming_qty

        # Get outgoing moves - all expected outgoing stock 
        outgoing_domain = [
            ('product_id', 'in', variant_ids),
            ('state', 'in', ['assigned', 'confirmed', 'waiting']),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '!=', 'internal')
        ]
        
        outgoing_data = self.env['stock.move'].read_group(
            outgoing_domain,
            ['product_id', 'product_qty:sum'],
            ['product_id']
        )

        for item in outgoing_data:
            product_id = item['product_id'][0]
            outgoing_qty = item['product_qty'] or 0.0
            stock_data[product_id]['outgoing_qty'] = outgoing_qty
            
            if use_forecast:
                stock_data[product_id]['virtual_available'] -= outgoing_qty

        # For products that don't have any inventory records, ensure we return the structure
        for variant_id in variant_ids:
            if variant_id not in stock_data:
                stock_data[variant_id] = {
                    'qty_available': 0.0,
                    'reserved_qty': 0.0,
                    'incoming_qty': 0.0,
                    'outgoing_qty': 0.0,
                    'virtual_available': 0.0
                }

        return stock_data

    def _get_attribute_data(self, attributes):
        return [{
            'id': attr.id,
            'name': attr.name,
            'values': [{
                'id': val.id,
                'name': val.name,
                'display_name': val.display_name
            } for val in attr.value_ids]
        } for attr in attributes if attr]

    def _prepare_products_data(self, product_templates, variants, stock_data, config):
        """
        Prepare detailed product data for the report, respecting the config settings.
        Handles both standard and forecasted quantities correctly.
        """
        products_data = []
        use_forecast = config.use_forecast

        for template in product_templates:
            template_variants = variants.filtered(lambda v: v.product_tmpl_id == template)
            
            # Skip processing if no variants were found
            if not template_variants:
                continue
                
            # Apply filters based on configuration
            if config.filter_zero:
                # Check if all variants have zero quantity (based on display mode)
                qty_field = 'virtual_available' if use_forecast else 'qty_available'
                if all(
                    stock_data.get(v.id, {}).get(qty_field, 0) == 0 
                    for v in template_variants
                ):
                    continue

            if not config.include_negative:
                # Skip if any variant has negative quantity (based on display mode)
                qty_field = 'virtual_available' if use_forecast else 'qty_available'
                if any(
                    stock_data.get(v.id, {}).get(qty_field, 0) < 0 
                    for v in template_variants
                ):
                    continue

            variant_data = []
            for variant in template_variants:
                stock = stock_data.get(variant.id, {})
                
                # Get the appropriate quantity based on the use_forecast setting
                display_qty = stock.get('virtual_available', 0) if use_forecast else stock.get('qty_available', 0)
                
                variant_data.append({
                    'id': variant.id,
                    'name': variant.name,
                    'default_code': variant.default_code,
                    'qty_available': stock.get('qty_available', 0),
                    'virtual_available': stock.get('virtual_available', 0),
                    'display_qty': display_qty,  # This is what will be displayed
                    'qty_reserved': stock.get('reserved_qty', 0),
                    'incoming_qty': stock.get('incoming_qty', 0),
                    'outgoing_qty': stock.get('outgoing_qty', 0),
                    'image_url': variant.image_1920 and f'/web/image/product.product/{variant.id}/image_1920' or False,
                    'product_url': f'/web#id={variant.id}&model=product.product&view_type=form',
                    'attributes': self._get_variant_attributes(variant)
                })

            products_data.append({
                'id': template.id,
                'name': template.name,
                'image_url': template.image_1920 and f'/web/image/product.template/{template.id}/image_1920' or False,
                'product_url': f'/web#id={template.id}&model=product.template&view_type=form',
                'variants': variant_data,
                'use_forecast': use_forecast  # Pass this to the frontend
            })

        return products_data

    def _get_variant_attributes(self, variant):
        return {
            str(attr.attribute_id.id): attr.product_attribute_value_id.id
            for attr in variant.product_template_attribute_value_ids
        }