from alembic import op
import sqlalchemy as sa
revision='d0c0sm3t1c5'
down_revision='c9d4e15f7a02'
branch_labels=None
depends_on=None

def _table(conn,n): return sa.inspect(conn).has_table(n)
def _cols(conn,n): return {c['name'] for c in sa.inspect(conn).get_columns(n)} if _table(conn,n) else set()

def upgrade():
    conn=op.get_bind()
    # Rename the old pharmacist role to manager. PostgreSQL uses a native enum;
    # SQLite stores the value as text.
    if _table(conn,'users') and 'role' in _cols(conn,'users'):
        if conn.dialect.name == 'postgresql':
            role_column = next(
                column
                for column in sa.inspect(conn).get_columns('users')
                if column['name'] == 'role'
            )
            role_type = role_column['type']
            enums = sa.inspect(conn).get_enums()
            role_enum = next(
                (
                    enum for enum in enums
                    if enum['name'] == getattr(role_type, 'name', None)
                ),
                None,
            )
            if role_enum:
                old_labels = {'PHARMACIST', 'pharmacist'} & set(role_enum['labels'])
                if old_labels and 'MANAGER' not in role_enum['labels']:
                    quoted_type = conn.dialect.identifier_preparer.quote(role_enum['name'])
                    with op.get_context().autocommit_block():
                        conn.execute(sa.text(
                            f"ALTER TYPE {quoted_type} ADD VALUE 'MANAGER'"
                        ))
                if old_labels:
                    conn.execute(sa.text(
                        "UPDATE users SET role='MANAGER' "
                        "WHERE role::text IN ('PHARMACIST', 'pharmacist')"
                    ))
        else:
            conn.execute(sa.text(
                "UPDATE users SET role='MANAGER' "
                "WHERE role IN ('PHARMACIST','pharmacist')"
            ))
    if _table(conn,'medicines') and not _table(conn,'products'): op.rename_table('medicines','products')
    if _table(conn,'medicine_alerts') and not _table(conn,'product_alerts'): op.rename_table('medicine_alerts','product_alerts')
    for table in ('inventory','sale_items','po_items','product_alerts'):
        cols=_cols(conn,table)
        if 'medicine_id' in cols and 'product_id' not in cols: op.alter_column(table,'medicine_id',new_column_name='product_id')
    cols=_cols(conn,'users')
    if 'pharmacy_name' in cols and 'business_name' not in cols: op.alter_column('users','pharmacy_name',new_column_name='business_name')
    cols=_cols(conn,'mpesa_transactions')
    if 'pending_pharmacy_name' in cols and 'pending_business_name' not in cols: op.alter_column('mpesa_transactions','pending_pharmacy_name',new_column_name='pending_business_name')
    if _table(conn,'products') and 'variant' not in _cols(conn,'products'): op.add_column('products',sa.Column('variant',sa.String(200),nullable=True))
    drops={'generic_name','atc_code','who_eml_code','openfda_id','external_catalog_id','dosage_form','strength','route','requires_prescription','is_controlled','ppb_registration_no','ppb_pack_size','ppb_origin','ppb_distributor','ppb_status','regulatory_registration_no','regulatory_pack_size','regulatory_origin','regulatory_distributor','regulatory_status','item_type'}
    if _table(conn,'products'):
        for col in sorted(drops & _cols(conn,'products')): op.drop_column('products',col)
    if _table(conn,'customers'):
        for col in ('date_of_birth','id_number','insurance_no'):
            if col in _cols(conn,'customers'): op.drop_column('customers',col)
    if _table(conn,'prescriptions'): op.drop_table('prescriptions')
    if _table(conn,'inventory') and 'manufactured_at' in _cols(conn,'inventory'): op.drop_column('inventory','manufactured_at')

def downgrade(): raise RuntimeError('Cosmetics conversion is intentionally one-way.')
