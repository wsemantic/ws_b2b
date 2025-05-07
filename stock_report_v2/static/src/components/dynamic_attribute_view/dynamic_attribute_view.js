/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Layout } from "@web/search/layout";

export class DynamicAttributeView extends Component {
    static template = "stock_report_v2.DynamicAttributeView";
    static components = { Layout };
    
    static props = {
        action: { type: Object },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        
        this.layoutProps = {
            display: { controlPanel: false },
            className: "o_stock_report_layout",
        };
        
        const context = this.props.action.context || {};
        this.configId = context.config_id || false;
        
        this.state = useState({
            products: [],
            attributes: [],
            filteredProducts: [],
            searchInput: "",
            filterType: "all",
            loading: true,
            config: null,
            showVariantModal: false,
            selectedVariant: null,
            error: null,
            currentPage: 1,
            pageSize: 20,
            totalCount: 0,
            totalPages: 1
        });

        onWillStart(async () => {
            if (this.configId) {
                try {
                    const configs = await this.orm.call(
                        "stock.report.config",
                        "read",
                        [this.configId, ["name", "primary_attribute_id", "secondary_attribute_id", "use_forecast", "filter_zero", "include_negative"]]
                    );
                    this.state.config = configs[0] || null;
                    
                    if (this.state.config) {
                        this.state.useForecast = this.state.config.use_forecast;
                    }
                    
                    await this.fetchData();
                } catch (error) {
                    this.state.error = error.message || error.data?.message || _t("Failed to load configuration");
                    this.notification.add(this.state.error, { type: "danger" });
                    this.state.loading = false;
                }
            } else {
                this.state.error = _t("No configuration provided");
                this.notification.add(this.state.error, { type: "warning" });
                this.state.loading = false;
            }
        });
    }

