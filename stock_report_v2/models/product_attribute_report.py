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


# ... existing code ...
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
        Get detailed stock data for variants:
        - Top-level fields reflect the location with highest quantity.
        - location_data key holds all warehouse-location-wise quantities.
        """
        stock_data = {}

        # Initialize stock data structure for all variants
        for variant_id in variant_ids:
            stock_data[variant_id] = {
                'qty_available': 0.0,
                'reserved_qty': 0.0,
                'incoming_qty': 0.0,
                'outgoing_qty': 0.0,
                'virtual_available': 0.0,
                'warehouse_name': '',
                'location_name': '',
                'location_data': []  # NEW: detailed data
            }

        # === MAIN LOGIC: Fetch location-wise stock ===
        self.env.cr.execute("""
        WITH quant_locations AS (
            SELECT
                sq.product_id,
                sl.id AS location_id,
                sl.name AS loc_name,
                parent.name AS parent_name,
                sl.parent_path,
                sl.company_id,
                SUM(sq.quantity) AS qty_available,
                SUM(sq.reserved_quantity) AS reserved_qty
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            LEFT JOIN stock_location parent ON sl.location_id = parent.id
            WHERE sq.product_id IN %s 
            AND sl.usage = 'internal'
            GROUP BY sq.product_id, sl.id, sl.name, parent.name, sl.parent_path, sl.company_id
        ),
        warehouse_map AS (
            SELECT 
                sw.name AS warehouse_name,
                sl.parent_path AS view_path,
                sw.company_id
            FROM stock_warehouse sw
            JOIN stock_location sl ON sw.view_location_id = sl.id
        ),
        with_warehouse AS (
            SELECT
                ql.product_id,
                ql.location_id,
                COALESCE(ql.parent_name || ' / ', '') || ql.loc_name AS location_name,
                ql.qty_available,
                ql.reserved_qty,
                COALESCE(wm.warehouse_name, 'Unassigned') AS warehouse_name
            FROM quant_locations ql
            LEFT JOIN warehouse_map wm 
                ON wm.company_id = ql.company_id
                AND ql.parent_path LIKE wm.view_path || '%%'
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY qty_available DESC) AS rn
            FROM with_warehouse
        )
        SELECT 
            product_id,
            location_id,
            location_name,
            warehouse_name,
            qty_available,
            reserved_qty,
            rn
        FROM ranked
        ORDER BY product_id, rn;
        """, (tuple(variant_ids),))

        rows = self.env.cr.dictfetchall()

        for row in rows:
            product_id = row['product_id']
            if product_id not in stock_data:
                continue  # safety check

            # Add full breakdown
            stock_data[product_id]['location_data'].append({
                'location_id': row['location_id'],
                'location_name': row['location_name'],
                'warehouse_name': row['warehouse_name'],
                'qty_available': row['qty_available'] or 0.0,
                'reserved_qty': row['reserved_qty'] or 0.0,
                'virtual_available': (row['qty_available'] or 0.0)
            })

            # Fill flat fields only for top-ranked location
            if row['rn'] == 1:
                stock_data[product_id].update({
                    'qty_available': row['qty_available'] or 0.0,
                    'reserved_qty': row['reserved_qty'] or 0.0,
                    'virtual_available': row['qty_available'] or 0.0,
                    'warehouse_name': row['warehouse_name'] or '',
                    'location_name': row['location_name'] or ''
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

        # Group templates by attribute series
        series_groups = {}
        for template in product_templates:
            serie_id = template.attribute_serie_id.id if template.attribute_serie_id else 0
            if serie_id not in series_groups:
                series_groups[serie_id] = {
                    'serie_id': serie_id,
                    'serie_name': template.attribute_serie_id.name if template.attribute_serie_id else _('No Series'),
                    'serie_values': template.attribute_serie_id.item_ids.mapped('attribute_value_id.name') if template.attribute_serie_id else [],
                    'templates': []
                }
            series_groups[serie_id]['templates'].append(template)

        # Process each series group
        for serie_group in series_groups.values():
            serie_products = []
            
            for template in serie_group['templates']:
                template_variants = variants.filtered(lambda v: v.product_tmpl_id == template)
                
                if not template_variants:
                    continue
                    
                if config.filter_zero:
                    qty_field = 'virtual_available' if use_forecast else 'qty_available'
                    if all(stock_data.get(v.id, {}).get(qty_field, 0) == 0 for v in template_variants):
                        continue

                if not config.include_negative:
                    qty_field = 'virtual_available' if use_forecast else 'qty_available'
                    if any(stock_data.get(v.id, {}).get(qty_field, 0) < 0 for v in template_variants):
                        continue

                variant_data = []
                for variant in template_variants:
                    stock = stock_data.get(variant.id, {})
                    display_qty = stock.get('virtual_available', 0) if use_forecast else stock.get('qty_available', 0)
                    
                    variant_data.append({
                        'id': variant.id,
                        'name': variant.name,
                        'default_code': variant.default_code,
                        'qty_available': stock.get('qty_available', 0),
                        'virtual_available': stock.get('virtual_available', 0),
                        'display_qty': display_qty,
                        'qty_reserved': stock.get('reserved_qty', 0),
                        'incoming_qty': stock.get('incoming_qty', 0),
                        'outgoing_qty': stock.get('outgoing_qty', 0),
                        'warehouse_name': stock.get('warehouse_name', ''),
                        'location_name': stock.get('location_name', ''),
                        'image_url': variant.image_1920 and f'/web/image/product.product/{variant.id}/image_1920' or False,
                        'product_url': f'/web#id={variant.id}&model=product.product&view_type=form',
                        'attributes': self._get_variant_attributes(variant),
                        'location_data': stock.get('location_data', [])
                    })

                serie_products.append({
                    'id': template.id,
                    'name': template.name,
                    'image_url': template.image_1920 and f'/web/image/product.template/{template.id}/image_1920' or False,
                    'product_url': f'/web#id={template.id}&model=product.template&view_type=form',
                    'variants': variant_data,
                    'use_forecast': use_forecast,
                    'serie_id': serie_group['serie_id'],
                    'serie_name': serie_group['serie_name'],
                    'serie_values': serie_group['serie_values']
                })

            if serie_products:
                products_data.extend(serie_products)

        return products_data

    def _get_variant_attributes(self, variant):
        return {
            str(attr.attribute_id.id): attr.product_attribute_value_id.id
            for attr in variant.product_template_attribute_value_ids
        }
