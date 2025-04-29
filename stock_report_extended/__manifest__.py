# -*- coding: utf-8 -*-
{
    'name': "Stock Report Extended",
    'summary': "Product attribute grouping report for stock module",
    'description': """
This module extends the stock module reports with a custom list view that:
- Groups products by their attributes (color, size, etc.)
- Shows product image, name, color, and other attributes
- Allows real-time exploration of inventory by attribute
- Color-codes stock status (in stock, reserved, replenishment)
    """,
    'category': 'Inventory/Reporting',
    'version': '1.0',
    'depends': [
        'base',
        'stock',
        'product',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_attribute_report_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/stock_report_extended/static/src/images/no-image-found.png',
            'stock_report_extended/static/src/components/product_table_view/product_table_view.scss',
            'stock_report_extended/static/src/components/product_table_view/product_table_view.js',
            'stock_report_extended/static/src/components/product_table_view/product_table_view.xml',
            'stock_report_extended/static/src/js/product_table_view_action.js',
        ],
    },
    
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

