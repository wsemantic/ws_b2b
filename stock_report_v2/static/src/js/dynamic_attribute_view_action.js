/** @odoo-module **/

import { registry } from "@web/core/registry";
import { DynamicAttributeView } from "../components/dynamic_attribute_view/dynamic_attribute_view";

// Register the component directly as the client action
registry.category("actions").add("dynamic_attribute_view", DynamicAttributeView); 