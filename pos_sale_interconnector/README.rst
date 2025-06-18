POS Sale Interconnector
=======================

This module provides a basic skeleton for synchronizing product catalog and POS
sales between a central Odoo instance and remote store databases.

Features
--------
* Push updated products and prices from the central database to stores.
* Import ``pos.order`` records from stores and transform them into confirmed
  ``sale.order`` records on the central instance using a dedicated warehouse.

Configuration
-------------
Create ``store.connector`` records for each remote store. Specify the remote
URL, database name and credentials as well as the warehouse representing the
store.

Usage
-----
Run ``sync_products`` to send product data to stores and ``import_pos_orders``
to fetch sales.

The methods are provided as starting points and should be extended with
real synchronization logic depending on the environment.
