# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    location_id = fields.Many2one('stock.location', check_company=False)