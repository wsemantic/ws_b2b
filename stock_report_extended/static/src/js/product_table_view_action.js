/** @odoo-module **/

import { registry } from "@web/core/registry";
import { StockReportExtended } from "../components/product_table_view/product_table_view";

registry.category("actions").add("stock_report_extended.stock_report_extended_action", StockReportExtended);