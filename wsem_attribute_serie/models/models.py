# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import logging
_logger = logging.getLogger(__name__)

class AttributeSerie(models.Model):
    _name = 'attribute.serie'
    _description = 'Series Tallas'

    name = fields.Char(string='Name', required=True)
    item_ids = fields.One2many('attribute.serie.item', 'attribute_serie_id', string='Items')

class AttributeSerieItem(models.Model):
    _name = 'attribute.serie.item'
    _description = 'Attribute Serie Item'
    _order = 'sequence'


    attribute_serie_id = fields.Many2one('attribute.serie', string='Serie Tallas', required=True, ondelete='cascade')
    attribute_value_id = fields.Many2one('product.attribute.value', string='Valor', required=True)
    sequence = fields.Integer(string='Sequencia')
