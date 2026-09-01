import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "outputs/order_desk_schema_20260830";
const workbook = Workbook.create();

const sourceUrl = "https://apidocs.orderdesk.com/";
const accent = "#2563EB";
const navy = "#0F172A";
const headerFill = "#DBEAFE";
const subFill = "#EFF6FF";
const border = "#CBD5E1";

const tables = [
  ["cx_order", "Core order header", "One row per customer order", "order_id"],
  ["cx_order_item", "Order line items", "Products, quantities, SKU, item metadata", "order_item_id"],
  ["cx_customer", "Customer profile", "Normalized buyer identity and contact data", "customer_id"],
  ["cx_order_address", "Order addresses", "Shipping, billing/customer, and return addresses", "address_id"],
  ["cx_payment", "Payment transaction", "Payment method, status, processor balance, refunds", "payment_id"],
  ["cx_shipment", "Shipment record", "Tracking, carrier, shipped date, label status", "shipment_id"],
  ["cx_inventory_item", "Inventory item", "SKU catalog, stock, weight, cost, metadata", "inventory_item_id"],
  ["cx_order_discount", "Order discounts", "Discount code, name, and amount", "discount_id"],
  ["cx_order_note", "Order notes", "Customer service notes and internal notes", "note_id"],
  ["cx_order_folder", "Order folders", "Operational queues such as New, Prepared, Closed", "folder_id"],
  ["cx_order_tag", "Order tags", "Visible status/risk labels attached to orders", "tag_id"],
  ["cx_order_history", "Order history", "Append-only status/action timeline", "history_id"],
  ["cx_integration_account", "Connected channels", "Shopify, Amazon, PayPal, Stripe, carrier accounts", "integration_id"],
  ["cx_automation_rule", "Automation rules", "If/then workflow rules for routing and fulfillment", "rule_id"],
  ["cx_user", "System users", "Operators, admins, fulfillment users", "user_id"],
  ["cx_role", "Roles", "Permission role definitions", "role_id"],
  ["cx_audit_log", "Audit log", "Security and data change events", "audit_id"],
  ["cx_file_attachment", "Attachments", "Packing slips, labels, invoices, artwork files", "attachment_id"],
];

