#!/usr/bin/env python3
"""
Utility for generating SAM configuration files
"""

import os
import uuid
import toml
import shutil
from datetime import datetime

def generate_unique_id():
    """Generate a unique identifier for resources"""
    timestamp = datetime.now().strftime("%m%d%H%M")
    random_suffix = uuid.uuid4().hex[:6]
    return f"{timestamp}-{random_suffix}"

def create_config_file(config_type, product_id, template_path=None, output_dir=None):
    """
    Create a customized SAM config file
    
    Args:
        config_type: Type of configuration (contracts, subscriptions, contracts_with_subscription)
        product_id: AWS Marketplace product ID
        template_path: Path to template samconfig.toml (if None, use default)
        output_dir: Directory to save the generated config file (if None, use current directory)
    
    Returns:
        Path to the generated config file
    """
    # Set default output directory to current directory if not specified
    if not output_dir:
        output_dir = os.getcwd()
        
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Use default template if not specified
    if not template_path:
        template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                    "samconfig.toml")
    
    # Generate unique identifier
    unique_id = generate_unique_id()
    
    # Load template
    try:
        with open(template_path, 'r') as f:
            config = toml.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load template config: {e}")
        return None
    
    # Set SaaS listing type based on config_type
    saas_listing_type = {
        "contracts": "contracts",
        "subscriptions": "subscriptions",
        "contracts_with_subscription": "contracts_with_subscription"
    }.get(config_type, "contracts_with_subscription")
    
    # Update configuration
    stack_name = f"mp-saas-{config_type}-{unique_id}"
    s3_prefix = f"mp-saas-{config_type}-{unique_id}"
    bucket_name = f"mp-saas-bucket-{unique_id}"
    subscribers_table = f"AWSMarketplaceSubscribers-{unique_id}"
    metering_table = f"AWSMarketplaceMeteringRecords-{unique_id}"
    
    # Update the parameter_overrides string
    param_overrides = config["default"]["deploy"]["parameters"]["parameter_overrides"]
    
    # Parse the parameter_overrides string into a dictionary
    params = {}
    for param in param_overrides.strip('"').split():
        if "=" in param:
            key, value = param.split("=", 1)
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            params[key] = value
    
    # Update parameters
    params["WebsiteS3BucketName"] = bucket_name
    params["NewSubscribersTableName"] = subscribers_table
    params["AWSMarketplaceMeteringRecordsTableName"] = metering_table
    params["TypeOfSaaSListing"] = saas_listing_type
    params["ProductId"] = product_id
    
    # Convert back to parameter_overrides string
    param_overrides_list = []
    for key, value in params.items():
        # Add quotes if value contains spaces
        if " " in str(value):
            value = f'"{value}"'
        param_overrides_list.append(f"{key}={value}")
    
    param_overrides_str = " ".join(param_overrides_list)
    
    # Update config
    config["default"]["deploy"]["parameters"]["stack_name"] = stack_name
    config["default"]["deploy"]["parameters"]["s3_prefix"] = s3_prefix
    config["default"]["deploy"]["parameters"]["parameter_overrides"] = f'"{param_overrides_str}"'
    
    # Write to file
    output_path = os.path.join(output_dir, f"samconfig.{config_type}.toml")
    with open(output_path, 'w') as f:
        toml.dump(config, f)
    
    print(f"Created config file: {output_path}")
    print(f"Stack name: {stack_name}")
    print(f"S3 prefix: {s3_prefix}")
    print(f"Bucket name: {bucket_name}")
    print(f"Subscribers table: {subscribers_table}")
    print(f"Metering table: {metering_table}")
    
    return {
        "config_path": output_path,
        "stack_name": stack_name,
        "s3_prefix": s3_prefix,
        "bucket_name": bucket_name,
        "subscribers_table": subscribers_table,
        "metering_table": metering_table,
        "product_id": product_id,
        "saas_listing_type": saas_listing_type
    }

if __name__ == "__main__":
    # Example usage
    create_config_file("contracts", "prod-example123")
    create_config_file("subscriptions", "prod-example123")
    create_config_file("contracts_with_subscription", "prod-example123")