    async fetchData() {
        try {
            if (!this.state.config) return;
            
            this.state.loading = true;
            this.state.error = null;
            
            const context = {
                params: {
                    page: this.state.currentPage,
                    page_size: this.state.pageSize,
                    search_term: this.state.searchInput || '',
                    use_forecast: this.state.config.use_forecast
                }
            };
            
            const result = await this.orm.call(
                "product.attribute.report", 
                "get_report_data_by_config", 
                [this.configId],
                { context }
            );
    
            if (result.error) {
                this.state.error = result.error;
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            
            this.state.products = this._transformProducts(result.products || []);
            this.state.attributes = result.attributes || [];
            
            if (result.pagination) {
                this.state.totalCount = result.pagination.total;
                this.state.totalPages = result.pagination.pages;
            }
            
            this.applyFilters();
            
        } catch (error) {
            this.state.error = error.message || error.data?.message || _t("Failed to fetch data");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async getRandomProductImage() {
        try {
            const response = await fetch('https://fakestoreapi.com/products');
            const products = await response.json();
            if (products && products.length > 0) {
                const randomIndex = Math.floor(Math.random() * products.length);
                return products[randomIndex].image;
            }
        } catch (error) {
            console.error('Failed to fetch product images:', error);
        }
        return null;
    }
    

    _transformProducts(products) {
        return products.map(product => ({
            ...product,
            name: this._getFormattedName(product.name),
            image_url: product.image_url || this.getRandomProductImage(),
            product_url: product.product_url || `/web#id=${product.id}&model=product.template&view_type=form`,
            variants: (product.variants || []).map(variant => ({
                ...variant,
                name: this._getFormattedName(variant.name),
                image_url: variant.image_url || product.image_url || this.getRandomProductImage(),
                product_url: variant.product_url || `/web#id=${variant.id}&model=product.product&view_type=form`,
                attributes: variant.attributes || {}
            }))
        }));
    }

    _getFormattedName(nameField) {
        if (!nameField) return _t('Product');
        if (typeof nameField === 'string') return nameField;
        if (typeof nameField === 'object') {
            if (nameField.template_name) return nameField.template_name;
            if (nameField.name) return nameField.name;
            if (nameField.value) return nameField.value;
            const keys = Object.keys(nameField);
            if (keys.length > 0) {
                const englishKeys = keys.filter(key => key.startsWith('en'));
                return nameField[englishKeys[0]] || nameField[keys[0]];
            }
        }
        return _t('Product');
    }

    applyFilters() {
        let filteredProducts = [...this.state.products];
        
        if (this.state.searchInput) {
            const term = this.state.searchInput.toLowerCase();
            filteredProducts = filteredProducts.filter(product => 
                product.name.toLowerCase().includes(term) ||
                product.variants.some(v => 
                    v.default_code?.toLowerCase().includes(term) ||
                    v.name.toLowerCase().includes(term)
                )
            );
        }
        
        if (this.state.filterType !== "all") {
            filteredProducts = filteredProducts.filter(product => 
                product.variants.some(v => this._matchesFilterType(v))
            );
        }
        
        if (this.state.config) {
            if (this.state.config.filter_zero) {
                filteredProducts = filteredProducts.filter(product => 
                    product.variants.some(v => v.qty !== 0)
                );
            }
            if (!this.state.config.include_negative) {
                filteredProducts = filteredProducts.filter(product => 
                    product.variants.every(v => v.qty >= 0)
                );
            }
        }
        
        this.state.filteredProducts = filteredProducts;
    }

    _matchesFilterType(variant) {
        switch (this.state.filterType) {
            case "negative": return variant.qty < 0;
            case "zero": return variant.qty === 0;
            case "positive": return variant.qty > 0;
            case "reserved": return variant.qty_reserved > 0;
            case "replenishment": return variant.qty_incoming > 0;
            case "outgoing": return variant.qty_outgoing > 0;
            default: return true;
        }
    }

    getQuantityClass(qty) {
        qty = parseFloat(qty || 0);
        
        if (qty === 0) return "qty-available light-red";
        if (qty < 0) return "qty-available strong-red";
        if (qty >= 1 && qty <= 2) return "qty-available light-yellow";
        if (qty >= 3 && qty <= 4) return "qty-available light-green";
        if (qty >= 5 && qty <= 7) return "qty-available strong-green";
        if (qty > 7) return "qty-available strong-blue";
        return "qty-available";
    }

    getAttributeDisplayValue(attributeId, valueId) {
        const attrId = typeof attributeId === 'string' ? parseInt(attributeId, 10) : Number(attributeId);
        const attr = this.state.attributes.find(a => a.id === attrId);
        if (!attr) return valueId;
        const valueObj = attr.values.find(v => v.id === valueId);
        return valueObj ? valueObj.display_name || valueObj.name : valueId;
    }

    async changePage(page) {
        if (page < 1 || page > this.state.totalPages) return;
        this.state.currentPage = page;
        await this.fetchData();
    }
    
    async nextPage() {
        if (this.state.currentPage < this.state.totalPages) {
            await this.changePage(this.state.currentPage + 1);
        }
    }
    
    async prevPage() {
        if (this.state.currentPage > 1) {
            await this.changePage(this.state.currentPage - 1);
        }
    }

    async onSearchInput(ev) {
        this.state.searchInput = ev.target.value.trim().toLowerCase();
        this.state.currentPage = 1;
        if (this._searchTimeout) {
            clearTimeout(this._searchTimeout);
        }
        this._searchTimeout = setTimeout(() => this.fetchData(), 500);
    }

    clearSearch() {
        this.state.searchInput = "";
        this.state.currentPage = 1;
        this.fetchData();
    }

    async onFilterChange(ev) {
        this.state.filterType = ev.target.value;
        this.state.currentPage = 1;
        this.applyFilters();
    }

    async refreshData() {
        try {
            this.state.loading = true;
            this.state.error = null;
            this.state.currentPage = 1;
            await this.fetchData();
            if (!this.state.error) {
                this.notification.add(_t("Data refreshed"), { type: "success" });
            }
        } catch (error) {
            this.state.error = error.message || error.data?.message || _t("Failed to refresh data");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    formatQty(qty) {
        return qty !== undefined && qty !== null ? Number(qty).toFixed(2) : '0.00';
    }
    
    showVariantDetails(variant) {
        if (!variant) return;
        
        const product = this.state.products.find(p => p.id === variant.product_tmpl_id);
        const productName = product ? this._getFormattedName(product.name) : this._getFormattedName(variant.name);
        
        const attributes = this.formatAttributesForDisplay(variant.attributes);
        const attributesList = attributes.map(attr => attr.value).join(', ');
        
        const qtyField = this.state.config && this.state.config.use_forecast ? 'virtual_available' : 'qty_available';
        
        this.state.selectedVariant = {
            product: { name: productName },
            id: variant.id,
            name: `${productName} - ${attributesList || variant.default_code || _t('Default')}`,
            default_code: variant.default_code,
            image: variant.image_url || this.getRandomProductImage(),
            qty: variant[qtyField] || 0,
            qty_on_hand: variant.qty_available || 0,
            qty_reserved: variant.qty_reserved || 0,
            qty_incoming: variant.qty_incoming || 0,
            qty_outgoing: variant.qty_outgoing || 0,
            virtual_available: variant.virtual_available || 0,
            attributes: attributes,
            attributesList: attributesList || variant.default_code || _t('Default'),
            quantityClass: this.getQuantityClass(variant[qtyField]),
            product_url: variant.product_url || (product ? product.product_url : '#')
        };

        this.state.showVariantModal = true;
    }
    
    formatAttributesForDisplay(attributes) {
        if (!attributes || typeof attributes !== 'object') return [];
        
        return Object.entries(attributes)
            .filter(([_, valueId]) => valueId)
            .map(([attrId, valueId]) => {
                const attribute = this.state.attributes.find(a => a.id === parseInt(attrId));
                if (!attribute) return { name: _t('Attribute %s', attrId), value: String(valueId) };
                
                const value = attribute.values.find(v => v.id === valueId);
                return {
                        name: attribute.name,
                    value: value ? (value.display_name || value.name) : String(valueId)
                };
            });
    }

    closeVariantModal() {
        this.state.showVariantModal = false;
        this.state.selectedVariant = null;
    }
    
    getFilteredProducts() {
        return this.state.filteredProducts.length > 0 ? this.state.filteredProducts : this.state.products;
    }
    
    _createAttributeMatrix(product) {
        if (!this.state.attributes.length || !product.variants?.length) return null;
        
        const [primaryAttr, secondaryAttr] = this.state.attributes;
        if (!primaryAttr || !secondaryAttr) return null;

        const primaryValues = primaryAttr.values.map(v => ({
            id: v.id,
            name: v.display_name || v.name
        }));
        
        const secondaryValues = secondaryAttr.values.map(v => ({
            id: v.id,
            name: v.display_name || v.name
        }));

        const column_headers = secondaryValues.map(v => v.name);

        const qtyField = this.state.config && this.state.config.use_forecast ? 'virtual_available' : 'qty_available';

        const rows = primaryValues.map(primaryValue => {
            return {
                header: primaryValue.name,
                cells: secondaryValues.map(secondaryValue => {
                    const variant = product.variants.find(v => {
                        return (
                            v.attributes?.[String(primaryAttr.id)] === primaryValue.id &&
                            v.attributes?.[String(secondaryAttr.id)] === secondaryValue.id
                        );
                    });
                    return variant ? { 
                        qty: variant[qtyField], 
                        variant 
                    } : null;
                })
            };
        });

        return {
            rows,
            column_headers
        };
    }
    
    handleCellClick(cell, productId) {
        if (cell?.variant) {
            this.showVariantDetails(cell.variant); 
            this.updateProductImage(productId, cell.variant.id);
        }
    }
    
    handleVariantClick(variant, productId) {
        if (!variant) return;
        this.showVariantDetails(variant);
        if (productId) {
        this.updateProductImage(productId, variant.id);
        }
    }

    getUniqueColumnHeaders() {
        const columnSet = new Set();
        this.state.filteredProducts.forEach(product => {
            if (product.matrix_values?.column_headers) {
                product.matrix_values.column_headers.forEach(column => columnSet.add(column));
            }
        });
        return Array.from(columnSet).sort();
    }
    
    getCellForColumnAndRow(product, row, columnName) {
        if (!product.matrix_values?.column_headers) return null;
        
        const columnIndex = product.matrix_values.column_headers.indexOf(columnName);
        if (columnIndex === -1) return null;
        
        return row.cells[columnIndex] || null;
    }

    getVariantCellClass(cell) {
        if (!cell) return 'o_empty_cell';
        if (!cell.variant) return 'o_no_variant_cell';
        if (cell.qty < 0) return 'o_negative_qty_cell';
        if (cell.qty === 0) return 'o_zero_qty_cell';
        if (cell.qty > 0) return 'o_positive_qty_cell';
        return '';
    }

    updateProductImage(productId, variantId) {
        const product = this.state.products.find(p => p.id === productId);
        if (!product) return;

        const variant = product.variants.find(v => v.id === variantId);
        if (!variant) return;

        const productImage = document.querySelector(`.o_product_image[data-product-id="${productId}"]`);
        if (productImage) {
            productImage.src = variant.image_url || product.image_url;
        }
    }

    rowIndex(index) {
        if (index === 0 || index === '0') return true;
        return false;
    }
    
    getCellKey(index) {
        return index || 0;
    }
} 