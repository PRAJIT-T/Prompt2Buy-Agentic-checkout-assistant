from pydantic import BaseModel
from typing import List, Optional,Dict
from datetime import datetime
from enum import Enum

# --- Core Data Models ---

class Product(BaseModel):
    """Represents a single product in the catalog."""
    id: str
    name: str
    description: str
    price: float
    stock: int
    category: str = "General"
    image_url: str = ""

class CartItem(BaseModel):
    """Represents an item within a shopping cart."""
    product_id: str
    quantity: int
    price: float

class Cart(BaseModel):
    """Represents a customer's shopping cart."""
    id: str
    items: Dict[str,CartItem]
    total_amount: float
    created_at: datetime

class OrderStatus(str,Enum):
    PENDING = "pending"
    PAID="paid"
    SHIPPED="shipped"
    CANCELLED="cancelled"


class Order(BaseModel):
    """Represents a customer order."""
    id: str
    customer_id: str
    items: List[CartItem]
    total_amount: float
    status: OrderStatus  # e.g., 'pending', 'paid', 'shipped', 'cancelled'
    created_at: datetime
    updated_at: datetime
    razorpay_order_id: Optional[str] = None

# --- Utility/State Models ---

class AuditLogEntry(BaseModel):
    """A log entry for tracking state mutations."""
    timestamp: datetime
    event_type: str  # e.g., 'CART_CREATED', 'ITEM_ADDED', 'ORDER_PLACED'
    user_id: Optional[str]
    details: dict
    status: str = "SUCCESS"

# Note: These models are designed to be used by the pure functions in other modules.
# They define the expected structure for data exchange.
