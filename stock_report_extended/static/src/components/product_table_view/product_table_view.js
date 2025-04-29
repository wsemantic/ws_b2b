/** @odoo-module **/

import { Component, onWillStart, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


export class StockReportExtended extends Component {
    static template = "stock_report_extended.Component";
    // static props = {};
    
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchInput = useRef("searchInput");
        
        this.state = useState({
            loading: true,
            data: null,
            selectedVariants: {},
            searchQuery: "",
            filter: "all",
            showVariantModal: false,
            selectedVariant: null
        });
        
        onWillStart(async () => {
            await this.fetchMatrixData();
        });
    }
    
    async fetchMatrixData() {
        try {
            this.state.loading = true;
            
            // Try to get real data first, fallback to demo data
            let result = await this.orm.call(
                'product.attribute.report',
                'get_real_stock_report_data',
                [],
                {}
            );
            
            if (!result || !result.products || result.products.length === 0) {
                result = await this.orm.call(
                    'product.attribute.report',
                    'get_stock_report_data',
                    [],
                    {}
                );
            }
            
            this.state.data = result;
            
        } catch (error) {
            this.notification.add("Failed to load product data", { type: "danger" });
            console.error("Error fetching matrix data:", error);
            this.state.data = { products: [] };
        } finally {
            this.state.loading = false;
        }
    }
    
    onSearchInput(value) {
        this.state.searchQuery = value.trim().toLowerCase();
    }
    
    clearSearch() {
        this.state.searchQuery = "";
        const searchInput = this.searchInput;
        if (searchInput) {
            searchInput.el.value = "";
        }
    }
    
    onFilterChange(value) {
        this.state.filter = value;
    }
    
    getFilteredProducts() {
        if (!this.state.data || !this.state.data.products) {
            return [];
        }
        
        const { searchQuery, filter } = this.state;
        
        return this.state.data.products.filter(product => {
            const matchesSearch = !searchQuery || 
                product.name.toLowerCase().includes(searchQuery);
            
            let matchesFilter = true;
            if (filter !== "all") {
                matchesFilter = product.variants && product.variants.some(variant => 
                    variant.qty_type === filter
                );
            }
            
            return matchesSearch && matchesFilter;
        });
    }
    
    getProductSizes(product) {
        if (!product.secondary_attribute || !product.secondary_attribute.values) {
            return [];
        }
        return product.secondary_attribute.values;
    }
    
    getProductColors(product) {
        if (!product.primary_attribute || !product.primary_attribute.values) {
            return [];
        }
        return product.primary_attribute.values;
    }
    
    getVariantByAttributes(product, color, size) {
        if (!product.variants) {
            return null;
        }
        
        return product.variants.find(variant => 
            variant.color === color && variant.size === size
        );
    }
    
    getQuantityCellClass(variant) {
        if (!variant) {
            return 'no-quantity';
        }
        
        switch (variant.qty_type) {
            case 'available':
                return 'qty-available';
            case 'reserved':
                return 'qty-reserved';
            case 'replenishment':
                return 'qty-replenishment';
            default:
                return 'qty-normal';
        }
    }
    
    formatQuantity(variant) {
        if (!variant) {
            return { value: '-', class: 'no-quantity' };
        }
        
        let value = 0;
        let qtyType = 'normal';
        
        // If on-hand quantity is 0, check for incoming/replenishment
        if (variant.qty === 0) {
            if (variant.incoming_qty > 0) {
                value = variant.incoming_qty;
                qtyType = 'replenishment';
            } else if (variant.reserved_qty > 0) {
                value = variant.reserved_qty;
                qtyType = 'reserved';
            }
        } else {
            value = variant.qty;
            qtyType = variant.qty_type;
        }
        
        return {
            value: value,
            class: this.getQuantityCellClass({ qty_type: qtyType })
        };
    }

    showVariantDetails(product, color, size) {
        const variant = this.getVariantByAttributes(product, color, size);
        if (!variant) return;

        // Update the selected variant in the main view
        this.state.selectedVariants[product.id] = { color, size };

        // Prepare variant details for the modal
        this.state.selectedVariant = {
            product,
            color,
            size,
            image: variant.image ? `data:image/png;base64,${variant.image}` : '/stock_report_extended/static/src/images/no-image-found.png',
            qty: variant.qty || 0,
            reserved_qty: variant.reserved_qty || 0,
            incoming_qty: variant.incoming_qty || 0,
            outgoing_qty: variant.outgoing_qty || 0
        };

        // Show the modal
        this.state.showVariantModal = true;
    }

    closeVariantModal() {
        this.state.showVariantModal = false;
        this.state.selectedVariant = null;
    }
    
    getSelectedVariantImage(product) {
        const { id: productId, image: productImage } = product;
        const selected = this.state.selectedVariants[productId];
    
        if (!selected) {
            return productImage ? `data:image/png;base64,${productImage}` : '/stock_report_extended/static/src/images/no-product-image-found.png';
        }
    
        const variant = this.getVariantByAttributes(product, selected.color, selected.size);
        const imageSource = (variant && variant.image) || productImage;
        return imageSource ? `data:image/png;base64,${imageSource}` : '/stock_report_extended/static/src/images/no-product-image-found.png';
    }
}