# -*- coding: utf-8 -*-
{
    'name': 'Advanced Stock Reports',
    'summary': 'Advanced Stock Reports',
    'description': """
        Advanced Stock Reports.
    """,
    'category': 'Inventory',
    'version': '17.0.1.0.0',
    'depends': ['base', 'stock', 'product', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_report_config_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Components
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.js',
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.xml',
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.scss',
            
            # Actions
            'stock_report_v2/static/src/js/dynamic_attribute_view_action.js',
            
            # Images
            'stock_report_v2/static/src/img/no-image-found.png',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 