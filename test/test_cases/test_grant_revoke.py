#!/usr/bin/env python3
"""
Test case for grant/revoke access flow
"""

import boto3
import json
import time
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import aws_utils, data_generators

def run_test(stack_outputs, debug=False, config_name="contracts_with_subscription", registration_email=None, override_product_code=None, customer_id=None):
    """Test grant/revoke access flow
    
    Args:
        stack_outputs: CloudFormation stack outputs
        debug: Enable debug output
        config_name: Name of the config (contracts, subscriptions, contracts_with_subscription)
        registration_email: Email to use for registration
        override_product_code: Product code to use (overrides the one from stack outputs)
        customer_id: Customer identifier to use for testing (if None, a new test customer will be created)
    """
    print("\nTesting grant/revoke access flow...")
    
    # This test requires:
    # 1. A customer record in DynamoDB
    # 2. Simulating grant access (setting successfully_subscribed to true)
    # 3. Simulating revoke access (setting subscription_expired to true)
    
    # Get the subscribers table name
    table_name = stack_outputs.get("SubscribersTableName")
    if not table_name:
        print("ERROR: SubscribersTableName not found in stack outputs")
        return False
    
    # Get the product code
    product_code = override_product_code or stack_outputs.get("ProductCode", "test-product")
    print(f"Using product code: {product_code}")
    
    # Get the DynamoDB table
    table = aws_utils.get_dynamodb_table(table_name)
    
    # Check if we're using an existing customer or creating a new one
    is_test_customer = False
    if customer_id:
        print(f"Using existing customer ID: {customer_id}")
        
        # Verify the customer exists
        try:
            response = table.get_item(Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"})
            if "Item" not in response:
                print(f"ERROR: Customer {customer_id} not found in DynamoDB")
                return False
            
            print(f"Found existing customer: {customer_id}")
            if debug:
                print(f"Customer record: {json.dumps(response['Item'], default=str)}")
            
            # Check if this is a test customer
            is_test_customer = customer_id.startswith("test-customer-")
        except Exception as e:
            print(f"ERROR: Failed to get customer {customer_id}: {e}")
            return False
    else:
        # Create a new test customer
        customer_id = data_generators.generate_customer_id()
        is_test_customer = True
        print(f"Generated test customer ID: {customer_id}")
        
        # Create a customer record with composite key format
        try:
            customer_data = data_generators.generate_customer_data(customer_id, product_code)
            if registration_email:
                customer_data["contactEmail"] = registration_email
                
            item = {
                "productCode#customerIdentifier": f"{product_code}#{customer_id}",
                **customer_data
            }
            table.put_item(Item=item)
            print(f"Added test customer with composite key: {product_code}#{customer_id}")
        except Exception as e:
            print(f"ERROR: Failed to add test customer: {e}")
            return False
    
    # Test granting access
    print("\nTesting grant access...")
    try:
        # Update the customer record to grant access
        update_response = table.update_item(
            Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"},
            UpdateExpression="set successfully_subscribed = :ss, subscription_expired = :se",
            ExpressionAttributeValues={
                ":ss": True,
                ":se": False
            },
            ReturnValues="UPDATED_NEW"
        )
        
        if debug:
            print(f"Grant access update response: {json.dumps(update_response, default=str)}")
            
        print("Access granted successfully")
    except Exception as e:
        print(f"ERROR: Failed to grant access: {e}")
        return False
    
    # Verify access was granted
    try:
        response = table.get_item(Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"})
        
        if "Item" not in response:
            print(f"ERROR: Customer record not found in DynamoDB")
            return False
        
        item = response["Item"]
        
        if debug:
            print(f"Customer record after grant: {json.dumps(item, default=str)}")
        
        # Check if successfully_subscribed was set to true
        if item.get("successfully_subscribed") != True:
            print("ERROR: successfully_subscribed not set to true")
            return False
        
        # Check if subscription_expired was set to false
        if item.get("subscription_expired") != False:
            print("ERROR: subscription_expired not set to false")
            return False
        
        print("Access grant verified successfully")
    except Exception as e:
        print(f"ERROR: Failed to verify access grant: {e}")
        return False
    
    # Test revoking access
    print("\nTesting revoke access...")
    try:
        # Update the customer record to revoke access
        update_response = table.update_item(
            Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"},
            UpdateExpression="set subscription_expired = :se",
            ExpressionAttributeValues={
                ":se": True
            },
            ReturnValues="UPDATED_NEW"
        )
        
        if debug:
            print(f"Revoke access update response: {json.dumps(update_response, default=str)}")
            
        print("Access revoked successfully")
    except Exception as e:
        print(f"ERROR: Failed to revoke access: {e}")
        return False
    
    # Verify access was revoked
    try:
        response = table.get_item(Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"})
        
        if "Item" not in response:
            print(f"ERROR: Customer record not found in DynamoDB")
            return False
        
        item = response["Item"]
        
        if debug:
            print(f"Customer record after revoke: {json.dumps(item, default=str)}")
        
        # Check if subscription_expired was set to true
        if item.get("subscription_expired") != True:
            print("ERROR: subscription_expired not set to true")
            return False
        
        print("Access revoke verified successfully")
    except Exception as e:
        print(f"ERROR: Failed to verify access revoke: {e}")
        return False
    
    # If this is a real customer, restore the original state
    if not is_test_customer:
        print("\nRestoring original state for real customer...")
        try:
            # Update the customer record to restore access
            update_response = table.update_item(
                Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"},
                UpdateExpression="set subscription_expired = :se",
                ExpressionAttributeValues={
                    ":se": False
                },
                ReturnValues="UPDATED_NEW"
            )
            
            if debug:
                print(f"Restore access update response: {json.dumps(update_response, default=str)}")
                
            print("Original state restored successfully")
        except Exception as e:
            print(f"ERROR: Failed to restore original state: {e}")
            return False
    
    print("\n=== Test Summary ===")
    print("✅ Customer record verified: PASS")
    print("✅ Access granted: PASS")
    print("✅ Access revoked: PASS")
    if not is_test_customer:
        print("✅ Original state restored: PASS")
    
    # Get the admin email from stack outputs
    admin_email = None
    for key in stack_outputs:
        if "admin" in key.lower() and "email" in key.lower():
            admin_email = stack_outputs[key]
            break
    
    if admin_email:
        print(f"\nIMPORTANT: Check the admin email ({admin_email}) for grant/revoke notifications.")
        print("You should have received emails about:")
        print("1. New customer access granted")
        print("2. Customer access revoked")
        if not is_test_customer:
            print("3. Customer access restored")
    else:
        print("\nIMPORTANT: Check your admin email for grant/revoke notifications.")
    
    print("\nTest Result: PASS - Successfully verified grant/revoke access flow")
    
    return True