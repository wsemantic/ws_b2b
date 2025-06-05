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
        
        // Add CSS styles for the table
        this._addTableStyles();
        
        const context = this.props.action.context || {};
        this.configId = context.config_id || false;
        
        // Bind methods to ensure 'this' is always available
        this.handleCellClick = this.handleCellClick.bind(this);
        this.getVariantCellClass = this.getVariantCellClass.bind(this);
        this.getCellForSerieValue = this.getCellForSerieValue.bind(this);
        
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
                        [this.configId, ["name", "primary_attribute_id", "secondary_attribute_id", "use_forecast", "show_images", "filter_zero", "include_negative"]]
                    );
                    this.state.config = configs[0] || null;
                    
                    if (this.state.config) {
                        this.state.useForecast = this.state.config.use_forecast;
                        this.state.show_images = this.state.config.show_images;
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

    _addTableStyles() {
        // Add CSS styles for the table layout
        const styleEl = document.createElement('style');
        styleEl.textContent = `
            .o_matrix_table {
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 1rem;
                box-shadow: 0 2px 3px rgba(0,0,0,0.1);
            }
            
            .o_matrix_table th {
                background-color: #f8f9fa;
                border-bottom: 2px solid #dee2e6;
                padding: 8px 12px;
                text-align: center;
                font-weight: bold;
            }
            
            .o_matrix_table td {
                padding: 8px 12px;
                border: 1px solid #dee2e6;
            }
            
            .o_size_header td:nth-child(n+3){
                background-color:rgb(116, 120, 106);
                border-top: 2px solidrgb(54, 116, 177);
                pointer-events: none;
            }
            
            .o_size_header td {
                border-bottom: 1px solid #adb5bd;
                user-select: none;
            }
            
            .o_size_header td:hover {
                background-color:rgb(116, 120, 106);
            }
            
            .o_size_header td:nth-child(n+3) {
                font-weight: bold;
                font-size: 1.1em;
                color: #212529;
                background-color:rgba(0,0,0,.075);
                border-left: 1px solid #adb5bd;
                border-right: 1px solidrgba(87, 154, 221, 0.38);
            }
            
            .o_size_header td:nth-child(n+3):hover {
                background-color:rgba(0,0,0,.075);
            }
            
            .o_image_cell {
                text-align: center;
                vertical-align: middle;
                width: 120px;
            }
            
            .o_quantity_cell {
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .o_quantity_cell:hover {
                background-color: rgba(0,123,255,0.1);
            }
            
            .o_quantity.o_positive_qty_cell {
                color: #28a745;
                font-weight: bold;
            }
            
            .o_quantity.o_negative_qty_cell {
                color: #dc3545;
                font-weight: bold;
            }
            
            .o_quantity.o_zero_qty_cell {
                color: #6c757d;
            }
            
            .o_no_quantity {
                color: #adb5bd;
            }
            
            .o_serie_value_col {
                min-width: 80px;
            }
        `;
        document.head.appendChild(styleEl);
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
                    use_forecast: this.state.config.use_forecast,
                    show_images: this.state.config.show_images
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
        console.log('Transforming products:', products);
        
        return products.map(product => {
            // Extract all unique serie values from the product
            const serieValues = product.serie_values || [];
            console.log('Product serie_values:', product.id, serieValues);
            
            return {
                ...product,
                name: this._getFormattedName(product.name),
                image_url: product.image_url || this.getRandomProductImage(),
                product_url: product.product_url || `/web#id=${product.id}&model=product.template&view_type=form`,
                serie_values: serieValues,
                variants: (product.variants || []).map(variant => {
                    // Make sure every variant has a serie_value if possible
                    if (!variant.serie_value && serieValues.length > 0) {
                        // If there's no serie_value, use attribute_value if available
                        variant.serie_value = variant.attribute_value || serieValues[0];
                    }
                    
                    console.log('Variant:', variant.id, 'serie_value:', variant.serie_value);
                    
                    return {
                        ...variant,
                        name: this._getFormattedName(variant.name),
                        image_url: variant.image_url || product.image_url || this.getRandomProductImage(),
                        product_url: variant.product_url || `/web#id=${variant.id}&model=product.product&view_type=form`,
                        attributes: variant.attributes || {},
                        warehouse_name: variant.warehouse_name || '',
                        location_name: variant.location_name || '',
                        serie_value: variant.serie_value
                    };
                })
            };
        });
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
        console.log('showVariantDetails - variant:', variant);
        if (!variant) {
            console.log('showVariantDetails - variant is null/undefined');
            return;
        }
        
        // Find product from the current filtered products
        const product = this.state.filteredProducts.length > 0 ? 
            this.state.filteredProducts.find(p => p.variants.some(v => v.id === variant.id)) :
            this.state.products.find(p => p.variants.some(v => v.id === variant.id));
            
        console.log('showVariantDetails - found product:', product);
        
        if (!product) {
            console.log('showVariantDetails - product not found');
            return;
        }

        const attributes = this.formatAttributesForDisplay(variant.attributes);
        console.log('showVariantDetails - attributes:', attributes);
        const attributesList = attributes.map(attr => attr.value).join(', ');
        
        const qtyField = this.state.config && this.state.config.use_forecast ? 'virtual_available' : 'qty_available';
        console.log('showVariantDetails - qtyField:', qtyField);
        
        this.state.selectedVariant = {
            product: { name: product.name },
            id: variant.id,
            name: `${product.name} - ${attributesList || variant.default_code || _t('Default')}`,
            default_code: variant.default_code,
            image: variant.image_url || product.image_url || this.getRandomProductImage(),
            qty: variant[qtyField] || 0,
            qty_on_hand: variant.qty_available || 0,
            qty_reserved: variant.qty_reserved || 0,
            qty_incoming: variant.qty_incoming || 0,
            qty_outgoing: variant.qty_outgoing || 0,
            virtual_available: variant.virtual_available || 0,
            attributes: attributes,
            attributesList: attributesList || variant.default_code || _t('Default'),
            quantityClass: this.getVariantCellClass({qty: variant[qtyField]}),
            product_url: variant.product_url || (product ? product.product_url : '#'),
            warehouse_name: variant.warehouse_name || '',
            location_name: variant.location_name || ''
        };
        console.log('showVariantDetails - selectedVariant:', this.state.selectedVariant);

        this.state.showVariantModal = true;
        console.log('showVariantDetails - modal shown');
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
        const products = this.state.filteredProducts.length > 0 ? this.state.filteredProducts : this.state.products;
        
        // Group products by their size attributes
        const groupedProducts = {};
        
        products.forEach(product => {
            const sizeAttr = this.state.attributes[1]; // Second attribute is size
            if (!sizeAttr || !product.variants) return;
            
            // Get unique size values for this product
            const productSizes = new Set();
            product.variants.forEach(variant => {
                if (variant.attributes && variant.attributes[sizeAttr.id]) {
                    const sizeValue = sizeAttr.values.find(v => v.id === variant.attributes[sizeAttr.id]);
                    if (sizeValue) {
                        productSizes.add(sizeValue.name);
                    }
                }
            });
            
            // Create a key for grouping
            const sizeKey = Array.from(productSizes).sort().join(',');
            if (!groupedProducts[sizeKey]) {
                groupedProducts[sizeKey] = {
                    sizes: Array.from(productSizes),
                    products: []
                };
            }
            groupedProducts[sizeKey].products.push(product);
        });
        
        // Convert grouped products to array format
        return Object.values(groupedProducts);
    }
    
    groupProductsBySeries(products) {
        const seriesGroups = {};
        console.log(products, 'product')
        products.forEach(product => {
            const serieId = product.serie_id || 0;
            console.log(serieId, 'serieId')
            if (!seriesGroups[serieId]) {
                console.log(product.serie_values, 'product.serie_values but i think hare sere vale avaliabe so we can diract add after ser name')

                seriesGroups[serieId] = {

                    serie_id: serieId,
                    serie_name: product.serie_name || _t('No Series'),
                    serie_values: product.serie_values ? [...new Set(product.serie_values)].sort() : [],
                    products: []
                };
                console.log(seriesGroups[serieId], 'seriesGroups[serieId]')
            }
            
            // Add product to the series group
            seriesGroups[serieId].products.push(product);
            
            // Collect unique serie values from variants
            product.variants.forEach(variant => {
                if (variant.serie_value && !seriesGroups[serieId].serie_values.includes(variant.serie_value)) {
                    seriesGroups[serieId].serie_values.push(variant.serie_value);
                }
            });
            
            // Sort serie values
            seriesGroups[serieId].serie_values.sort();
        });
        console.log(seriesGroups, 'seriesGroups')
        return Object.values(seriesGroups);
    }
    
    // Get the maximum number of series values across all series groups
    getMaxSerieValuesCount(series_groups) {
        if (!series_groups || !Array.isArray(series_groups) || series_groups.length === 0) {
            return 5; // Default to 5 if no series groups
        }
        
        // Find the maximum number of serie_values across all series groups
        const maxCount = Math.max(...series_groups.map(group => 
            group.serie_values && Array.isArray(group.serie_values) ? group.serie_values.length : 0
        ));
        
        // Return at least 5, or the actual maximum if greater
        return Math.max(5, maxCount);
    }
    
    // getCellForSerieValue(row, serieValue, location_id) {
    //     if (!row || !row.cells) return null;
        
    //     // Find a cell where the variant has a matching serie_value (size)
    //     const cell = row.cells.find(c => 
    //         c && c.variant && c.variant.serie_value === serieValue
    //     );
        
    //     if (!cell) return null;
        
    //     const qtyField = this.state.config && this.state.config.use_forecast ? 
    //         'virtual_available' : 'qty_available';
            
    //     return {
    //         qty: cell.variant[qtyField] || 0,
    //         variant: cell.variant
    //     };
    // }
    
    getCellForSerieValue(row, serieValue, location_id) {
    if (!row || !row.cells) return null;
    
    // Find a cell where the variant has a matching serie_value (size)
    const cell = row.cells.find(c => 
        c && c.variant && c.variant.serie_value === serieValue
    );
    
    if (!cell) return null;
    
    // FIXED: Get quantity from the specific location_data that matches the location_id
    let qty = 0;
    
    if (cell.variant && cell.variant.location_data) {
        // Check if location_data matches the requested location_id
        if (cell.variant.location_data.location_id === location_id) {
            const qtyField = this.state.config && this.state.config.use_forecast ? 
                'virtual_available' : 'qty_available';
            
            qty = cell.variant.location_data[qtyField] || cell.variant.location_data.qty_available || 0;
        }
    }
    
    return {
        qty: qty,
        variant: cell.variant
    };
}

    _createAttributeMatrix(product) {
        if (!this.state.attributes.length || !product.variants?.length) return null;
        
        const [primaryAttr, secondaryAttr] = this.state.attributes;
        if (!primaryAttr) return null;

        // Get all primary attribute values
        const primaryValues = primaryAttr.values.map(v => ({
            id: v.id,
            name: v.name || v.display_name
        }));

        // Get all unique serie values for this product (these are likely sizes: S, M, L, XL)
        const serieValues = product.serie_values || [];
        
        // Map to store size/attribute mapping for each variant
        const variantSizeMap = new Map();
        
        // First, identify which attribute is the size attribute (likely the secondary attribute)
        const sizeAttribute = secondaryAttr || 
            this.state.attributes.find(attr => 
                attr.name.toLowerCase().includes('size') || 
                attr.name.toLowerCase().includes('talla') ||
                attr.name.toLowerCase().includes('tamaño')
            );
        
        // Assign the correct size value to each variant
        product.variants.forEach(variant => {
            // If there's a secundary attribute (size), use that to set the serie_value
            if (sizeAttribute && variant.attributes) {
                const sizeAttrId = String(sizeAttribute.id);
                const sizeValueId = variant.attributes[sizeAttrId];
                
                if (sizeValueId) {
                    const sizeValue = sizeAttribute.values.find(v => v.id === sizeValueId);
                    if (sizeValue) {
                        // Use the size attribute value as the serie_value
                        variant.serie_value = sizeValue.name;
                        
                        // Store in the map for easy lookup
                        variantSizeMap.set(variant.id, sizeValue.name);
                    }
                }
            }
            
            // If still no serie_value, use attribute_value as fallback
            if (!variant.serie_value && variant.attribute_value) {
                variant.serie_value = variant.attribute_value;
                variantSizeMap.set(variant.id, variant.attribute_value);
            }
        });

        // Create rows based on primary attribute values (e.g., colors)
        const rows = primaryValues.map(primaryValue => {
            // Find variants matching this primary attribute value (e.g., all "Red" variants)
            const matchingVariants = product.variants.filter(v => 
                v.attributes?.[String(primaryAttr.id)] === primaryValue.id
            );

            if (matchingVariants.length === 0) return null;

            return {
                header: primaryValue.name,
                cells: matchingVariants.map(variant => {
                    if (!variant) return null;
                    
                    // Get the size for this variant
                    const variantSize = variantSizeMap.get(variant.id) || variant.serie_value;
                    
                    // Set quantity field based on config
                    const qtyField = this.state.config && this.state.config.use_forecast ? 
                        'virtual_available' : 'qty_available';
                    
                    // Make sure all stock quantities are values, not undefined
                    const qty = variant[qtyField] || 0;
                    
                    // Return a complete cell with all data
                    return {
                        qty: qty,
                        variant: {
                            ...variant,
                            serie_value: variantSize  // Ensure serie_value is set to the size
                        }
                    };
                })
            };
        }).filter(row => row !== null);

        return {
            rows,
            column_headers: serieValues
        };
    }

    _createAttributeMatrixStock(product) {
        if (!this.state.attributes.length || !product.variants?.length) return null;
        
        const [primaryAttr, secondaryAttr] = this.state.attributes;
        if (!primaryAttr) return null;

        // Get all primary attribute values (colors)
        const primaryValues = primaryAttr.values.map(v => ({
            id: v.id,
            name: v.name || v.display_name
        }));

        // Get all unique serie values for this product (sizes)
        const serieValues = product.serie_values || [];
        
        // Collect all unique locations from all variants
        const locationMap = new Map();
        
        product.variants.forEach(variant => {
            if (variant.location_data && Array.isArray(variant.location_data)) {
                variant.location_data.forEach(locationInfo => {
                    if (!locationMap.has(locationInfo.location_id)) {
                        locationMap.set(locationInfo.location_id, {
                            id: locationInfo.location_id,
                            name: locationInfo.location_name,
                            warehouse_name: locationInfo.warehouse_name
                        });
                    }
                });
            }
        });

        // Convert location map to array and sort by name for consistent ordering
        const locations = Array.from(locationMap.values()).sort((a, b) => a.name.localeCompare(b.name));

        // Identify which attribute is the size attribute
        const sizeAttribute = secondaryAttr || 
            this.state.attributes.find(attr => 
                attr.name.toLowerCase().includes('size') || 
                attr.name.toLowerCase().includes('talla') ||
                attr.name.toLowerCase().includes('tamaño')
            );

        // Create a flattened structure: variant + location combinations
        const variantLocationCombinations = [];
        
        product.variants.forEach(variant => {
            if (variant.location_data && Array.isArray(variant.location_data)) {
                variant.location_data.forEach(locationData => {
                    // Get the color for this variant
                    const colorId = variant.attributes?.[String(primaryAttr.id)];
                    const colorValue = primaryValues.find(pv => pv.id === colorId);
                    
                    if (!colorValue) return;
                    
                    // Get the size for this variant
                    let variantSize = variant.serie_value;
                    
                    if (sizeAttribute && variant.attributes) {
                        const sizeAttrId = String(sizeAttribute.id);
                        const sizeValueId = variant.attributes[sizeAttrId];
                        
                        if (sizeValueId) {
                            const sizeVal = sizeAttribute.values.find(v => v.id === sizeValueId);
                            if (sizeVal) {
                                variantSize = sizeVal.name;
                            }
                        }
                    }
                    
                    console.log(`Adding combination: Variant ${variant.id}, Color: ${colorValue.name}, Size: ${variantSize}, Location: ${locationData.location_name}, Qty: ${locationData.qty_available}`);
                    
                    variantLocationCombinations.push({
                        variant: variant,
                        locationData: locationData,
                        colorValue: colorValue,
                        size: variantSize,
                        locationId: locationData.location_id
                    });
                });
            }
        });

        // Group by color and location
        const colorLocationGroups = new Map();
        
        variantLocationCombinations.forEach(combo => {
            const key = `${combo.colorValue.id}_${combo.locationId}`;
            
            if (!colorLocationGroups.has(key)) {
                colorLocationGroups.set(key, {
                    colorValue: combo.colorValue,
                    locationId: combo.locationId,
                    locationName: combo.locationData.location_name,
                    warehouseName: combo.locationData.warehouse_name,
                    variants: []
                });
            }
            
            colorLocationGroups.get(key).variants.push(combo);
        });

        // Create rows: For each color-location combination
        const rows = [];
        
        Array.from(colorLocationGroups.values()).forEach(group => {
            // Create cells for each size
            const cells = serieValues.map(sizeValue => {
                // Find the variant-location combination that matches this size
                const matchingCombo = group.variants.find(combo => combo.size === sizeValue);
                
                if (!matchingCombo) {
                    return {
                        qty: 0,
                        variant: null
                    };
                }

                // Set quantity field based on config - use the specific location data
                const qtyField = this.state.config && this.state.config.use_forecast ? 
                    'virtual_available' : 'qty_available';
                
                // IMPORTANT: Use the quantity from the specific location data, not from the variant
                // Make sure we're accessing the correct property from location_data
                const qty = matchingCombo.locationData[qtyField] || matchingCombo.locationData.qty_available || 0;
                
                console.log(`Location: ${matchingCombo.locationData.location_name}, Size: ${sizeValue}, Qty: ${qty}`, matchingCombo.locationData);
                
                return {
                    qty: qty,
                    variant: {
                        ...matchingCombo.variant,
                        serie_value: sizeValue,
                        location_data: matchingCombo.locationData // Include the specific location data
                    }
                };
            });

            // Only add row if it has some stock
            if (cells.some(cell => cell.qty > 0)) {
                rows.push({
                    header: group.colorValue.name, // Color name
                    color_name: group.colorValue.name,
                    location_id: group.locationId,
                    location_name: group.locationName,
                    warehouse_name: group.warehouseName,
                    cells: cells
                });
            }
        });

        return {
            rows: rows,
            column_headers: serieValues
        };
    }
    
    handleCellClick(cell, productId) {
        try {
            if (!cell) return;
            
            const variant = cell.variant;
            if (!variant) return;
            
            // Find the product from the current filtered products
            const product = this.state.filteredProducts.length > 0 ? 
                this.state.filteredProducts.find(p => p.id === productId) :
                this.state.products.find(p => p.id === productId);
                
            if (!product) return;

            const attributes = this.formatAttributesForDisplay(variant.attributes);
            const attributesList = attributes.map(attr => attr.value).join(', ');
            
            const qtyField = this.state.config && this.state.config.use_forecast ? 'virtual_available' : 'qty_available';
            
            this.state.selectedVariant = {
                product: { name: product.name },
                id: variant.id,
                name: `${product.name} - ${attributesList || variant.default_code || _t('Default')}`,
                default_code: variant.default_code,
                image: variant.image_url || product.image_url || this.getRandomProductImage(),
                qty: variant[qtyField] || 0,
                qty_on_hand: variant.qty_available || 0,
                qty_reserved: variant.qty_reserved || 0,
                qty_incoming: variant.qty_incoming || 0,
                qty_outgoing: variant.qty_outgoing || 0,
                virtual_available: variant.virtual_available || 0,
                attributes: attributes,
                attributesList: attributesList || variant.default_code || _t('Default'),
                quantityClass: this.getVariantCellClass(cell),
                product_url: variant.product_url || (product ? product.product_url : '#'),
                warehouse_name: variant.warehouse_name || '',
                location_name: variant.location_name || ''
            };

            this.state.showVariantModal = true;
            this.updateProductImage(productId, variant.id);
        } catch (error) {
            console.error('Error in handleCellClick:', error);
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
    
    async onForecastCheckboxChange(ev) {
        const newVal = ev.target.checked;
        this.state.config.use_forecast = newVal;

        await this.orm.write('stock.report.config', [this.configId], {
            use_forecast: newVal,
        });
        await this.fetchData();
    }

    async onImageCheckboxChange(ev) {
        const newVal = ev.target.checked;
        this.state.config.show_images = newVal;

        await this.orm.write('stock.report.config', [this.configId], {
            show_images: newVal,
        });

    }

    getProductRowspan(product, matrix) {
        // Calculate total rowspan for a product's image cell
        // This considers all rows in all products in the same series
        
        // For the current product, get the number of rows
        const currentProductRows = matrix.rows ? matrix.rows.length : 0;
        
        return currentProductRows;
    }
} 