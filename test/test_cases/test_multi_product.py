#!/usr/bin/env python3
"""
Test case for multi-product functionality
"""

import boto3
import json
import time
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import aws_utils, data_generators

def run_test(stack_outputs, debug=False, config_name="contracts_with_subscription", registration_email=None, override_product_code=None, customer_id=None, second_product_code=None):
    """Test multi-product functionality
    
    Args:
        stack_outputs: CloudFormation stack outputs
        debug: Enable debug output
        config_name: Name of the config (contracts, subscriptions, contracts_with_subscription)
        registration_email: Email to use for registration
        override_product_code: Product code to use (overrides the one from stack outputs)
        customer_id: Customer identifier to use for testing (if None, a new test customer will be created)
        second_product_code: Product code for the second product to test
    """
    print("\nTesting multi-product functionality...")
    
    # This test requires:
    # 1. A primary product code
    # 2. A secondary product code
    # 3. DynamoDB tables with multi-product schema
    
    # Get the subscribers table name
    subscribers_table_name = stack_outputs.get("SubscribersTableName")
    if not subscribers_table_name:
        print("ERROR: SubscribersTableName not found in stack outputs")
        return False
    
    # Get the primary product code
    primary_product_code = override_product_code or stack_outputs.get("ProductCode", "test-product")
    print(f"Using primary product code: {primary_product_code}")
    
    # Get the secondary product code
    if not second_product_code:
        second_product_code = f"test-product-{uuid.uuid4().hex[:8]}"
        print(f"No secondary product code provided, using generated code: {second_product_code}")
    else:
        print(f"Using provided secondary product code: {second_product_code}")
    
    # Get the DynamoDB table
    subscribers_table = aws_utils.get_dynamodb_table(subscribers_table_name)
    
    # Create a test customer for the primary product
    primary_customer_id = customer_id or data_generators.generate_customer_id()
    print(f"Using customer ID for primary product: {primary_customer_id}")
    
    # Create a customer record for the primary product
    try:
        primary_customer_data = data_generators.generate_customer_data(primary_customer_id, primary_product_code)
        if registration_email:
            primary_customer_data["contactEmail"] = registration_email
            
        primary_item = {
            "productCode#customerIdentifier": f"{primary_product_code}#{primary_customer_id}",
            **primary_customer_data
        }
        
        # Check if the customer already exists
        try:
            response = subscribers_table.get_item(Key={"productCode#customerIdentifier": f"{primary_product_code}#{primary_customer_id}"})
            if "Item" not in response:
                # Customer doesn't exist, create it
                subscribers_table.put_item(Item=primary_item)
                print(f"Added customer for primary product with composite key: {primary_product_code}#{primary_customer_id}")
            else:
                print(f"Customer for primary product already exists with composite key: {primary_product_code}#{primary_customer_id}")
                if debug:
                    print(f"Primary customer record: {json.dumps(response['Item'], default=str)}")
        except Exception as e:
            print(f"ERROR: Failed to check if primary customer exists: {e}")
            return False
    except Exception as e:
        print(f"ERROR: Failed to add customer for primary product: {e}")
        return False
    
    # Create a customer record for the secondary product with the same customer ID
    try:
        secondary_customer_data = data_generators.generate_customer_data(primary_customer_id, second_product_code)
        if registration_email:
            secondary_customer_data["contactEmail"] = registration_email
            
        secondary_item = {
            "productCode#customerIdentifier": f"{second_product_code}#{primary_customer_id}",
            **secondary_customer_data
        }
        
        subscribers_table.put_item(Item=secondary_item)
        print(f"Added customer for secondary product with composite key: {second_product_code}#{primary_customer_id}")
    except Exception as e:
        print(f"ERROR: Failed to add customer for secondary product: {e}")
        return False
    
    # Verify both records exist
    try:
        # Check primary product record
        primary_response = subscribers_table.get_item(Key={"productCode#customerIdentifier": f"{primary_product_code}#{primary_customer_id}"})
        if "Item" not in primary_response:
            print(f"ERROR: Primary product customer record not found in DynamoDB")
            return False
        
        print("Primary product customer record found in DynamoDB")
        if debug:
            print(f"Primary product customer record: {json.dumps(primary_response['Item'], default=str)}")
        
        # Check secondary product record
        secondary_response = subscribers_table.get_item(Key={"productCode#customerIdentifier": f"{second_product_code}#{primary_customer_id}"})
        if "Item" not in secondary_response:
            print(f"ERROR: Secondary product customer record not found in DynamoDB")
            return False
        
        print("Secondary product customer record found in DynamoDB")
        if debug:
            print(f"Secondary product customer record: {json.dumps(secondary_response['Item'], default=str)}")
    except Exception as e:
        print(f"ERROR: Failed to verify customer records: {e}")
        return False
    
    # Test querying across products using the GSI
    try:
        print("\nTesting cross-product query using GSI...")
        
        # Query the CustomerIdentifierIndex GSI
        response = subscribers_table.query(
            IndexName="CustomerIdentifierIndex",
            KeyConditionExpression="customerIdentifier = :customerId",
            ExpressionAttributeValues={
                ":customerId": primary_customer_id
            }
        )
        
        if not response.get("Items"):
            print("ERROR: No items found in cross-product query")
            return False
        
        print(f"Found {len(response['Items'])} items in cross-product query")
        
        # Verify we found records for both products
        product_codes = set()
        for item in response["Items"]:
            if "productCode" in item:
                product_codes.add(item["productCode"])
        
        if primary_product_code not in product_codes:
            print(f"ERROR: Primary product code {primary_product_code} not found in cross-product query results")
            return False
        
        if second_product_code not in product_codes:
            print(f"ERROR: Secondary product code {second_product_code} not found in cross-product query results")
            return False
        
        print(f"Cross-product query successfully found records for both products: {', '.join(product_codes)}")
        
        if debug:
            print(f"Cross-product query results: {json.dumps(response['Items'], default=str)}")
    except Exception as e:
        print(f"ERROR: Failed to perform cross-product query: {e}")
        return False
    
    print("\n=== Test Summary ===")
    print("✅ Primary product customer record created: PASS")
    print("✅ Secondary product customer record created: PASS")
    print("✅ Cross-product query using GSI: PASS")
    print("\nTest Result: PASS - Successfully verified multi-product functionality")
    
    return True

if __name__ == "__main__":
    # This allows the test to be run directly
    import argparse
    
    parser = argparse.ArgumentParser(description="Test multi-product functionality")
    parser.add_argument("--stack-name", required=True, help="CloudFormation stack name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--email", help="Email to use for registration")
    parser.add_argument("--product-code", help="Primary product code")
    parser.add_argument("--customer-id", help="Customer identifier to use")
    parser.add_argument("--second-product-code", required=True, help="Secondary product code")
    
    args = parser.parse_args()
    
    # Get stack outputs
    cloudformation = boto3.client('cloudformation', region_name=args.region)
    response = cloudformation.describe_stacks(StackName=args.stack_name)
    stack_outputs = {output["OutputKey"]: output["OutputValue"] 
                   for output in response["Stacks"][0]["Outputs"]}
    
    # Run the test
    success = run_test(
        stack_outputs,
        args.debug,
        "contracts_with_subscription",
        args.email,
        args.product_code,
        args.customer_id,
        args.second_product_code
    )
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)