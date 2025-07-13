#!/usr/bin/env python3
"""
Utility functions for generating test data
"""

import uuid
import json
import random
from datetime import datetime, timedelta

def generate_customer_id():
    """Generate a unique customer ID"""
    return f"test-customer-{uuid.uuid4().hex[:8]}"

def generate_customer_data(customer_id=None, product_code=None):
    """Generate customer registration data"""
    if not customer_id:
        customer_id = generate_customer_id()
    
    return {
        "customerIdentifier": customer_id,
        "productCode": product_code,
        "companyName": f"Test Company {customer_id}",
        "contactPerson": "Test User",
        "contactEmail": f"test-{customer_id}@example.com",
        "contactPhone": f"123-456-{random.randint(1000, 9999)}",
        "timestamp": int(datetime.now().timestamp()),
        "registration_token": f"test-token-{uuid.uuid4().hex[:8]}"
    }

def generate_entitlement_notification(customer_id, product_code, dimensions=None):
    """Generate an entitlement notification"""
    if not dimensions:
        dimensions = [
            {
                "name": "admin_users",
                "value": random.randint(1, 5)
            },
            {
                "name": "users",
                "value": random.randint(5, 20)
            }
        ]
    
    expiration_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return {
        "action": "entitlement-updated",
        "customer-identifier": customer_id,
        "product-code": product_code,
        "dimensions": dimensions,
        "expiration-date": expiration_date
    }

def generate_subscription_notification(customer_id, product_code, action="subscribe-success"):
    """Generate a subscription notification"""
    return {
        "action": action,
        "customer-identifier": customer_id,
        "product-code": product_code
    }

def generate_metering_record(customer_id, product_code, dimensions=None):
    """Generate a metering record"""
    if not dimensions:
        dimensions = [
            {
                "dimension": "admin_users",
                "value": random.randint(1, 5)
            },
            {
                "dimension": "users",
                "value": random.randint(5, 20)
            }
        ]
    
    return {
        "customerIdentifier": customer_id,
        "productCode": product_code,
        "dimension_usage": dimensions,
        "create_timestamp": int(datetime.now().timestamp()),
        "metering_pending": "true"
    }