# CUS SO & FnV Sales Order Automation Platform

Welcome to the **CUS SO & FnV Sales Order Automation Platform** documentation repository. This platform provides an end-to-end automated pipeline for processing Grocery (GRO), Fruits & Vegetables (FnV), and Brand Purchase Orders (PO), generating standardized Sales Orders (SO) and Purchase Orders for multiple cities across India.

---

## 📚 Master Documentation Index

| Document | Description | Target Audience |
| :--- | :--- | :--- |
| 🏗️ [**ARCHITECTURE.md**](file:///d:/CUS%20SO/ARCHITECTURE.md) | Technical architecture, system components, data flows, database schemas, and API routes. | Developers & System Architects |
| 🚨 [**ERROR_LOG_AND_EDGE_CASES.md**](file:///d:/CUS%20SO/ERROR_LOG_AND_EDGE_CASES.md) | Failure modes, DB lookup fallbacks, edge cases, error logs, and troubleshooting matrix. | Developers & Support Engineers |
| 📋 [**DB_Lookup_and_Output_Formats.md**](file:///d:/CUS%20SO/DB_Lookup_and_Output_Formats.md) | Database queries, city mappings, and side-by-side format specifications. | Data Analysts & Engineers |
| 🔄 [**Institutional_Format_Changes.md**](file:///d:/CUS%20SO/Institutional_Format_Changes.md) | Detailed mapping rules for the Institutional SO output format. | Operations & Developers |
| 📜 [**CHANGELOG.md**](file:///d:/CUS%20SO/CHANGELOG.md) | Comprehensive log of system changes, feature releases, and architectural evolutions. | All Contributors |
| 📐 [**DOCUMENTATION_GUIDELINE.md**](file:///d:/CUS%20SO/DOCUMENTATION_GUIDELINE.md) | Standard operating protocol and templates for documenting future updates and issues. | AI Agents & Developers |

---

## ⚡ Quick System Overview

The platform transforms raw daily vendor/store allocation files into validated, upload-ready Sales Order CSV files and PO Mappings for major hubs:

* **Supported Cities**: Bangalore, Chennai, Mumbai, Hyderabad, Trichy, Coimbatore, Nashik.
* **Dual Format Generation**: Every run automatically produces both **Standard GRO SO CSV** (16 columns) and **Institutional SO CSV** (15 columns).
* **Hybrid Data Resolution Engine**:
  1. **Primary**: Live Google Sheets evaluation (Formula drag-down & cell reading).
  2. **Fallback**: Direct read-only MySQL Database lookup (`cyclops`, `asgard`, `vormir` databases) for instant resolution of missing SKUs, Prices, Lot IDs, and Customer Contacts.
* **FnV Two-Phase Optimization**: Parallel formula calculation engine reducing wait times from ~35s to ~10s across all cities.

---

## 🚀 Running the Application

### Prerequisites
* Python 3.9+
* Required packages listed in [`requirements.txt`](file:///d:/CUS%20SO/requirements.txt)
* MySQL database credentials in `db_credentials.json` (optional, for DB fallback)
* Google Service Account credentials (`xd-allocation-9640b0ce66d2.json` or `ecom-so-reader-credetials.json`)

### Installation & Execution
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the local Flask Server
python app.py
```
Access the web dashboard at `http://localhost:5000`.

---

## 🛠️ Main Components Reference

- **Flask Server Entrypoint**: [`app.py`](file:///d:/CUS%20SO/app.py) & [`api/index.py`](file:///d:/CUS%20SO/api/index.py)
- **GRO SO Engine**: [`automation_script.py`](file:///d:/CUS%20SO/automation_script.py)
- **FnV Multi-City Engine**: [`fnv_automation.py`](file:///d:/CUS%20SO/fnv_automation.py)
- **Brand PO Engine**: [`generate_brand_po.py`](file:///d:/CUS%20SO/generate_brand_po.py)
- **Direct Database Connector**: [`db_lookup.py`](file:///d:/CUS%20SO/db_lookup.py)
- **Web UI Dashboard**: [`templates/index.html`](file:///d:/CUS%20SO/templates/index.html)