const fields = [
  ["cx_order","order_id","Order ID","bigint","20","NO","PK","","100001","Internal primary key"],
  ["cx_order","external_order_id","Source Order ID","varchar","100","YES","UK","","OD-412218073","Original marketplace/cart order id"],
  ["cx_order","source_name","Source","varchar","80","YES","IDX","Order Desk","Shopify","Cart, marketplace, manual, API"],
  ["cx_order","email","Customer Email","varchar","255","YES","IDX","","buyer@example.com","Buyer email"],
  ["cx_order","customer_id","Customer ID","bigint","20","YES","FK","","501","Links to cx_customer"],
  ["cx_order","folder_id","Folder ID","bigint","20","YES","FK","1","1","Operational folder/queue"],
  ["cx_order","status","Order Status","varchar","40","NO","IDX","new","new","new, prepared, shipped, closed, canceled"],
  ["cx_order","payment_status","Payment Status","varchar","40","YES","IDX","Captured","Approved","Approved, Authorized, Captured, Pending, Refunded"],
  ["cx_order","fulfillment_status","Fulfillment Status","varchar","40","YES","IDX","unfulfilled","unfulfilled","unfulfilled, routed, shipped, canceled"],
  ["cx_order","shipping_method","Shipping Method","varchar","120","YES","","","UPS Ground","Selected shipping service"],
  ["cx_order","quantity_total","Quantity Total","int","11","NO","","0","2","Calculated total item quantity"],
  ["cx_order","weight_total","Weight Total","decimal","12,3","NO","","0","2.375","Calculated shipment weight"],
  ["cx_order","product_total","Product Total","decimal","12,2","NO","","0","39.98","Item subtotal"],
  ["cx_order","shipping_total","Shipping Total","decimal","12,2","NO","","0","9.50","Shipping charged"],
  ["cx_order","handling_total","Handling Total","decimal","12,2","NO","","0","0.00","Handling charged"],
  ["cx_order","tax_total","Tax Total","decimal","12,2","NO","","0","1.25","Tax amount"],
  ["cx_order","discount_total","Discount Total","decimal","12,2","NO","","0","5.00","Positive discount total"],
  ["cx_order","refund_total","Refund Total","decimal","12,2","NO","","0","0.00","Total refunded"],
  ["cx_order","order_total","Order Total","decimal","12,2","NO","","0","45.73","Grand total"],
  ["cx_order","currency","Currency","char","3","NO","","USD","USD","ISO 4217 currency code"],
  ["cx_order","ip_address","IP Address","varchar","45","YES","","","181.16.150.12","IPv4/IPv6 buyer IP"],
  ["cx_order","checkout_data_json","Checkout Data","json","","YES","","","{}","Editable extra flat key-value data"],
  ["cx_order","metadata_json","Order Metadata","json","","YES","","","{}","Hidden extra flat key-value data"],
  ["cx_order","order_date","Order Date","datetime","","NO","IDX","","2026-08-30 10:30:00","Use real datetime, not Excel serial number"],
  ["cx_order","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","2026-08-30 10:35:00","System created time"],
  ["cx_order","updated_time","Updated Time","datetime","","YES","","","2026-08-30 10:50:00","System updated time"],
  ["cx_order","owner_user_id","Owner","bigint","20","YES","FK","","12","Assigned operator"],
  ["cx_order","del_flag","Deleted Flag","tinyint","1","NO","","0","0","Soft delete flag"],
  ["cx_order_item","order_item_id","Order Item ID","bigint","20","NO","PK","","90001","Internal line item id"],
  ["cx_order_item","order_id","Order ID","bigint","20","NO","FK","","100001","Parent order"],
  ["cx_order_item","inventory_item_id","Inventory Item ID","bigint","20","YES","FK","","7001","Optional SKU catalog link"],
  ["cx_order_item","item_name","Item Name","varchar","255","NO","","","Black Shirt","Product title"],
  ["cx_order_item","sku","SKU / Code","varchar","120","YES","IDX","","SKU-BLK-001","Product code"],
  ["cx_order_item","category_code","Category Code","varchar","80","YES","","DEFAULT","DEFAULT","Category or fulfillment classification"],
  ["cx_order_item","delivery_type","Delivery Type","varchar","20","NO","","ship","ship","ship, noship, download, future"],
  ["cx_order_item","quantity","Quantity","int","11","NO","","1","1","Ordered quantity"],
  ["cx_order_item","unit_price","Unit Price","decimal","12,2","NO","","0","19.99","Item sale price"],
  ["cx_order_item","unit_cost","Unit Cost","decimal","12,2","YES","","","8.50","Optional margin analysis"],
  ["cx_order_item","weight","Weight","decimal","12,3","YES","","","1.100","Item weight"],
  ["cx_order_item","variation_json","Variation List","json","","YES","","","{\"Size\":\"Large\"}","Flat key-value item variations"],
  ["cx_order_item","metadata_json","Item Metadata","json","","YES","","","{\"image\":\"https://...\"}","Image, print SKU, artwork URL, extras"],
  ["cx_order_item","fulfillment_method","Fulfillment Method","varchar","120","YES","","","Printful","Routing destination"],
  ["cx_order_item","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_customer","customer_id","Customer ID","bigint","20","NO","PK","","501","Internal customer id"],
  ["cx_customer","external_customer_id","External Customer ID","varchar","100","YES","IDX","","8173875","Customer id from source channel"],
  ["cx_customer","email","Email","varchar","255","YES","IDX","","buyer@example.com","Primary email"],
  ["cx_customer","first_name","First Name","varchar","80","YES","","","Jimmy",""],
  ["cx_customer","last_name","Last Name","varchar","80","YES","","","Dean",""],
  ["cx_customer","company","Company","varchar","160","YES","","","Acme Inc.",""],
  ["cx_customer","phone","Phone","varchar","40","YES","","","555-555-5555","Normalize where possible"],
  ["cx_customer","order_count","Order Count","int","11","NO","","0","3","Can be derived or cached"],
  ["cx_customer","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_customer","updated_time","Updated Time","datetime","","YES","","","",""],
  ["cx_order_address","address_id","Address ID","bigint","20","NO","PK","","30001","Internal address id"],
  ["cx_order_address","order_id","Order ID","bigint","20","NO","FK","","100001","Parent order"],
  ["cx_order_address","address_type","Address Type","varchar","20","NO","IDX","","shipping","shipping, customer/billing, return"],
  ["cx_order_address","first_name","First Name","varchar","80","YES","","","Jimmy",""],
  ["cx_order_address","last_name","Last Name","varchar","80","YES","","","Dean",""],
  ["cx_order_address","company","Company","varchar","160","YES","","","",""],
  ["cx_order_address","address1","Address 1","varchar","255","YES","","","800 Emmet St",""],
  ["cx_order_address","address2","Address 2","varchar","255","YES","","","",""],
  ["cx_order_address","address3","Address 3","varchar","255","YES","","","","Shipping only"],
  ["cx_order_address","address4","Address 4","varchar","255","YES","","","","Shipping only"],
  ["cx_order_address","city","City","varchar","120","YES","","","Nashville",""],
  ["cx_order_address","state","State / Region","varchar","120","YES","","","TN",""],
  ["cx_order_address","postal_code","Postal Code","varchar","30","YES","","","55555","Keep as text"],
  ["cx_order_address","country","Country","varchar","80","YES","","","US","Country code or full name"],
  ["cx_order_address","phone","Phone","varchar","40","YES","","","555-555-5555",""],
  ["cx_payment","payment_id","Payment ID","bigint","20","NO","PK","","80001","Internal payment id"],
  ["cx_payment","order_id","Order ID","bigint","20","NO","FK","","100001","Parent order"],
  ["cx_payment","payment_type","Payment Type","varchar","40","YES","","Visa","PayPal","Visa, MasterCard, PayPal, Stripe, Bank Card"],
  ["cx_payment","payment_status","Payment Status","varchar","40","NO","IDX","Captured","Captured","Approved, Authorized, Captured, Pending, Rejected"],
  ["cx_payment","cc_number_masked","Card Masked","varchar","30","YES","","","xxxxxxxxxxxx4242","Never store full card number"],
  ["cx_payment","cc_exp","Card Expiration","varchar","7","YES","","","02/2028","MM/YYYY"],
  ["cx_payment","processor_name","Processor","varchar","80","YES","","","Stripe","Payment gateway"],
  ["cx_payment","processor_transaction_id","Processor Transaction ID","varchar","160","YES","IDX","","pi_123","Gateway transaction id"],
  ["cx_payment","processor_response","Processor Response","varchar","500","YES","","","Stripe: pi_123","Raw gateway reference"],
  ["cx_payment","processor_balance","Processor Balance","decimal","12,2","NO","","0","45.73","Remaining captured balance"],
  ["cx_payment","refund_total","Refund Total","decimal","12,2","NO","","0","0.00","Refund amount"],
  ["cx_payment","paid_time","Paid Time","datetime","","YES","","","2026-08-30 10:31:00",""],
  ["cx_shipment","shipment_id","Shipment ID","bigint","20","NO","PK","","60001","Internal shipment id"],
  ["cx_shipment","order_id","Order ID","bigint","20","NO","FK","","100001","Parent order"],
  ["cx_shipment","tracking_number","Tracking Number","varchar","160","YES","IDX","","1Z132456789","Carrier tracking number"],
  ["cx_shipment","carrier_code","Carrier Code","varchar","40","YES","","","UPS","UPS, FedEx, USPS, DHL"],
  ["cx_shipment","shipment_method","Shipment Method","varchar","120","YES","","","UPS Ground","Service name"],
  ["cx_shipment","weight","Shipment Weight","decimal","12,3","YES","","0","2.375",""],
  ["cx_shipment","cost","Shipment Cost","decimal","12,2","YES","","0","7.50",""],
  ["cx_shipment","status","Shipment Status","varchar","40","YES","IDX","","shipped","created, label_printed, shipped, delivered"],
  ["cx_shipment","tracking_url","Tracking URL","varchar","500","YES","","","https://...",""],
  ["cx_shipment","label_format","Label Format","varchar","20","YES","","","PDF","PDF, PNG, ZPL"],
  ["cx_shipment","label_url","Label URL","varchar","500","YES","","","https://...","Do not store large binary in DB if avoidable"],
  ["cx_shipment","print_status","Print Status","tinyint","1","NO","","0","1","0 not printed, 1 printed"],
  ["cx_shipment","cart_shipment_id","Cart Shipment ID","varchar","100","YES","","","","External shipment id"],
  ["cx_shipment","date_shipped","Date Shipped","date","","YES","IDX","","2026-08-30",""],
  ["cx_shipment","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_inventory_item","inventory_item_id","Inventory Item ID","bigint","20","NO","PK","","7001","Internal SKU id"],
  ["cx_inventory_item","name","Item Name","varchar","255","NO","","","Black Shirt",""],
  ["cx_inventory_item","sku","SKU / Code","varchar","120","NO","UK","","SKU-BLK-001","Unique SKU"],
  ["cx_inventory_item","price","Price","decimal","12,2","NO","","0","19.99",""],
  ["cx_inventory_item","cost","Cost","decimal","12,2","YES","","","8.50",""],
  ["cx_inventory_item","weight","Weight","decimal","12,3","YES","","","1.100",""],
  ["cx_inventory_item","stock_qty","Stock Qty","int","11","NO","","0","125",""],
  ["cx_inventory_item","manufacturer_sku","Manufacturer SKU","varchar","120","YES","","","MFG-001",""],
  ["cx_inventory_item","warehouse_location","Warehouse Location","varchar","120","YES","","","A1-B2",""],
  ["cx_inventory_item","update_source","Update Source","varchar","80","YES","","","Shopify","Last system to update item"],
  ["cx_inventory_item","metadata_json","Metadata","json","","YES","","","{}","Extra SKU attributes"],
  ["cx_inventory_item","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_inventory_item","updated_time","Updated Time","datetime","","YES","","","",""],
  ["cx_order_discount","discount_id","Discount ID","bigint","20","NO","PK","","40001",""],
  ["cx_order_discount","order_id","Order ID","bigint","20","NO","FK","","100001",""],
  ["cx_order_discount","discount_name","Discount Name","varchar","120","NO","","Discount","Holiday Discount",""],
  ["cx_order_discount","discount_code","Discount Code","varchar","80","YES","","MN234DX78","MN234DX78",""],
  ["cx_order_discount","amount","Amount","decimal","12,2","NO","","0","5.00","Store positive amount"],
  ["cx_order_note","note_id","Note ID","bigint","20","NO","PK","","50001",""],
  ["cx_order_note","order_id","Order ID","bigint","20","NO","FK","","100001",""],
  ["cx_order_note","username","Username","varchar","80","YES","","","Customer Service Rep",""],
  ["cx_order_note","note_type","Note Type","varchar","30","NO","","internal","internal","internal, customer, system"],
  ["cx_order_note","content","Content","varchar","1800","NO","","","Customer called to change address","Keep under 1800 chars"],
  ["cx_order_note","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_order_folder","folder_id","Folder ID","bigint","20","NO","PK","","1",""],
  ["cx_order_folder","folder_name","Folder Name","varchar","80","NO","UK","","New","New, Prepared, Closed, Canceled"],
  ["cx_order_folder","sort_order","Sort Order","int","11","NO","","0","1",""],
  ["cx_order_folder","is_active","Active","tinyint","1","NO","","1","1",""],
  ["cx_order_tag","tag_id","Tag ID","bigint","20","NO","PK","","10",""],
  ["cx_order_tag","order_id","Order ID","bigint","20","NO","FK","","100001",""],
  ["cx_order_tag","tag_name","Tag Name","varchar","80","NO","IDX","","Fraud Review",""],
  ["cx_order_tag","tag_color","Tag Color","varchar","20","YES","","","#EF4444",""],
  ["cx_order_tag","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_order_history","history_id","History ID","bigint","20","NO","PK","","11001",""],
  ["cx_order_history","order_id","Order ID","bigint","20","NO","FK","","100001",""],
  ["cx_order_history","event_type","Event Type","varchar","80","NO","IDX","","status_changed",""],
  ["cx_order_history","event_title","Event Title","varchar","200","NO","","","Moved to Prepared",""],
  ["cx_order_history","event_detail","Event Detail","text","","YES","","","{}","Message or JSON payload"],
  ["cx_order_history","operator_user_id","Operator","bigint","20","YES","FK","","12",""],
  ["cx_order_history","created_time","Created Time","datetime","","NO","IDX","CURRENT_TIMESTAMP","",""],
  ["cx_integration_account","integration_id","Integration ID","bigint","20","NO","PK","","2001",""],
  ["cx_integration_account","integration_type","Integration Type","varchar","60","NO","IDX","","shopify","cart, marketplace, payment, shipping, fulfillment"],
  ["cx_integration_account","integration_name","Integration Name","varchar","120","NO","","","Shopify Main Store",""],
  ["cx_integration_account","account_status","Status","varchar","30","NO","","active","active","active, paused, error"],
  ["cx_integration_account","credential_ref","Credential Ref","varchar","255","YES","","","secret://...","Store secrets outside plain table when possible"],
  ["cx_integration_account","settings_json","Settings","json","","YES","","","{}","Integration configuration"],
  ["cx_integration_account","last_sync_time","Last Sync Time","datetime","","YES","","","",""],
  ["cx_automation_rule","rule_id","Rule ID","bigint","20","NO","PK","","3001",""],
  ["cx_automation_rule","rule_name","Rule Name","varchar","160","NO","","","Route Paid Orders",""],
  ["cx_automation_rule","trigger_event","Trigger Event","varchar","80","NO","IDX","","order_created",""],
  ["cx_automation_rule","condition_json","Conditions","json","","YES","","","{}","Rule condition tree"],
  ["cx_automation_rule","action_json","Actions","json","","NO","","","{}","Rule actions"],
  ["cx_automation_rule","priority","Priority","int","11","NO","","100","100","Lower runs earlier"],
  ["cx_automation_rule","enabled","Enabled","tinyint","1","NO","","1","1",""],
  ["cx_automation_rule","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
  ["cx_user","user_id","User ID","bigint","20","NO","PK","","12",""],
  ["cx_user","username","Username","varchar","80","NO","UK","","admin",""],
  ["cx_user","display_name","Display Name","varchar","120","YES","","","Admin",""],
  ["cx_user","email","Email","varchar","255","YES","IDX","","admin@example.com",""],
  ["cx_user","role_id","Role ID","bigint","20","YES","FK","","1",""],
  ["cx_user","status","Status","varchar","20","NO","","active","active","active, disabled"],
  ["cx_role","role_id","Role ID","bigint","20","NO","PK","","1",""],
  ["cx_role","role_name","Role Name","varchar","80","NO","UK","","Administrator",""],
  ["cx_role","permission_json","Permissions","json","","NO","","","{}","Menu/API permissions"],
  ["cx_audit_log","audit_id","Audit ID","bigint","20","NO","PK","","9001",""],
  ["cx_audit_log","actor_user_id","Actor","bigint","20","YES","FK","","12",""],
  ["cx_audit_log","entity_type","Entity Type","varchar","80","NO","IDX","","cx_order",""],
  ["cx_audit_log","entity_id","Entity ID","varchar","80","NO","IDX","","100001",""],
  ["cx_audit_log","action","Action","varchar","80","NO","IDX","","update","create, update, delete, export, login"],
  ["cx_audit_log","before_json","Before","json","","YES","","","{}",""],
  ["cx_audit_log","after_json","After","json","","YES","","","{}",""],
  ["cx_audit_log","ip_address","IP Address","varchar","45","YES","","","52.94.123.166",""],
  ["cx_audit_log","created_time","Created Time","datetime","","NO","IDX","CURRENT_TIMESTAMP","",""],
  ["cx_file_attachment","attachment_id","Attachment ID","bigint","20","NO","PK","","12001",""],
  ["cx_file_attachment","order_id","Order ID","bigint","20","YES","FK","","100001",""],
  ["cx_file_attachment","order_item_id","Order Item ID","bigint","20","YES","FK","","90001",""],
  ["cx_file_attachment","file_type","File Type","varchar","40","NO","","","packing_slip","label, invoice, artwork, packing_slip"],
  ["cx_file_attachment","file_name","File Name","varchar","255","NO","","","label.pdf",""],
  ["cx_file_attachment","file_url","File URL","varchar","500","NO","","","https://...","Prefer object storage URL"],
  ["cx_file_attachment","created_time","Created Time","datetime","","NO","","CURRENT_TIMESTAMP","",""],
];

const relationships = [
  ["cx_order.customer_id", "cx_customer.customer_id", "many-to-one", "Each order belongs to one customer when known"],
  ["cx_order.folder_id", "cx_order_folder.folder_id", "many-to-one", "Orders live in one operational folder"],
  ["cx_order_item.order_id", "cx_order.order_id", "many-to-one", "One order has many items"],
  ["cx_order_item.inventory_item_id", "cx_inventory_item.inventory_item_id", "many-to-one", "Optional SKU normalization"],
  ["cx_order_address.order_id", "cx_order.order_id", "many-to-one", "Shipping/customer/return addresses per order"],
  ["cx_payment.order_id", "cx_order.order_id", "one-to-many", "Allow split payments/refunds"],
  ["cx_shipment.order_id", "cx_order.order_id", "one-to-many", "Partial shipments supported"],
  ["cx_order_discount.order_id", "cx_order.order_id", "one-to-many", "Multiple discounts per order"],
  ["cx_order_note.order_id", "cx_order.order_id", "one-to-many", "Operational notes"],
  ["cx_order_tag.order_id", "cx_order.order_id", "one-to-many", "Multiple tags per order"],
  ["cx_order_history.order_id", "cx_order.order_id", "one-to-many", "Append-only event timeline"],
  ["cx_order.owner_user_id", "cx_user.user_id", "many-to-one", "Assigned owner"],
  ["cx_user.role_id", "cx_role.role_id", "many-to-one", "User permission role"],
  ["cx_file_attachment.order_id", "cx_order.order_id", "many-to-one", "Order-level files"],
  ["cx_file_attachment.order_item_id", "cx_order_item.order_item_id", "many-to-one", "Item-level artwork/files"],
];

const picklists = [
  ["order.status", "new, prepared, on_hold, shipped, closed, canceled"],
  ["payment_status", "Approved, Authorized, Captured, Fully Refunded, Partially Refunded, Pending, Rejected, Voided"],
  ["fulfillment_status", "unfulfilled, routed, partially_shipped, shipped, canceled"],
  ["delivery_type", "ship, noship, download, future"],
  ["address_type", "shipping, customer, billing, return"],
  ["shipment.status", "created, label_printed, shipped, delivered, returned, canceled"],
  ["integration_type", "cart, marketplace, payment, shipping, fulfillment, email, webhook"],
  ["rule.trigger_event", "order_created, order_updated, payment_captured, folder_changed, shipment_created, inventory_low"],
  ["file_type", "label, invoice, artwork, packing_slip, receipt, customs_doc"],
];

function title(sheet, text, subtitle = "") {
  sheet.showGridLines = false;
  sheet.getRange("A1:H1").merge();
  sheet.getRange("A1").values = [[text]];
  sheet.getRange("A1").format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };
  sheet.getRange("A1").format.rowHeight = 30;
  if (subtitle) {
    sheet.getRange("A2:H2").merge();
    sheet.getRange("A2").values = [[subtitle]];
    sheet.getRange("A2").format = { fill: subFill, font: { color: "#334155" }, wrapText: true };
    sheet.getRange("A2").format.rowHeight = 38;
  }
}

