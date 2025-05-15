# -*- coding: utf-8 -*-

from . import models
from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Post-install script"""
    # Force recreation of the product_attribute_report view
    env = api.Environment(cr, SUPERUSER_ID, {})
    report_model = env['product.attribute.report']
    if hasattr(report_model, '_table'):
        cr.execute("DROP VIEW IF EXISTS %s CASCADE" % report_model._table)
    report_model.init() 