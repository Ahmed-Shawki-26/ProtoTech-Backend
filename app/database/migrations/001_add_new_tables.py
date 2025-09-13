# Migration: Add new tables from proto_tech3-main
# This migration adds the new tables that your friend created

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    """Add new tables to the database"""
    
    # Create OrderStatus enum
    order_status_enum = postgresql.ENUM(
        'PENDING', 'PROCESSING', 'COMPLETED', 'SHIPPED', 'CANCELLED', 'FAILED',
        name='orderstatus',
        create_type=False
    )
    order_status_enum.create(op.get_bind())
    
    # Create PaymentStatus enum
    payment_status_enum = postgresql.ENUM(
        'PENDING', 'PAID', 'FAILED', 'REFUNDED',
        name='paymentstatus',
        create_type=False
    )
    payment_status_enum.create(op.get_bind())
    
    # Create PCB OrderStatus enum
    pcb_order_status_enum = postgresql.ENUM(
        'PENDING', 'PROCESSING', 'COMPLETED', 'SHIPPED', 'CANCELLED', 'FAILED',
        name='pcb_orderstatus',
        create_type=False
    )
    pcb_order_status_enum.create(op.get_bind())
    
    # Create orders table
    op.create_table('orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_number', sa.String(), nullable=False, unique=True),
        sa.Column('total_amount', sa.Integer(), nullable=False),  # Stored in cents/piastres
        sa.Column('shipping_cost', sa.Integer(), nullable=False, default=0),
        sa.Column('tax_amount', sa.Integer(), nullable=False, default=0),
        sa.Column('discount_amount', sa.Integer(), nullable=False, default=0),
        sa.Column('shipping_address', sa.JSON(), nullable=False),
        sa.Column('billing_address', sa.JSON(), nullable=True),
        sa.Column('status', order_status_enum, nullable=False, default='PENDING'),
        sa.Column('payment_status', payment_status_enum, nullable=False, default='PENDING'),
        sa.Column('stripe_session_id', sa.String(), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(), nullable=True),
        sa.Column('tracking_number', sa.String(), nullable=True),
        sa.Column('shipping_method', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    
    # Create indexes for orders table
    op.create_index('ix_orders_user_id', 'orders', ['user_id'])
    op.create_index('ix_orders_stripe_session_id', 'orders', ['stripe_session_id'])
    op.create_index('ix_orders_stripe_payment_intent_id', 'orders', ['stripe_payment_intent_id'])
    
    # Create order_items table
    op.create_table('order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),  # Odoo product ID
        sa.Column('product_name', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),  # Stored in cents/piastres
        sa.Column('total_price', sa.Integer(), nullable=False),  # Stored in cents/piastres
        sa.Column('product_data', sa.JSON(), nullable=True),  # Extra details like color, options
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
    )
    
    # Create index for order_items table
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])
    
    # Create pcb_orders table
    op.create_table('pcb_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_number', sa.String(), nullable=False, unique=True),
        sa.Column('status', pcb_order_status_enum, nullable=False, default='PENDING'),
        sa.Column('width_mm', sa.Float(), nullable=False),
        sa.Column('height_mm', sa.Float(), nullable=False),
        sa.Column('final_price_egp', sa.Float(), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(), nullable=True),
        sa.Column('base_material', sa.String(), nullable=False),
        sa.Column('manufacturing_parameters', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    
    # Create indexes for pcb_orders table
    op.create_index('ix_pcb_orders_user_id', 'pcb_orders', ['user_id'])
    op.create_index('ix_pcb_orders_order_number', 'pcb_orders', ['order_number'], unique=True)
    op.create_index('ix_pcb_orders_stripe_payment_intent_id', 'pcb_orders', ['stripe_payment_intent_id'])
    
    # Create user_carts table
    op.create_table('user_carts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('items', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

def downgrade():
    """Remove the new tables"""
    op.drop_table('user_carts')
    op.drop_table('pcb_orders')
    op.drop_table('order_items')
    op.drop_table('orders')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS pcb_orderstatus')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS orderstatus')
