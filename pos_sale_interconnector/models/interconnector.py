from odoo import api, fields, models
from odoo.exceptions import UserError
import xmlrpc.client


class StoreConnector(models.Model):
    _name = "store.connector"
    _description = "Remote store connection"

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    db_name = fields.Char(required=True)
    username = fields.Char(required=True)
    password = fields.Char(required=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True)

    def _get_rpc_client(self):
        self.ensure_one()
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        uid = common.authenticate(self.db_name, self.username, self.password, {})
        if not uid:
            raise UserError("Authentication failed for %s" % self.name)
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return uid, models

    def sync_products(self):
        """Push updated products to remote store"""
        uid, models = self._get_rpc_client()
        products = self.env["product.product"].search([("write_date", ">", fields.Datetime.to_datetime('1970-01-01'))])
        for product in products:
            vals = {
                "name": product.name,
                "list_price": product.lst_price,
            }
            models.execute_kw(
                self.db_name,
                uid,
                self.password,
                "product.product",
                "create",
                [vals],
            )

    def import_pos_orders(self):
        """Import POS orders from remote store as confirmed sale orders"""
        uid, models = self._get_rpc_client()
        domain = [["state", "=", "paid"]]
        order_ids = models.execute_kw(
            self.db_name,
            uid,
            self.password,
            "pos.order",
            "search",
            [domain],
        )
        orders = models.execute_kw(
            self.db_name,
            uid,
            self.password,
            "pos.order",
            "read",
            [order_ids],
        )
        SaleOrder = self.env["sale.order"]
        for order in orders:
            partner = self.env["res.partner"].search([("name", "=", order.get("partner_id"))], limit=1)
            vals = {
                "partner_id": partner.id,
                "warehouse_id": self.warehouse_id.id,
                "order_line": [],
            }
            sale_order = SaleOrder.create(vals)
            sale_order.action_confirm()

