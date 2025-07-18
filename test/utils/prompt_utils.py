#!/usr/bin/env python3
"""
Utility functions for prompting the user for input
"""

import re
import os

# We don't actually need to import toml since we're parsing the file manually
# import toml

def extract_parameter_value(config_content, param_name):
    """Extract a parameter value from the config content"""
    # Try different patterns to handle various quoting styles
    patterns = [
        f'{param_name}="([^"]+)"',  # Standard quotes
        f'{param_name}=\\"([^"]+)\\"',  # Escaped quotes
        f'{param_name}=([^ ]+)'  # No quotes
    ]
    
    for pattern in patterns:
        match = re.search(pattern, config_content)
        if match:
            return match.group(1)
    
    # Debug output
    print(f"DEBUG: Could not find parameter {param_name} in config")
    return None

def load_config_parameters(config_path):
    """Load parameters from a SAM config file"""
    try:
        if not os.path.exists(config_path):
            return {}
            
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Extract region parameter
        region_match = re.search(r'region\s*=\s*"([^"]+)"', content)
        region = region_match.group(1) if region_match else "us-east-1"
        
        # Extract parameter_overrides - handle escaped quotes
        match = re.search(r'parameter_overrides\s*=\s*"(.+?)"\s*$', content, re.MULTILINE | re.DOTALL)
        if not match:
            return {"region": region}
            
        params_str = match.group(1)
        
        # Parse parameters directly
        params = {"region": region}  # Include region parameter
        # Split by spaces but respect quoted values
        parts = re.findall(r'([^\s]+?)=\\?"([^"]+)\\?"', params_str)
        for key, value in parts:
            # Remove trailing backslashes
            params[key] = value.rstrip('\\')
        
        return params
    except Exception as e:
        print(f"Error loading config parameters: {e}")
        return {}

def prompt_for_parameter(prompt, default=None, validator=None):
    """Prompt the user for a parameter value"""
    default_str = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{default_str}: ") or default
        if not value:
            print("A value is required.")
            continue
            
        # Special validation for S3 bucket and DynamoDB table names
        if ("S3" in prompt or "table name" in prompt) and "_" in value:
            print("S3 bucket and DynamoDB table names cannot contain underscores. Please use hyphens instead.")
            continue
            
        if validator and not validator(value):
            print("Invalid value. Please try again.")
            continue
            
        return value

def prompt_for_optional_parameter(prompt, default=None, validator=None):
    """Prompt the user for an optional parameter value (allows empty values)"""
    default_str = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{default_str}: ") or default
        # Allow empty values
        
        # Special validation for S3 bucket and DynamoDB table names
        if value and ("S3" in prompt or "table name" in prompt) and "_" in value:
            print("S3 bucket and DynamoDB table names cannot contain underscores. Please use hyphens instead.")
            continue
            
        if value and validator and not validator(value):
            print("Invalid value. Please try again.")
            continue
            
        return value