function writeTable(sheet, startCell, headers, rows, tableName) {
  const startCol = startCell.match(/[A-Z]+/)[0];
  const startRow = Number(startCell.match(/\d+/)[0]);
  const data = [headers, ...rows];
  const endCol = String.fromCharCode(startCol.charCodeAt(0) + headers.length - 1);
  const endRow = startRow + data.length - 1;
  const range = sheet.getRange(`${startCell}:${endCol}${endRow}`);
  range.values = data;
  sheet.getRange(`${startCell}:${endCol}${startRow}`).format = {
    fill: headerFill,
    font: { bold: true, color: navy },
    borders: { preset: "doubleBottom", style: "thin", color: border },
  };
  range.format.borders = { preset: "outside", style: "thin", color: border };
  range.format.wrapText = true;
  const table = sheet.tables.add(`${startCell}:${endCol}${endRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  return range;
}

const overview = workbook.worksheets.add("Overview");
title(overview, "Order Desk Style OMS Database Design", "Reference workbook for building a CellX/RDP order management platform similar to Order Desk.");
overview.getRange("A4:B12").values = [
  ["Purpose", "Design database fields and import Excel templates for an order desk platform."],
  ["Primary access pattern", "Orders list, search, order detail, payment, shipping, fulfillment, inventory, automation."],
  ["Recommended UI split", "Marketing site on cellaidata.com, app on app.cellaidata.com."],
  ["Key warning", "Date fields must be real yyyy-mm-dd hh:mm:ss datetimes, not Excel serial numbers such as 46244.3236111111."],
  ["Source reference", sourceUrl],
  ["Suggested DB", "MySQL 8 compatible schema using bigint PKs, varchar identifiers, decimal money fields, JSON extension fields."],
  ["MVP tables", "cx_order, cx_order_item, cx_customer, cx_order_address, cx_payment, cx_shipment, cx_inventory_item."],
  ["Phase 2 tables", "automation rules, integrations, audit logs, attachments, advanced permissions."],
  ["Generated on", new Date()],
];
overview.getRange("A4:A12").format = { fill: headerFill, font: { bold: true, color: navy } };
overview.getRange("B4:B12").format.wrapText = true;
overview.getRange("B12").setNumberFormat("yyyy-mm-dd hh:mm:ss");
overview.getRange("A14:D14").values = [["Metric", "Formula", "Value", "Meaning"]];
overview.getRange("A15:D18").values = [
  ["Table count", "=COUNTA('ERD'!A5:A100)", null, "Number of proposed DB tables"],
  ["Field count", "=COUNTA('Field Dictionary'!B5:B300)", null, "Number of proposed columns"],
  ["MVP table count", "7", 7, "Tables needed for first usable order flow"],
  ["Import templates", "3", 3, "Orders, items, shipments"],
];
overview.getRange("C15").formulas = [["=COUNTA('ERD'!A5:A100)"]];
overview.getRange("C16").formulas = [["=COUNTA('Field Dictionary'!B5:B300)"]];
overview.getRange("A14:D18").format.borders = { preset: "all", style: "thin", color: border };
overview.getRange("A14:D14").format = { fill: headerFill, font: { bold: true, color: navy } };
overview.getRange("A:A").format.columnWidth = 24;
overview.getRange("B:B").format.columnWidth = 72;
overview.getRange("C:D").format.columnWidth = 18;

const erd = workbook.worksheets.add("ERD");
title(erd, "Tables and Relationships", "Use this sheet as the implementation map before creating menus, forms, and child tables in RDP.");
writeTable(erd, "A4", ["Table", "Module", "Purpose", "Primary Key"], tables, "TablesTable");
writeTable(erd, "F4", ["From", "To", "Cardinality", "Notes"], relationships, "RelationshipsTable");
erd.getRange("A:D").format.columnWidth = 28;
erd.getRange("F:I").format.columnWidth = 30;
erd.freezePanes.freezeRows(4);

const dict = workbook.worksheets.add("Field Dictionary");
title(dict, "Field Dictionary", "Column-level database design. Required, key, type, and examples are prepared for table-generation work.");
writeTable(dict, "A4", ["Table", "Field", "Display Name", "DB Type", "Length", "Required", "Key", "Default", "Example", "Notes"], fields, "FieldDictionaryTable");
dict.getRange("A:J").format.columnWidth = 18;
dict.getRange("C:C").format.columnWidth = 24;
dict.getRange("J:J").format.columnWidth = 42;
dict.getRange("F5:F205").dataValidation = { rule: { type: "list", values: ["YES", "NO"] } };
dict.freezePanes.freezeRows(4);
dict.freezePanes.freezeColumns(2);

const orderImportHeaders = [
  "external_order_id","source_name","email","customer_first_name","customer_last_name","customer_company","customer_phone",
  "shipping_first_name","shipping_last_name","shipping_company","shipping_address1","shipping_address2","shipping_city",
  "shipping_state","shipping_postal_code","shipping_country","shipping_phone","shipping_method","payment_type",
  "payment_status","product_total","shipping_total","handling_total","tax_total","discount_total","refund_total",
  "order_total","currency","order_date","ip_address","checkout_data_json","metadata_json"
];
const orderImportExample = [
  "OD-10001","Shopify","buyer@example.com","Jimmy","Dean","","555-555-5555",
  "Jimmy","Dean","","800 Emmet St","","Nashville","TN","55555","US","555-555-5555","UPS Ground","Visa",
  "Captured",39.98,9.50,0,1.25,5.00,0,45.73,"USD",new Date("2026-08-30T10:30:00"),"181.16.150.12","{\"PackingSlip\":\"url\"}","{\"fraud_score\":0}"
];

const importOrders = workbook.worksheets.add("Import Orders");
title(importOrders, "Excel Import Template - Orders", "Copy this header row for order header imports. Keep date values as yyyy-mm-dd hh:mm:ss.");
writeTable(importOrders, "A4", orderImportHeaders, [orderImportExample], "ImportOrdersTable");
importOrders.getRange("AC5:AC5").setNumberFormat("yyyy-mm-dd hh:mm:ss");
importOrders.getRange("A:AF").format.columnWidth = 20;
importOrders.freezePanes.freezeRows(4);

const itemHeaders = ["external_order_id","sku","item_name","category_code","delivery_type","quantity","unit_price","unit_cost","weight","variation_json","metadata_json","fulfillment_method"];
const itemExample = ["OD-10001","SKU-BLK-001","Black Shirt","DEFAULT","ship",1,19.99,8.50,1.10,"{\"Size\":\"Large\",\"Color\":\"Black\"}","{\"image\":\"https://example.com/image.jpg\"}","Warehouse"];
const importItems = workbook.worksheets.add("Import Order Items");
title(importItems, "Excel Import Template - Order Items", "Use external_order_id to connect line items to imported orders.");
writeTable(importItems, "A4", itemHeaders, [itemExample], "ImportItemsTable");
importItems.getRange("A:L").format.columnWidth = 22;
importItems.freezePanes.freezeRows(4);

const shipmentHeaders = ["external_order_id","tracking_number","carrier_code","shipment_method","weight","cost","status","tracking_url","label_format","label_url","print_status","date_shipped"];
const shipmentExample = ["OD-10001","1Z132456789","UPS","UPS Ground",2.375,7.50,"shipped","https://carrier.example/track/1Z132456789","PDF","https://files.example/label.pdf",1,new Date("2026-08-31T00:00:00")];
const importShipments = workbook.worksheets.add("Import Shipments");
title(importShipments, "Excel Import Template - Shipments", "Use this sheet after orders are imported or synced.");
writeTable(importShipments, "A4", shipmentHeaders, [shipmentExample], "ImportShipmentsTable");
importShipments.getRange("L5:L5").setNumberFormat("yyyy-mm-dd");
importShipments.getRange("A:L").format.columnWidth = 22;
importShipments.freezePanes.freezeRows(4);

const lists = workbook.worksheets.add("Picklists");
title(lists, "Picklists and Validation Values", "Use these values for dropdowns, enums, and field validation.");
writeTable(lists, "A4", ["Field", "Allowed Values"], picklists, "PicklistsTable");
lists.getRange("A:A").format.columnWidth = 28;
lists.getRange("B:B").format.columnWidth = 90;

const notes = workbook.worksheets.add("Implementation Notes");
title(notes, "Implementation Notes", "Practical notes for building this in CellX/RDP and avoiding common import failures.");
notes.getRange("A4:C14").values = [
  ["Area", "Recommendation", "Reason"],
  ["Order date", "Store as datetime and import as yyyy-mm-dd hh:mm:ss.", "Prevents MySQL Incorrect datetime errors from Excel serial values."],
  ["Money", "Use decimal(12,2), never float/double.", "Avoids rounding issues in order totals and refunds."],
  ["Identifiers", "Keep external ids, postal codes, tracking numbers, SKUs as varchar.", "Leading zeros and letters must be preserved."],
  ["Address", "Use a child table with address_type.", "Supports shipping, billing/customer, and return addresses without many duplicate columns."],
  ["Metadata", "Use JSON columns for flexible channel-specific fields.", "Keeps core schema stable while integrations differ."],
  ["Payments", "Do not store full card numbers.", "Store masked number and gateway transaction id only."],
  ["Search", "Index external_order_id, email, status, payment_status, order_date, tracking_number.", "Matches common Order Desk list filters."],
  ["Security", "Limit export/import and integration settings to admin roles.", "These areas expose sensitive customer and payment-adjacent data."],
  ["Automation", "Keep rules in JSON but log each execution to order_history.", "Makes workflow behavior auditable."],
  ["Source", sourceUrl, "Order Desk public API reference used for field inspiration."],
];
notes.getRange("A4:C4").format = { fill: headerFill, font: { bold: true, color: navy } };
notes.getRange("A4:C14").format.borders = { preset: "all", style: "thin", color: border };
notes.getRange("A:A").format.columnWidth = 24;
notes.getRange("B:B").format.columnWidth = 70;
notes.getRange("C:C").format.columnWidth = 62;
notes.getRange("A4:C14").format.wrapText = true;

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  used.format.font.name = "Aptos";
  used.format.font.size = 10;
  used.format.verticalAlignment = "top";
  used.format.autofitRows();
}

await fs.mkdir(outputDir, { recursive: true });
for (const sheet of workbook.worksheets.items) {
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
  const safeName = sheet.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
  await fs.writeFile(`${outputDir}/${safeName}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const overviewInspect = await workbook.inspect({
  kind: "table",
  range: "Overview!A4:D18",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
});
console.log(overviewInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/order_desk_database_design.xlsx`);
console.log(`${outputDir}/order_desk_database_design.xlsx`);
