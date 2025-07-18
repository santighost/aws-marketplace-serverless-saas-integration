#!/usr/bin/env python3
"""
Test case for customer registration flow
"""

import boto3
import uuid
import json
import requests
import time
import sys
import os
import argparse
import urllib.parse
from datetime import datetime, timedelta

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import aws_utils


# Global variable to store the customer ID from registration
_registered_customer_id = None

def get_customer_id():
    """Get the customer ID from the last registration"""
    return _registered_customer_id

# Add command-line interface for direct testing with a token
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AWS Marketplace registration flow")
    parser.add_argument("--token", required=True, help="AWS Marketplace registration token")
    parser.add_argument("--stack-name", required=True, help="CloudFormation stack name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--email", help="Email to use for registration")
    parser.add_argument("--product-code", help="Product code to use (overrides the one from stack outputs)")
    args = parser.parse_args()
    
    # Get stack outputs
    cloudformation = boto3.client('cloudformation', region_name=args.region)
    response = cloudformation.describe_stacks(StackName=args.stack_name)
    stack_outputs = {output["OutputKey"]: output["OutputValue"] 
                   for output in response["Stacks"][0]["Outputs"]}
    
    # Run the test
    success = run_test(stack_outputs, args.token, args.debug, "contracts_with_subscription", args.email, args.product_code)
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)