def validate_email(email):
    """Validate an email address"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def prompt_for_deployment_parameters(config_name, config_dir):
    """Prompt for deployment parameters"""
    config_path = os.path.join(config_dir, f"samconfig.{config_name}.toml")
    params = load_config_parameters(config_path)
    
    # Use the config name directly
    display_name = config_name
    # Replace underscores with hyphens for S3 bucket compatibility
    display_name_safe = display_name.replace('_', '-')
    stack_name = f"mp-saas-{display_name_safe}"
    print(f"\nConfiguring deployment parameters for {display_name}:")
    
    # Print current config values
    print("\nCurrent config values:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    print()
    
    # Define all parameters with their defaults
    parameters = {
        "WebsiteS3BucketName": params.get("WebsiteS3BucketName", ""),
        "NewSubscribersTableName": params.get("NewSubscribersTableName", f"AWSMarketplaceSubscribers-{display_name_safe}"),
        "AWSMarketplaceMeteringRecordsTableName": params.get("AWSMarketplaceMeteringRecordsTableName", f"AWSMarketplaceMeteringRecords-{display_name_safe}"),
        "TypeOfSaaSListing": params.get("TypeOfSaaSListing", "contracts_with_subscription"),
        "SNSAccountID": params.get("SNSAccountID", "287250355862"),
        "SNSRegion": params.get("SNSRegion", "us-east-1"),
        "ProductId": params.get("ProductId", ""),
        "MarketplaceTechAdminEmail": params.get("MarketplaceTechAdminEmail", ""),
        "MarketplaceSellerEmail": params.get("MarketplaceSellerEmail", ""),
        "CreateCrossAccountRole": params.get("CreateCrossAccountRole", "false"),
        "CrossAccountId": params.get("CrossAccountId", ""),
        "CrossAccountRoleName": params.get("CrossAccountRoleName", ""),
        "CreateRegistrationWebPage": params.get("CreateRegistrationWebPage", "true"),
        "UpdateFulfillmentURL": params.get("UpdateFulfillmentURL", "false"),
        "region": params.get("region", "us-east-1")
    }
    
    # Prompt for each parameter
    # Ensure S3 bucket name doesn't contain underscores
    default_bucket_name = (parameters["WebsiteS3BucketName"] or f"{stack_name}-bucket").replace('_', '-')
    parameters["WebsiteS3BucketName"] = prompt_for_parameter("Specify S3 bucket name for website (no underscores)", default_bucket_name)
    # Ensure DynamoDB table names don't contain underscores
    default_subscribers_table = parameters["NewSubscribersTableName"].replace('_', '-')
    default_metering_table = parameters["AWSMarketplaceMeteringRecordsTableName"].replace('_', '-')
    parameters["NewSubscribersTableName"] = prompt_for_parameter("Specify subscribers table name (no underscores)", default_subscribers_table)
    parameters["AWSMarketplaceMeteringRecordsTableName"] = prompt_for_parameter("Specify metering records table name (no underscores)", default_metering_table)
    parameters["TypeOfSaaSListing"] = prompt_for_parameter("Specify type of SaaS listing (contracts_with_subscription, contracts, subscriptions)", parameters["TypeOfSaaSListing"])
    
    # Prompt for seller email
    parameters["MarketplaceSellerEmail"] = prompt_for_parameter("Specify seller email", parameters["MarketplaceSellerEmail"], validate_email)
    
    # Prompt for admin email
    parameters["MarketplaceTechAdminEmail"] = prompt_for_parameter("Specify tech admin email", parameters["MarketplaceTechAdminEmail"], validate_email)
    
    # Prompt for product ID (not to be confused with product code)
    # Product ID is used for AWS Marketplace listing (e.g., prod-vc7pjbuqesi2q)
    # Product Code is returned by resolveCustomer API and used in DynamoDB keys
    parameters["ProductId"] = prompt_for_parameter("Specify AWS Marketplace Product ID", parameters["ProductId"])
    
    # Prompt for cross-account role settings
    parameters["CreateCrossAccountRole"] = prompt_for_parameter("Create cross-account role? (true/false)", parameters["CreateCrossAccountRole"])
    if parameters["CreateCrossAccountRole"].lower() == "true":
        parameters["CrossAccountId"] = prompt_for_parameter("Specify cross-account ID", parameters["CrossAccountId"])
        parameters["CrossAccountRoleName"] = prompt_for_parameter("Specify cross-account role name", parameters["CrossAccountRoleName"])
    
    # Prompt for registration web page
    parameters["CreateRegistrationWebPage"] = prompt_for_parameter("Create registration web page? (true/false)", parameters["CreateRegistrationWebPage"])
    
    # Prompt for updating fulfillment URL
    parameters["UpdateFulfillmentURL"] = prompt_for_parameter("Update fulfillment URL? (true/false)", parameters["UpdateFulfillmentURL"])
    
    # Prompt for region
    parameters["region"] = prompt_for_parameter("Specify AWS region", parameters["region"])
    
    return parameters

def prompt_for_test_parameters(test_name, config_name, config_dir, stack_outputs=None, marketplace_token=None, chained_mode=False):
    """Prompt for test-specific parameters"""
    config_path = os.path.join(config_dir, f"samconfig.{config_name}.toml")
    params = load_config_parameters(config_path)
    
    # Use the config name directly
    display_name = config_name
    
    # Print current config values
    print(f"\nCurrent config values for {test_name} test:")
    for key in ["MarketplaceSellerEmail", "ProductId"]:
        if key in params:
            print(f"  {key}: {params[key]}")
    
    # Print stack outputs related to the test
    if stack_outputs:
        print("\nRelevant stack outputs:")
        for key in ["ProductCode", "MarketplaceFulfillmentURL", "SubscribersTableName"]:
            if key in stack_outputs:
                print(f"  {key}: {stack_outputs[key]}")
    print()
    
    if test_name == "registration":
        print(f"Configuring parameters for registration test:")
        
        # Prompt for customer email
        customer_email = params.get("MarketplaceSellerEmail", "")
        customer_email = prompt_for_parameter("Specify customer email", customer_email, validate_email)
        
        # Prompt for marketplace token if not provided
        if not marketplace_token:
            # Use a special prompt function that allows empty values
            marketplace_token = prompt_for_optional_parameter("Specify AWS Marketplace token (leave empty for simulated test)", "")
        
        # Prompt for product code (returned by resolveCustomer API)
        # This is different from Product ID used in AWS Marketplace listing
        # Product Code is used in DynamoDB composite keys: productCode#customerIdentifier
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        product_code = prompt_for_parameter("Specify product code (for testing only)", product_code)
        print("Note: For real tokens, the product code from resolveCustomer API will be used")
        
        return {
            "email": customer_email,
            "product_code": product_code if product_code else None,
            "marketplace_token": marketplace_token if marketplace_token else None
        }
    
    elif test_name == "entitlement":
        print(f"Configuring parameters for entitlement test:")
        
        # Prompt for customer identifier (skip in chained mode)
        customer_id = None
        if not chained_mode:
            customer_id = prompt_for_optional_parameter("Specify customer identifier (leave empty to create a test customer)", "")
        
        # Prompt for product code (skip in chained mode)
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        if not chained_mode:
            product_code = prompt_for_parameter("Specify product code", product_code)
        
        return {
            "customer_id": customer_id if customer_id else None,
            "product_code": product_code if product_code else None
        }
    
    elif test_name == "subscription":
        print(f"Configuring parameters for subscription test:")
        
        # Prompt for customer identifier (skip in chained mode)
        customer_id = None
        if not chained_mode:
            customer_id = prompt_for_optional_parameter("Specify customer identifier (leave empty to create a test customer)", "")
        
        # Prompt for product code (skip in chained mode)
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        if not chained_mode:
            product_code = prompt_for_parameter("Specify product code", product_code)
        
        return {
            "customer_id": customer_id if customer_id else None,
            "product_code": product_code if product_code else None
        }
    
    elif test_name == "metering":
        print(f"Configuring parameters for metering test:")
        
        # Prompt for customer identifier (skip in chained mode)
        customer_id = None
        if not chained_mode:
            customer_id = prompt_for_optional_parameter("Specify customer identifier (leave empty to create a test customer)", "")
        
        # Prompt for product code (skip in chained mode)
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        if not chained_mode:
            product_code = prompt_for_parameter("Specify product code", product_code)
        
        return {
            "customer_id": customer_id if customer_id else None,
            "product_code": product_code if product_code else None
        }
    
    elif test_name == "grant_revoke":
        print(f"Configuring parameters for grant/revoke access test:")
        
        # Prompt for customer identifier (skip in chained mode)
        customer_id = None
        if not chained_mode:
            customer_id = prompt_for_optional_parameter("Specify customer identifier (leave empty to create a test customer)", "")
        
        # Prompt for product code (skip in chained mode)
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        if not chained_mode:
            product_code = prompt_for_parameter("Specify product code", product_code)
        
        return {
            "customer_id": customer_id if customer_id else None,
            "product_code": product_code if product_code else None
        }
    
    elif test_name == "multi_product":
        print(f"Configuring parameters for multi-product test:")
        
        # Prompt for customer identifier (skip in chained mode)
        customer_id = None
        if not chained_mode:
            customer_id = prompt_for_optional_parameter("Specify customer identifier (leave empty to create a test customer)", "")
        
        # Prompt for primary product code (skip in chained mode)
        product_code = None
        if stack_outputs and "ProductCode" in stack_outputs:
            product_code = stack_outputs["ProductCode"]
        if not chained_mode:
            product_code = prompt_for_parameter("Specify primary product code", product_code)
        
        # Always prompt for secondary product code
        second_product_code = prompt_for_parameter("Specify secondary product code", "")
        
        return {
            "customer_id": customer_id if customer_id else None,
            "product_code": product_code if product_code else None,
            "second_product_code": second_product_code
        }
    
    return {}