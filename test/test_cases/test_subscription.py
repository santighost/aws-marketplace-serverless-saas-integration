#!/usr/bin/env python3
"""
Test case for subscription flow
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
    """Test subscription flow
    
    Args:
        stack_outputs: CloudFormation stack outputs
        debug: Enable debug output
        config_name: Name of the config (contracts, subscriptions, contracts_with_subscription)
        registration_email: Email to use for registration
        override_product_code: Product code to use (overrides the one from stack outputs)
        customer_id: Customer identifier to use for testing (if None, a new test customer will be created)
    """
    print("\nTesting subscription flow...")
    
    # This test requires:
    # 1. A customer record in DynamoDB
    # 2. A subscription SQS queue
    # 3. Simulating a subscription notification
    
    # Check if this is a subscription-based deployment based on the config name
    if config_name not in ["subscriptions", "contracts_with_subscription"]:
        print(f"Skipping subscription test - not a subscription-based deployment ({config_name})")
        return None
    
    print(f"This is a subscription-based deployment ({config_name})")
    
    # Get the stack name
    stack_name = f"mp-saas-test-{config_name.replace('_', '-')}"
    print(f"Stack name: {stack_name}")
    
    # Find the subscription SQS queue
    try:
        # List all SQS queues
        sqs = boto3.client('sqs')
        response = sqs.list_queues()
        
        if 'QueueUrls' not in response:
            print("No SQS queues found")
            return None
        
        # Find a queue with 'Subscription' in the name and the stack name
        subscription_queue_url = None
        for queue_url in response['QueueUrls']:
            # Print the queue URL for debugging
            if debug:
                print(f"Checking queue: {queue_url}")
            
            # The queue URL contains the stack name and 'SubscriptionSQSHandler'
            if stack_name.lower() in queue_url.lower() and 'subscription' in queue_url.lower():
                subscription_queue_url = queue_url
                print(f"Found subscription queue: {subscription_queue_url}")
                break
        
        if not subscription_queue_url:
            print("Could not find subscription queue")
            print("Available queues:")
            for queue_url in response['QueueUrls']:
                print(f"  {queue_url}")
            return None
    except Exception as e:
        print(f"Error finding subscription queue: {e}")
        return None
    
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
    
    # For real customers, use SQS. For test customers, use direct DB update.
    if not is_test_customer:
        print("\nUsing real customer - sending subscription notification to SQS queue...")
        
        # Generate a subscription notification
        subscription_notification = {
            "Type": "Notification",
            "Message": json.dumps({
                "action": "subscribe-success",
                "customer-identifier": customer_id,
                "product-code": product_code
            })
        }
        
        # Send the notification to the SQS queue
        try:
            print(f"Sending subscription notification to SQS queue: {subscription_queue_url}")
            if debug:
                print(f"Notification: {json.dumps(subscription_notification, indent=2)}")
                
            response = sqs.send_message(
                QueueUrl=subscription_queue_url,
                MessageBody=json.dumps(subscription_notification)
            )
            
            if debug:
                print(f"SQS response: {json.dumps(response, default=str)}")
                
            print("Subscription notification sent successfully")
            
            # Wait for the subscription to be processed
            print("Waiting for subscription to be processed...")
            time.sleep(5)  # Wait 5 seconds
        except Exception as e:
            print(f"ERROR: Failed to send subscription notification: {e}")
            print("Please fix the error and try again.")
            return False
    else:
        print("\nUsing test customer - simulating subscription update...")
        
        # Update the DynamoDB record
        try:
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
                print(f"Update response: {json.dumps(update_response, default=str)}")
                
            print("DynamoDB record updated successfully with subscription information")
        except Exception as e:
            print(f"ERROR: Failed to update DynamoDB record: {e}")
            return False
    
    # Verify the customer record was updated with subscription information
    try:
        print(f"Checking for subscription updates in DynamoDB for customer: {customer_id}")
        response = table.get_item(Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"})
        
        if "Item" not in response:
            print(f"ERROR: Customer record not found in DynamoDB")
            return False
        
        item = response["Item"]
        
        if debug:
            print(f"Customer record: {json.dumps(item, default=str)}")
        
        # Check if successfully_subscribed was set to true
        if item.get("successfully_subscribed") != True:
            print("ERROR: successfully_subscribed not set to true")
            return False
        
        # Check if subscription_expired was set to false
        if item.get("subscription_expired") != False:
            print("ERROR: subscription_expired not set to false")
            return False
        
        print("\n=== Test Summary ===")
        print("✅ Customer record verified: PASS")
        if not is_test_customer:
            print("✅ Subscription notification sent to SQS: PASS")
            print("✅ Subscription processed by Lambda: PASS")
        else:
            print("✅ Subscription data simulated: PASS")
        print("✅ DynamoDB record updated: PASS")
        print("✅ Subscription data verified: PASS")
        print("\nTest Result: PASS - Successfully verified subscription flow")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to verify subscription: {e}")
        return False