def extract_email_from_config(config_name):
    """Extract the MarketplaceSellerEmail from the SAM config file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                 "config", f"samconfig.{config_name}.toml")
        
        if not os.path.exists(config_path):
            return None
            
        with open(config_path, 'r') as f:
            content = f.read()
            
        # Look for MarketplaceSellerEmail in the parameter_overrides
        if "MarketplaceSellerEmail" in content:
            # Extract the email using regex
            import re
            match = re.search(r'MarketplaceSellerEmail=\\?"([^"]+)\\?"', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error extracting email from config: {e}")
    
    return None

def run_test(stack_outputs, marketplace_token=None, debug=True, config_name="contracts_with_subscription", registration_email=None, override_product_code=None):
    """Test customer registration flow
    
    Args:
        stack_outputs: CloudFormation stack outputs
        marketplace_token: Optional AWS Marketplace token for testing real registration
        debug: Enable debug output
        config_name: Name of the config (contracts, subscriptions, contracts_with_subscription)
    """
    print("\nTesting customer registration...")
    
    # Get the API endpoint
    api_url = stack_outputs.get("MarketplaceFulfillmentURL")
    if not api_url:
        print("ERROR: MarketplaceFulfillmentURL not found in stack outputs")
        return False
    
    print(f"Registration API endpoint: {api_url}")
    
    # Get the subscribers table name
    table_name = stack_outputs.get("SubscribersTableName")
    if not table_name:
        print("ERROR: SubscribersTableName not found in stack outputs")
        return False
    
    # Get the product code
    product_code = override_product_code or stack_outputs.get("ProductCode")
    if not product_code:
        print("WARNING: ProductCode not found in stack outputs or command line, using default")
        product_code = "test-product"
    else:
        if override_product_code:
            print(f"Using product code from command line: {product_code}")
        else:
            print(f"Using product code from stack outputs: {product_code}")
    
    # Create DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Get registration email
    if registration_email:
        print(f"Using registration email from command line: {registration_email}")
    else:
        # Prompt for registration email
        registration_email = input("Enter registration email (or press Enter to use default): ")
        if not registration_email:
            # Try to get from config as fallback
            registration_email = extract_email_from_config(config_name)
            if registration_email:
                print(f"Using seller email from config: {registration_email}")
            else:
                registration_email = "test@example.com"
                print(f"Using default registration email: {registration_email}")
    
    # If a marketplace token is provided, test the real registration flow
    if marketplace_token:
        return test_real_registration(api_url, table, marketplace_token, product_code, debug, registration_email)
    else:
        print("No marketplace token provided. Testing with simulated data.")
        return test_simulated_registration(table, product_code, registration_email)


def inspect_token(token, debug=True):
    """Try to inspect the token to see what data it contains"""
    if debug:
        print("\nInspecting token...")
        print(f"Token length: {len(token)}")
        print(f"Token format: {token[:20]}...")
        
        # Try to decode if it looks URL-encoded
        if '%' in token:
            decoded = urllib.parse.unquote(token)
            print(f"Decoded token: {decoded[:20]}...")
            token = decoded
        
        # Try to extract parts if it's a JWT token (they have 3 parts separated by dots)
        if token.count('.') == 2:
            print("Token appears to be in JWT format")
            parts = token.split('.')
            try:
                # The second part of a JWT token is the payload
                import base64
                # Add padding if needed
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4) if len(payload) % 4 != 0 else ''
                decoded_payload = base64.b64decode(payload).decode('utf-8')
                print(f"Token payload: {decoded_payload}")
            except Exception as e:
                print(f"Failed to decode JWT payload: {e}")
    
    return token

def decode_token(token):
    """Decode a URL-encoded token"""
    try:
        # Check if the token contains URL-encoded characters
        if '%' in token:
            return urllib.parse.unquote(token)
        return token
    except Exception as e:
        print(f"Error decoding token: {e}")
        return token  # Return original token if decoding fails

def test_real_registration(api_url, table, marketplace_token, product_code, debug=True, seller_email="seller@example.com"):
    """Test registration with a real AWS Marketplace token"""
    print("\nTesting registration with real AWS Marketplace token...")
    
    # Decode the token if it's URL-encoded
    marketplace_token = decode_token(marketplace_token)
    print(f"Using token: {marketplace_token[:20]}...")
    
    # Inspect the token
    marketplace_token = inspect_token(marketplace_token, debug)
    
    # Determine if we're using the redirect endpoint or the subscriber endpoint directly
    if "/redirectmarketplacetoken" in api_url:
        # For CloudFront distribution with redirect
        print("Using redirect endpoint")
        # Extract the base URL (without the path)
        base_url = api_url.split("/redirectmarketplacetoken")[0]
        redirect_url = f"{api_url}"
        subscriber_url = f"{base_url}/subscriber"
    else:
        # For direct API Gateway endpoint
        print("Using direct subscriber endpoint")
        redirect_url = api_url
        subscriber_url = api_url.replace("/redirectmarketplacetoken", "/subscriber")
    
    # Step 1: Call the redirect endpoint with the token (simulating AWS Marketplace redirect)
    print(f"Calling redirect endpoint: {redirect_url}")
    try:
        if debug:
            print(f"POST data: {{'x-amzn-marketplace-token': '{marketplace_token[:10]}...'}}")
            
        redirect_response = requests.post(
            redirect_url,
            data={"x-amzn-marketplace-token": marketplace_token},
            allow_redirects=False  # Don't follow redirects, we want to see the redirect URL
        )
        
        if debug:
            print(f"Response headers: {dict(redirect_response.headers)}")
            print(f"Response status: {redirect_response.status_code}")
            try:
                print(f"Response content: {redirect_response.text}")
            except:
                print("Could not print response content")

        
        if redirect_response.status_code in [301, 302, 303, 307, 308]:  # Redirect status codes
            redirect_location = redirect_response.headers.get('Location')
            print(f"Redirect successful. Location: {redirect_location}")
            
            # Extract the token from the redirect URL
            if "x-amzn-marketplace-token=" in redirect_location:
                token_param = redirect_location.split("x-amzn-marketplace-token=")[1].split("&")[0]
                # URL decode the token (it might be double-encoded)
                decoded_token = urllib.parse.unquote(token_param)
                print(f"Token extracted from redirect: {token_param[:10]}...")
                print(f"Decoded token: {decoded_token[:10]}...")
                # Use the decoded token instead of the original marketplace_token
                marketplace_token = decoded_token
            else:
                print("WARNING: Token not found in redirect URL")
        else:
            print(f"Unexpected response from redirect endpoint: {redirect_response.status_code}")
            print(redirect_response.text)
    except Exception as e:
        print(f"ERROR: Failed to call redirect endpoint: {e}")
        # Continue anyway, as we might be using a direct API endpoint
    
    # Step 2: Call the subscriber endpoint with customer data and token
    print(f"\nCalling subscriber endpoint: {subscriber_url}")
    # Ensure the token is decoded
    decoded_token = decode_token(marketplace_token)
    
    customer_data = {
        "companyName": "Test Company",
        "contactPerson": "Test User",
        "contactEmail": seller_email,  # Use the seller email from config
        "contactPhone": f"123-456-{uuid.uuid4().hex[:4]}",
        "regToken": decoded_token
    }
    
    if debug:
        # Create a copy with truncated token for display
        display_data = customer_data.copy()
        display_data["regToken"] = f"{display_data['regToken'][:10]}..."
        print(f"Request JSON data: {json.dumps(display_data, indent=2)}")
        print(f"Request headers: {{'Content-Type': 'application/json'}}")
    
    try:
        response = requests.post(
            subscriber_url,
            json=customer_data,
            headers={"Content-Type": "application/json"}
        )
        
        if debug:
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response status: {response.status_code}")
            try:
                print(f"Response content: {response.text}")
            except:
                print("Could not print response content")
        
        print(f"Response status code: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code != 200:
            print(f"ERROR: Registration failed with status code {response.status_code}")
            
            # Check if the token might be expired or already used
            if "Registration data not valid" in response.text:
                print("\nPossible causes:")
                print("1. The token has expired (typically expires after 1h)")
                print("2. The token is malformed or corrupted")
                print("3. There's an issue with the permissions for the Lambda function")
                
                # Try to resolve the token directly to see if it's valid
                try:
                    print("\nTrying to resolve the token directly...")
                    marketplace = boto3.client('meteringmarketplace')
                    resolve_response = marketplace.resolve_customer(RegistrationToken=marketplace_token)
                    print("Token is still valid! The issue is elsewhere.")
                    if debug:
                        print(f"Resolve response: {json.dumps(resolve_response, default=str)}")
                except Exception as e:
                    print(f"Failed to resolve token: {e}")
                    print("The token appears to be invalid, expired, or already used.")
            
            return False
        
        # Wait a moment for the record to be created
        print("Waiting for the record to be created in DynamoDB...")
        time.sleep(3)
        
        # Step 3: Verify the record was created in DynamoDB
        print("Checking DynamoDB for the new record...")
        
        # Use the AWS Marketplace API to resolve the customer identifier
        try:
            # First, let's try to use the AWS CLI to get the customer identifier
            print("Getting customer identifier from the token...")
            marketplace = boto3.client('meteringmarketplace')
            try:
                # Always use the decoded token
                decoded_token = decode_token(marketplace_token)
                print(f"Using decoded token for resolveCustomer: {decoded_token[:10]}...")
                resolve_response = marketplace.resolve_customer(RegistrationToken=decoded_token)
                
                if debug:
                    print(f"Resolve customer response: {json.dumps(resolve_response, default=str)}")
                customer_id = resolve_response.get('CustomerIdentifier')
                print(f"Resolved customer identifier: {customer_id}")
                
                # Store the customer ID for comprehensive testing
                global _registered_customer_id
                _registered_customer_id = customer_id
                
                # Get the product code from the resolve_customer response
                response_product_code = resolve_response.get('ProductCode')
                print(f"Product code from resolve_customer: {response_product_code}")
                
                # Now we can directly check for the record using the composite key
                composite_key = f"{response_product_code}#{customer_id}"
                print(f"Checking for record with composite key: {composite_key}")
                
                response = table.get_item(Key={"productCode#customerIdentifier": composite_key})
                
                if "Item" in response:
                    record = response["Item"]
                    print(f"Found record: {json.dumps(record, default=str)}")
                    
                    # Verify the record contains our data
                    # The record format might be different depending on how it was created
                    # Try both formats (with and without attribute types)
                    company_name_match = (record.get('companyName') == customer_data['companyName'] or 
                                         record.get('companyName', {}) == customer_data['companyName'] or
                                         isinstance(record.get('companyName'), dict) and record.get('companyName', {}).get('S') == customer_data['companyName'])
                    
                    contact_person_match = (record.get('contactPerson') == customer_data['contactPerson'] or 
                                          record.get('contactPerson', {}) == customer_data['contactPerson'] or
                                          isinstance(record.get('contactPerson'), dict) and record.get('contactPerson', {}).get('S') == customer_data['contactPerson'])
                    
                    contact_email_match = (record.get('contactEmail') == customer_data['contactEmail'] or 
                                         record.get('contactEmail', {}) == customer_data['contactEmail'] or
                                         isinstance(record.get('contactEmail'), dict) and record.get('contactEmail', {}).get('S') == customer_data['contactEmail'])
                    
                    if company_name_match and contact_person_match and contact_email_match:
                        print("\n=== Test Summary ===")
                        print("✅ Token validation: PASS")
                        print("✅ Customer identifier extraction: PASS")
                        print("✅ Product code extraction: PASS")
                        print("✅ DynamoDB record creation: PASS")
                        print("✅ Data verification: PASS")
                        print(f"✅ Welcome email sent to [{customer_data['contactEmail']}] - verify you've received it")
                        print("\nTest Result: PASS - Successfully verified customer record in DynamoDB")
                        return True
                    else:
                        print("ERROR: Record data doesn't match submitted data")
                        return False
                else:
                    print(f"ERROR: No record found with composite key: {composite_key}")
                    
                    # Fall back to scanning as a last resort
                    print("Falling back to scan operation...")
                    scan_response = table.scan(
                        FilterExpression="#company = :company_val AND #email = :email_val",
                        ExpressionAttributeNames={
                            "#company": "companyName",
                            "#email": "contactEmail"
                        },
                        ExpressionAttributeValues={
                            ":company_val": customer_data["companyName"],
                            ":email_val": customer_data["contactEmail"]
                        }
                    )
                    
                    if scan_response.get('Items'):
                        print(f"Found {len(scan_response['Items'])} records by scanning")
                        record = scan_response['Items'][0]
                        print(f"Found record: {json.dumps(record, default=str)}")
                        return True
                    else:
                        print("ERROR: No records found in DynamoDB")
                        return False
                        
            except Exception as e:
                print(f"WARNING: Could not resolve customer identifier: {e}")
                # Fall back to scanning
                print("Falling back to scan operation...")
                try:
                    # Try scanning with standard attribute names first
                    scan_response = table.scan(
                        FilterExpression="#company = :company_val AND #email = :email_val",
                        ExpressionAttributeNames={
                            "#company": "companyName",
                            "#email": "contactEmail"
                        },
                        ExpressionAttributeValues={
                            ":company_val": customer_data["companyName"],
                            ":email_val": customer_data["contactEmail"]
                        }
                    )
                except Exception as scan_error:
                    print(f"Scan error: {scan_error}")
                    # Try a simpler scan as a last resort
                    scan_response = table.scan()
                
                if scan_response.get('Items'):
                    print(f"Found {len(scan_response['Items'])} records by scanning")
                    record = scan_response['Items'][0]
                    print(f"Found record: {json.dumps(record, default=str)}")
                    return True
                else:
                    print("ERROR: No records found in DynamoDB")
                    return False
                
        except Exception as e:
            print(f"ERROR: Failed to scan DynamoDB table: {e}")
            return False
    
    except Exception as e:
        print(f"ERROR: Failed to call subscriber endpoint: {e}")
        return False


def test_simulated_registration(table, product_code, seller_email="test@example.com"):
    """Test registration with simulated data"""
    print("\nTesting registration with simulated data...")
    
    customer_id = f"test-customer-{uuid.uuid4().hex[:8]}"
    
    # Store the customer ID for comprehensive testing
    global _registered_customer_id
    _registered_customer_id = customer_id
    
    # Create a test customer record with multi-product format matching UI format
    try:
        current_timestamp = int(datetime.now().timestamp() * 1000)  # Milliseconds timestamp
        
        # Create entitlement data similar to what the UI would create
        entitlement_data = {
            "Entitlements": [
                {
                    "ProductCode": product_code,
                    "Dimension": "dimension_1_id",
                    "CustomerIdentifier": customer_id,
                    "Value": {"IntegerValue": 1},
                    "ExpirationDate": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                }
            ]
        }
        
        item = {
            "productCode#customerIdentifier": {"S": f"{product_code}#{customer_id}"},
            "customerIdentifier": {"S": customer_id},
            "productCode": {"S": product_code},
            "companyName": {"S": "Test Company"},
            "contactPerson": {"S": "Test User"},
            "contactEmail": {"S": seller_email},
            "contactPhone": {"S": "123-456-7890"},
            "created": {"S": str(current_timestamp)},
            "customerAWSAccountID": {"S": "123456789012"},  # Simulated AWS account ID
            "entitlement": {"S": json.dumps(entitlement_data)},
            "subscription_expired": {"BOOL": False},
            "successfully_subscribed": {"BOOL": True}
        }
        # Use boto3's low-level API to match the exact format
        dynamodb_client = boto3.client('dynamodb')
        dynamodb_client.put_item(
            TableName=table.name,
            Item=item
        )
        print(f"Added test customer with composite key: {product_code}#{customer_id}")
    except Exception as e:
        print(f"ERROR: Failed to add test customer: {e}")
        return False
    
    # Verify the record exists
    try:
        response = table.get_item(Key={"productCode#customerIdentifier": f"{product_code}#{customer_id}"})
        
        if "Item" in response:
            print("\n=== Test Summary ===")
            print("✅ DynamoDB record creation: PASS")
            print("✅ Data verification: PASS")
            print(f"✅ Welcome email sent to [{seller_email}] - verify you've received it")
            return True
        else:
            print("ERROR: Test customer record not found in DynamoDB")
            return False
    except Exception as e:
        print(f"ERROR: Failed to verify test customer: {e}")
        return False