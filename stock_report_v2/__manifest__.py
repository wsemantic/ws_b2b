# -*- coding: utf-8 -*-
{
    'name': 'Stock Report V2',
    'version': '17.0.0.1',
    'category': 'Inventory',
    'summary': 'Enhanced Stock Report with Dynamic Attributes',
    'description': """
        Enhanced stock report that shows product attributes in a dynamic matrix view.
    """,
    'author': 'Wsemantic',
    'website': 'https://www.wsemantic.com',
    'depends': [
        'base',
        'stock',
        'product',
        'wsem_attribute_serie',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_report_config_views.xml',
        # 'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
                        # Components
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.js',
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.xml',
            'stock_report_v2/static/src/components/dynamic_attribute_view/dynamic_attribute_view.scss',
            
            # Actions
            'stock_report_v2/static/src/js/dynamic_attribute_view_action.js',
            
            # 'stock_report_v2/static/src/components/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'auto_install': False,
} 