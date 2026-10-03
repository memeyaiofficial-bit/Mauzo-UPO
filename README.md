# Cosmetics POS

A simple cosmetics point-of-sale and stock management system.

## Product model
Adding a product can include its **initial stock in the same form**. This prevents the old double-entry workflow of creating a product first and then immediately receiving that same opening stock separately.

Required when adding a product:
- Product name
- Selling price
- Initial stock may be 0 if the product is not yet in stock

Optional:
- Brand
- Variant / shade / size
- Category
- Barcode
- Manufacturer
- Description
- Reorder level
- Initial unit cost
- Initial batch / expiry

## Stock receiving
Receiving stock adds the received quantity to the existing inventory total. Example: existing stock 5 + received 10 = 15 available units.

## Removed pharmacy functionality
This version removes the medicine-specific catalogue fields and workflows, including prescriptions, PPB/regulatory medicine sync, dosage/strength/route, controlled-drug flags and pharmacy-specific product fields.

## Run locally
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Set `SECRET_KEY` and database settings in `.env`.
